"""Same-floor holonomic proxy carrying, with one real revolute door.

Builds on the previous fixed-base contract. No new city/asset is generated;
door actuation is scripted and the arm is a bounded virtual end effector.
"""
from dataclasses import asdict, dataclass, replace
from functools import cached_property
import hashlib
import json
import math

from cityg.geometry.model import InteractionStateMachine, StateTransition
from cityg.runtime.interaction import InteractionRuntime
from cityg.runtime.transport import Box, TransportTask, task_from_dict
from cityg.runtime.transport_planning import primitive_box
from cityg.runtime.mobile_geometry import (door_pose, hit_ids, inflated,
    plan_fixed_yaw_route, rect_overlap, supported_sweep, xy_bounds)


@dataclass(frozen=True)
class MobileTask:
    reference: TransportTask
    prior_trace_sha256: str
    door: Box
    door_machine_id: str
    open_duration_s: float
    close_duration_s: float
    obstacles: tuple[Box,...]
    floor_slabs: tuple[Box,...]
    workspace: tuple[float,float,float,float]
    approach: tuple[float,float,float]
    corridor_goal: tuple[float,float,float]
    carry_offset: tuple[float,float,float]
    speed_mps: float = .3
    margin_m: float = .01
    door_hinge_local_m: tuple[float,float,float] | None = None
    door_aperture: Box | None = None

    def __post_init__(self):
        from cityg.geometry.door_kinematics import local_hinge
        if self.door_hinge_local_m is not None:
            object.__setattr__(self,'door_hinge_local_m',local_hinge(
                self.door.size,{'hinge_local_m':self.door_hinge_local_m}))
        if self.door_aperture is not None and (
                self.door_aperture.center != self.door.center
                or self.door_aperture.yaw != self.door.yaw
                or any(a < b for a,b in zip(self.door_aperture.size,self.door.size))):
            raise ValueError('Door leaf must fit its preserved opening')
        for key in ('obstacles','floor_slabs','workspace','approach','corridor_goal','carry_offset'):
            object.__setattr__(self,key,tuple(getattr(self,key)))
        if (not self.prior_trace_sha256 or not self.door_machine_id or not self.floor_slabs
                or len(self.workspace)!=4 or any(len(p)!=3 for p in (self.approach,self.corridor_goal,self.carry_offset))
                or not all(math.isfinite(v) for v in (*self.workspace,*self.approach,*self.corridor_goal,
                    *self.carry_offset,self.speed_mps,self.margin_m,self.open_duration_s,self.close_duration_s))
                or min(self.open_duration_s,self.close_duration_s,self.speed_mps)<=0
                or not 0<=self.margin_m<=.1):
            raise ValueError('Invalid mobile contract')
        ids=[o.id for o in self.obstacles]
        if (len(ids)!=len(set(ids)) or self.door.id in ids
                or set(ids)&set(self.reference.source_primitive_ids)):
            raise ValueError('Mobile world duplicates promoted object/door')
        if not {self.reference.source.primitive_id,self.reference.target.primitive_id}<=set(ids):
            raise ValueError('Required support is absent from mobile collision world')
        if self.workspace[0]>=self.workspace[2] or self.workspace[1]>=self.workspace[3]:
            raise ValueError('Invalid mobile workspace extent')
        if any(abs(s.yaw%90)>1e-7 for s in self.floor_slabs):
            raise ValueError('Initial mobile support checker requires rectangular axis-aligned slabs')
        if (abs(self.approach[2]-self.reference.robot_base.center[2])>1e-7
                or abs(self.corridor_goal[2]-self.approach[2])>1e-7):
            raise ValueError('Mobile route must remain on one floor')

    @cached_property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(asdict(self),sort_keys=True,allow_nan=False).encode()).hexdigest()

    def controller(self):
        return InteractionRuntime([InteractionStateMachine(self.door_machine_id,self.door.id,
            'revolute_door','closed',{'closed':{'joint_angle_deg':0.,'nav_passable':False},
            'open':{'joint_angle_deg':90.,'nav_passable':True}},
            [StateTransition('open','closed','open',self.open_duration_s),
             StateTransition('close','open','closed',self.close_duration_s)])])


def mobile_task_from_dict(data):
    data=dict(data);data['reference']=task_from_dict(data['reference'])
    data['door']=Box(**data['door'])
    if data.get('door_aperture') is not None:data['door_aperture']=Box(**data['door_aperture'])
    for name in ('obstacles','floor_slabs'):data[name]=tuple(Box(**b) for b in data[name])
    return MobileTask(**data)


def bind_mobile_task(scene, prior, prior_trace, *, corridor_id):
    """Bind an existing adjacent room/corridor door; never insert a new one."""
    from cityg.runtime.transport_validation import validate_trace
    if not validate_trace(prior,prior_trace)['ok']:raise ValueError('Prior trace failed independent check')
    object_id=prior.object_id
    final=prior_trace['frames'][-1]['objects'][object_id]
    box=replace(prior.object_box,center=final['position'])
    reference=replace(prior,object_box=box,source=prior.target,destination=tuple(final['position']))
    primitive=next(p for p in scene.primitives if p.id==prior.source_primitive_ids[0])
    room_ids=primitive.metadata.get('room_ids',[])
    doors=[p for p in scene.primitives if p.semantic_class=='door' and p.layer_id==primitive.layer_id
        and corridor_id in p.metadata.get('room_ids',[]) and set(room_ids)&set(p.metadata.get('room_ids',[]))]
    if len(doors)!=1:raise ValueError('Expected one unambiguous realized room/corridor door')
    door=doors[0];state_id=door.metadata.get('state_machine_id')
    machines=[s for s in scene.state_machines if s.id==state_id]
    if len(machines)!=1:raise ValueError('Door state machine missing')
    machine=machines[0]
    if (machine.state_type!='revolute_door' or machine.initial_state!='closed'
            or machine.states['closed'].get('joint_angle_deg')!=0
            or machine.states['open'].get('joint_angle_deg')!=90):
        raise ValueError('Unsupported door controller')
    transitions={t.action:t for t in machine.transitions}
    for action,start,end in [('open','closed','open'),('close','open','closed')]:
        if action not in transitions or (transitions[action].from_state,transitions[action].to_state)!=(start,end):
            raise ValueError('Door transition contract mismatch')
    floor_z=prior.robot_base.center[2]-prior.robot_base.size[2]/2
    layer_by_id={layer.id:layer for layer in scene.layers}
    parent=layer_by_id[layer_by_id[primitive.layer_id].parent_layer_id]
    shell_ids={layer.id for layer in scene.layers if layer.layer_type=='building_shell'
               and layer.owner_id==parent.owner_id}
    # Collision slab union, including stair holes. Do not use the solid visual slab.
    slabs=tuple(primitive_box(p) for p in scene.primitives if p.layer_id in shell_ids and p.collision_enabled
        and p.primitive_type=='box' and p.semantic_class=='collision_envelope'
        and abs(p.center.z+p.size.z/2-floor_z)<1e-5 and p.size.z<.5)
    # Bound the probe near this room and corridor, include intersecting geometry
    # from all layers (shell walls and overhead slabs included).
    dc=door.center;bc=prior.robot_base.center
    workspace=(min(dc.x,bc[0])-2.8,min(dc.y,bc[1])-3.4,
               max(dc.x,bc[0])+2.0,max(dc.y,bc[1])+3.4)
    obstacles=[]
    for p in scene.primitives:
        if p.id in (*prior.source_primitive_ids,door.id):continue
        if not (p.collision_enabled or p.semantic_class=='interior_wall' or p.metadata.get('surface_subentity')):continue
        if p.size.z<=0 or p.size.x<=0 or p.size.y<=0:continue
        if p.center.z+p.size.z/2<floor_z-1e-6 or p.center.z-p.size.z/2>floor_z+3.0:continue
        b=primitive_box(p)
        if rect_overlap(xy_bounds(b),workspace):obstacles.append(b)
    axis=(1,0) if door.size.x<door.size.y else (0,1)
    yaw=math.radians(door.rotation_z_deg);c,s=math.cos(yaw),math.sin(yaw)
    normal=(axis[0]*c-axis[1]*s,axis[0]*s+axis[1]*c)
    sign=1 if sum((bc[i]-(dc.x,dc.y)[i])*normal[i] for i in range(2))>0 else -1
    normal=tuple(sign*x for x in normal)
    approach=(dc.x+normal[0],dc.y+normal[1],bc[2])
    goal=(dc.x-normal[0]*1.4,dc.y-normal[1]*1.4,bc[2])
    offset=(0.,0.,prior.robot_base.size[2]/2+box.size[2]/2+.02)
    digest=hashlib.sha256(json.dumps(prior_trace,sort_keys=True,allow_nan=False).encode()).hexdigest()
    return MobileTask(reference,digest,primitive_box(door),state_id,
        transitions['open'].duration_s,transitions['close'].duration_s,
        tuple(obstacles),slabs,workspace,approach,goal,offset,
        door_hinge_local_m=door.metadata.get('hinge_local_m'),
        door_aperture=replace(primitive_box(door),
            size=tuple(door.metadata.get('aperture_size_m',(door.size.x,door.size.y,door.size.z)))))


def plan_mobile_route(task, *, max_expansions=12000):
    ref=task.reference;base=ref.robot_base
    # Portal center is not necessarily the free aperture center once leaf opens.
    normal=tuple((task.approach[i]-task.door.center[i]) for i in range(2))
    tangent=(-normal[1],normal[0]);attempts=[]
    for offset in (0.,.025,-.025,.05,-.05):
        approach=tuple(task.approach[i]+(tangent[i]*offset if i<2 else 0) for i in range(3))
        goal=tuple(task.corridor_goal[i]+(tangent[i]*offset if i<2 else 0) for i in range(3))
        candidate=replace(task,approach=approach,corridor_goal=goal)
        aperture_base=inflated(replace(base,center=approach),task.margin_m)
        opened=door_pose(task.door,90,task.door_hinge_local_m)
        blocked=hit_ids(aperture_base,goal,(*task.obstacles,opened))
        if blocked or not supported_sweep(aperture_base,goal,task.floor_slabs):
            attempts.append({'offset_m':offset,'status':'portal_blocked','obstacle_ids':blocked});continue
        route,report=plan_fixed_yaw_route(base,approach,(*task.obstacles,task.door),
            task.floor_slabs,task.workspace,margin=task.margin_m,max_expansions=max_expansions)
        attempts.append({'offset_m':offset,**report})
        if route:return candidate,route,{'status':'planned','attempts':attempts,
            'model_calls':0,'base_model':'fixed_yaw_holonomic_proxy',
            'authorized_changes':['task_waypoints','task_door_state'],
            'scene_geometry_changed':False}
    return None,None,{'status':'unresolved','attempts':attempts,'model_calls':0}


def execute_mobile_roundtrip(task,route):
    """Take, stow, approach, open, cross, return, close and put back."""
    ref=task.reference;position=list(ref.object_box.center);base=list(ref.robot_base.center)
    holder=None;support=ref.source.id;time=0.;runtime=task.controller();frames=[]
    def record(action):
        frames.append({'contract_sha256':task.fingerprint,'time_s':time,'action':action,
            'robot_base':list(base),'robot_yaw_deg':ref.robot_base.yaw,
            'door_angle_deg':runtime.value(task.door_machine_id,'joint_angle_deg'),
            'door_state':runtime.current_states[task.door_machine_id],
            'door_moving':bool(runtime.active),
            'objects':{ref.object_id:{'position':list(position),'holder':holder,'support':support}}})
    def move(target,walking=False):
        nonlocal time,position,base
        start=tuple(base if walking else position)
        speed=task.speed_mps if walking else ref.speed_mps
        steps=max(1,math.ceil(math.dist(start,target)/(speed*ref.dt_s)))
        for i in range(1,steps+1):
            p=[a+(b-a)*i/steps for a,b in zip(start,target)]
            if walking:base=p;position=[p[j]+task.carry_offset[j] for j in range(3)]
            else:position=p
            time+=ref.dt_s;record('walk' if walking else 'manipulate')
    def actuate(action):
        nonlocal time
        runtime.trigger(task.door_machine_id,action)
        while runtime.active:
            runtime.step(ref.dt_s);time+=ref.dt_s;record('door_'+action)
    record('start');holder='scripted_effector';support=None;time+=ref.dt_s;record('attach')
    carried=tuple(base[i]+task.carry_offset[i] for i in range(3))
    lift=max(position[2],carried[2])+.2
    move((position[0],position[1],lift));move((carried[0],carried[1],lift));move(carried)
    for p in route[1:]:move(p,True)
    actuate('open');move(task.corridor_goal,True);time+=ref.dt_s;record('checkpoint')
    move(task.approach,True);actuate('close')
    for p in reversed(route[:-1]):move(p,True)
    target=ref.destination
    move((position[0],position[1],lift));move((target[0],target[1],lift));move(target)
    holder=None;support=ref.target.id;time+=ref.dt_s;record('release')
    return {'schema_version':'cityg.mobile_transport_trace.v1','frames':frames,
            'mode':'same_floor_holonomic_roundtrip','claims':{'dynamics':False,'arm_ik':False,
                'door_handle_contact':False,'door_vs_jamb_dynamics':False,'cross_building':False}}
