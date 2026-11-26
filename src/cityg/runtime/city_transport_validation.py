"""Independent continuous-segment audit of the complete scripted task.

Checks measured frames, scene-bound static geometry and support, not a boolean
AND of unrelated subtask reports. Linear operations are verified to remain on
their swept segment; elevator motion uses its separate continuous checker.
"""
from dataclasses import replace
import math

from cityg.runtime.transport import Box,Surface
from cityg.runtime.transport_planning import primitive_box
from cityg.runtime.transport_validation import sweep_hit,supported
from cityg.runtime.mobile_geometry import (hit_ids,inflated,xy_bounds,segment_bounds,
    rect_overlap,supported_sweep,door_pose,audit_door_static_clearance,door_sweep_hit)
from cityg.runtime.elevator_transit import transit_task_from_dict
from cityg.runtime.elevator_validation import validate_elevator_transit
from cityg.runtime.city_transport import contract_hash


def static_world(scene,task):
    dynamic=set(task['doors'])|set(task['source_primitive_ids'])
    for value in task['lifts'].values():
        dynamic.update(b['id'] for b in value['cabin_parts'])
        dynamic.update(p['box']['id'] for p in value['panels'])
    return tuple(primitive_box(p) for p in scene.primitives if p.id not in dynamic and
        (p.collision_enabled or p.semantic_class=='interior_wall' or p.metadata.get('surface_subentity')
         or not p.layer_id.startswith(('floor:','shell:'))))


def local_world(box,end,obstacles):
    bounds=segment_bounds(box,end);lo=min(box.center[2],end[2])-box.size[2]/2
    hi=max(box.center[2],end[2])+box.size[2]/2
    return [b for b in obstacles if b.center[2]+b.size[2]/2>lo-1e-6
            and b.center[2]-b.size[2]/2<hi+1e-6 and rect_overlap(xy_bounds(b),bounds)]


def validate_city_trace(task,trace,scene,*,scene_sha256):
    errors=[];reports=[]
    def fail(code):
        if code not in errors:errors.append(code)
    if task['scene_sha256']!=scene_sha256:fail('stale_scene')
    frames=trace.get('frames',[])
    if not frames:return {'ok':False,'errors':['empty_trace']}
    digest=contract_hash(task);object_id=task['object_id'];obj=Box(**task['object']);robot=Box(**task['robot'])
    source=Surface(**task['source']);target=Surface(**task['target']);obstacles=static_world(scene,task)
    realized={p.id:p for p in scene.primitives}
    if len(task['source_primitive_ids'])!=1:fail('unsupported_compound_payload')
    else:
        primitive=realized.get(task['source_primitive_ids'][0])
        if primitive is None:fail('missing_source_primitive')
        else:
            actual=primitive_box(primitive)
            if (actual.center!=obj.center or actual.size!=obj.size or actual.yaw!=obj.yaw
                or primitive.metadata.get('subentity_id')!=object_id):fail('source_binding_mismatch')
    slabs=tuple(primitive_box(p) for p in scene.primitives if p.collision_enabled and p.primitive_type=='box'
        and p.semantic_class in ('collision_envelope','transport_walkway','road_surface','sidewalk','elevator_sill') and p.size.z<.5)
    lifts={key:transit_task_from_dict(v) for key,v in task['lifts'].items()}
    groups={};previous=None;path=0.;object_path=0.;last_op=-1
    for f in frames:
        try:
            if f['contract_sha256']!=digest:fail('stale_task_contract')
            if set(f['objects'])!={object_id}:fail('object_identity_or_duplicate');continue
            base=f['robot_base'];state=f['objects'][object_id];position=state['position'];i=f['operation']
            if not all(math.isfinite(v) for v in (*base,*position,f['time_s'])):fail('nonfinite_frame');continue
            if f['robot_yaw_deg']!=robot.yaw:fail('unvalidated_rotation')
            if set(f['doors'])!=set(task['doors']) or set(f['lifts'])!=set(lifts):fail('missing_actuator_state');continue
            if any(not math.isfinite(v) or not 0<=v<=90 for v in f['doors'].values()):fail('invalid_door_angle')
            if any(not all(math.isfinite(v) for v in (s['z'],s['opening'],s['landing_z'])) or not 0<=s['opening']<=1 for s in f['lifts'].values()):fail('invalid_lift_state')
            if i not in (last_op,last_op+1) or not -1<=i<len(task['operations']):fail('operation_order');continue
            if previous is None:
                if i!=-1 or f['time_s']!=0 or math.dist(base,robot.center)>1e-7 or math.dist(position,obj.center)>1e-7:fail('initial_state_mismatch')
                if state['holder'] is not None or state['support']!=source.id:fail('initial_support_mismatch')
                if not supported(obj,source):fail('source_not_supported')
                if any(angle!=0 for angle in f['doors'].values()):fail('initial_door_state')
                if any(abs(f['lifts'][k]['z']-v.initial_floor_z)>1e-7 or f['lifts'][k]['opening']!=0 for k,v in lifts.items()):fail('initial_lift_teleport')
            else:
                dt=f['time_s']-previous['time_s']
                if dt<=0 or dt>task['dt_s']+1e-6:fail('invalid_timestep')
                before=previous['objects'][object_id];kind=task['operations'][i]['kind']
                if i not in groups:groups[i]=[previous]
                groups[i].append(f)
                bd=math.dist(base,previous['robot_base']);pd=math.dist(position,before['position'])
                path+=bd;object_path+=pd
                speed=.8 if kind=='transit' else task['base_speed_mps']
                if bd>speed*max(dt,0)+1e-6:fail('base_speed_discontinuity')
                if kind not in ('walk','transit') and bd>1e-7:fail('unexpected_base_motion')
                if kind=='manipulate' and pd>task['effector_speed_mps']*max(dt,0)+1e-6:fail('payload_speed_discontinuity')
                if kind in ('door','call_lift','attach','release') and pd>1e-7:fail('unexpected_payload_motion')
                if kind=='release':
                    if before['holder']!='scripted_effector' or state['holder'] is not None or state['support']!=target.id:fail('invalid_release')
                elif state['holder']!='scripted_effector' or state['support'] is not None:fail('lost_attachment')
                if kind in ('walk','door','call_lift','transit'):
                    if math.dist(position,[base[j]+task['carry_offset'][j] for j in range(3)])>1e-7:fail('carry_offset_mismatch')
                if kind!='door' and f['doors']!=previous['doors']:fail('uncommanded_door_change')
                if kind not in ('call_lift','transit') and f['lifts']!=previous['lifts']:fail('uncommanded_lift_change')
                shoulder=(base[0],base[1],base[2]+.4)
                if math.dist(position,shoulder)>task['reach_m']:fail('effector_out_of_reach')
            previous=f;last_op=i
        except (KeyError,TypeError,ValueError,IndexError):fail('malformed_frame')
    if set(groups)!=set(range(len(task['operations']))):fail('incomplete_operation_sequence')
    if errors:
        return {'ok':False,'errors':errors,'scope':'complete_scripted_kinematic_A403_to_B716',
                'full_cross_building_task_verified':False,'geometry_checks_skipped':'invalid_state_trace',
                'contract_sha256':digest,'scene_sha256':scene_sha256,'frames':len(frames)}
    for i,op in enumerate(task['operations']):
        if i not in groups:continue
        rows=groups[i];first,last=rows[0],rows[-1];kind=op['kind'];before_errors=len(errors)
        start=first['robot_base'];end=last['robot_base'];a=first['objects'][object_id]['position'];b=last['objects'][object_id]['position']
        body=inflated(replace(robot,center=start),task['margin_m']);payload=replace(obj,center=a)
        moving_doors=[door_pose(Box(**v['box']),first['doors'][key],v['hinge']) for key,v in task['doors'].items()]
        dynamic=[];support=list(slabs)
        for key,lift in lifts.items():
            state=first['lifts'][key];cabin=lift.cabin(state['z'])
            dynamic.extend((*cabin,*lift.door_boxes(state['z'],state['opening'],state['landing_z'])))
            support.extend(p for p in cabin if p.id==lift.cabin_floor_id)
        world=(*obstacles,*moving_doors,*dynamic)
        if kind!='transit':
            for hit in hit_ids(body,end,local_world(body,end,world)):fail(f'robot_collision:{i}:{hit}')
            if not supported_sweep(body,end,support):fail(f'unsupported_base:{i}')
            for other in local_world(payload,b,(*world,replace(robot,center=start))):
                tolerance=1e-6
                for surface in (source,target):
                    if (other.id==surface.primitive_id and abs(other.center[2]+other.size[2]/2-surface.center[2])<=.001
                        and min(a[2],b[2])-obj.size[2]/2>=surface.center[2]-1e-5):tolerance=.001
                if sweep_hit(payload,b,other,contact_tolerance=tolerance):fail(f'payload_collision:{i}:{other.id}')
        if kind in ('walk','manipulate'):
            p0,p1=(start,end) if kind=='walk' else (a,b)
            if math.dist(p1,op['target'])>1e-7:fail('segment_goal_mismatch')
            # The whole continuous segment is checked above. Reject deviations
            # from it, rather than allowing intermediate frames to leave its envelope.
            duration=last['time_s']-first['time_s']
            for row in rows:
                alpha=(row['time_s']-first['time_s'])/duration
                actual=row['robot_base'] if kind=='walk' else row['objects'][object_id]['position']
                if math.dist(actual,[u+(v-u)*alpha for u,v in zip(p0,p1)])>1e-6:fail('nonlinear_unchecked_motion')
        elif kind=='door':
            key=op['door_id'];v=task['doors'][key];closed=Box(**v['box']);hinge=v['hinge']
            envelope=replace(closed,size=(4,4,closed.size[2]))
            near=local_world(envelope,envelope.center,obstacles)
            result=audit_door_static_clearance(closed,near,hinge)
            if not result['ok']:fail(f'door_static_conflict:{key}:'+str([r['obstacle_id'] for r in result['hits']]))
            if door_sweep_hit(closed,first['doors'][key],last['doors'][key],body,hinge):fail('door_hits_robot')
            if door_sweep_hit(closed,first['doors'][key],last['doors'][key],payload,hinge):fail('door_hits_payload')
            if last['doors'][key]!=op['angle']:fail('door_goal_mismatch')
            for previous,row in zip(rows,rows[1:]):
                if abs(row['doors'][key]-previous['doors'][key])>90*(row['time_s']-previous['time_s'])/task['door_s']+1e-6:fail('door_speed')
                if any(row['doors'][k]!=previous['doors'][k] for k in task['doors'] if k!=key):fail('uncommanded_other_door')
        elif kind=='call_lift':
            key=op['elevator_id'];lift=lifts[key];z0=first['lifts'][key]['z'];z1=last['lifts'][key]['z']
            if abs(z1-op['target_z'])>1e-7:fail('lift_call_goal')
            for previous,row in zip(rows,rows[1:]):
                old,new=previous['lifts'][key],row['lifts'][key]
                if new['opening']!=0 or abs(new['z']-old['z'])>.8*(row['time_s']-previous['time_s'])+1e-6:fail('unsafe_empty_lift_call')
                if not min(z0,z1)-1e-7<=new['z']<=max(z0,z1)+1e-7:fail('unchecked_lift_overshoot')
                if any(row['lifts'][k]!=previous['lifts'][k] for k in lifts if k!=key):fail('uncommanded_other_lift')
            old=(*lift.cabin(z0),*lift.door_boxes(z0,0,z0));new=(*lift.cabin(z1),*lift.door_boxes(z1,0,z1))
            for u,v in zip(old,new):
                for hit in hit_ids(u,v.center,local_world(u,v.center,(*obstacles,body,payload))):fail('empty_lift_collision:'+hit)
        elif kind=='transit':
            key=op['elevator_id'];lift=lifts[key];local=[]
            for j,row in enumerate(rows):
                state=row['lifts'][key]
                local.append({'contract_sha256':lift.fingerprint,'time_s':row['time_s']-first['time_s'],
                    'action':'start' if j==0 else row['action'].split(':',1)[-1],
                    'robot_base':row['robot_base'],'objects':row['objects'],
                    'cabin_floor_z_m':state['z'],'opening':state['opening'],'landing_z':state['landing_z']})
                if any(row['lifts'][k]!=first['lifts'][k] for k in lifts if k!=key):fail('uncommanded_other_lift')
            result=validate_elevator_transit(lift,{'frames':local})
            for error in result['errors']:fail('transit:'+key+':'+error)
        reports.append({'operation':i,'kind':kind,'ok':before_errors==len(errors)})
    final=frames[-1];state=final['objects'].get(object_id,{})
    if (state.get('holder') is not None or state.get('support')!=target.id
        or math.dist(state.get('position',(0,0,0)),task['destination'])>1e-7):fail('destination_not_released')
    if not supported(replace(obj,center=state.get('position',(0,0,0))),target):fail('target_not_supported')
    if math.dist(final['robot_base'],task['final_robot'])>1e-7:fail('robot_final_goal')
    if any(final['doors'].values()) or any(s['opening'] for s in final['lifts'].values()):fail('final_doors_not_closed')
    return {'ok':not errors,'errors':errors,'scope':'complete_scripted_kinematic_A403_to_B716',
            'scene_sha256':scene_sha256,'contract_sha256':digest,'frames':len(frames),'operations':reports,
            'duration_s':final['time_s'],'base_path_m':path,'object_path_m':object_path,
            'single_persistent_object':object_id,'full_cross_building_task_verified':not errors,
            'physics_dynamics_verified':False,'learned_policy':False,'arm_ik':False,'model_calls':0}
