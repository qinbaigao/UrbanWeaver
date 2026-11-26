"""Vary an existing exterior skyline; rebuild buildings only, retain site dressing."""
import argparse
from dataclasses import replace
import json
from pathlib import Path

from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.geometry.incremental import scene_from_manifest, merge_building_scene, entity_building_index
from cityg.planning.showcase_heights import vary_showcase_heights, KEY
from cityg.serialization import load_city, save_json
from cityg.services import OpenUSDBackend
from cityg.subtree_transactions import _refresh_world_program
from cityg.validation import CityValidator
from extend_city_landscape import fingerprint
from refresh_parcel_planting import update_viewer


def run(source,output,viewer,seed=20261017,plan_only=False,publish=True):
    if output.exists() and any(output.iterdir()):raise ValueError('Use an empty output directory; original is retained')
    print('Loading canonical exterior city',flush=True)
    old=load_city(source/'city.json')
    city,report=vary_showcase_heights(old,seed)
    affected={r['building_id'] for r in report['changes']}
    assert fingerprint([old.road_network,old.rivers,old.bridges])==fingerprint([city.road_network,city.rivers,city.bridges])
    old_buildings={b.id:b for b in old.iter_buildings()}
    for b in city.iter_buildings():
        previous=old_buildings[b.id]
        assert fingerprint([b.footprint,b.entrance,b.function])==fingerprint([previous.footprint,previous.entrance,previous.function])
    changed={eid for eid,bid in entity_building_index(city).items() if bid in affected}
    print('Refreshing identities/contracts and validating floor stacks',flush=True)
    _refresh_world_program(city,producer=KEY,changed_ids=changed|{city.id})
    validation=CityValidator().validate(city)
    output.mkdir(parents=True,exist_ok=True)
    save_json(report,output/'height_variation_report.json')
    save_json(validation.to_dict(),output/'validation_report.json')
    if not validation.ok:raise ValueError(str(validation.to_dict())[:5000])
    print(json.dumps({k:v for k,v in report.items() if k!='changes'},indent=2),flush=True)
    if plan_only:return
    print('Loading pinned geometry and assets',flush=True)
    previous=scene_from_manifest(json.loads((source/'geometry_manifest.json').read_text()))
    if previous.metadata.get('interiors_compiled'):raise ValueError('Source contains compiled interiors')
    owners=entity_building_index(old)
    retained={p.id:fingerprint(p) for p in previous.primitives if owners.get(p.owner_id) not in affected}
    registry=AssetRegistry();project=Path(__file__).resolve().parents[1]
    for path in (source/'assets/asset_registry.json',project/'assets/asset_registry.json'):
        existing=AssetRegistry(path)
        for record in existing.list_all():
            if registry.get(record.asset_id) is None:
                registry.register(replace(record,geometry_path=str(existing.resolve_path(record.geometry_path)) if record.geometry_path else None))
    compiler=GeometryCompiler(registry,MaterialLibrary(source/'assets/material_library.json'),include_interiors=False)
    print(f'Recompiling {len(affected)} building shells, facades and furnished roofs (no interiors)',flush=True)
    subset=compiler.compile(city,building_ids=affected)
    # Authored site layers may not be declared by the ordinary layer planner.
    current={v.id:v for v in subset.layers}
    required={p.layer_id for p in previous.primitives if p.id in retained}
    for layer in previous.layers:
        if layer.id in required and layer.id not in current:subset.layers.append(layer)
    scene,merge=merge_building_scene(city,previous,subset,affected,previous_city=old)
    for p in scene.primitives:
        if p.id in retained and fingerprint(p)!=retained[p.id]:raise AssertionError('Unrelated geometry changed: '+p.id)
    assert set(retained).issubset(p.id for p in scene.primitives)
    assert len({p.id for p in scene.primitives})==len(scene.primitives)
    report.update(merge,unchanged_site_geometry_verified=True,unchanged_footprints_verified=True)
    channels=('base_color_path','normal_path','roughness_path','ambient_occlusion_path')
    scene.materials=[replace(m,**{key:str((source/getattr(m,key)).resolve()) for key in channels if getattr(m,key)}) for m in scene.materials]
    for key in ('streetscape_stats','parcel_landscape_stats'):
        if key in previous.metadata:scene.metadata[key]=previous.metadata[key]
    scene.metadata.update(compiler._metadata(scene));scene.metadata[KEY]=report
    print('Exporting OpenUSD and running geometry/USD/interaction checks',flush=True)
    OpenUSDBackend(compiler).compile(city,output,_scene_override=scene)
    save_json(report,output/'height_variation_report.json')
    save_json(validation.to_dict(),output/'validation_report.json')
    if publish:
        print('Refreshing the existing portable Viewer; unchanged assets are retained',flush=True)
        update_viewer(output,viewer)
    print(f'Completed: {output}',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--viewer',type=Path,required=True);p.add_argument('--seed',type=int,default=20261017)
    p.add_argument('--plan-only',action='store_true');p.add_argument('--no-publish',action='store_true')
    a=p.parse_args();run(a.source.resolve(),a.output.resolve(),a.viewer.resolve(),a.seed,a.plan_only,not a.no_publish)
