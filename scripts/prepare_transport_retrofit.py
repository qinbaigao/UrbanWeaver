"""Prepare an explicitly authorized NEW core-retrofit version, entirely offline."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

from cityg.serialization import load_city,save_json
from cityg.geometry.incremental import scene_from_manifest
from cityg.planning.transport_retrofit import plan_transport_retrofit
from cityg.geometry.transport_retrofit import compile_transport_retrofit
from cityg.geometry import GeometryValidator
from cityg.runtime.transport_readiness import audit_transport_readiness
from cityg.runtime.transport import Box
from cityg.validation import CityValidator
from cityg.usd import UsdaWriter,UsdaPackageValidator


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--building',action='append',required=True)
    parser.add_argument('--authorize-interior-retrofit',action='store_true')
    args=parser.parse_args()
    if args.output.exists():raise ValueError('New output directory required')
    hashes={n:hashlib.sha256((args.source/n).read_bytes()).hexdigest() for n in ('city.json','geometry_manifest.json')}
    city=load_city(args.source/'city.json')
    before=scene_from_manifest(json.loads((args.source/'geometry_manifest.json').read_text()))
    adapted,receipt=plan_transport_retrofit(city,set(args.building),authorized=args.authorize_interior_retrofit)
    args.output.mkdir(parents=True)
    save_json(receipt,args.output/'retrofit_receipt.json')
    canonical=CityValidator().validate(adapted);save_json(canonical.to_dict(),args.output/'city_validation.json')
    if not canonical.ok:raise ValueError('Canonical retrofit failed validation')
    scene=compile_transport_retrofit(adapted,before,receipt)
    geometry=GeometryValidator().validate(adapted,scene);save_json(geometry.to_dict(),args.output/'geometry_validation.json')
    save_json(adapted,args.output/'city.json');save_json(scene,args.output/'geometry_manifest.json')
    save_json(scene.navigation,args.output/'navigation.json')
    save_json({'state_machines':scene.state_machines},args.output/'interactions.json')
    readiness=audit_transport_readiness(adapted,scene,args.building,Box('robot',(0,0,.75),(.65,.8,1.5)))
    save_json(readiness,args.output/'readiness.json')
    # A new version must retain the frozen registry/PBR files as well as IR.
    # Copy, not shared hard links: later edits cannot mutate the source package.
    if (args.source/'assets').is_dir():shutil.copytree(args.source/'assets',args.output/'assets')
    UsdaWriter().write(adapted,scene,args.output/'usd')
    usd=UsdaPackageValidator().validate(args.output/'usd'/'city.usda')
    save_json(usd.to_dict(),args.output/'usd_validation_report.json')
    unchanged=all(hashlib.sha256((args.source/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
    report={'ok':canonical.ok and geometry.ok and readiness['ok'] and unchanged and usd.ok,
        'scope':'authorized_core_retrofit_structural_preflight','source':str(args.source.resolve()),
        'source_hashes':hashes,'source_unchanged':unchanged,'model_calls':0,
        'geometry_merge':scene.metadata['transport_core_retrofit'],'full_route_verified':False,
        'elevator_entry_ride_exit_verified':False}
    save_json(report,args.output/'acceptance.json')
    print(json.dumps({k:v for k,v in report.items() if k!='geometry_merge'},indent=2))
    print('geometry errors:',[e.message for e in geometry.errors][:5])
    return 0 if report['ok'] else 2


if __name__=='__main__':raise SystemExit(main())
