"""Extend an existing showcase west with a park and east with a raised hill."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.geometry.edge_landscape import compile_edge_landscape, plan_extension
from cityg.geometry.incremental import scene_from_manifest
from cityg.serialization import load_city, save_json, to_primitive
from cityg.services import OpenUSDBackend
from cityg.subtree_transactions import _refresh_world_program
from cityg.validation import CityValidator
from refresh_parcel_planting import update_viewer


def fingerprint(value):
    return hashlib.sha256(json.dumps(to_primitive(value),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def run(source,output,viewer):
    if output.exists() and any(output.iterdir()):raise ValueError('Output must be empty; source is preserved')
    print('Loading existing city',flush=True)
    city=load_city(source/'city.json')
    preserved=fingerprint([city.districts,city.road_network,city.rivers,city.bridges])
    plan_extension(city)
    _refresh_world_program(city,producer='edge_landscape_showcase',changed_ids={city.id})
    if fingerprint([city.districts,city.road_network,city.rivers,city.bridges])!=preserved:
        raise AssertionError('Existing canonical layout changed')
    print('Validating extended canonical bounds and unchanged layout',flush=True)
    validation=CityValidator().validate(city)
    if not validation.ok:raise ValueError(validation.to_dict())
    scene=scene_from_manifest(json.loads((source/'geometry_manifest.json').read_text()))
    before={p.id:fingerprint(p) for p in scene.primitives}
    project=Path(__file__).resolve().parents[1]
    registry=AssetRegistry()
    for path in (project/'assets/asset_registry.json',source/'assets/asset_registry.json'):
        old=AssetRegistry(path)
        for record in old.list_all():
            if registry.get(record.asset_id) is None:
                registry.register(replace(record,geometry_path=str(old.resolve_path(record.geometry_path)) if record.geometry_path else None))
    compiler=GeometryCompiler(registry,MaterialLibrary(source/'assets/material_library.json'),include_interiors=False)
    print('Building terrain, connected paths, rest nodes and planted clusters',flush=True)
    report=compile_edge_landscape(compiler,city,scene)
    for p in scene.primitives:
        if p.id in before and fingerprint(p)!=before[p.id]:raise AssertionError(f'Existing primitive changed: {p.id}')
    if not set(before).issubset(p.id for p in scene.primitives):raise AssertionError('Existing primitive removed')
    report['canonical_layout_unchanged']=True
    report['preserved_primitive_count']=len(before)
    scene.metadata.update(compiler._metadata(scene))
    channels=['base_color_path','normal_path','roughness_path','ambient_occlusion_path']
    scene.materials=[replace(m,**{key:str((source/getattr(m,key)).resolve()) for key in channels if getattr(m,key)}) for m in scene.materials]
    print(json.dumps(report,indent=2),flush=True)
    print('Exporting validated OpenUSD and portable Viewer',flush=True)
    OpenUSDBackend(compiler).compile(city,output,_scene_override=scene)
    save_json(validation.to_dict(),output/'validation_report.json')
    save_json(report,output/'edge_landscape_report.json')
    update_viewer(output,viewer)
    print(f'Complete: {viewer}',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--viewer',type=Path,required=True)
    a=p.parse_args();run(a.source.resolve(),a.output.resolve(),a.viewer.resolve())
