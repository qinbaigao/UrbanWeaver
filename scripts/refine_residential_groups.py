"""Replace selected residential parcels; retain unrelated compiled geometry exactly."""
import argparse
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.geometry.geography import constrain_ground_geometry
from cityg.geometry.incremental import scene_from_manifest, entity_building_index
from cityg.geometry.parcel_sites import compile_parcel_sites
from cityg.geometry.parcel_courtyards import compile_parcel_courtyards
from cityg.geometry.residential_groups import compile_group_paths
from cityg.planning.residential_groups import replace_residential_groups, KEY
from cityg.serialization import load_city, save_json
from cityg.services import OpenUSDBackend
from cityg.subtree_transactions import _refresh_world_program
from cityg.validation import CityValidator
from extend_city_landscape import fingerprint
from refresh_parcel_planting import update_viewer


def run(source, output, viewer, publish=True):
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a new output directory; previous scene is retained')
    print('Loading and planning 6 apartment parcels + 4 townhouse parcels', flush=True)
    old = load_city(source/'city.json')
    city, report = replace_residential_groups(old)
    parcels = {r['parcel_id'] for r in report['parcels']}
    removed = {bid for r in report['parcels'] for bid in r['removed_buildings']}
    added = {bid for r in report['parcels'] for bid in r['building_ids']}
    assert fingerprint([city.road_network,city.rivers,city.bridges]) == fingerprint([old.road_network,old.rivers,old.bridges])
    old_buildings = {b.id:b for b in old.iter_buildings()}
    assert all(fingerprint(b) == fingerprint(old_buildings[b.id]) for b in city.iter_buildings() if b.id not in added)
    changed = {eid for eid,bid in entity_building_index(city).items() if bid in added}
    _refresh_world_program(city, producer=KEY, changed_ids=changed|parcels|{city.id})
    validation = CityValidator().validate(city)
    output.mkdir(parents=True, exist_ok=True)
    save_json(report, output/'residential_groups_report.json')
    save_json(validation.to_dict(), output/'validation_report.json')
    if not validation.ok:
        raise ValueError(str(validation.to_dict())[:8000])
    print(json.dumps(report, indent=2), flush=True)
    project = Path(__file__).resolve().parents[1]; registry = AssetRegistry()
    for path in (source/'assets/asset_registry.json', project/'assets/asset_registry.json'):
        existing = AssetRegistry(path)
        for record in existing.list_all():
            if registry.get(record.asset_id) is None:
                registry.register(replace(record, geometry_path=str(existing.resolve_path(record.geometry_path)) if record.geometry_path else None))
    compiler = GeometryCompiler(registry, MaterialLibrary(source/'assets/material_library.json'), include_interiors=False)
    staging = replace(city, districts=[replace(d, parcels=[p for p in d.parcels if p.id in parcels])
                                      for d in city.districts if any(p.id in parcels for p in d.parcels)],
                      metadata=deepcopy(city.metadata))
    staging.metadata['parcel_courtyard_programs'] = {pid:{'theme':'residential','adaptive':True} for pid in parcels}
    # Preserve the authored new courtyard program in future recompiles too.
    city.metadata.setdefault('parcel_courtyard_programs', {}).update(staging.metadata['parcel_courtyard_programs'])
    print('Compiling group envelopes, shared-wall roofs, paths and gardens', flush=True)
    addition = compiler.compile(staging, building_ids=added)
    compiler._compile_parcel_landscape(staging, addition)
    constrain_ground_geometry(staging, addition)
    path_report = compile_group_paths(compiler, staging, addition)
    compile_parcel_sites(compiler, staging, addition)
    courtyard_report = compile_parcel_courtyards(compiler, staging, addition)
    print('Merging only the 10 edited parcels', flush=True)
    scene = scene_from_manifest(json.loads((source/'geometry_manifest.json').read_text()))
    owners = entity_building_index(old)
    def affected(p):
        return (owners.get(p.owner_id) in removed or p.owner_id in parcels
                or p.metadata.get('parcel_id') in parcels or p.metadata.get('building_id') in removed)
    kept = [p for p in scene.primitives if not affected(p)]
    fingerprints = {p.id:fingerprint(p) for p in kept}
    assert not (set(fingerprints)&{p.id for p in addition.primitives})
    scene.primitives = kept+addition.primitives
    assert len(scene.primitives) == len({p.id for p in scene.primitives})
    materials = {m.id:m for m in addition.materials}
    materials.update({m.id:m for m in scene.materials})  # old shared appearance wins
    channels = ('base_color_path','normal_path','roughness_path','ambient_occlusion_path')
    scene.materials = [replace(m, **{k:str((source/getattr(m,k)).resolve()) for k in channels if getattr(m,k)}) for m in materials.values()]
    valid_layers = {p.layer_id for p in scene.primitives}
    scene.layers = list({v.id:v for v in [*scene.layers,*addition.layers] if v.id in valid_layers or owners.get(v.owner_id) not in removed}.values())
    scene.state_machines = [m for m in scene.state_machines if owners.get(m.owner_id) not in removed]+addition.state_machines
    scene.building_prototypes = {k:v for k,v in scene.building_prototypes.items() if k not in removed}
    scene.building_prototypes.update(addition.building_prototypes)
    scene.navigation = compiler._compile_navigation(city, scene)
    report.update(unchanged_buildings_verified=True, unchanged_roads_water_bridges_verified=True,
        retained_primitive_count=len(kept), new_primitive_count=len(addition.primitives),
        entrance_paths=path_report, courtyards=courtyard_report)
    assert all(fingerprint(p)==fingerprints[p.id] for p in scene.primitives if p.id in fingerprints)
    report['retained_geometry_verified'] = True
    scene.metadata.update(compiler._metadata(scene))
    scene.metadata.update({KEY:report, 'compile_scope':'residential_parcel_replacement',
                           'compiled_building_ids':[b.id for b in city.iter_buildings()]})
    print('Exporting and validating the complete city; old package retained', flush=True)
    OpenUSDBackend(compiler).compile(city, output, _scene_override=scene)
    save_json(report, output/'residential_groups_report.json')
    save_json(validation.to_dict(), output/'validation_report.json')
    if publish:
        print('Refreshing existing portable Viewer', flush=True)
        update_viewer(output, viewer)
    print('Completed: '+str(output), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--viewer', type=Path, required=True)
    p.add_argument('--no-publish', action='store_true')
    a = p.parse_args(); run(a.source.resolve(), a.output.resolve(), a.viewer.resolve(), not a.no_publish)
