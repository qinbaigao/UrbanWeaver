"""Add layered greenery to an existing canonical city, then update its Viewer.

The input package is retained for rollback. No LLM or building recompilation.
"""
import argparse
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path

from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.geometry.dense_greenery import compile_dense_greenery, KEY, VERSION, PLANTS
from cityg.geometry.incremental import scene_from_manifest
from cityg.serialization import load_city, save_json
from cityg.services import OpenUSDBackend
from extend_city_landscape import fingerprint
from refresh_parcel_planting import update_viewer


def run(source, output, viewer, density=1., publish=True, urban_borders=False, street_trees=False):
    if urban_borders and street_trees:
        raise ValueError('Choose only one planting scope')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output must be new/empty; original package is retained')
    print('Loading canonical city and compiled geometry',flush=True)
    city = load_city(source/'city.json')
    scene = scene_from_manifest(json.loads((source/'geometry_manifest.json').read_text()))
    key,version,compile_pass=KEY,VERSION,compile_dense_greenery
    if urban_borders:
        from cityg.geometry.urban_greenbelts import KEY as key, VERSION as version, compile_urban_greenbelts as compile_pass
    if street_trees:
        from cityg.geometry.street_tree_infill import KEY as key, VERSION as version, compile_street_tree_infill as compile_pass
    old = {p.id:fingerprint(p) for p in scene.primitives if p.metadata.get(key) != version}
    before = Counter(p.metadata['asset_category'] for p in scene.primitives if p.metadata.get('asset_category') in PLANTS)
    city.metadata[key] = {'enabled':True,'version':version,'density':density,'seed':20261017}
    project = Path(__file__).resolve().parents[1]; registry = AssetRegistry()
    for path in (source/'assets/asset_registry.json',project/'assets/asset_registry.json'):
        existing = AssetRegistry(path)
        for record in existing.list_all():
            if registry.get(record.asset_id) is None:
                registry.register(replace(record,geometry_path=str(existing.resolve_path(record.geometry_path)) if record.geometry_path else None))
    compiler = GeometryCompiler(registry,MaterialLibrary(source/'assets/material_library.json'),include_interiors=False)
    print('Applying '+key+' to available land',flush=True)
    report = compile_pass(compiler,city,scene)
    if not report.get('new_asset_instances'):
        raise ValueError(f'No additions; Viewer unchanged: {report}')
    assert len(scene.primitives) == len({p.id for p in scene.primitives})
    assert all(fingerprint(p)==old[p.id] for p in scene.primitives if p.id in old)
    assert set(old).issubset({p.id for p in scene.primitives})
    report.update(retained_primitive_count=len(old),retained_geometry_verified=True,before_vegetation=dict(before),
                  after_vegetation=dict(Counter(p.metadata['asset_category'] for p in scene.primitives if p.metadata.get('asset_category') in PLANTS)))
    channels = ('base_color_path','normal_path','roughness_path','ambient_occlusion_path')
    scene.materials = [replace(m,**{k:str((source/getattr(m,k)).resolve()) for k in channels if getattr(m,k)}) for m in scene.materials]
    scene.metadata.update(compiler._metadata(scene))
    output.mkdir(parents=True,exist_ok=True)
    report_file = 'street_tree_infill_report.json' if street_trees else 'urban_greenbelts_report.json' if urban_borders else 'greenery_report.json'
    save_json(report,output/report_file)
    print(json.dumps({k:v for k,v in report.items() if k not in {'zones','parcels'}},indent=2),flush=True)
    print('Exporting complete city; retaining previous package',flush=True)
    OpenUSDBackend(compiler).compile(city,output,_scene_override=scene)
    if publish:
        print('Incrementally updating existing portable Viewer',flush=True)
        update_viewer(output,viewer)
    print('Completed: '+str(output),flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--viewer',type=Path,required=True);p.add_argument('--density',type=float,default=1.)
    p.add_argument('--no-publish',action='store_true')
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--urban-borders',action='store_true',help='Target road edges and building gardens; preserve prior park/hill planting')
    mode.add_argument('--street-trees',action='store_true',help='Only add roadside trees; preserve all gardens and other vegetation')
    a=p.parse_args();run(a.source.resolve(),a.output.resolve(),a.viewer.resolve(),a.density,not a.no_publish,a.urban_borders,a.street_trees)
