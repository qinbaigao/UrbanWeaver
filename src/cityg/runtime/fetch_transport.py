"""Adapt an accepted coarse route to Fetch differential drive and pose IK.

Produces a NEW candidate trace. Never inherits the proxy's collision approval.
Doors and lifts remain scripted actuators. Grasp is a kinematic attachment.
"""
from copy import deepcopy
import math
import numpy as np
from scipy.spatial.transform import Rotation, Slerp
from cityg.runtime.articulated_robot import rotation


def angle_delta(target, start):
    return (target-start+math.pi) % (2*math.pi)-math.pi


def ground_offset(model):
    bounds = model.collision_boxes({})
    return -min(bounds[n][0, 2] for n in ('l_wheel_link:0', 'r_wheel_link:0'))


def adapt_fetch_trace(task, reference, model, *, pose_gate=None):
    source = reference['frames'][0]
    frames = []
    turns = []
    q = {j['name']:0. for j in model.joints if j['type']!='fixed'}
    q.update(zip(model.arm_names, [.15, 0, -.7, 0, 1.8, 0, -1.1, 0]))
    q.update(l_gripper_finger_joint=.05, r_gripper_finger_joint=.05,
             l_wheel_joint=0., r_wheel_joint=0., head_pan_joint=0., head_tilt_joint=.25)
    carry = np.array([.75, 0., 1.0])
    q = model.solve(carry, q, orientation=np.eye(3))
    root = np.array(source['robot_base'], dtype=float)
    offset = ground_offset(model)
    root[2] += offset-task['robot']['size'][2]/2
    yaw = math.atan2(task['object']['center'][1]-root[1], task['object']['center'][0]-root[0])
    held = False
    position = list(task['object']['center'])
    object_rotation = Rotation.from_euler('z', task['object']['yaw'], degrees=True).as_quat().tolist()
    environment = deepcopy(source)
    time = 0.
    radius = .0603
    track = .37476
    previous_root = root.copy()
    previous_yaw = yaw
    def emit(action, dt=.1):
        nonlocal time, position, previous_root, previous_yaw, object_rotation
        delta = root-previous_root
        distance = float(delta[0]*math.cos(yaw)+delta[1]*math.sin(yaw))
        turn = yaw-previous_yaw
        q['l_wheel_joint'] += (distance-turn*track/2)/radius
        q['r_wheel_joint'] += (distance+turn*track/2)/radius
        previous_root, previous_yaw = root.copy(), yaw
        ee = model.effector(q, root, yaw)
        if held:
            position = ee[:3, 3].tolist()
            object_rotation = Rotation.from_matrix(ee[:3, :3]).as_quat().tolist()
        row = deepcopy(environment)
        time += dt
        row.update(time_s=time, action=action, robot_base=(root+[0,0,.75-offset]).tolist(),
                   robot_root=root.tolist(), robot_yaw_deg=math.degrees(yaw),
                   robot_joints=dict(q), effector_matrix=ee.tolist(), reference_time_s=environment['time_s'])
        row['objects'] = {task['object_id']: {'position': list(position), 'quaternion': object_rotation,
            'holder': 'fetch_gripper' if held else None,
            'support': None if held else (task['target']['id'] if action=='release' else task['source']['id'])}}
        frames.append(row)
    def turn_to(target):
        nonlocal yaw
        delta = angle_delta(target, yaw)
        count = max(1, math.ceil(abs(delta)/.035))
        start = yaw
        for i in range(1, count+1):
            yaw = start+delta*i/count
            emit('base_turn')
    def move_joints(target, action):
        nonlocal q
        old = dict(q)
        # Respect the official velocity limits, with a deliberately slow arm.
        duration = max(abs(target.get(n, 0)-old.get(n, 0))/min(.35,model.limits[n].get('velocity',.35))
                       for n in target if n not in ('l_wheel_joint','r_wheel_joint'))
        count = max(1, math.ceil(duration/.1))
        for i in range(1,count+1):
            q = {n: old.get(n,0)+(v-old.get(n,0))*i/count for n,v in target.items()}
            emit(action)
    def arm_to(target, action, orientation=None):
        target = np.array(target)
        initial = model.effector(q)
        start = initial[:3,3]
        orientation = np.eye(3) if orientation is None else orientation
        rotations = Slerp([0,1],Rotation.from_matrix(np.array([initial[:3,:3],orientation])))
        angle = float(np.linalg.norm(Rotation.from_matrix(initial[:3,:3].T@orientation).as_rotvec()))
        count = max(1, math.ceil(float(np.linalg.norm(target-start))/.025),math.ceil(angle/.06))
        for i in range(1,count+1):
            solution = model.solve(start+(target-start)*i/count, q, orientation=rotations(i/count).as_matrix())
            move_joints(solution, action)
    def local(point):
        return rotation((0,0,1),-yaw)[:3,:3] @ (np.array(point)-root)
    emit('start', 0.)
    cup = local(task['object']['center'])
    grasp_orientation=np.eye(3)
    arm_to(cup+[0,0,.15], 'reach_pregrasp',grasp_orientation)
    arm_to(cup, 'reach_grasp',grasp_orientation)
    # URDF finger collision faces are at +/- q; the 90 mm cup is not squeezed.
    fingers = dict(q, l_gripper_finger_joint=.045, r_gripper_finger_joint=.045)
    move_joints(fingers, 'close_gripper')
    held = True
    emit('attach')
    arm_to(cup+[0,0,.15], 'lift_object',grasp_orientation)
    arm_to(carry, 'stow_object')
    # Keep the original scene actuator state sequence, but replace manipulation,
    # carry pose and mobile heading. Insert turns with paused actuators.
    walking = [i for i, op in enumerate(task['operations']) if op['kind']=='walk']
    route_frames = [f for f in reference['frames'] if walking[0] <= f['operation'] <= walking[-1]]
    endpoints={(f['operation'],f['action']):np.array(f['robot_base'])+[0,0,offset-.75] for f in route_frames}
    last_motion_key=None
    for original in route_frames:
        desired = np.array(original['robot_base'],dtype=float)
        desired[2] += offset-task['robot']['size'][2]/2
        delta = desired-root
        if np.linalg.norm(delta[:2]) > 1e-8:
            heading = math.atan2(delta[1],delta[0])
            # Differential drive may reverse, but never strafe. Check both
            # headings: a shortest turn can point the carried cup into a corner.
            candidates=sorted((heading,heading+math.pi),key=lambda a:abs(angle_delta(a,yaw)))
            heading=candidates[0]
            motion_key=(original['operation'],original['action'])
            if pose_gate is not None and motion_key!=last_motion_key:
                receipt={'reference_time_s':original['time_s'],'root':root.tolist(),'attempts':[]}
                next_op=task['operations'][original['operation']+1] if original['operation']+1<len(task['operations']) else {}
                post_states=[environment]
                if next_op.get('kind')=='door':
                    door_id=next_op['door_id'];before=environment['doors'][door_id]
                    for angle in np.linspace(before,next_op['angle'],19):
                        post=deepcopy(environment);post['doors'][door_id]=float(angle);post_states.append(post)
                for choice in candidates:
                    difference=angle_delta(choice,yaw);count=max(1,math.ceil(abs(difference)/.035))
                    hit=None
                    for post in post_states:
                        hit=pose_gate.hit(endpoints[motion_key],choice,q,post)
                        if hit is not None:break
                    if hit is None:
                        for i in range(1,count+1):
                            hit=pose_gate.hit(root,yaw+difference*i/count,q,environment)
                            if hit is not None:break
                    receipt['attempts'].append({'yaw_deg':math.degrees(choice),'collision':hit})
                    if hit is None:heading=choice;break
                else:raise ValueError('No collision-free local heading: '+str(receipt))
                turns.append(receipt)
                print('fetch_heading',len(turns),'operation',original['operation'],'choices',len(receipt['attempts']),flush=True)
            last_motion_key=motion_key
            if abs(angle_delta(heading,yaw)) > 1e-6:
                turn_to(heading)
        root = desired
        environment = deepcopy(original)
        emit(original['action'], .05 if original['action'].startswith('transit:') else .1)
    goal = np.array(task['destination'])
    turn_to(math.atan2(goal[1]-root[1],goal[0]-root[0]))
    target = local(goal)
    table_yaw=math.radians(task['target']['yaw'])
    approach=min((table_yaw,table_yaw+math.pi),key=lambda v:abs(angle_delta(v,yaw)))
    # Align jaws with the table edge; aiming diagonally from the base can
    # sweep a fingertip into the adjacent cup despite a free payload target.
    place_orientation=rotation((0,0,1),approach-yaw)[:3,:3]
    arm_to(target+[0,0,.15], 'reach_preplace',place_orientation)
    arm_to(target, 'place_object',place_orientation)
    # Opening is explicit before release; object remains kinematically attached
    # until the terminal release event, not a force-closure grasp simulation.
    move_joints(dict(q,l_gripper_finger_joint=.05,r_gripper_finger_joint=.05), 'open_gripper')
    held=False
    emit('release')
    return {'schema_version':'cityg.fetch_transport_trace.v1', 'frames':frames,
        'mode':'scripted_differential_drive_pose_ik',
        'claims':{'learned_policy':False,'arm_ik':True,'robot_dynamics':False,'grasp_dynamics':False},
        'ground_offset_m':offset, 'wheel_radius_m':radius, 'wheel_track_m':track,
        'carry_target_local_m':carry.tolist(),'heading_receipts':turns}
