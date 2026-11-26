"""Curate four functional parcel courts without rebuilding the existing city.

Use --check-only to assess placement without writing a compiled output/Viewer.
Programs can instead be supplied as a JSON parcel-ID -> program mapping.
"""
import argparse
from dataclasses import replace
import json
from pathlib import Path

from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.geometry.incremental import scene_from_manifest
from cityg.geometry.parcel_courtyards import compile_parcel_courtyards, VERSION
from cityg.geometry.courtyard_programs import citywide_programs
from cityg.serialization import load_city, save_json, to_primitive
from cityg.services import OpenUSDBackend
from cityg.subtree_transactions import _refresh_world_program
from cityg.validation import CityValidator
from extend_city_landscape import fingerprint
from refresh_parcel_planting import update_viewer

SHOWCASE_PROGRAMS={
    'parcel_022':{'theme':'residential'},
    'parcel_043':{'theme':'commercial'},
    'parcel_063':{'theme':'civic'},
    'parcel_074':{'theme':'mixed_use'},
}


def run(source, output, viewer, programs=None, check_only=False, all_parcels=False):
    if not check_only and output.exists() and any(output.iterdir()):
        raise ValueError('Output must be empty; source is retained for rollback')
    print('Loading existing city and geometry',flush=True)
    city=load_city(source/'city.json')
    preserved=fingerprint([city.districts,city.road_network,city.rivers,city.bridges])
    if all_parcels and programs is not None:
        raise ValueError('Choose --all-parcels or --programs, not both')
    city.metadata['parcel_courtyard_programs']=citywide_programs(city) if all_parcels else (programs if programs is not None else SHOWCASE_PROGRAMS)
    scene=scene_from_manifest(json.loads((source/'geometry_manifest.json').read_text()))
    previous_overrides=scene.metadata.get('courtyard_collision_originals',{})
    before={}
    for p in scene.primitives:
        if p.metadata.get('site_system')==VERSION:continue
        checked=to_primitive(p) if p.id in previous_overrides else p
        if p.id in previous_overrides:checked.update(previous_overrides[p.id])
        before[p.id]=fingerprint(checked)
    project=Path(__file__).resolve().parents[1]
    registry=AssetRegistry()
    for path in (project/'assets/asset_registry.json',source/'assets/asset_registry.json'):
        old=AssetRegistry(path)
        for record in old.list_all():
            if registry.get(record.asset_id) is None:
                registry.register(replace(record,geometry_path=str(old.resolve_path(record.geometry_path)) if record.geometry_path else None))
    compiler=GeometryCompiler(registry,MaterialLibrary(source/'assets/material_library.json'),include_interiors=False)
    print(f"Planning connected outdoor rooms in {len(city.metadata['parcel_courtyard_programs'])} parcels",flush=True)
    report=compile_parcel_courtyards(compiler,city,scene)
    overrides=scene.metadata.get('courtyard_collision_originals',{})
    for p in scene.primitives:
        checked=to_primitive(p) if p.id in overrides else p
        if p.id in overrides:
            checked.update(overrides[p.id])
        if p.id in before and fingerprint(checked)!=before[p.id]:
            raise AssertionError(f'Existing primitive changed: {p.id}')
    if not set(before).issubset(p.id for p in scene.primitives):
        raise AssertionError('Existing primitive removed')
    if fingerprint([city.districts,city.road_network,city.rivers,city.bridges])!=preserved:
        raise AssertionError('Canonical layout changed')
    report['preserved_primitive_count']=len(before)-len(overrides)
    report['preserved_visible_geometry']=True
    report['canonical_layout_unchanged']=True
    print(json.dumps({k:v for k,v in report.items() if k!='parcels'},indent=2),flush=True)
    if check_only:
        return report
    if not all_parcels and report['changed_parcel_count']!=len(city.metadata['parcel_courtyard_programs']):
        raise ValueError('Not all requested parcels were usable; Viewer left unchanged')
    if all_parcels:
        report['preserved_worksite_parcels']=[r['parcel_id'] for r in city.metadata.get('construction_sites',{}).get('sites',[])]
        if not report['changed_parcel_count']:
            raise ValueError('No safe placements; Viewer left unchanged')
    _refresh_world_program(city,producer='parcel_courtyard_curator',changed_ids={city.id,*city.metadata['parcel_courtyard_programs']})
    validation=CityValidator().validate(city)
    if not validation.ok:raise ValueError(validation.to_dict())
    scene.metadata.update(compiler._metadata(scene))
    channels=['base_color_path','normal_path','roughness_path','ambient_occlusion_path']
    scene.materials=[replace(m,**{key:str((source/getattr(m,key)).resolve()) for key in channels if getattr(m,key)}) for m in scene.materials]
    print('Exporting validated scene; preserving source and existing Viewer assets',flush=True)
    OpenUSDBackend(compiler).compile(city,output,_scene_override=scene)
    save_json(validation.to_dict(),output/'validation_report.json')
    save_json(report,output/'parcel_courtyard_report.json')
    update_viewer(output,viewer)
    print(f'Complete: {viewer}',flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--viewer',type=Path,required=True)
    p.add_argument('--programs',type=Path)
    p.add_argument('--all-parcels',action='store_true',help='Size-aware programs for all parcels except reserved worksites')
    p.add_argument('--check-only',action='store_true')
    a=p.parse_args()
    run(a.source.resolve(),a.output.resolve(),a.viewer.resolve(),
        json.loads(a.programs.read_text()) if a.programs else None,a.check_only,a.all_parcels)
