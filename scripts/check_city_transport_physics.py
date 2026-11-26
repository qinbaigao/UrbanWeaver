"""CPU free release of the SAME transported payload at the accepted B716 endpoint.

This checks endpoint proxy contact, not whole-route robot dynamics.
"""
import argparse
from dataclasses import replace
import hashlib
import importlib.metadata
import json
from pathlib import Path

from cityg.serialization import save_json
from cityg.geometry.incremental import scene_from_manifest
from cityg.runtime.city_transport import contract_hash
from cityg.runtime.city_transport_validation import static_world,local_world
from cityg.runtime.transport import Box,Surface,TransportTask
from check_transport_physics import stage_text,simulate


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('scene',type=Path)
    p.add_argument('--task',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--fetch-run',type=Path,help='Use a separately accepted articulated Fetch trace')
    a=p.parse_args()
    if a.output.exists():raise ValueError('Use a new physics output')
    task=json.loads((a.task/'task.json').read_text())
    trace_dir=a.fetch_run or a.task
    trace=json.loads((trace_dir/'trace.json').read_text())
    acceptance=json.loads((trace_dir/('acceptance.json' if a.fetch_run else 'independent_check.json')).read_text());manifest=a.scene/'geometry_manifest.json'
    digest=hashlib.sha256(manifest.read_bytes()).hexdigest()
    if (not acceptance['ok'] or acceptance['source_contract_sha256' if a.fetch_run else 'contract_sha256']!=contract_hash(task)
        or acceptance['trace_sha256']!=hashlib.sha256((trace_dir/'trace.json').read_bytes()).hexdigest()
        or task['scene_sha256']!=digest or acceptance['scene_sha256']!=digest):raise ValueError('Stale or unsuccessful full task')
    if a.fetch_run and (acceptance.get('stride')!=1 or acceptance['robot_sha256']!=trace['robot_sha256']):
        raise ValueError('Stale or partial articulated check')
    final=trace['frames'][-1]['objects'][task['object_id']]
    if final['support']!=task['target']['id'] or final['holder'] is not None:raise ValueError('Payload not released')
    scene=scene_from_manifest(json.loads(manifest.read_text()));target=Surface(**task['target'])
    box=replace(Box(**task['object']),center=tuple(final['position']))
    region=Box('region',target.center,(12,12,8))
    obstacles=tuple(local_world(region,region.center,static_world(scene,task)))
    robot=replace(Box(**task['robot']),center=tuple(task['final_robot']))
    local=TransportTask(digest,task['endpoint_uids']['B716'],task['object_id'],tuple(task['source_primitive_ids']),
        box,target,target,box.center,obstacles,robot,(robot.center[0],robot.center[1],robot.center[2]+.4))
    a.output.mkdir(parents=True);cases={}
    for name,remove in [('release',False),('missing_support_negative_control',True)]:
        path=a.output/(name+'.usda');path.write_text(stage_text(local,box.center,remove_support=remove))
        cases[name]=simulate(path,local)
        cases[name]['stage_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    result={'ok':cases['release']['ok'] and not cases['missing_support_negative_control']['ok'],
        'scope':'B716_endpoint_free_proxy_release_after_'+('Fetch_articulated_route' if a.fetch_run else 'full_kinematic_route'),'cpu_only':True,
        'ovphysx_version':importlib.metadata.version('ovphysx'),'contract_sha256':contract_hash(task),
        'trace_sha256':acceptance['trace_sha256'],'cases':cases,'full_robot_dynamics_verified':False}
    save_json(result,a.output/'acceptance.json')
    print(json.dumps({**result,'cases':{k:{i:v for i,v in r.items() if i!='poses'} for k,r in cases.items()}},indent=2))
    return 0 if result['ok'] else 2


if __name__=='__main__':raise SystemExit(main())
