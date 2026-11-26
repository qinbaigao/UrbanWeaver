"""Persistent, simulator-neutral scripted attachment (not grasp dynamics).

The original scene is immutable. A task promotes exactly one compiled subentity
into an overlay; adapters must suppress its original primitive IDs. The first
controller has a fixed base and a bounded virtual end effector, not an IK arm.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from functools import cached_property

Point = tuple[float, float, float]


def distance(a, b):
    return math.dist(a, b)


@dataclass(frozen=True)
class Box:
    id: str
    center: Point
    size: Point
    yaw: float = 0.0

    def __post_init__(self):
        object.__setattr__(self, 'center', tuple(self.center))
        object.__setattr__(self, 'size', tuple(self.size))
        if (not self.id or len(self.center) != 3 or len(self.size) != 3
                or not all(math.isfinite(v) for v in (*self.center, *self.size, self.yaw))
                or min(self.size) <= 0):
            raise ValueError('Invalid task collision box')


@dataclass(frozen=True)
class Surface:
    id: str
    primitive_id: str
    center: Point
    size: tuple[float, float]
    yaw: float

    def __post_init__(self):
        object.__setattr__(self, 'center', tuple(self.center))
        object.__setattr__(self, 'size', tuple(self.size))
        if (not self.id or not self.primitive_id or len(self.center) != 3 or len(self.size) != 2
                or not all(math.isfinite(v) for v in (*self.center, *self.size, self.yaw))
                or min(self.size) <= 0):
            raise ValueError('Invalid task support surface')


@dataclass(frozen=True)
class TransportTask:
    scene_sha256: str
    room_uid: str
    object_id: str
    source_primitive_ids: tuple[str, ...]
    object_box: Box
    source: Surface
    target: Surface
    destination: Point
    obstacles: tuple[Box, ...]
    robot_base: Box
    shoulder: Point
    reach_m: float = 1.6
    speed_mps: float = .25
    dt_s: float = .05

    def __post_init__(self):
        for key in ('source_primitive_ids','destination','obstacles','shoulder'):
            object.__setattr__(self, key, tuple(getattr(self,key)))
        if (not self.scene_sha256 or not self.room_uid or not self.object_id
                or not self.source_primitive_ids
                or len(set(self.source_primitive_ids)) != len(self.source_primitive_ids)
                or self.object_box.id != self.object_id
                or len(self.destination) != 3 or len(self.shoulder) != 3
                or not all(math.isfinite(v) for v in (*self.destination, *self.shoulder,
                                                     self.reach_m, self.speed_mps, self.dt_s))
                or min(self.reach_m, self.speed_mps, self.dt_s) <= 0 or self.dt_s > .1):
            raise ValueError('Invalid transport contract')
        ids = [o.id for o in self.obstacles]
        if len(ids) != len(set(ids)) or set(ids) & set(self.source_primitive_ids):
            raise ValueError('Duplicated obstacles or unremoved promoted object')
        if not {self.source.primitive_id, self.target.primitive_id} <= set(ids):
            raise ValueError('Support primitive missing from collision world')

    @cached_property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True,
            separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def task_from_dict(data):
    data = dict(data)
    for field in ('object_box', 'robot_base'):
        data[field] = Box(**data[field])
    for field in ('source', 'target'):
        data[field] = Surface(**data[field])
    data['obstacles'] = tuple(Box(**b) for b in data['obstacles'])
    data['source_primitive_ids'] = tuple(data['source_primitive_ids'])
    return TransportTask(**data)


class AttachmentRuntime:
    """One object, one holder, explicit support changes, resumable mid-carry."""
    def __init__(self, task):
        self.task = task
        self.position = tuple(task.object_box.center)
        self.holder = None
        self.support = task.source.id
        self.time = 0.0

    def snapshot(self, action):
        return {'contract_sha256': self.task.fingerprint, 'time_s': self.time,
                'action': action, 'robot_base': list(self.task.robot_base.center),
                'effector': list(self.position),
                'objects': {self.task.object_id: {'position': list(self.position),
                    'holder': self.holder, 'support': self.support}}}

    def restore(self, frame):
        if frame['contract_sha256'] != self.task.fingerprint:
            raise ValueError('Stale task state')
        if set(frame['objects']) != {self.task.object_id}:
            raise ValueError('Object identity mismatch')
        state = frame['objects'][self.task.object_id]
        point = state['position']
        if (len(point) != 3 or not all(math.isfinite(v) for v in (*point, frame['time_s']))
                or frame['time_s'] < 0 or state['holder'] not in (None, 'scripted_effector')
                or (state['holder'] is not None and state['support'] is not None)
                or (state['holder'] is None and state['support'] not in (self.task.source.id, self.task.target.id))):
            raise ValueError('Invalid persistent object state')
        if (frame.get('robot_base') != list(self.task.robot_base.center)
                or frame.get('effector') != list(point)):
            raise ValueError('Invalid persistent transform binding')
        self.position = tuple(point)
        self.holder, self.support = state['holder'], state['support']
        self.time = frame['time_s']

    def attach(self):
        if self.holder is not None or self.support is None:
            raise ValueError('Object is not supported')
        self.holder, self.support = 'scripted_effector', None
        self.time += self.task.dt_s
        return self.snapshot('attach')

    def move_to(self, destination):
        if self.holder != 'scripted_effector':
            raise ValueError('Move requires attachment')
        if len(destination) != 3 or not all(math.isfinite(v) for v in destination):
            raise ValueError('Invalid destination')
        start = self.position
        steps = max(1, math.ceil(distance(start, destination) / (self.task.speed_mps*self.task.dt_s)))
        frames = []
        for i in range(1, steps+1):
            self.position = tuple(a+(b-a)*i/steps for a, b in zip(start, destination))
            self.time += self.task.dt_s
            frames.append(self.snapshot('move'))
        return frames

    def release(self):
        if self.holder is None or distance(self.position, self.task.destination) > 1e-7:
            raise ValueError('Release requires held object at contracted destination')
        self.holder, self.support = None, self.task.target.id
        self.time += self.task.dt_s
        return self.snapshot('release')


def execute_script(task, *, lift_m=.3):
    if not math.isfinite(lift_m) or lift_m <= 0:
        raise ValueError('Positive finite lift required')
    runtime = AttachmentRuntime(task)
    frames = [runtime.snapshot('start'), runtime.attach()]
    a, b = task.object_box.center, task.destination
    height = max(a[2], b[2])+lift_m
    for point in ((a[0], a[1], height), (b[0], b[1], height), b):
        frames.extend(runtime.move_to(point))
    frames.append(runtime.release())
    return {'schema_version': 'cityg.transport_trace.v1',
            'mode': 'fixed_base_scripted_attachment', 'frames': frames,
            'claims': {'arm_ik': False, 'grasp_dynamics': False,
                       'mobile_navigation': False, 'cross_building': False}}
