"""Independent same-floor trajectory and actual door aperture verification."""
from dataclasses import replace
import math

from cityg.runtime.mobile_geometry import (door_pose, door_sweep_hit, hit_ids,
    inflated, supported_sweep, xy_bounds)
from cityg.runtime.transport_validation import axes, dot, radius, supported, sweep_hit


def validate_mobile_trace(task,trace):
    errors=[]
    def fail(code):
        if code not in errors:errors.append(code)
    frames=trace.get('frames',[])
    if not isinstance(frames,list) or len(frames)<5:return {'ok':False,'errors':['missing_mobile_trace']}
    ref=task.reference;previous_base=ref.robot_base.center;previous_object=ref.object_box.center
    previous_time=0.;previous_angle=0.;phase='initial';checkpoints=0;crossings=0
    open_elapsed=0.;close_elapsed=0.;base_length=0.;object_length=0.
    if not supported(ref.object_box,ref.source):fail('invalid_initial_support')
    if not supported(replace(ref.object_box,center=ref.destination),ref.target):fail('invalid_final_support')
    # Approach may be shifted along aperture; infer normal from the door itself.
    aperture=task.door_aperture or task.door
    normal=axes(aperture.yaw)[0 if aperture.size[0]<aperture.size[1] else 1]
    tangent=(-normal[1],normal[0],0.)
    width=max(aperture.size[:2])
    for index,frame in enumerate(frames):
        try:
            if frame['contract_sha256']!=task.fingerprint:fail('stale_mobile_contract')
            if set(frame['objects'])!={ref.object_id}:fail('object_identity_or_duplicate');continue
            state=frame['objects'][ref.object_id];p=state['position'];base=frame['robot_base']
            angle=frame['door_angle_deg'];t=frame['time_s'];yaw=frame['robot_yaw_deg'];action=frame['action']
            if (len(base)!=3 or len(p)!=3 or not all(math.isfinite(x) for x in (*p,*base,angle,t,yaw))):
                fail('malformed_nonfinite_frame');continue
            dt=t-previous_time;bd=math.dist(base,previous_base);od=math.dist(p,previous_object)
            if index==0:
                if action!='start' or t!=0 or bd>1e-7 or od>1e-7 or angle!=0:fail('invalid_initial_frame')
            elif dt<=0 or dt>ref.dt_s+1e-6:fail('invalid_time_step')
            if abs(yaw-ref.robot_base.yaw)>1e-7:fail('unvalidated_base_rotation')
            if abs(base[2]-ref.robot_base.center[2])>1e-7:fail('floor_teleport')
            if bd>task.speed_mps*max(dt,0)+1e-6:fail('base_speed_discontinuity')
            expected=(None,ref.source.id) if index==0 else ('scripted_effector',None)
            if action=='start' and index==0:pass
            elif action=='attach' and index==1 and phase=='initial':
                phase='held'
                if od>1e-7 or bd>1e-7:fail('attach_teleport')
            elif action=='manipulate' and phase=='held':
                if math.dist(base,ref.robot_base.center)>1e-7 or bd>1e-7:fail('manipulation_away_from_fixed_station')
                if od>ref.speed_mps*max(dt,0)+1e-6:fail('object_speed_discontinuity')
            elif action in ('walk','door_open','door_close','checkpoint') and phase=='held':
                expected_p=tuple(base[i]+task.carry_offset[i] for i in range(3))
                if math.dist(p,expected_p)>1e-7:fail('carry_transform_discontinuity')
                if action!='walk' and (bd>1e-7 or od>1e-7):fail('motion_during_door_or_checkpoint')
                if action=='checkpoint':
                    if checkpoints or math.dist(base,task.corridor_goal)>1e-7 or abs(angle-90)>1e-7:
                        fail('invalid_corridor_checkpoint')
                    checkpoints+=1
            elif action=='release' and phase=='held' and index==len(frames)-1:
                phase='released';expected=(None,ref.target.id)
                if (od>1e-7 or bd>1e-7 or math.dist(p,ref.destination)>1e-7
                        or math.dist(base,ref.robot_base.center)>1e-7):fail('invalid_final_release')
            else:fail('invalid_action_order')
            if (state['holder'],state['support'])!=expected:fail('attachment_support_mismatch')
            shoulder=tuple(base[i]+ref.shoulder[i]-ref.robot_base.center[i] for i in range(3))
            if math.dist(shoulder,p)>ref.reach_m:fail('effector_out_of_reach')
            if action=='door_open':
                if checkpoints or close_elapsed or math.dist(base,task.approach)>1e-7 or previous_angle>=90-1e-7:
                    fail('unauthorized_door_open')
                open_elapsed+=max(dt,0);expected_angle=min(90.,90.*open_elapsed/task.open_duration_s)
                door_state='open' if expected_angle>=90-1e-7 else 'closed'
                moving=expected_angle<90-1e-7
            elif action=='door_close':
                if checkpoints!=1 or math.dist(base,task.approach)>1e-7 or previous_angle<=1e-7:
                    fail('unauthorized_door_close')
                close_elapsed+=max(dt,0);expected_angle=max(0.,90.-90.*close_elapsed/task.close_duration_s)
                door_state='closed' if expected_angle<=1e-7 else 'open';moving=expected_angle>1e-7
            else:
                expected_angle=previous_angle;door_state='closed' if angle<=1e-7 else 'open';moving=False
                if 1e-7<angle<90-1e-7:fail('motion_before_door_transition_complete')
            if (abs(angle-expected_angle)>1e-6 or frame['door_state']!=door_state
                    or frame['door_moving'] is not moving):fail('door_state_or_speed_mismatch')
            body=inflated(replace(ref.robot_base,center=previous_base),task.margin_m)
            current_body=inflated(replace(ref.robot_base,center=base),task.margin_m)
            bounds=xy_bounds(current_body)
            if not (bounds[0]>=task.workspace[0] and bounds[1]>=task.workspace[1]
                    and bounds[2]<=task.workspace[2] and bounds[3]<=task.workspace[3]):fail('outside_task_workspace')
            if not supported_sweep(body,base,task.floor_slabs):fail('unsupported_base_sweep')
            for key in hit_ids(body,base,task.obstacles):fail('base_collision:'+key)
            carried=replace(ref.object_box,center=previous_object)
            for obstacle in task.obstacles:
                tolerance=1e-6
                for surface in (ref.source,ref.target):
                    if (obstacle.id==surface.primitive_id and
                        abs(obstacle.center[2]+obstacle.size[2]/2-surface.center[2])<=.001 and
                        min(previous_object[2],p[2])-carried.size[2]/2>=surface.center[2]-1e-5):tolerance=.001
                if sweep_hit(carried,p,obstacle,contact_tolerance=tolerance):fail('carried_collision:'+obstacle.id)
            # Relative motion avoids a false sweep through the moving base.
            relative_end=tuple(p[i]-(base[i]-previous_base[i]) for i in range(3))
            if sweep_hit(carried,relative_end,replace(ref.robot_base,center=previous_base)):
                fail('carried_robot_self_collision')
            if abs(angle-previous_angle)>1e-7:
                if door_sweep_hit(task.door,previous_angle,angle,current_body,task.door_hinge_local_m):fail('door_sweep_robot_collision')
                if door_sweep_hit(task.door,previous_angle,angle,replace(ref.object_box,center=p),task.door_hinge_local_m):
                    fail('door_sweep_payload_collision')
            else:
                leaf=door_pose(task.door,angle,task.door_hinge_local_m)
                if sweep_hit(body,base,leaf):fail('base_door_collision')
                if sweep_hit(carried,p,leaf):fail('carried_door_collision')
            old_side=dot(tuple(previous_base[i]-task.door.center[i] for i in range(3)),normal)
            new_side=dot(tuple(base[i]-task.door.center[i] for i in range(3)),normal)
            if old_side*new_side<0 or (abs(old_side)>1e-9 and abs(new_side)<=1e-9):
                crossings+=1
                alpha=abs(old_side)/(abs(old_side)+abs(new_side))
                at=tuple(previous_base[i]+alpha*(base[i]-previous_base[i])-task.door.center[i] for i in range(3))
                if abs(angle-90)>1e-7:fail('closed_door_crossing')
                if abs(dot(at,tangent))+radius(body,tangent)>width/2+1e-6:fail('outside_real_aperture')
            previous_base,previous_object,previous_time,previous_angle=base,p,t,angle
            base_length+=bd;object_length+=od
        except (KeyError,TypeError,ValueError,OverflowError):fail('malformed_frame')
    if (phase!='released' or checkpoints!=1 or crossings!=2 or abs(previous_angle)>1e-7
            or open_elapsed+1e-7<task.open_duration_s or close_elapsed+1e-7<task.close_duration_s):
        fail('incomplete_roundtrip')
    return {'ok':not errors,'errors':errors,'independent':True,'frames':len(frames),
        'base_path_m':base_length,'object_path_m':object_length,'portal_crossings':crossings,
        'door_open_time_s':open_elapsed,'door_close_time_s':close_elapsed,
        'scope':'same_floor_fixed_yaw_holonomic_proxy_and_scripted_door',
        'checked':['real_collision_slabs','continuous_base_and_payload_sweeps',
            'door_hinge_rotation','door_sweep_against_robot_and_payload',
            'real_aperture_crossing','door_timing','identity_and_support','speed_and_reach'],
        'not_checked':['arm_links_IK','wheel_steering_dynamics','door_handle_contact',
            'door_leaf_vs_static_jamb_contact','mesh_contact','elevator','cross_building']}
