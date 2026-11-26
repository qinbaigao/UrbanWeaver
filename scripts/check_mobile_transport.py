"""Offline same-floor carrying roundtrip through the frozen scene's real door.

Starts from the previous accepted task overlay, not a newly duplicated cup.
No renderer, vLLM or canonical city edits. Does not claim arm/vehicle dynamics.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path

from cityg.geometry.incremental import scene_from_manifest
from cityg.runtime.transport import task_from_dict
from cityg.runtime.mobile_transport import (bind_mobile_task,plan_mobile_route,
    execute_mobile_roundtrip,mobile_task_from_dict)
from cityg.runtime.mobile_validation import validate_mobile_trace
from cityg.runtime.mobile_geometry import audit_door_static_clearance
from cityg.serialization import save_json


def negative_controls(task,trace):
    results={}
    index=next(i for i,f in enumerate(trace['frames']) if f['action']=='walk')
    for name in ('teleport','duplicate_object','lost_attachment','closed_door',
                 'missing_checkpoint','instant_open','base_yaw','stale_contract'):
        bad=deepcopy(trace);frame=bad['frames'][index];state=frame['objects'][task.reference.object_id]
        if name=='teleport':frame['robot_base'][0]+=1;state['position'][0]+=1
        elif name=='duplicate_object':frame['objects']['copy']=deepcopy(state)
        elif name=='lost_attachment':state['holder']=None
        elif name=='closed_door':
            for f in bad['frames']:f['door_angle_deg']=0.;f['door_state']='closed';f['door_moving']=False
        elif name=='missing_checkpoint':bad['frames']=[f for f in bad['frames'] if f['action']!='checkpoint']
        elif name=='instant_open':
            f=next(f for f in bad['frames'] if f['action']=='door_open');f['door_angle_deg']=90.;f['door_moving']=False;f['door_state']='open'
        elif name=='base_yaw':frame['robot_yaw_deg']+=90
        elif name=='stale_contract':frame['contract_sha256']='stale'
        result=validate_mobile_trace(task,bad)
        expected={'teleport':'base_speed_discontinuity','duplicate_object':'object_identity_or_duplicate',
            'lost_attachment':'attachment_support_mismatch','closed_door':'closed_door_crossing',
            'missing_checkpoint':'incomplete_roundtrip','instant_open':'door_state_or_speed_mismatch',
            'base_yaw':'unvalidated_base_rotation','stale_contract':'stale_mobile_contract'}[name]
        results[name]={**result,'expected_error':expected,'expected_error_observed':expected in result['errors']}
    return results


def run(prior_dir,output, *, repair_door_fit=False):
    source_report=json.loads((prior_dir/'acceptance.json').read_text())
    source=Path(source_report['source'])
    original=source_report['source_hashes']
    if not all(hashlib.sha256((source/name).read_bytes()).hexdigest()==digest for name,digest in original.items()):
        raise ValueError('Original city changed; rebind instead of replaying stale task')
    reference=task_from_dict(json.loads((prior_dir/'task.json').read_text()))
    prior_trace=json.loads((prior_dir/'trace.json').read_text())
    if reference.scene_sha256!=original['geometry_manifest.json']:raise ValueError('Task geometry hash mismatch')
    binding=json.loads((prior_dir/'binding.json').read_text())
    scene=scene_from_manifest(json.loads((source/'geometry_manifest.json').read_text()))
    corridors={node.owner_id for node in scene.navigation.nodes if node.node_type=='corridor'}
    adjacent={room_id for p in scene.primitives if p.semantic_class=='door'
              and binding['room_id'] in p.metadata.get('room_ids',[])
              for room_id in p.metadata['room_ids'] if room_id in corridors}
    if len(adjacent)!=1:raise ValueError('Ambiguous or missing adjacent corridor')
    task=bind_mobile_task(scene,reference,prior_trace,corridor_id=next(iter(adjacent)))
    output.mkdir(parents=True,exist_ok=False)
    repair=None
    if repair_door_fit:
        from cityg.geometry.door_kinematics import fit_door_leaf
        from cityg.usd.writer import UsdaWriter
        before=next(p for p in scene.primitives if p.id==task.door.id)
        after=fit_door_leaf(before)
        old_operability=audit_door_static_clearance(task.door,task.obstacles,task.door_hinge_local_m)
        # A replayable versioned delta, never an in-place edit to the frozen R1.
        delta={'schema_version':'cityg.geometry_delta.v1',
            'base_geometry_sha256':original['geometry_manifest.json'],
            'replace_primitives':[asdict(after)],'removed_primitive_ids':[]}
        save_json(delta,output/'geometry_delta.json')
        revision=hashlib.sha256((output/'geometry_delta.json').read_bytes()).hexdigest()
        scene.primitives=[after if p.id==before.id else p for p in scene.primitives]
        fitted_task=bind_mobile_task(scene,reference,prior_trace,corridor_id=next(iter(adjacent)))
        repair={'door_id':before.id,'before':asdict(before),'after':asdict(after),
            'base_geometry_sha256':original['geometry_manifest.json'],
            'geometry_delta_sha256':revision,'revision_identity':'sha256_of_delta_including_base_hash',
            'before_operability':old_operability,
            'preserved_aperture':asdict(fitted_task.door_aperture),
            'aperture_unchanged':fitted_task.door_aperture==task.door,
            'obstacles_unchanged':fitted_task.obstacles==task.obstacles,
            'floor_slabs_unchanged':fitted_task.floor_slabs==task.floor_slabs,
            'walls_or_headers_removed':False}
        if not all(repair[k] for k in ('aperture_unchanged','obstacles_unchanged','floor_slabs_unchanged')):
            raise ValueError('Door repair changed frozen surrounding geometry')
        task=replace(fitted_task,reference=replace(fitted_task.reference,scene_sha256=revision))
        save_json(repair,output/'door_fit_receipt.json')
        (output/'door_leaf.usda').write_text('#usda 1.0\n'+ '\n'.join(UsdaWriter()._articulated_primitive(after,0))+'\n')
    task,route,planning=plan_mobile_route(task)
    save_json(planning,output/'planning_receipt.json')
    report={'scope':'offline_same_floor_carrying_probe','prior_package':str(prior_dir.resolve()),
        'source':str(source),'source_hashes':original,'model_calls':0,'render_calls':0,
        'canonical_scene_edits':0,'derived_geometry_edits':1 if repair else 0,
        'door_fit_receipt':'door_fit_receipt.json' if repair else None,
        'robot_dynamics_verified':False,'cross_building_execution':False}
    if task is None:
        report.update(ok=False,reason='no_supported_route')
    else:
        trace=execute_mobile_roundtrip(task,route)
        save_json(asdict(task),output/'task.json');save_json(trace,output/'trace.json')
        save_json({'points':route,'corridor_goal':task.corridor_goal,
                   'roundtrip':True},output/'waypoints.json')
        task=mobile_task_from_dict(json.loads((output/'task.json').read_text()))
        trace=json.loads((output/'trace.json').read_text())
        checked=validate_mobile_trace(task,trace);save_json(checked,output/'independent_check.json')
        negatives=negative_controls(task,trace);save_json(negatives,output/'negative_controls.json')
        operability=audit_door_static_clearance(task.door,task.obstacles,task.door_hinge_local_m)
        save_json(operability,output/'door_operability.json')
        unchanged=all(hashlib.sha256((source/name).read_bytes()).hexdigest()==digest for name,digest in original.items())
        root=Path(__file__).resolve().parents[1]
        files=[Path(__file__),root/'src/cityg/geometry/door_kinematics.py',
               *sorted((root/'src/cityg/runtime').glob('mobile*.py'))]
        negative_ok=all(not n['ok'] and n['expected_error_observed'] for n in negatives.values())
        report.update(ok=checked['ok'] and unchanged and negative_ok and operability['ok'],
            status='passed' if checked['ok'] and operability['ok'] and unchanged and negative_ok else 'partial_or_blocked',
            kinematic_roundtrip_passed=checked['ok'],door_operability=operability,
            source_unchanged=unchanged,kinematic_check=checked,
            negative_controls_rejected=negative_ok,
            door_id=task.door.id,door_machine_id=task.door_machine_id,
            room_uid=task.reference.room_uid,object_id=task.reference.object_id,
            contract_sha256=task.fingerprint,prior_trace_sha256=task.prior_trace_sha256,
            collision_primitive_count=len(task.obstacles),support_slab_count=len(task.floor_slabs),
            implementation_hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
        if not operability['ok']:
            report['next_required']='Correct door leaf/hinge within preserved aperture in a new version, then recheck; no jamb exemption or full-task success claim.'
        save_json({'schema_version':'cityg.mobile_task_overlay.v1',
            'scene_sha256':task.reference.scene_sha256,
            'suppress_primitive_ids':[*task.reference.source_primitive_ids,task.door.id],
            'object_id':task.reference.object_id,'door_id':task.door.id,
            'door_hinge_convention':'cityg.geometry.door_kinematics.local_hinge',
            'door_hinge_local_m':task.door_hinge_local_m,
            'geometry_delta':'geometry_delta.json' if repair else None,
            'prior_trace_sha256':task.prior_trace_sha256,'trace':'trace.json',
            'viewer_adapter_implemented':False},output/'overlay.json')
    save_json(report,output/'acceptance.json');return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('prior_package',type=Path);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--repair-door-fit',action='store_true',
        help='Derive a new door-only geometry revision; preserve original walls/opening')
    args=parser.parse_args();report=run(args.prior_package,args.output,repair_door_fit=args.repair_door_fit)
    print(json.dumps(report,indent=2));return 0 if report['ok'] else 2


if __name__=='__main__':raise SystemExit(main())
