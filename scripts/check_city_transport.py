"""Bind and run the actual A403 -> B716 scripted offline transport task."""
import argparse
from dataclasses import asdict,replace
import hashlib
import json
from pathlib import Path

from cityg.serialization import load_city,save_json
from cityg.geometry.incremental import scene_from_manifest
from cityg.runtime.transport_planning import bind_room_task,plan_relocation,primitive_box
from cityg.runtime.mobile_transport import bind_mobile_task,plan_mobile_route
from cityg.runtime.city_transport import plan_city_operations,execute_city_task
from check_scene_elevators import bind_scene_elevator


def bind_task(scene,city,digest,fixture):
    mobiles=[];routes=[];receipts=[];raws=[]
    for alias in ('A403','B716'):
        endpoint=fixture['endpoints'][alias]
        raw,binding=bind_room_task(scene,endpoint,digest);raws.append(raw)
        ref,trace,receipt=plan_relocation(raw)
        if ref is None:raise ValueError('Cannot find endpoint placement: '+alias)
        corridor=next(r for b in city.iter_buildings() for f in b.floors for r in f.rooms
                      if f.id==endpoint['floor_id'] and r.id.endswith('_corridor'))
        mobile=bind_mobile_task(scene,ref,trace,corridor_id=corridor.id)
        if alias=='A403':
            mobile=replace(mobile,reference=replace(mobile.reference,object_box=raw.object_box))
        else:
            # The B table's own cup stays in the scene. Carry the original A cup,
            # not a substituted B object, to the independently proposed free spot.
            obstacles=(*mobile.obstacles,primitive_box(next(p for p in scene.primitives if p.id==raw.source_primitive_ids[0])))
            reference=replace(mobile.reference,object_id=raws[0].object_id,
                source_primitive_ids=raws[0].source_primitive_ids,
                object_box=replace(raws[0].object_box,center=mobile.reference.destination),
                obstacles=obstacles)
            mobile=replace(mobile,reference=reference,obstacles=obstacles)
        mobile,route,planning=plan_mobile_route(mobile)
        if mobile is None:raise ValueError('No endpoint route '+alias+': '+str(planning))
        mobiles.append(mobile);routes.append(route);receipts.append({'binding':binding,'placement':receipt,'route':planning})
    source,target=mobiles
    lifts=[]
    for bid,start,end in [('building_001',3,0),('building_000',0,6)]:
        lift=bind_scene_elevator(city,scene,digest,bid,start,end)
        lift=replace(lift,payload=replace(lift.payload,id=raws[0].object_id,yaw=raws[0].object_box.yaw))
        lifts.append(lift)
    access=scene.metadata['transport_access']
    entrance_ids=[e['door_id'] for e in access['entrances']]
    door_ids=[source.door.id,target.door.id,*entrance_ids]
    doors={p.id:{'box':asdict(primitive_box(p)),'hinge':p.metadata['hinge_local_m'],
                  'machine_id':p.metadata['state_machine_id']} for p in scene.primitives if p.id in door_ids}
    operations=plan_city_operations(source,routes[0],target,routes[1],lifts,access,entrance_ids)
    task={'schema_version':'cityg.cross_building_task.v1','scene_sha256':digest,
          'object_id':raws[0].object_id,'source_primitive_ids':list(raws[0].source_primitive_ids),
          'object':asdict(raws[0].object_box),'robot':asdict(source.reference.robot_base),
          'source':asdict(source.reference.source),'target':asdict(target.reference.target),
          'destination':list(target.reference.destination),'final_robot':list(target.reference.robot_base.center),
          'carry_offset':list(source.carry_offset),'dt_s':.1,'base_speed_mps':.5,
          'effector_speed_mps':.25,'door_s':.8,'reach_m':1.6,'margin_m':.01,
          'doors':doors,'lifts':{v.elevator_id:asdict(v) for v in lifts},'operations':operations,
          'endpoint_uids':{key:fixture['endpoints'][key]['identity']['uid'] for key in ('A403','B716')}}
    return task,receipts


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('scene',type=Path)
    p.add_argument('--fixture',type=Path,default=Path('outputs/paper_r1_20261010_retry4/r1_audit/fixture_report.json'))
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('Use a new task output directory')
    path=a.scene/'geometry_manifest.json';digest=hashlib.sha256(path.read_bytes()).hexdigest()
    scene=scene_from_manifest(json.loads(path.read_text()));city=load_city(a.scene/'city.json')
    task,receipts=bind_task(scene,city,digest,json.loads(a.fixture.read_text()))
    save_json(task,a.output/'task.json');save_json(receipts,a.output/'planning_receipts.json')
    task=json.loads((a.output/'task.json').read_text())
    trace=execute_city_task(task);save_json(trace,a.output/'trace.json')
    from cityg.runtime.city_transport_validation import validate_city_trace
    report=validate_city_trace(task,trace,scene,scene_sha256=digest)
    report['trace_sha256']=hashlib.sha256((a.output/'trace.json').read_bytes()).hexdigest()
    save_json(report,a.output/'acceptance.json');print(json.dumps(report,indent=2),flush=True)
    return 0 if report['ok'] else 2


if __name__=='__main__':raise SystemExit(main())
