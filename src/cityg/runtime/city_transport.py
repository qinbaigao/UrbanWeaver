"""One persistent scripted cup/robot trajectory across two real buildings.

The controller is explicitly kinematic: fixed-yaw holonomic base, virtual
end effector, scripted doors/elevators. No learned policy or arm IK is claimed.
"""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import math

from cityg.runtime.elevator_transit import execute_elevator_transit, transit_task_from_dict


def contract_hash(task):
    return hashlib.sha256(json.dumps(task,sort_keys=True,allow_nan=False).encode()).hexdigest()


def plan_city_operations(source,source_route,target,target_route,lifts,access,entrance_doors):
    operations=[]
    def op(kind,**kwargs):operations.append({'kind':kind,**kwargs})
    def walk(point):op('walk',target=list(point))
    def manipulate(point):op('manipulate',target=list(point))
    def door(key,angle):op('door',door_id=key,angle=angle)
    base=source.reference.robot_base.center
    cup=source.reference.object_box.center
    offset=source.carry_offset
    carried=tuple(base[i]+offset[i] for i in range(3));height=max(cup[2],carried[2])+.2
    op('attach')
    manipulate((cup[0],cup[1],height));manipulate((carried[0],carried[1],height));manipulate(carried)
    for p in source_route[1:]:walk(p)
    door(source.door.id,90);walk(source.corridor_goal);door(source.door.id,0)
    lift=lifts[0];x,y,z=lift.robot.center
    walk((x,source.corridor_goal[1],z));walk(lift.robot.center)
    op('call_lift',elevator_id=lift.elevator_id,target_z=lift.start_z)
    op('transit',elevator_id=lift.elevator_id)
    entrance=access['route'][0]
    walk((entrance[0],lift.goal[1],lift.goal[2]));walk(entrance)
    door(entrance_doors[0],90);walk(access['route'][1]);door(entrance_doors[0],0)
    for p in access['route'][2:-1]:walk(p)
    door(entrance_doors[1],90);walk(access['route'][-1]);door(entrance_doors[1],0)
    lift=lifts[1];x,y,z=lift.robot.center
    walk((access['route'][-1][0],y,z));walk(lift.robot.center)
    op('transit',elevator_id=lift.elevator_id)
    walk((x,target.corridor_goal[1],lift.goal[2]));walk(target.corridor_goal)
    door(target.door.id,90);walk(target.approach);door(target.door.id,0)
    for p in reversed(target_route[:-1]):walk(p)
    base=target.reference.robot_base.center;destination=target.reference.destination
    carried=tuple(base[i]+offset[i] for i in range(3));height=max(carried[2],destination[2])+.2
    manipulate((carried[0],carried[1],height));manipulate((destination[0],destination[1],height));manipulate(destination)
    op('release')
    return operations


def execute_city_task(task):
    digest=contract_hash(task);dt=task['dt_s'];time=0.;frames=[]
    base=list(task['robot']['center']);position=list(task['object']['center'])
    holder=None;support=task['source']['id'];angles={k:0. for k in task['doors']}
    lifts={k:transit_task_from_dict(v) for k,v in task['lifts'].items()}
    states={k:{'z':v.initial_floor_z,'opening':0.,'landing_z':v.initial_floor_z} for k,v in lifts.items()}
    def record(index,action):
        frames.append({'contract_sha256':digest,'time_s':time,'operation':index,'action':action,
            'robot_base':list(base),'robot_yaw_deg':task['robot']['yaw'],
            'objects':{task['object_id']:{'position':list(position),'holder':holder,'support':support}},
            'doors':dict(angles),'lifts':deepcopy(states)})
    record(-1,'start')
    for index,op in enumerate(task['operations']):
        kind=op['kind']
        if kind in ('attach','release'):
            holder='scripted_effector' if kind=='attach' else None
            support=None if kind=='attach' else task['target']['id'];time+=dt;record(index,kind)
        elif kind in ('walk','manipulate'):
            start=tuple(base if kind=='walk' else position);end=op['target']
            speed=task['base_speed_mps'] if kind=='walk' else task['effector_speed_mps']
            n=max(1,math.ceil(math.dist(start,end)/(speed*dt)))
            for i in range(1,n+1):
                p=[a+(b-a)*i/n for a,b in zip(start,end)]
                if kind=='walk':
                    base=p;position=[base[j]+task['carry_offset'][j] for j in range(3)]
                else:position=p
                time+=dt;record(index,kind)
        elif kind=='door':
            key=op['door_id'];start=angles[key];n=math.ceil(task['door_s']/dt)
            for i in range(1,n+1):
                angles[key]=start+(op['angle']-start)*i/n;time+=dt;record(index,kind)
        elif kind=='call_lift':
            key=op['elevator_id'];start=states[key]['z'];end=op['target_z']
            n=max(1,math.ceil(abs(end-start)/(.8*dt)))
            for i in range(1,n+1):
                states[key]['z']=start+(end-start)*i/n
                if i==n:states[key]['landing_z']=end
                time+=dt;record(index,kind)
        elif kind=='transit':
            key=op['elevator_id'];lift=lifts[key]
            if math.dist(base,lift.robot.center)>1e-7 or abs(states[key]['z']-lift.start_z)>1e-7:
                raise ValueError('Cannot teleport robot or cabin at segment handoff')
            local=execute_elevator_transit(lift)
            origin=time
            for f in local['frames'][1:]:
                base=list(f['robot_base']);position=list(f['objects'][task['object_id']]['position'])
                states[key]={'z':f['cabin_floor_z_m'],'opening':f['opening'],'landing_z':f['landing_z']}
                time=origin+f['time_s'];record(index,'transit:'+f['action'])
        else:raise ValueError('Unsupported operation '+kind)
    return {'schema_version':'cityg.cross_building_trace.v1','frames':frames,
            'mode':'scripted_kinematic_cross_building_transport',
            'claims':{'learned_policy':False,'arm_ik':False,'robot_dynamics':False}}
