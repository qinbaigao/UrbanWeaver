"""Refresh only rooftop presentation; retain the source and canonical layout."""
import argparse
from dataclasses import replace
import json
from pathlib import Path

from cityg.assets import AssetRegistry,MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.geometry.incremental import scene_from_manifest
from cityg.geometry.roofscape import compile_roofscape,VERSION
from cityg.serialization import load_city,save_json,to_primitive
from cityg.services import OpenUSDBackend
from cityg.validation import CityValidator
from extend_city_landscape import fingerprint
from refresh_parcel_planting import update_viewer


def run(source,output,viewer,building_ids=None,publish=True,textures_only=False):
    if output.exists() and any(output.iterdir()):raise ValueError('Use an empty output; source retained for rollback')
    print('Loading existing city and geometry',flush=True)
    city=load_city(source/'city.json');scene=scene_from_manifest(json.loads((source/'geometry_manifest.json').read_text()))
    if building_ids and not building_ids.issubset({b.id for b in city.iter_buildings()}):
        raise ValueError('Roof scope contains an unknown building ID')
    layout=fingerprint([city.districts,city.road_network,city.rivers,city.bridges])
    from cityg.geometry.roof_textures import apply_roof_textures, VERSION as TEXTURE_VERSION
    def unchanged_payload(p):
        data=to_primitive(p)
        if textures_only:
            data.pop('material_id');data['metadata'].pop(TEXTURE_VERSION,None)
        return fingerprint(data)
    before={p.id:unchanged_payload(p) for p in scene.primitives
            if textures_only or p.metadata.get('roof_system')!=VERSION}
    project=Path(__file__).resolve().parents[1];registry=AssetRegistry()
    # Existing assets are pinned to this compiled scene; the project registry
    # supplies new roof assets only, never silently substitutes older payloads.
    for path in (source/'assets/asset_registry.json',project/'assets/asset_registry.json'):
        old=AssetRegistry(path)
        for record in old.list_all():
            if registry.get(record.asset_id) is None:
                registry.register(replace(record,geometry_path=str(old.resolve_path(record.geometry_path)) if record.geometry_path else None))
    compiler=GeometryCompiler(registry,MaterialLibrary(source/'assets/material_library.json'),include_interiors=False)
    print('Applying roof textures' if textures_only else 'Planning roof uses from actual exposed surfaces',flush=True)
    def progress(done,total,bid):
        if done%10==0 or done==total:print(f'Roof zoning {done}/{total}: {bid}',flush=True)
    if textures_only:
        if building_ids:raise ValueError('--textures-only currently applies to the whole city')
        city.metadata['roof_textures']={'enabled':True}
        report=apply_roof_textures(city,scene)
    else:
        city.metadata['roofscape']={'enabled':True}
        report=compile_roofscape(compiler,city,scene,building_ids=building_ids,progress=progress)
        if city.metadata.get('roof_textures',{}).get('enabled'):apply_roof_textures(city,scene)
    for p in scene.primitives:
        if p.id in before and before[p.id]!=unchanged_payload(p):raise AssertionError('Existing primitive changed: '+p.id)
    if not set(before).issubset(p.id for p in scene.primitives):raise AssertionError('Existing primitive removed')
    if layout!=fingerprint([city.districts,city.road_network,city.rivers,city.bridges]):raise AssertionError('Layout changed')
    report.update(original_geometry_preserved=True,canonical_layout_unchanged=True)
    print(json.dumps({k:v for k,v in report.items() if k!='surfaces'},indent=2),flush=True)
    validation=CityValidator().validate(city)
    if not validation.ok:raise ValueError(validation.to_dict())
    if not report.get('rebound_primitives' if textures_only else 'new_primitives'):raise ValueError('No roof changes; Viewer left unchanged')
    channels=['base_color_path','normal_path','roughness_path','ambient_occlusion_path']
    scene.materials=[replace(m,**{key:str((source/getattr(m,key)).resolve()) for key in channels if getattr(m,key)}) for m in scene.materials]
    scene.metadata.update(compiler._metadata(scene))
    print('Exporting validated roofscape',flush=True)
    OpenUSDBackend(compiler).compile(city,output,_scene_override=scene)
    save_json(report,output/('roof_texture_report.json' if textures_only else 'roofscape_report.json'))
    save_json(validation.to_dict(),output/'validation_report.json')
    if publish:update_viewer(output,viewer)
    print(f'Complete: {viewer if publish else output}',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--viewer',type=Path,required=True);p.add_argument('--building',action='append')
    p.add_argument('--no-publish',action='store_true',help='Export first, review before publishing to existing Viewer')
    p.add_argument('--textures-only',action='store_true',help='Vary roof PBR without changing geometry or replanning zones')
    a=p.parse_args();run(a.source.resolve(),a.output.resolve(),a.viewer.resolve(),set(a.building) if a.building else None,not a.no_publish,a.textures_only)
