"""Re-read full task artifacts, audit and reject corrupt trajectory controls."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from cityg.geometry.incremental import scene_from_manifest
from cityg.runtime.city_transport_validation import validate_city_trace
from cityg.serialization import save_json


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('scene',type=Path)
    p.add_argument('--task',type=Path,required=True);a=p.parse_args()
    path=a.scene/'geometry_manifest.json';digest=hashlib.sha256(path.read_bytes()).hexdigest()
    scene=scene_from_manifest(json.loads(path.read_text()));task=json.loads((a.task/'task.json').read_text())
    trace=json.loads((a.task/'trace.json').read_text())
    report=validate_city_trace(task,trace,scene,scene_sha256=digest)
    report['trace_sha256']=hashlib.sha256((a.task/'trace.json').read_bytes()).hexdigest()
    save_json(report,a.task/'independent_check.json');print('positive',report['ok'],report['errors'],flush=True)
    negatives={}
    for name,expected in [('teleport','base_speed_discontinuity'),('duplicate','object_identity_or_duplicate'),
        ('lost_attachment','lost_attachment'),('skip_operation','incomplete_operation_sequence'),
        ('stale','stale_task_contract'),('initial_lift_teleport','initial_lift_teleport'),
        ('missing_release','incomplete_operation_sequence')]:
        bad=deepcopy(trace);f=next(f for f in bad['frames'] if f['action']=='walk')
        if name=='teleport':f['robot_base'][0]+=2
        elif name=='duplicate':f['objects']['copy']=deepcopy(f['objects'][task['object_id']])
        elif name=='lost_attachment':f['objects'][task['object_id']]['holder']=None
        elif name=='skip_operation':bad['frames']=[r for r in bad['frames'] if r['operation']!=16]
        elif name=='stale':f['contract_sha256']='stale'
        elif name=='initial_lift_teleport':bad['frames'][0]['lifts']['building_001_transport_elevator']['z']=9.6
        elif name=='missing_release':bad['frames'].pop()
        checked=validate_city_trace(task,bad,scene,scene_sha256=digest)
        negatives[name]={'rejected':not checked['ok'],'expected_error':expected,
                         'expected_error_observed':expected in checked['errors'],'errors':checked['errors']}
        print(name,negatives[name]['expected_error_observed'],flush=True)
    save_json(negatives,a.task/'negative_controls.json')
    result={'ok':report['ok'] and all(v['rejected'] and v['expected_error_observed'] for v in negatives.values()),
        'scope':'full_scripted_route_with_negative_controls','independent_check':'independent_check.json',
        'trace_sha256':report['trace_sha256'],'contract_sha256':report['contract_sha256'],
        'full_cross_building_task_verified':report['ok'],'negative_controls':len(negatives)}
    save_json(result,a.task/'audit_acceptance.json');print(json.dumps(result,indent=2))
    return 0 if result['ok'] else 2


if __name__=='__main__':raise SystemExit(main())
