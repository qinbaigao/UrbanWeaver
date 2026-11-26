"""Offline R3/R4 first increment on a frozen R1 scene, no model or rendering.

Only same-room fixed-base object relocation; elevator probe is synthetic and
separate. Output is a version-bound overlay, never an overwritten source city.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from cityg.geometry.incremental import scene_from_manifest
from cityg.geometry.model import InteractionStateMachine, StateTransition
from cityg.runtime.transport import AttachmentRuntime, task_from_dict
from cityg.runtime.transport_planning import bind_room_task, plan_relocation
from cityg.runtime.transport_validation import validate_trace
from cityg.runtime.lift_transport import LiftTransport, validate_lift_ride
from cityg.serialization import save_json


def elevator_probe():
    machine=InteractionStateMachine('probe_lift','synthetic_core','elevator_controller','level_0',
        {'level_0':{'cabin_z_m':0.,'current_level':0},'level_1':{'cabin_z_m':3.2,'current_level':1}},
        [StateTransition('go_to_level_1','level_0','level_1',4.)])
    lift=LiftTransport(machine);lift.open_door()
    lift.board(object_id='probe_cup',robot_local=(0,0,.75),object_local=(.1,0,1.2),robot_size=(.65,.8,1.5))
    lift.close_door();frames=[lift.snapshot()];lift.travel('go_to_level_1')
    for _ in range(80):frames.append(lift.step(.05))
    report=validate_lift_ride(frames,object_id='probe_cup',start_z=0,end_z=3.2,max_step_m=.04)
    broken=deepcopy(frames);broken[40]['object_world'][2]-=1
    negative=validate_lift_ride(broken,object_id='probe_cup',start_z=0,end_z=3.2,max_step_m=.04)
    return {'fixture':'synthetic_two_stop_cabin_not_generated_city','frames':frames,
            'check':report,'negative_control':negative,
            'ok':report['ok'] and not negative['ok']}


def run(fixture_path, output):
    report=json.loads(fixture_path.read_text())
    scene_path=Path(report['scene'])
    source_paths=[scene_path/'city.json',scene_path/'geometry_manifest.json']
    original={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    if original['geometry_manifest.json']!=report['geometry_sha256'] or original['city.json']!=report['city_sha256']:
        raise ValueError('Stale fixture: source hashes changed')
    output.mkdir(parents=True,exist_ok=False)
    scene=scene_from_manifest(json.loads(source_paths[1].read_text()))
    initial,binding=bind_room_task(scene,report['endpoints']['A403'],original['geometry_manifest.json'])
    task,trace,receipt=plan_relocation(initial)
    save_json(binding,output/'binding.json');save_json(receipt,output/'planning_receipt.json')
    lift=elevator_probe();save_json(lift,output/'synthetic_lift_probe.json')
    root=Path(__file__).resolve().parents[1]
    files=[Path(__file__), *sorted((root/'src/cityg/runtime').glob('*transport*.py')),
           root/'src/cityg/planning/negotiation.py']
    result={'scope':'offline_same_room_fixed_base_not_cross_building',
        'source':str(scene_path),'source_hashes':original,'model_calls':0,
        'implementation_hashes':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'render_calls':0,'planning_status':receipt['status'],'elevator_probe_ok':lift['ok'],
        'source_route_contains_stairs':report['route']['stairs_on_candidate_route'],
        'cross_building_execution':False,'arm_IK':False,'physics_verified':False}
    if task:
        save_json(asdict(task),output/'task.json');save_json(trace,output/'trace.json')
        # Serialize and read back before validating, also exercise carry restore.
        task=task_from_dict(json.loads((output/'task.json').read_text()))
        trace=json.loads((output/'trace.json').read_text())
        checked=validate_trace(task,trace)
        runtime=AttachmentRuntime(task);middle=trace['frames'][len(trace['frames'])//2]
        runtime.restore(middle)
        persistence=runtime.snapshot(middle['action'])==middle
        negatives={}
        for name in ('duplicate_object','teleport','lost_attachment','missing_release','stale_contract'):
            bad=deepcopy(trace);frame=bad['frames'][len(bad['frames'])//2]
            state=frame['objects'][task.object_id]
            if name=='duplicate_object':frame['objects']['duplicate']=deepcopy(state)
            elif name=='teleport':state['position'][0]+=1
            elif name=='lost_attachment':state['holder']=None
            elif name=='missing_release':bad['frames'].pop()
            elif name=='stale_contract':frame['contract_sha256']='old'
            negatives[name]=validate_trace(task,bad)
        save_json(negatives,output/'negative_controls.json')
        save_json(checked,output/'independent_check.json')
        save_json({'schema_version':'cityg.task_overlay.v1','scene_sha256':task.scene_sha256,
            'suppress_primitive_ids':list(task.source_primitive_ids),
            'object_id':task.object_id,'initial_box':asdict(task.object_box),
            'final_state':trace['frames'][-1]['objects'][task.object_id],
            'trace':'trace.json','viewer_adapter_implemented':False},output/'overlay.json')
        result.update(kinematic_check=checked,carry_snapshot_roundtrip=persistence,
            negative_controls_rejected=all(not c['ok'] for c in negatives.values()),
            ok=checked['ok'] and persistence and all(not c['ok'] for c in negatives.values()) and lift['ok'])
    else:
        result.update(ok=False,reason='no_feasible_task_candidate')
    result['source_unchanged']=all(hashlib.sha256(p.read_bytes()).hexdigest()==original[p.name] for p in source_paths)
    result['ok']=result['ok'] and result['source_unchanged']
    save_json(result,output/'acceptance.json')
    return result


def audit_package(output):
    """Aggregate separate scope claims without upgrading them to task success."""
    task=task_from_dict(json.loads((output/'task.json').read_text()))
    trace=json.loads((output/'trace.json').read_text())
    initial=json.loads((output/'acceptance.json').read_text())
    physics=json.loads((output/'physics/physics_acceptance.json').read_text())
    methods=json.loads((output/'method_mechanisms/acceptance.json').read_text())
    source=Path(initial['source'])
    checks={'trace_independent':validate_trace(task,trace)['ok'],
        'source_unchanged':all(hashlib.sha256((source/name).read_bytes()).hexdigest()==digest
                               for name,digest in initial['source_hashes'].items()),
        'physics_contract_matches':physics['contract_sha256']==task.fingerprint,
        'endpoint_proxy_physics':physics['ok'] is True,
        'method_engineering_probes':methods['ok'] is True,
        'synthetic_lift_probe':json.loads((output/'synthetic_lift_probe.json').read_text())['ok'] is True,
        'physics_stages_unchanged':all(hashlib.sha256((output/'physics'/(name+'.usda')).read_bytes()).hexdigest()==row['stage_sha256']
                                      for name,row in physics['cases'].items())}
    report={'ok':all(checks.values()),'checks':checks,
        'scope':'R3_R4_offline_first_increment',
        'demonstrated':['real_room_fixed_base_scripted_attachment',
                       'endpoint_free_proxy_release','synthetic_in_cabin_transport',
                       'bounded_existing_negotiation_and_independent_receipts'],
        'not_demonstrated':['arm_IK','same_floor_mobile_route','actual_scene_elevator',
                            'A403_to_B716_execution','VLM_or_paper_method_efficacy'],
        'model_calls':0,'render_calls':0}
    path=output/'functional_acceptance.json'
    if path.exists():raise FileExistsError(path)
    save_json(report,path);return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fixture',type=Path,nargs='?')
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--audit-existing',action='store_true')
    args=parser.parse_args()
    if not args.audit_existing and args.fixture is None:parser.error('fixture is required')
    result=audit_package(args.output) if args.audit_existing else run(args.fixture,args.output)
    print(json.dumps(result,indent=2))
    return 0 if result['ok'] else 2


if __name__=='__main__':
    raise SystemExit(main())
