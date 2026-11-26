"""Publish an additive/reversible worksite edit of a compiled showcase city."""
import argparse
from dataclasses import replace
import json
from pathlib import Path

from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.geometry.construction_sites import compile_construction_sites, plan_construction_sites
from cityg.geometry.incremental import scene_from_manifest
from cityg.serialization import load_city, save_json
from cityg.services import OpenUSDBackend
from cityg.subtree_transactions import _refresh_world_program
from cityg.validation import CityValidator
from extend_city_landscape import fingerprint
from refresh_parcel_planting import update_viewer


def run(source, output, viewer, ids):
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use an empty output directory; the source must be retained')
    print('Loading source city and compiled geometry', flush=True)
    city=load_city(source/'city.json')
    before_buildings={b.id:fingerprint(b) for b in city.iter_buildings()}
    protected=fingerprint([city.road_network,city.rivers,city.bridges,city.metadata.get('edge_landscape_extension')])
    plan=plan_construction_sites(city,ids)
    _refresh_world_program(city,producer='construction_showcase',changed_ids={city.id}|{r['parcel_id'] for r in plan['sites']})
    remaining={b.id:fingerprint(b) for b in city.iter_buildings()}
    assert remaining=={k:v for k,v in before_buildings.items() if k not in ids}
    assert protected==fingerprint([city.road_network,city.rivers,city.bridges,city.metadata.get('edge_landscape_extension')])
    validation=CityValidator().validate(city)
    if not validation.ok:raise ValueError(validation.to_dict())
    scene=scene_from_manifest(json.loads((source/'geometry_manifest.json').read_text()))
    before={p.id:fingerprint(p) for p in scene.primitives}
    registry=AssetRegistry(); project=Path(__file__).resolve().parents[1]
    for path in (project/'assets/asset_registry.json',source/'assets/asset_registry.json'):
        old=AssetRegistry(path)
        for record in old.list_all():
            if registry.get(record.asset_id) is None:
                registry.register(replace(record,geometry_path=str(old.resolve_path(record.geometry_path)) if record.geometry_path else None))
    compiler=GeometryCompiler(registry,MaterialLibrary(source/'assets/material_library.json'),include_interiors=False)
    print('Replacing two dedicated parcels; preserving all other compiled geometry',flush=True)
    report=compile_construction_sites(compiler,city,scene)
    removed=set(report['removed_primitive_ids']); after={p.id for p in scene.primitives}
    assert set(before)-after==removed
    for p in scene.primitives:
        if p.id in before:assert fingerprint(p)==before[p.id],p.id
    report.update(preserved_primitive_count=len(before)-len(removed),other_buildings_unchanged=True,
        source_package=str(source),removed_building_ids=ids)
    scene.metadata.update(compiler._metadata(scene))
    channels=['base_color_path','normal_path','roughness_path','ambient_occlusion_path']
    scene.materials=[replace(m,**{key:str((source/getattr(m,key)).resolve()) for key in channels if getattr(m,key)}) for m in scene.materials]
    print(json.dumps({k:v for k,v in report.items() if k not in ('sites','removed_primitive_ids')},indent=2),flush=True)
    print('Validating and exporting OpenUSD',flush=True)
    OpenUSDBackend(compiler).compile(city,output,_scene_override=scene)
    save_json(validation.to_dict(),output/'validation_report.json')
    save_json(report,output/'construction_update_report.json')
    print('Updating portable Viewer',flush=True)
    update_viewer(output,viewer)
    print(f'Complete: {viewer}',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--viewer',type=Path,required=True);p.add_argument('--buildings',nargs='+',required=True)
    a=p.parse_args();run(a.source.resolve(),a.output.resolve(),a.viewer.resolve(),a.buildings)
