"""New geometry revision for the bounded paper transport access route.

Input is a previously accepted core-retrofit package. Original city and assets
are not overwritten. This is an explicit fixture adaptation, not automatic
general city-generation capability or a model-quality experiment.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

from cityg.geometry import GeometryValidator
from cityg.geometry.incremental import scene_from_manifest
from cityg.geometry.transport_access import compile_transport_access
from cityg.serialization import load_city,save_json
from cityg.usd import UsdaWriter,UsdaPackageValidator
from cityg.validation import CityValidator


def package_scene(source,output,city,scene,receipt):
    hashes={n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in ('city.json','geometry_manifest.json')}
    save_json(city,output/'city.json');save_json(scene,output/'geometry_manifest.json')
    save_json(receipt,output/'access_receipt.json')
    save_json(scene.navigation,output/'navigation.json')
    save_json({'state_machines':scene.state_machines},output/'interactions.json')
    validation=CityValidator().validate(city);geometry=GeometryValidator().validate(city,scene)
    save_json(validation.to_dict(),output/'validation_report.json')
    save_json(geometry.to_dict(),output/'geometry_validation_report.json')
    if (source/'assets').is_dir():shutil.copytree(source/'assets',output/'assets')
    UsdaWriter().write(city,scene,output/'usd')
    usd=UsdaPackageValidator().validate(output/'usd/city.usda');save_json(usd.to_dict(),output/'usd_validation_report.json')
    unchanged=all(hashlib.sha256((source/n).read_bytes()).hexdigest()==v for n,v in hashes.items())
    report={'ok':validation.ok and geometry.ok and usd.ok and unchanged,
        'scope':'geometry_access_repair_only','source':str(source.resolve()),'source_hashes':hashes,
        'source_unchanged':unchanged,'full_cross_building_task_verified':False,'model_calls':0}
    save_json(report,output/'access_acceptance.json');return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('Use a new geometry revision directory')
    city=load_city(a.source/'city.json');previous=scene_from_manifest(json.loads((a.source/'geometry_manifest.json').read_text()))
    scene,receipt=compile_transport_access(city,previous,['building_001','building_000'])
    report=package_scene(a.source,a.output,city,scene,receipt)
    print(json.dumps(report,indent=2));return 0 if report['ok'] else 2


if __name__=='__main__':raise SystemExit(main())
