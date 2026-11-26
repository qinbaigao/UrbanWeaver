"""Minimal continuous cabin/payload binding over existing InteractionRuntime.

Only in-cabin kinematics; doorway approach, shaft collisions and dynamics need
scene integration. A synthetic probe must never imply an existing city lift.
"""
import math

from cityg.runtime.interaction import InteractionRuntime


class LiftTransport:
    def __init__(self, machine, *, cabin_width=1.8, cabin_depth=2.0):
        if machine.state_type != 'elevator_controller':
            raise ValueError('Expected elevator controller')
        if not all(math.isfinite(v) and v > 0 for v in (cabin_width,cabin_depth)):
            raise ValueError('Invalid cabin size')
        heights = [s.get('cabin_z_m') for s in machine.states.values()]
        if len(heights)<2 or any(not isinstance(z,(int,float)) or not math.isfinite(z) for z in heights):
            raise ValueError('Invalid elevator levels')
        if any(t.duration_s<=0 or not math.isfinite(t.duration_s) for t in machine.transitions):
            raise ValueError('Invalid elevator travel time')
        self.runtime = InteractionRuntime([machine])
        self.machine = machine
        self.cabin_size = (cabin_width,cabin_depth)
        self.door_open = False
        self.payload = None

    @property
    def height(self):
        return self.runtime.value(self.machine.id,'cabin_z_m')

    def open_door(self):
        if self.runtime.active:
            raise ValueError('Door cannot open during travel')
        self.door_open = True

    def close_door(self):
        self.door_open = False

    def board(self, *, object_id, robot_local, object_local, robot_size):
        if not self.door_open or self.runtime.active or self.payload is not None:
            raise ValueError('Boarding requires stopped open empty cabin')
        if (not object_id or any(len(p)!=3 for p in (robot_local, object_local, robot_size))
                or not all(math.isfinite(v) for p in (robot_local,object_local,robot_size) for v in p)
                or min(robot_size)<=0):
            raise ValueError('Invalid rider payload')
        if any(abs(x)+size/2+.05 > bound/2 for x,size,bound in zip(robot_local,robot_size,self.cabin_size)):
            raise ValueError('Robot does not fit cabin')
        if abs(robot_local[2]-robot_size[2]/2)>1e-5 or object_local[2]<.1:
            raise ValueError('Rider must be supported by cabin floor')
        if any(abs(x)+.1 > bound/2 for x,bound in zip(object_local,self.cabin_size)):
            raise ValueError('Carried item outside cabin')
        self.payload = {'object_id':object_id,'robot_local':tuple(robot_local),'object_local':tuple(object_local)}

    def travel(self, action):
        if self.door_open or self.payload is None:
            raise ValueError('Travel requires closed door and boarded payload')
        self.runtime.trigger(self.machine.id,action)

    def step(self, dt):
        self.runtime.step(dt)
        return self.snapshot()

    def snapshot(self):
        row = {'cabin_z_m':self.height,'door_open':self.door_open,
               'moving':bool(self.runtime.active),'object_id':None}
        if self.payload:
            row.update(object_id=self.payload['object_id'])
            for kind in ('robot','object'):
                p = self.payload[kind+'_local']
                row[kind+'_world'] = [p[0],p[1],p[2]+self.height]
        return row


def validate_lift_ride(frames, *, object_id, start_z, end_z, max_step_m):
    """Check observed trajectory, not the controller's terminal-state flag."""
    errors = []
    if not all(math.isfinite(v) for v in (start_z,end_z,max_step_m)) or max_step_m<=0:
        raise ValueError('Invalid lift check limits')
    if not frames:
        return {'ok':False,'errors':['missing_lift_trace']}
    try:
        first = frames[0]
        offsets = {k:first[k+'_world'][2]-first['cabin_z_m'] for k in ('robot','object')}
        previous = start_z
        for row in frames:
            z = row['cabin_z_m']
            if not math.isfinite(z) or abs(z-previous)>max_step_m+1e-7:
                errors.append('cabin_discontinuity')
            if row['object_id'] != object_id:
                errors.append('object_identity_changed')
            if row['moving'] and row['door_open']:
                errors.append('open_door_during_travel')
            for kind in ('robot','object'):
                p = row[kind+'_world']
                if (len(p)!=3 or not all(math.isfinite(v) for v in p)
                        or abs(p[2]-z-offsets[kind])>1e-7
                        or p[:2]!=first[kind+'_world'][:2]):
                    errors.append('payload_discontinuity')
            previous=z
        if abs(first['cabin_z_m']-start_z)>1e-7 or abs(previous-end_z)>1e-7 or frames[-1]['moving']:
            errors.append('incorrect_terminal_floor')
    except (KeyError, TypeError, ValueError):
        errors.append('malformed_lift_trace')
    return {'ok':not errors,'errors':sorted(set(errors)),
            'scope':'in_cabin_kinematics_only_no_entry_exit_or_physics'}
