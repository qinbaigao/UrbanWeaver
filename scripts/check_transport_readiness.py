"""Audit a frozen fixture for actual cross-floor transport prerequisites."""
import argparse
import hashlib
import json
from pathlib import Path

from cityg.serialization import load_city,save_json
from cityg.geometry.incremental import scene_from_manifest
from cityg.runtime.transport import Box
from cityg.runtime.transport_readiness import audit_transport_readiness


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scene',type=Path);parser.add_argument('--fixture-report',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Use a new report path')
    manifest=args.scene/'geometry_manifest.json';city_path=args.scene/'city.json'
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (city_path,manifest)}
    fixture=json.loads(args.fixture_report.read_text())
    ids=list(dict.fromkeys(e['building_id'] for e in fixture['endpoints'].values()))
    report=audit_transport_readiness(load_city(city_path),scene_from_manifest(json.loads(manifest.read_text())),
        ids,Box('robot',(0,0,.75),(.65,.8,1.5)))
    report.update(source=str(args.scene.resolve()),source_hashes=hashes,
        source_unchanged=all(hashlib.sha256((args.scene/name).read_bytes()).hexdigest()==h for name,h in hashes.items()))
    save_json(report,args.output)
    print(json.dumps({'ok':report['ok'],'issues':report['issues'],'report':str(args.output)},indent=2))
    return 0 if report['ok'] else 2


if __name__=='__main__':raise SystemExit(main())
