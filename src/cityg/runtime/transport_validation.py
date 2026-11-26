"""Independent trace checking; does not trust controller success flags.

Fixed-yaw boxes and translational sweeps are conservative mesh approximations.
This checks the base and carried object, NOT articulated arm links or physics.
"""
from dataclasses import replace
import math

from cityg.runtime.transport import distance


def axes(yaw):
    angle = math.radians(yaw)
    c, s = math.cos(angle), math.sin(angle)
    return ((c, s, 0), (-s, c, 0), (0, 0, 1))


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def radius(box, axis):
    return sum(abs(dot(direction, axis))*size/2
               for direction, size in zip(axes(box.yaw), box.size))


def sweep_hit(box, end, obstacle, *, contact_tolerance=1e-6):
    """Continuous separating-axis intervals: a thin wall cannot be skipped.

    A micron of tolerance permits resting face contact, not penetration.
    No support mesh is globally exempted from collision checks.
    """
    low, high = 0.0, 1.0
    delta = tuple(b-a for a, b in zip(box.center, end))
    separation = tuple(a-b for a, b in zip(box.center, obstacle.center))
    for axis in (*axes(box.yaw), *axes(obstacle.yaw)[:2]):
        extent = radius(box, axis)+radius(obstacle, axis)-contact_tolerance
        offset, speed = dot(separation, axis), dot(delta, axis)
        if abs(speed) < 1e-12:
            if abs(offset) >= extent:
                return False
            continue
        bounds = sorted(((-extent-offset)/speed, (extent-offset)/speed))
        low, high = max(low, bounds[0]), min(high, bounds[1])
        if low >= high:
            return False
    return True


def supported(box, surface, *, margin=.01):
    offset = tuple(a-b for a, b in zip(box.center, surface.center))
    if abs(box.center[2]-box.size[2]/2-surface.center[2]) > 1e-5:
        return False
    return all(abs(dot(offset, axis))+radius(box, axis)+margin <= size/2+1e-8
               for axis, size in zip(axes(surface.yaw), surface.size))


def validate_trace(task, trace):
    errors = []
    def fail(code):
        if code not in errors:
            errors.append(code)
    frames = trace.get('frames', [])
    if not isinstance(frames, list) or len(frames) < 4:
        return {'ok': False, 'errors': ['missing_trace'], 'independent': True}
    if not supported(task.object_box, task.source):
        fail('invalid_source_support')
    if not supported(replace(task.object_box, center=task.destination), task.target):
        fail('invalid_target_support')
    for obstacle in task.obstacles:
        if sweep_hit(task.robot_base, task.robot_base.center, obstacle):
            fail('robot_base_collision:'+obstacle.id)
    phase = 'initial'
    previous, previous_time = task.object_box.center, 0.0
    length = 0.0
    for index, frame in enumerate(frames):
        try:
            if frame['contract_sha256'] != task.fingerprint:
                fail('stale_contract')
            if set(frame['objects']) != {task.object_id}:
                fail('object_identity_or_duplicate')
                continue
            state = frame['objects'][task.object_id]
            point, effector, base, timestamp = state['position'], frame['effector'], frame['robot_base'], frame['time_s']
            if (any(len(p) != 3 for p in (point, effector, base))
                    or not all(math.isfinite(v) for v in (*point, *effector, *base, timestamp))):
                fail('nonfinite_or_malformed_state')
                continue
            action = frame['action']
            step = distance(previous, point)
            dt = timestamp-previous_time
            if distance(base, task.robot_base.center) > 1e-7:
                fail('unauthorized_base_motion')
            if index == 0:
                if action != 'start' or timestamp != 0 or step > 1e-7:
                    fail('invalid_initial_state')
            elif dt <= 0 or dt > task.dt_s+1e-6 or step > task.speed_mps*dt+1e-6:
                fail('time_or_speed_discontinuity')
            if action == 'start' and index == 0:
                expected = (None, task.source.id)
            elif action == 'attach' and phase == 'initial' and index == 1:
                phase, expected = 'held', ('scripted_effector', None)
                if step > 1e-7:
                    fail('attach_teleport')
            elif action == 'move' and phase == 'held':
                expected = ('scripted_effector', None)
            elif action == 'release' and phase == 'held' and index == len(frames)-1:
                phase, expected = 'released', (None, task.target.id)
                if step > 1e-7 or distance(point, task.destination) > 1e-7:
                    fail('release_off_target')
            else:
                fail('invalid_action_order')
                expected = (None, None)
            if (state['holder'], state['support']) != expected:
                fail('attachment_support_mismatch')
            if distance(point, effector) > 1e-7:
                fail('attachment_transform_mismatch')
            if distance(task.shoulder, point) > task.reach_m:
                fail('effector_out_of_reach')
            box = replace(task.object_box, center=previous)
            for obstacle in (*task.obstacles, task.robot_base):
                tolerance = 1e-6
                # Reviewed mesh top annotations can differ from the box top by
                # sub-mm rounding. Permit <=1 mm resting contact only ABOVE an
                # annotated top near that box top; never exempt inset cavities.
                for surface in (task.source, task.target):
                    if (obstacle.id == surface.primitive_id
                            and abs(obstacle.center[2]+obstacle.size[2]/2-surface.center[2]) <= .001
                            and min(previous[2],point[2])-box.size[2]/2 >= surface.center[2]-1e-5):
                        tolerance = .001
                if sweep_hit(box, point, obstacle, contact_tolerance=tolerance):
                    fail('carried_collision:'+obstacle.id)
            previous, previous_time = point, timestamp
            length += step
        except (KeyError, TypeError, ValueError, OverflowError):
            fail('malformed_frame')
    if phase != 'released':
        fail('not_released')
    return {'ok': not errors, 'errors': errors, 'independent': True,
            'frame_count': len(frames), 'object_path_m': length,
            'collision_model': 'continuous_translation_yaw_boxes',
            'annotated_top_contact_tolerance_m': .001,
            'checked': ['identity', 'state_transitions', 'speed', 'support',
                        'fixed_base_occupancy', 'effector_reach_sphere', 'carried_swept_volume'],
            'not_checked': ['arm_IK_and_links', 'grasp_dynamics', 'mobile_route',
                            'mesh_contact_physics', 'cross_floor_execution']}
