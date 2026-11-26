"""Compiled-scene elevator entry/ride/exit, scripted holonomic boxes only.

The cabin floor is authoritative. No teleport boarding, disabled landing-door
collisions, invented floor slabs, or implicit change to a canonical scene.
"""
from dataclasses import asdict, dataclass, replace
from functools import cached_property
import hashlib
import json
import math

from cityg.runtime.transport import Box
from cityg.runtime.transport_planning import primitive_box


@dataclass(frozen=True)
class SlidingPanel:
    box: Box
    offset: tuple[float,float,float]
    level_z: float | None  # None = cabin panel; otherwise fixed landing height

    def __post_init__(self):
        object.__setattr__(self,'offset',tuple(self.offset))
        if (len(self.offset)!=3 or not all(math.isfinite(v) for v in self.offset)
                or self.offset[2]!=0 or math.hypot(*self.offset[:2])<=0
                or (self.level_z is not None and not math.isfinite(self.level_z))):
            raise ValueError('Invalid sliding panel')


@dataclass(frozen=True)
class ElevatorTransitTask:
    scene_sha256: str
    elevator_id: str
    robot: Box
    payload: Box
    cabin_parts: tuple[Box,...]
    cabin_floor_id: str
    panels: tuple[SlidingPanel,...]
    obstacles: tuple[Box,...]
    landing_slabs: tuple[Box,...]
    initial_floor_z: float
    start_z: float
    end_z: float
    cabin_center_xy: tuple[float,float]
    goal: tuple[float,float,float]
    carry_offset: tuple[float,float,float]
    travel_s: float
    door_s: float = .8
    dt_s: float = .05
    speed_mps: float = .3
    margin_m: float = .01

    def __post_init__(self):
        for key in ('cabin_parts','panels','obstacles','landing_slabs','cabin_center_xy','goal','carry_offset'):
            object.__setattr__(self,key,tuple(getattr(self,key)))
        numbers=(self.initial_floor_z,self.start_z,self.end_z,self.travel_s,self.door_s,
                 self.dt_s,self.speed_mps,self.margin_m,*self.cabin_center_xy,*self.goal,*self.carry_offset)
        if (not self.scene_sha256 or not self.elevator_id or len(self.goal)!=3
                or len(self.carry_offset)!=3 or len(self.cabin_center_xy)!=2
                or not all(math.isfinite(v) for v in numbers)
                or min(self.travel_s,self.door_s,self.dt_s,self.speed_mps)<=0
                or self.dt_s>.1 or self.start_z==self.end_z or not 0<=self.margin_m<=.1):
            raise ValueError('Invalid elevator transit contract')
        boxes=(*self.cabin_parts,*(p.box for p in self.panels),*self.obstacles)
        ids=[b.id for b in boxes]
        if len(ids)!=len(set(ids)) or self.robot.id in ids or self.payload.id in ids:
            raise ValueError('Duplicate elevator geometry/actors')
        floor=[b for b in self.cabin_parts if b.id==self.cabin_floor_id]
        if len(floor)!=1 or abs(floor[0].center[2]+floor[0].size[2]/2-self.initial_floor_z)>1e-7:
            raise ValueError('Missing or inconsistent compiled cabin floor')
        if any(abs(b.yaw%90)>1e-7 for b in (*self.landing_slabs,floor[0])):
            raise ValueError('Transit support currently requires cardinal floor boxes')
        if (sum(p.level_z is None for p in self.panels)!=2
                or any(sum(p.level_z==z for p in self.panels)!=2 for z in (self.start_z,self.end_z))):
            raise ValueError('Both cabin and served landing door pairs required')
        if (abs(self.robot.center[2]-self.robot.size[2]/2-self.start_z)>1e-7
                or abs(self.goal[2]-self.robot.size[2]/2-self.end_z)>1e-7
                or math.dist(self.payload.center,tuple(a+b for a,b in zip(self.robot.center,self.carry_offset)))>1e-7):
            raise ValueError('Actor entry height/carry transform mismatch')

    @cached_property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(asdict(self),sort_keys=True,allow_nan=False).encode()).hexdigest()

    def cabin(self,z):
        return tuple(replace(b,center=(b.center[0],b.center[1],b.center[2]+z-self.initial_floor_z))
                     for b in self.cabin_parts)

    def door_boxes(self,z,opening,landing_z):
        result=[]
        for p in self.panels:
            fraction=opening if p.level_z is None or p.level_z==landing_z else 0.
            dz=z-self.initial_floor_z if p.level_z is None else 0.
            result.append(replace(p.box,center=tuple(p.box.center[i]+p.offset[i]*fraction
                +(dz if i==2 else 0.) for i in range(3))))
        return tuple(result)


def transit_task_from_dict(data):
    data=dict(data)
    for key in ('robot','payload'):data[key]=Box(**data[key])
    for key in ('cabin_parts','obstacles','landing_slabs'):data[key]=tuple(Box(**x) for x in data[key])
    data['panels']=tuple(SlidingPanel(Box(**p['box']),p['offset'],p['level_z']) for p in data['panels'])
    return ElevatorTransitTask(**data)


def bind_elevator_transit(scene, *, scene_sha256, elevator_id, robot, payload,
                         start_level, end_level, goal, obstacles, landing_slabs):
    machines=[m for m in scene.state_machines if m.owner_id==elevator_id and m.state_type=='elevator_controller']
    if len(machines)!=1:raise ValueError('One compiled elevator controller required')
    machine=machines[0];states={v['current_level']:(k,v) for k,v in machine.states.items()}
    a,sa=states[start_level];b,sb=states[end_level]
    if 'cabin_floor_z_m' not in sa or 'cabin_floor_z_m' not in sb:
        raise ValueError('Legacy visual elevator has no physical cabin-floor contract')
    transitions=[t for t in machine.transitions if t.from_state==a and t.to_state==b]
    if len(transitions)!=1:raise ValueError('Missing elevator travel transition')
    parts=[p for p in scene.primitives if p.owner_id==elevator_id]
    if not parts or any(p.metadata.get('transport_elevator_version')!=1 or not p.collision_enabled for p in parts):
        raise ValueError('Unrealized elevator colliders')
    floors=[p for p in parts if p.metadata['elevator_role']=='cabin_floor']
    if len(floors)!=1:raise ValueError('Exactly one compiled moving cabin floor required')
    floor=floors[0];panels=[];cabin=[];static=list(obstacles)
    for p in parts:
        role=p.metadata['elevator_role'];box=primitive_box(p)
        if role in ('cabin_door','landing_door'):
            x,y,z=p.metadata['slide_local_m'];a=math.radians(p.rotation_z_deg)
            offset=(x*math.cos(a)-y*math.sin(a),x*math.sin(a)+y*math.cos(a),z)
            level_z=None if role=='cabin_door' else states[p.metadata['served_level']][1]['cabin_floor_z_m']
            panels.append(SlidingPanel(box,offset,level_z))
        elif role.startswith('cabin'):cabin.append(box)
        else:static.append(box)
    sills=[primitive_box(p) for p in parts if p.metadata['elevator_role']=='sill']
    return ElevatorTransitTask(scene_sha256,elevator_id,robot,payload,tuple(cabin),floor.id,
        tuple(panels),tuple(static),(*landing_slabs,*sills),floor.metadata['cabin_initial_floor_z_m'],
        sa['cabin_floor_z_m'],sb['cabin_floor_z_m'],(floor.center.x,floor.center.y),goal,
        tuple(p-b for p,b in zip(payload.center,robot.center)),transitions[0].duration_s)


def execute_elevator_transit(task):
    """Caller supplies an already-held object; approach is never teleported."""
    frames=[];base=list(task.robot.center);z=task.start_z;opening=0.;time=0.;landing=task.start_z
    def record(action):
        frames.append({'contract_sha256':task.fingerprint,'time_s':time,'action':action,
            'robot_base':list(base),'cabin_floor_z_m':z,'opening':opening,'landing_z':landing,
            'objects':{task.payload.id:{'position':[base[i]+task.carry_offset[i] for i in range(3)],
                'holder':'scripted_effector','support':None}}})
    def doors(target,action):
        nonlocal opening,time
        before=opening;steps=math.ceil(task.door_s/task.dt_s)
        for i in range(1,steps+1):
            opening=before+(target-before)*i/steps;time+=task.dt_s;record(action)
    def walk(target,action):
        nonlocal base,time
        start=tuple(base);steps=max(1,math.ceil(math.dist(start,target)/(task.speed_mps*task.dt_s)))
        for i in range(1,steps+1):
            base=[x+(y-x)*i/steps for x,y in zip(start,target)];time+=task.dt_s;record(action)
    record('start');doors(1.,'open_start')
    walk((*task.cabin_center_xy,task.start_z+task.robot.size[2]/2),'enter')
    doors(0.,'close_start')
    steps=math.ceil(task.travel_s/task.dt_s)
    for i in range(1,steps+1):
        z=task.start_z+(task.end_z-task.start_z)*i/steps
        base=[*task.cabin_center_xy,z+task.robot.size[2]/2];time+=task.dt_s;record('ride')
    landing=task.end_z;doors(1.,'open_end');walk(task.goal,'exit');doors(0.,'close_end')
    time+=task.dt_s;record('done')
    return {'schema_version':'cityg.elevator_transit_trace.v1','frames':frames,
        'claims':{'entry_exit':True,'in_cabin_kinematics':True,'dynamics':False,'autonomous_policy':False}}
