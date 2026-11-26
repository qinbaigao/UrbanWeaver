"""Upgrade only paved-parcel planting; retain original compiled output for rollback.

Writes a new compiled directory, then incrementally refreshes the existing
portable Viewer without deleting assets or saved camera settings. No LLM calls.
"""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import shutil

from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.geometry.incremental import scene_from_manifest
from cityg.geometry.parcel_planting import enrich_paved_parcels
from cityg.serialization import load_city, save_json, to_primitive
from cityg.services import OpenUSDBackend
from cityg.viewer import build_viewer_dataset, viewer_static_dir


def refresh(source, output, viewer, site_amenities=False, metro_entrances=False, metro_decor_budget=0):
    if output.exists() and any(output.iterdir()):
        raise ValueError('New compiled output must be empty')
    project = Path(__file__).resolve().parents[1]
    city = load_city(source/'city.json')
    if metro_entrances:
        city.metadata.setdefault('metro_entrances',{})['max_decor_removals_per_entrance']=metro_decor_budget
    scene = scene_from_manifest(json.loads((source/'geometry_manifest.json').read_text()))
    registry = AssetRegistry()
    # In-memory union: never mutate the user's production asset registry.
    for path in (project/'assets/asset_registry.json',source/'assets/asset_registry.json'):
        existing=AssetRegistry(path)
        for record in existing.list_all():
            if registry.get(record.asset_id) is None:
                registry.register(replace(record,geometry_path=str(existing.resolve_path(record.geometry_path))
                    if record.geometry_path else None))
    compiler = GeometryCompiler(registry,MaterialLibrary(project/'assets/material_library.json'),include_interiors=False)
    before = {p.id:to_primitive(p) for p in scene.primitives}
    if metro_entrances:
        from cityg.geometry.metro_sites import compile_metro_entrances
        report=compile_metro_entrances(compiler,city,scene)
    elif site_amenities:
        from cityg.geometry.parcel_sites import compile_parcel_sites
        report=compile_parcel_sites(compiler,city,scene)
    else:
        report = enrich_paved_parcels(compiler,city,scene)
    if not report.get('new_asset_instances') and not report.get('new_primitives'):
        raise ValueError(f'No usable additions; source and Viewer left unchanged: {report}')
    allowed_cuts={p['id'] for p in scene.metadata.get('metro_ground_originals',[])} if metro_entrances else set()
    all_changed = {p.id for p in scene.primitives if p.id in before and to_primitive(p)!=before[p.id]}
    changed = sorted(all_changed-allowed_cuts)
    assert not changed, ('Unexpected modification to an existing primitive',changed[:5])
    report['unchanged_existing_primitives'] = sum(p.id in before and p.id not in all_changed for p in scene.primitives)
    scene.metadata.update(compiler._metadata(scene))
    print(json.dumps({k:v for k,v in report.items() if k!='parcels'},indent=2),flush=True)
    print('Writing validated OpenUSD; original package is retained',flush=True)
    OpenUSDBackend(compiler).compile(city,output,_scene_override=scene)
    if (source/'validation_report.json').exists():
        shutil.copyfile(source/'validation_report.json',output/'validation_report.json')
    save_json(report,output/('metro_update_report.json' if metro_entrances else
                            'site_update_report.json' if site_amenities else 'planting_update_report.json'))
    print('Updating portable Viewer; unchanged assets are not rewritten',flush=True)
    update_viewer(output, viewer)
    print(f'Complete: {viewer}',flush=True)


def update_viewer(output, viewer):
    """Incrementally publish an exported package without losing saved views."""
    dataset = build_viewer_dataset(output)
    config_path = viewer/'viewer-config.json'
    config = json.loads(config_path.read_text())
    def write_changed(path,data):
        if path.exists() and path.read_bytes()==data:
            return
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_bytes(data);tmp.replace(path)
    for folder,files in [('scene',dataset.files),('assets',{f'{k}.glb':v for k,v in dataset.assets.items()}),
                         ('textures',dataset.textures),('environment',dataset.environments)]:
        for name,data in files.items():
            write_changed(viewer/folder/name,data)
    config.update(files=sorted(dataset.files),original_source=str(output.resolve()),
        asset_files={a:f'{a}.glb' for a in sorted(dataset.assets)},asset_lods=dataset.asset_lods,
        texture_files={n:n for n in sorted(dataset.textures)},material_textures=dataset.material_textures,
        sky_presets=dataset.sky_presets)
    write_changed(config_path,(json.dumps(config,ensure_ascii=False,indent=2)+'\n').encode())
    shutil.copytree(viewer_static_dir(),viewer,dirs_exist_ok=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--viewer',type=Path,required=True)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--site-amenities',action='store_true',help='Add connected parcel paths and amenity nodes; preserve planting')
    mode.add_argument('--metro-entrances',action='store_true',help='Add reviewed exterior metro entries and local ground openings')
    p.add_argument('--metro-decor-budget',type=int,default=0,help='Explicit per-entrance removable-decoration budget (0..6)')
    args=p.parse_args();refresh(args.source.resolve(),args.output.resolve(),args.viewer.resolve(),args.site_amenities,args.metro_entrances,args.metro_decor_budget)
