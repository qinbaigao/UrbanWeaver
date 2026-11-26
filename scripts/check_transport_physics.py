"""CPU endpoint release probe using the checked task's local box colliders.

Run in .venv-ovphysx. No pxr, GPU or renderer is required. A free rigid box
stands in for the cup: this is NOT mesh contact, grasp or robot dynamics.
"""
import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path

from cityg.runtime.transport import task_from_dict
from cityg.runtime.transport_validation import validate_trace


def stage_text(task, position, *, remove_support=False):
    origin=task.target.center
    lines=['#usda 1.0','(metersPerUnit = 1\n upAxis = "Z")',
        'def PhysicsScene "Physics" {',
        ' vector3f physics:gravityDirection = (0, 0, -1)',
        ' float physics:gravityMagnitude = 9.81','}']
    shapes=[(f'Obstacle_{i}',b,False) for i,b in enumerate(task.obstacles)
            if not (remove_support and b.id==task.target.primitive_id)]
    shapes.append(('Payload',task.object_box,True))
    for name,box,dynamic in shapes:
        center=position if dynamic else box.center
        p=tuple(center[i]-origin[i]+(.02 if dynamic and i==2 else 0) for i in range(3))
        schemas='"PhysicsCollisionAPI", "PhysicsRigidBodyAPI", "PhysicsMassAPI"' if dynamic else '"PhysicsCollisionAPI"'
        lines.extend([f'def Cube "{name}" (prepend apiSchemas = [{schemas}]) {{',
            ' double size = 1',f' double3 xformOp:translate = {p}',
            f' float xformOp:rotateZ = {box.yaw}',f' float3 xformOp:scale = {tuple(box.size)}',
            ' uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateZ", "xformOp:scale"]'])
        if dynamic:
            lines.extend([' bool physics:rigidBodyEnabled = true',
                ' bool physics:kinematicEnabled = false',' float physics:mass = 0.2'])
        lines.append('}')
    return '\n'.join(lines)+'\n'


def simulate(path,task):
    import numpy as np
    import ovstage
    from ovphysx import PhysX, PhysXConfig, TensorType
    PhysX.set_cpu_mode(True)
    physx=None;stage=None;binding=None;attached=False
    try:
        cache=path.parent/'collider_cache';cache.mkdir(exist_ok=True)
        physx=PhysX(config=PhysXConfig(cooked_collider_cache_dir=str(cache.resolve()),num_threads=2))
        stage=ovstage.Stage('cityg-release-check')
        ovstage.population.open_usd(stage,str(path.resolve()),ordinal=1,domains=ovstage.PopulationDomain.PHYSICS)
        stage.advance_write_floor(ordinal=1).wait();physx.attach_ovstage(stage,read_ordinal=1);attached=True
        physx.step_sync(1/120)
        binding=physx.create_tensor_binding(prim_paths=['/Payload'],tensor_type=TensorType.RIGID_BODY_POSE)
        if list(binding.prim_paths)!=['/Payload']:raise RuntimeError('Payload body missing')
        poses=[]
        for i in range(600):
            physx.step_sync(1/120)
            if i%12==0 or i==599:
                data=np.zeros(binding.shape,dtype=np.dtype(str(binding.dtype)));binding.read(data)
                poses.append({'step':i+1,'pose':data[0].tolist()})
        xyz=[p['pose'][:3] for p in poses]
        tail=np.array(xyz[-11:]);last=tail[-1]
        target=np.array(task.destination)-np.array(task.target.center)
        finite=bool(np.isfinite(np.array([p['pose'] for p in poses])).all())
        xy_drift=float(np.linalg.norm(last[:2]-target[:2]))
        tail_drift=float(np.max(np.linalg.norm(tail-tail[0],axis=1)))
        quaternion=np.array(poses[-1]['pose'][3:7])
        # ovphysx.types.RIGID_BODY_POSE explicitly specifies (p, qx,qy,qz,qw).
        x,y,z,w=quaternion/np.linalg.norm(quaternion)
        rotation=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                           [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                           [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
        half=np.array(task.object_box.size)/2
        bottom=float(last[2]-np.abs(rotation[2])@half)
        tilt=math.degrees(math.acos(float(np.clip(rotation[2,2],-1,1))))
        angle=math.radians(task.target.yaw)
        support_axes=np.array([[math.cos(angle),math.sin(angle),0],[-math.sin(angle),math.cos(angle),0]])
        extent=np.abs(support_axes@rotation)@half
        contained=bool(np.all(np.abs(support_axes@last)+extent+.01 <= np.array(task.target.size)/2))
        angular_drift=max(2*math.acos(float(np.clip(abs(np.dot(
            np.array(p['pose'][3:7])/np.linalg.norm(p['pose'][3:7]),
            quaternion/np.linalg.norm(quaternion))),-1,1))) for p in poses[-11:])
        ok=finite and abs(bottom)<.015 and xy_drift<.015 and tail_drift<.003 and contained and tilt<5 and angular_drift<.01
        return {'ok':ok,'finite':finite,'bottom_relative_to_annotated_support_m':bottom,
            'xy_drift_m':xy_drift,'last_second_drift_m':tail_drift,
            'footprint_within_support':contained,'tilt_deg':tilt,
            'last_second_angular_drift_rad':angular_drift,
            'poses':poses,'final_quaternion_raw':quaternion.tolist(),
            'physics_dt_s':1/120,'steps':601,'release_height_m':.02,'mass_kg':.2,
            'collision_model':'local_compiled_yaw_boxes','free_dynamic_payload':True,
            'not_checked':['cup_mesh_contact','grasp','robot_dynamics','full_route']}
    finally:
        if binding is not None:binding.destroy()
        if physx is not None and attached:physx.detach_ovstage()
        if physx is not None:physx.release()
        if stage is not None:stage.destroy()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package',type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    task=task_from_dict(json.loads((args.package/'task.json').read_text()))
    trace=json.loads((args.package/'trace.json').read_text())
    if not validate_trace(task,trace)['ok']:raise ValueError('Refusing physics for invalid kinematic trace')
    position=trace['frames'][-1]['objects'][task.object_id]['position']
    report={'contract_sha256':task.fingerprint,'cpu_only':True,
        'ovphysx_version':importlib.metadata.version('ovphysx'),
        'scope':'endpoint_proxy_release_not_complete_robot_task','cases':{}}
    for name,remove in [('release',False),('missing_support_negative_control',True)]:
        stage=args.output/(name+'.usda');stage.write_text(stage_text(task,position,remove_support=remove))
        try:result=simulate(stage,task)
        except Exception as error:result={'ok':False,'runtime_error':repr(error)}
        result['stage_sha256']=hashlib.sha256(stage.read_bytes()).hexdigest()
        report['cases'][name]=result
    positive=report['cases']['release'];negative=report['cases']['missing_support_negative_control']
    report['ok']=positive['ok'] and not negative['ok'] and 'runtime_error' not in negative
    (args.output/'physics_acceptance.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({**report,'cases':{k:{i:v for i,v in r.items() if i!='poses'} for k,r in report['cases'].items()}},indent=2))
    return 0 if report['ok'] else 2


if __name__=='__main__':raise SystemExit(main())
