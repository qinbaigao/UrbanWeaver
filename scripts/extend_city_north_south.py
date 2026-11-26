"""Extend the curated exterior showcase to a square without rebuilding its buildings."""
import argparse
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.geometry.incremental import scene_from_manifest
from cityg.geometry.geography import polygon_mesh, primitive_footprint
from cityg.polygons import geos
from cityg.planning.showcase_extension import extend_showcase, KEY
from cityg.planning.appearance import appearance_program_for_city
from cityg.planning.streetscape import StreetProgramPlanner
from cityg.serialization import load_city, save_json, to_primitive
from cityg.services import OpenUSDBackend
from cityg.subtree_transactions import _refresh_world_program
from cityg.validation import CityValidator
from extend_city_landscape import fingerprint
from refresh_parcel_planting import update_viewer


ROAD_SURFACES = {'road_surface','road_median','sidewalk','curb','lane_marking','crosswalk',
    'stop_line','bicycle_lane_surface','sidewalk_frontage_strip','sidewalk_furnishing_strip',
    'median_planter','median_shrub','parking_bay'}


def preserve_metro_ground_openings(scene):
    """Reapply existing station apertures to a regenerated city base plane.

    Other parcel grounds/forecourts are retained verbatim. Update the pre-cut
    backup too, so a later metro recompilation cannot restore the old extent.
    """
    s=geos()
    holes=[s.Polygon(r['opening_polygon']) for r in scene.metadata.get('metro_entrances',{}).get('entrances',[])
           if r.get('opening_polygon')]
    cut=s.union_all(holes);changes=[]
    for i,p in enumerate(scene.primitives):
        if p.semantic_class!='city_ground' or p.metadata.get('metro_ground_cut') or cut.is_empty:continue
        shape=primitive_footprint(p)
        if shape.intersection(cut).area<1e-6:continue
        q=polygon_mesh(p.id,p.owner_id,shape.difference(cut),p.center.z+p.size.z/2,p.size.z,
            p.semantic_class,p.material_id,collision=p.collision_enabled,layer=p.layer_id,
            metadata={**p.metadata,'metro_ground_cut':True})
        assert q is not None
        originals=[v for v in scene.metadata.get('metro_ground_originals',[]) if v['id']!=p.id]
        scene.metadata['metro_ground_originals']=[*originals,to_primitive(p)]
        scene.primitives[i]=q;changes.append((p,q))
    return changes


def repair_export_ground(output,viewer):
    """Narrow post-export repair for packages made before aperture preservation."""
    from cityg.usd import UsdaWriter, UsdaPackageValidator
    scene=scene_from_manifest(json.loads((output/'geometry_manifest.json').read_text()))
    changes=preserve_metro_ground_openings(scene)
    writer=UsdaWriter();writer._material_specs={m.id:m for m in scene.materials}
    layers={v.id:output/'usd'/v.relative_path for v in scene.layers}
    for before,after in changes:
        path=layers[before.layer_id];content=path.read_text()
        old='\n'.join(writer._path_mesh(before,1));new='\n'.join(writer._path_mesh(after,1))
        if content.count(old)!=1:raise ValueError('Expected exactly one matching ground mesh in USD')
        path.write_text(content.replace(old,new,1))
    report=json.loads((output/'north_south_extension_report.json').read_text())
    report['metro_openings_preserved']=True
    scene.metadata[KEY]=report
    save_json(scene,output/'geometry_manifest.json')
    validation=UsdaPackageValidator().validate(output/'usd/city.usda')
    if not validation.ok:raise ValueError(validation.to_dict())
    save_json(validation.to_dict(),output/'usd_validation_report.json')
    save_json(report,output/'north_south_extension_report.json')
    metrics_path=output/'compile_metrics.json'
    if metrics_path.exists():
        metrics=json.loads(metrics_path.read_text())
        metrics['usda_bytes']=sum(p.stat().st_size for p in (output/'usd').rglob('*.usda'))
        save_json(metrics,metrics_path)
    update_viewer(output,viewer)
    print(f'Preserved station apertures; ground meshes updated: {len(changes)}',flush=True)


def run(source, output, viewer):
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a new empty output package; the source is preserved')
    print('Loading canonical source city',flush=True)
    original=load_city(source/'city.json')
    old_buildings={b.id:fingerprint(b) for b in original.iter_buildings()}
    old_roads={r.id:fingerprint(r) for r in original.road_network.segments}
    print('Planning additive north/south districts',flush=True)
    city,report=extend_showcase(original)
    city.metadata['street_network_program']=StreetProgramPlanner().plan(city,appearance_program_for_city(city)).to_dict()
    _refresh_world_program(city,producer='square_showcase_extension',changed_ids={city.id,*report['added_buildings'],
        *report['added_roads'],*report['added_junctions'],*report['added_districts'],city.rivers[0].id})
    assert all(fingerprint(b)==old_buildings[b.id] for b in city.iter_buildings() if b.id in old_buildings)
    assert all(fingerprint(r)==old_roads[r.id] for r in city.road_network.segments if r.id in old_roads)
    print('Validating canonical city and river/road/parcel clearances',flush=True)
    validation=CityValidator().validate(city)
    if not validation.ok:
        raise ValueError(validation.to_dict())
    print(f'Validated: {len(old_buildings)} preserved + {len(report["added_buildings"])} new buildings',flush=True)
    project=Path(__file__).resolve().parents[1]
    registry=AssetRegistry()
    for path in (project/'assets/asset_registry.json',source/'assets/asset_registry.json'):
        old=AssetRegistry(path)
        for record in old.list_all():
            if registry.get(record.asset_id) is None:
                registry.register(replace(record,geometry_path=str(old.resolve_path(record.geometry_path)) if record.geometry_path else None))
    compiler=GeometryCompiler(registry,MaterialLibrary(source/'assets/material_library.json'),include_interiors=False)
    # All road axes are visible to clipping and junction planning. Only new
    # building/parcel districts are expanded. No previous showcase stage replays.
    staging=replace(city,districts=[d for d in city.districts if d.id in report['added_districts']],
        metadata=deepcopy(city.metadata))
    for key in ('edge_landscape_extension','construction_sites','metro_entrances','landscape_sites'):
        staging.metadata.pop(key,None)
    print('Compiling new exterior districts and connected street geometry',flush=True)
    addition=compiler.compile(staging)
    print('Loading original geometry for preservation merge',flush=True)
    scene=scene_from_manifest(json.loads((source/'geometry_manifest.json').read_text()))
    river_ids={r.id for r in city.rivers};bridge_ids={b.id for b in city.bridges}
    old_road_ids=set(old_roads)
    old_junctions={j.id for j in original.road_network.junctions}
    new_buildings=set(report['added_buildings'])
    joined=[j.position for j in original.road_network.junctions if j.id in report['connected_existing_junctions']]

    def replaced_global(p):
        return (p.semantic_class=='city_ground' or p.owner_id in river_ids|bridge_ids or
                p.owner_id in old_road_ids and p.semantic_class in ROAD_SURFACES or
                p.owner_id in old_junctions and p.semantic_class=='junction_surface')

    def junction_prop(p):
        # New junction arms must not acquire a tree/light from the old dead end.
        return p.owner_id in old_road_ids and p.semantic_class not in ROAD_SURFACES and any(
            (p.center.x-q.x)**2+(p.center.y-q.y)**2 < 18**2 for q in joined)

    kept=[p for p in scene.primitives if not replaced_global(p) and not junction_prop(p)]
    before={p.id:fingerprint(p) for p in kept}
    fresh=[p for p in addition.primitives if p.owner_id not in old_road_ids or
        p.semantic_class in ROAD_SURFACES or p.metadata.get('building_id') in new_buildings]
    duplicates=set(before)&{p.id for p in fresh}
    if duplicates:
        raise ValueError(f'Unexpected overlap between preserved and generated geometry: {sorted(duplicates)[:12]}')
    report.update(preserved_building_count=len(old_buildings),preserved_primitive_count=len(kept),
        replaced_global_primitive_count=sum(replaced_global(p) for p in scene.primitives),
        removed_boundary_props=sum(junction_prop(p) for p in scene.primitives),added_primitive_count=len(fresh))
    scene.primitives=kept+fresh
    preserve_metro_ground_openings(scene)
    report['metro_openings_preserved']=True
    assert len(scene.primitives)==len({p.id for p in scene.primitives})
    materials={m.id:m for m in addition.materials};materials.update({m.id:m for m in scene.materials})
    channels=('base_color_path','normal_path','roughness_path','ambient_occlusion_path')
    scene.materials=[replace(m,**{key:str((source/getattr(m,key)).resolve()) for key in channels if getattr(m,key)}) for m in materials.values()]
    scene.layers=list({v.id:v for v in [*scene.layers,*addition.layers]}.values())
    scene.state_machines.extend(addition.state_machines)
    scene.building_prototypes.update(addition.building_prototypes)
    scene.navigation=compiler._compile_navigation(city,scene)
    scene.metadata.update(compiler._metadata(scene))
    scene.metadata.update({KEY:report,'interiors_compiled':False,'compile_scope':'additive_exterior_districts',
        'compiled_building_ids':[b.id for b in city.iter_buildings()]})
    assert all(fingerprint(p)==before[p.id] for p in scene.primitives if p.id in before)
    report['preserved_geometry_verified']=True
    print(json.dumps({k:v for k,v in report.items() if not isinstance(v,list)},indent=2),flush=True)
    print('Exporting OpenUSD and updating the existing portable Viewer',flush=True)
    OpenUSDBackend(compiler).compile(city,output,_scene_override=scene)
    save_json(validation.to_dict(),output/'validation_report.json')
    save_json(report,output/'north_south_extension_report.json')
    update_viewer(output,viewer)
    print(f'Complete: {viewer}',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--viewer',type=Path,required=True)
    p.add_argument('--repair-export-ground',action='store_true')
    a=p.parse_args()
    if a.repair_export_ground:repair_export_ground(a.output.resolve(),a.viewer.resolve())
    else:run(a.source.resolve(),a.output.resolve(),a.viewer.resolve())
