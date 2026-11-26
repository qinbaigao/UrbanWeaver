"""Independent entry/ride/exit checks against actual compiled yaw boxes."""
from dataclasses import replace
import math

from cityg.runtime.mobile_geometry import hit_ids, inflated, supported_sweep
from cityg.runtime.transport_validation import sweep_hit


def validate_elevator_transit(task,trace):
    errors=[]
    def fail(code):
        if code not in errors:errors.append(code)
    frames=trace.get('frames',[])
    if not isinstance(frames,list) or len(frames)<10:return {'ok':False,'errors':['missing_transit_trace']}
    order=['start','open_start','enter','close_start','ride','open_end','exit','close_end','done']
    phase=0;times={};previous=None;distance=0.;vertical=0.
    for f in frames:
        try:
            if f['contract_sha256']!=task.fingerprint:fail('stale_transit_contract')
            action=f['action'];base=f['robot_base'];z=f['cabin_floor_z_m'];opening=f['opening'];landing=f['landing_z'];t=f['time_s']
            if (len(base)!=3 or not all(math.isfinite(v) for v in (*base,z,opening,landing,t))
                    or not 0<=opening<=1):
                fail('nonfinite_or_invalid_transit_frame');continue
            if set(f['objects'])!={task.payload.id}:fail('object_identity_or_duplicate');continue
            held=f['objects'][task.payload.id];p=held['position']
            if len(p)!=3 or not all(math.isfinite(v) for v in p):fail('invalid_payload');continue
            if held['holder']!='scripted_effector' or held['support'] is not None:fail('lost_attachment')
            if math.dist(p,tuple(base[i]+task.carry_offset[i] for i in range(3)))>1e-7:fail('carry_transform_discontinuity')
            index=order.index(action)
            if index not in (phase,phase+1):fail('transit_phase_order')
            if index!=phase:
                old=order[phase]
                if old in ('open_start','close_start','open_end','close_end') and times.get(old,0)+1e-7<task.door_s:
                    fail('door_transition_too_fast')
                if old=='ride' and times.get(old,0)+1e-7<task.travel_s:fail('lift_travel_too_fast')
                phase=index
            if previous is None:
                if (action!='start' or t!=0 or math.dist(base,task.robot.center)>1e-7
                        or abs(z-task.start_z)>1e-7 or opening!=0 or landing!=task.start_z):fail('initial_transit_teleport')
                dt=0;old_base=base;old_p=p;old_z=z;old_open=opening;old_landing=landing
            else:
                dt=t-previous['time_s'];old_base=previous['robot_base'];old_p=previous['objects'][task.payload.id]['position']
                old_z=previous['cabin_floor_z_m'];old_open=previous['opening'];old_landing=previous['landing_z']
                if dt<=0 or dt>task.dt_s+1e-7:fail('invalid_transit_timestep')
                if abs(opening-old_open)>max(dt,0)/task.door_s+1e-7:fail('door_transition_too_fast')
            times[action]=times.get(action,0)+max(dt,0)
            landing_expected=task.end_z if index>=5 else task.start_z
            if landing!=landing_expected:fail('wrong_landing_unlocked')
            bd=math.dist(base,old_base);zd=abs(z-old_z)
            if action=='ride':
                if opening!=0 or old_open!=0:fail('open_door_during_travel')
                if (math.dist(base[:2],task.cabin_center_xy)>1e-7
                        or abs(base[2]-task.robot.size[2]/2-z)>1e-7):fail('rider_not_on_cabin_floor')
                if math.dist(old_base[:2],base[:2])>1e-7:fail('rider_teleport_into_cabin')
                if zd>abs(task.end_z-task.start_z)/task.travel_s*max(dt,0)+1e-7:fail('cabin_discontinuity')
                if (z-old_z)*(task.end_z-task.start_z)<-1e-7:fail('wrong_lift_direction')
            else:
                expected_z=task.start_z if index<4 else task.end_z
                if abs(z-expected_z)>1e-7 or zd>1e-7:fail('cabin_wrong_stop')
                if abs(base[2]-task.robot.size[2]/2-z)>1e-7:fail('unsupported_landing_height')
                if bd>task.speed_mps*max(dt,0)+1e-7:fail('base_discontinuity')
                if action in ('enter','exit'):
                    if opening!=1 or old_open!=1:fail('crossing_closed_lift_door')
                elif bd>1e-7:fail('motion_during_lift_doors')
            if action.startswith('open') and opening<old_open-1e-7:fail('wrong_door_direction')
            if action.startswith('close') and opening>old_open+1e-7:fail('wrong_door_direction')
            old_cabin=task.cabin(old_z);cabin=task.cabin(z)
            old_doors=task.door_boxes(old_z,old_open,old_landing);doors=task.door_boxes(z,opening,landing)
            body=inflated(replace(task.robot,center=old_base),task.margin_m)
            payload=replace(task.payload,center=old_p)
            for b,end,tag in ((body,base,'robot'),(payload,p,'payload')):
                for key in hit_ids(b,end,task.obstacles):fail(tag+'_static_collision:'+key)
                # Relative continuous translation handles moving floors/doors.
                for before,after in zip((*old_cabin,*old_doors),(*cabin,*doors)):
                    relative=tuple(end[i]-(after.center[i]-before.center[i]) for i in range(3))
                    if sweep_hit(b,relative,before):fail(tag+'_moving_collision:'+before.id)
            for before,after in zip((*old_cabin,*old_doors),(*cabin,*doors)):
                for key in hit_ids(before,after.center,task.obstacles):fail('elevator_static_collision:'+key)
            # Door panels must not sweep through cabin parts or each other.
            old_moving=(*old_cabin,*old_doors);moving=(*cabin,*doors)
            for i in range(len(old_moving)):
                for j in range(i+1,len(old_moving)):
                    # Cabin structure is a rigid assembly with joined edges.
                    if i<len(old_cabin) and j<len(old_cabin):continue
                    a,b=old_moving[i],old_moving[j]
                    end=tuple(moving[i].center[k]-(moving[j].center[k]-b.center[k]) for k in range(3))
                    if sweep_hit(a,end,b):fail('elevator_panel_collision:'+a.id+':'+b.id)
            floor=next(b for b in cabin if b.id==task.cabin_floor_id)
            if action=='ride':
                local_body=replace(body,center=base)
                if not supported_sweep(local_body,base,(floor,)):fail('rider_outside_cabin_floor')
            elif not supported_sweep(body,base,(*task.landing_slabs,floor)):
                fail('unsupported_entry_exit_sweep')
            relative_end=tuple(p[i]-(base[i]-old_base[i]) for i in range(3))
            if sweep_hit(payload,relative_end,replace(task.robot,center=old_base)):fail('payload_robot_collision')
            distance+=bd;vertical+=zd;previous=f
        except (KeyError,ValueError,TypeError,OverflowError,StopIteration):fail('malformed_transit_frame')
    if (phase!=8 or not previous or previous['action']!='done'
            or math.dist(previous['robot_base'],task.goal)>1e-7
            or previous['opening']!=0 or abs(previous['cabin_floor_z_m']-task.end_z)>1e-7
            or not all(key in times for key in order)):
        fail('incomplete_elevator_transit')
    return {'ok':not errors,'errors':errors,'frames':len(frames),'base_path_m':distance,
        'vertical_travel_m':vertical,'scope':'compiled_box_entry_ride_exit_kinematics',
        'checked':['landing_and_cabin_support','continuous_actor_sweeps','moving_cabin_vs_static',
                   'sliding_panel_sweeps','door_interlocks','persistent_payload','speed_and_phase_order'],
        'not_checked':['physics_actuation','wheel_dynamics','arm_ik','full_city_route']}
