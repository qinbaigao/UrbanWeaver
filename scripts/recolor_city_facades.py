"""Edit facade colourways or roof finishes of a compiled city; preserve geometry."""
import argparse
from dataclasses import replace
import json
from pathlib import Path

from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.geometry.facade_colorways import apply_facade_colorways, select_warm_buildings
from cityg.geometry.roof_finishes import apply_roof_finishes, assign_roof_finishes
from cityg.geometry.incremental import scene_from_manifest
from cityg.serialization import load_city, save_json, to_primitive
from cityg.services import OpenUSDBackend
from refresh_parcel_planting import update_viewer


def run(source, output, viewer, count, roofs=False):
    if count < 1:
        raise ValueError('count must be positive')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use an empty new output directory; original is preserved')
    print('Loading existing city and geometry', flush=True)
    city = load_city(source/'city.json')
    scene = scene_from_manifest(json.loads((source/'geometry_manifest.json').read_text()))
    selected = [] if roofs else select_warm_buildings(city, scene, count)
    if not selected and not roofs:
        raise ValueError('No warm facade candidates; Viewer left unchanged')
    # Mostly neutral finishes with a few muted accents; not rainbow buildings.
    cycle = ['pearl_gray','cool_gray','pearl_gray','muted_sage','pearl_gray','slate_blue',
             'pearl_gray','cool_gray','pearl_gray','muted_sage','pearl_gray','cool_gray']
    buildings = {b.id:b for b in city.iter_buildings()}
    for i,bid in enumerate(selected):
        buildings[bid].metadata['facade_colorway'] = cycle[i % len(cycle)]
    before = {p.id:to_primitive(p) for p in scene.primitives}
    if roofs:
        assign_roof_finishes(city)
        report = apply_roof_finishes(city, scene)
    else:
        report = apply_facade_colorways(city, scene)
    for p in scene.primitives:
        new = to_primitive(p); old = before[p.id]
        for value in (new,old):
            value.pop('material_id')
            value['metadata'].pop('roof_finish_v1' if roofs else 'facade_colorway_v1', None)
        if new != old:
            raise AssertionError(f'Unexpected non-material edit: {p.id}')
    # Resolve portable source texture paths before writing to a new directory.
    channels = ['base_color_path','normal_path','roughness_path','ambient_occlusion_path']
    scene.materials = [replace(m, **{c:str((source/getattr(m,c)).resolve())
        for c in channels if getattr(m,c)}) for m in scene.materials]
    compiler = GeometryCompiler(AssetRegistry(source/'assets/asset_registry.json'),
        MaterialLibrary(source/'assets/material_library.json'), include_interiors=False)
    print(json.dumps(report, indent=2), flush=True)
    print('Exporting validated package', flush=True)
    OpenUSDBackend(compiler).compile(city,output,_scene_override=scene)
    save_json(report,output/('roof_finish_report.json' if roofs else 'facade_colorway_report.json'))
    print('Updating existing portable Viewer', flush=True)
    update_viewer(output,viewer)
    print(f'Complete: {viewer}', flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--viewer',type=Path,required=True)
    p.add_argument('--count',type=int,default=24)
    p.add_argument('--roofs',action='store_true',help='Assign flat-roof finishes to all buildings instead of recolouring facades')
    a=p.parse_args()
    run(a.source.resolve(),a.output.resolve(),a.viewer.resolve(),a.count,a.roofs)
