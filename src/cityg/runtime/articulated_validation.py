"""Independent Fetch FK, drive, attachment and sampled link-collision audit.

Official collision meshes are conservatively convexified per link. Compiled
scene obstacles use their existing OBBs. This is NOT continuous arm CCD or
contact dynamics; the report records sampling resolution and these limits.
"""
import math
import numpy as np
from scipy.optimize import linprog
from scipy.spatial.transform import Rotation
from cityg.runtime.articulated_robot import rotation
from cityg.runtime.city_transport_validation import static_world
from cityg.runtime.elevator_transit import transit_task_from_dict
from cityg.runtime.mobile_geometry import door_pose,supported_sweep
from cityg.runtime.transport import Box
from cityg.runtime.transport_planning import primitive_box


def box_planes(box):
    basis = rotation((0,0,1),math.radians(box.yaw))[:3,:3]
    normals = np.concatenate((basis.T,-basis.T))
    distances = -normals @ np.array(box.center)-np.tile(np.array(box.size)/2,2)
    return np.c_[normals,distances]


def transform_planes(planes, matrix):
    normals = np.array(planes)[:,:3] @ matrix[:3,:3].T
    return np.c_[normals,np.array(planes)[:,3]-normals @ matrix[:3,3]]


def convex_overlap(a,b,tolerance=1e-5):
    """Positive inscribed intersection radius, not bounding-box contact."""
    planes = np.r_[a,b]
    result = linprog([0,0,0,-1], A_ub=np.c_[planes[:,:3],np.ones(len(planes))],
                     b_ub=-planes[:,3], bounds=[(None,None)]*4, method='highs')
    return bool(result.success and result.x[3] > tolerance)


def validate_fetch_trace(task, trace, model, scene, *, stride=1, reference=None, max_collision_frames=None,start_collision_frame=0):
    errors=[];collisions=[];self_hits=[]; max_attach=0.;max_slip=0.;max_joint_step=0.
    def fail(code):
        if code not in errors:errors.append(code)
    rows=trace.get('frames',[])
    if not rows:return {'ok':False,'errors':['empty_trace']}
    object_id=task['object_id']; previous=None;phase='source';attachments=0;releases=0
    reference_rows={round(f['time_s'],6):f for f in reference['frames']} if reference else {}
    seen_reference=set()
    for i,row in enumerate(rows):
        try:
            root=np.array(row['robot_root']);yaw=math.radians(row['robot_yaw_deg']);q=row['robot_joints']
            if set(row['objects'])!={object_id}:fail('object_identity_or_duplicate');continue
            if not all(math.isfinite(v) for v in (*root,yaw,row['time_s'],*q.values())):fail('nonfinite_frame');continue
            for joint in model.joints:
                name=joint['name'];limit=joint.get('limit',{})
                if joint['type']!='fixed' and name not in q:fail('missing_joint:'+name)
                if not limit.get('lower',-math.inf)-1e-8<=q.get(name,0)<=limit.get('upper',math.inf)+1e-8:fail('joint_limit:'+name)
            ee=model.effector(q,root,yaw);state=row['objects'][object_id]
            if (len(state['position'])!=3 or len(state['quaternion'])!=4
                or not all(math.isfinite(v) for v in (*state['position'],*state['quaternion']))):
                fail('nonfinite_payload');continue
            if abs(np.linalg.norm(state['quaternion'])-1)>1e-5:fail('nonunit_payload_orientation')
            if np.linalg.norm(root-(np.array(row['robot_base'])+[0,0,trace['ground_offset_m']-.75]))>1e-7:fail('robot_frame_mismatch')
            if row['action']=='attach':phase='held';attachments+=1
            if row['action']=='release':phase='released';releases+=1
            expected_holder='fetch_gripper' if phase=='held' else None
            expected_support=None if phase=='held' else task['source' if phase=='source' else 'target']['id']
            if state['holder']!=expected_holder or state['support']!=expected_support:fail('attachment_state_sequence')
            if phase=='source' and np.linalg.norm(np.array(state['position'])-task['object']['center'])>1e-7:fail('source_object_moved_before_grasp')
            if reference:
                rt=round(row['reference_time_s'],6);old=reference_rows.get(rt);seen_reference.add(rt)
                if old is None or row['doors']!=old['doors'] or row['lifts']!=old['lifts']:fail('actuator_reference_mismatch')
                if old is not None and np.linalg.norm(root-(np.array(old['robot_base'])+[0,0,trace['ground_offset_m']-.75]))>1e-7:fail('route_reference_mismatch')
            if np.max(np.abs(ee-np.array(row['effector_matrix'])))>1e-6:fail('forged_effector')
            if state['holder']=='fetch_gripper':
                error=float(np.linalg.norm(ee[:3,3]-state['position']));max_attach=max(max_attach,error)
                if error>.003:fail('attachment_position')
                orientation=Rotation.from_quat(state['quaternion']).as_matrix()
                if np.max(np.abs(orientation-ee[:3,:3]))>1e-5:fail('attachment_orientation')
            elif state['holder'] is not None:fail('unknown_holder')
            if previous is not None:
                dt=row['time_s']-previous['time_s']
                if not 0<dt<=.100001:fail('invalid_timestep');continue
                delta=root-np.array(previous['robot_root'])
                old_yaw=math.radians(previous['robot_yaw_deg']);dyaw=yaw-old_yaw
                slip=abs(-math.sin(yaw)*delta[0]+math.cos(yaw)*delta[1]);max_slip=max(max_slip,slip)
                if slip>1e-6:fail('lateral_base_slip')
                if np.linalg.norm(delta[:2])>.5*dt+1e-6 or abs(dyaw)>.36*dt+1e-6:fail('base_speed')
                if abs(delta[2])>.8*dt+1e-6:fail('vertical_speed')
                if abs(delta[2])>1e-7 and not row['action'].startswith('transit:'):fail('unsupported_vertical_motion')
                for joint in model.joints:
                    name=joint['name'];dq=abs(q.get(name,0)-previous['robot_joints'].get(name,0))
                    if joint['type']!='fixed' and dq>joint.get('limit',{}).get('velocity',math.inf)*dt+1e-6:fail('joint_speed:'+name)
                    if name in model.arm_names:max_joint_step=max(max_joint_step,dq)
                signed_distance=float(delta[0]*math.cos(yaw)+delta[1]*math.sin(yaw))
                for wheel,sign in [('l_wheel_joint',-1),('r_wheel_joint',1)]:
                    expected=(signed_distance+sign*dyaw*trace['wheel_track_m']/2)/trace['wheel_radius_m']
                    if abs(q[wheel]-previous['robot_joints'][wheel]-expected)>1e-6:fail('wheel_odometry_mismatch')
                if np.linalg.norm(np.array(state['position'])-previous['objects'][object_id]['position'])>1.5*dt+.003:fail('payload_teleport')
            previous=row
        except (KeyError,ValueError,TypeError):fail('malformed_frame')
    if attachments!=1 or releases!=1 or rows[-1]['action']!='release':fail('incomplete_grasp_release_sequence')
    if reference:
        walk=[i for i,op in enumerate(task['operations']) if op['kind']=='walk']
        required={round(f['time_s'],6) for f in reference['frames'] if walk[0]<=f['operation']<=walk[-1]}
        if not required<=seen_reference:fail('incomplete_reference_route')
    if errors:return {'ok':False,'errors':errors,'geometry_skipped':'invalid_state'}
    obstacles=static_world(scene,task)
    slabs=[primitive_box(p) for p in scene.primitives if p.collision_enabled and p.primitive_type=='box'
           and p.semantic_class in ('collision_envelope','transport_walkway','road_surface','sidewalk','elevator_sill') and p.size.z<.5]
    box_lo=[];box_hi=[]
    for b in obstacles:
        basis=np.abs(rotation((0,0,1),math.radians(b.yaw))[:3,:3]);half=basis @ (np.array(b.size)/2)
        box_lo.append(np.array(b.center)-half);box_hi.append(np.array(b.center)+half)
    box_lo=np.array(box_lo);box_hi=np.array(box_hi)
    static_planes={};near_cache={};self_cache={}
    ignored={frozenset((v['link1'],v['link2'])) for v in model.spec.get('disabled_self_collisions',[])}
    lifts={key:transit_task_from_dict(value) for key,value in task['lifts'].items()}
    checked=0
    for index in range(start_collision_frame,len(rows),stride):
        if max_collision_frames is not None and checked>=max_collision_frames:break
        row=rows[index];root=np.array(row['robot_root']);q=row['robot_joints'];yaw=math.radians(row['robot_yaw_deg'])
        fk=model.fk(q,root,yaw);link_bounds=model.collision_boxes(q,root,yaw)
        key=tuple(np.floor(root).astype(int))
        if key not in near_cache:
            lo=np.array(key)-2;hi=np.array(key)+3
            near_cache[key]=np.nonzero(np.all(box_hi>lo,axis=1)&np.all(box_lo<hi,axis=1))[0]
        near=near_cache[key]
        dynamic=[door_pose(Box(**v['box']),row['doors'][k],v['hinge']) for k,v in task['doors'].items()]
        for k,lift in lifts.items():
            s=row['lifts'][k]
            dynamic.extend((*lift.cabin(s['z']),*lift.door_boxes(s['z'],s['opening'],s['landing_z'])))
        support=[b for b in slabs if abs(b.center[2]+b.size[2]/2-(root[2]-trace['ground_offset_m']))<1e-4]
        support.extend(b for b in dynamic if any(b.id==v.cabin_floor_id for v in lifts.values()))
        for wheel in ('l_wheel_link','r_wheel_link'):
            point=fk[wheel][:3,3]
            contact=Box(wheel,(point[0],point[1],root[2]-trace['ground_offset_m']+.01),(.03,.03,.02))
            # Floor/cabin/threshold union: a valid seam need not be covered by
            # one slab on its own, but an actual gap must still fail.
            if not supported_sweep(contact,contact.center,support):fail('wheel_support_missing')
        nearby_dynamic=[b for b in dynamic if np.linalg.norm(np.array(b.center)-root)<5]
        dplanes={b.id:box_planes(b) for b in nearby_dynamic}
        dbounds={b.id:(np.array(b.center)-np.abs(rotation((0,0,1),math.radians(b.yaw))[:3,:3]) @ (np.array(b.size)/2),
                      np.array(b.center)+np.abs(rotation((0,0,1),math.radians(b.yaw))[:3,:3]) @ (np.array(b.size)/2)) for b in nearby_dynamic}
        hulls={name:[transform_planes(h,fk[name]) for h in spec.get('collision_hulls',[])] for name,spec in model.spec['links'].items()}
        state=row['objects'][object_id]
        payload_basis=Rotation.from_quat(state['quaternion']).as_matrix()
        payload_normals=np.r_[payload_basis.T,-payload_basis.T]
        payload_position=np.array(state['position']);payload_half=np.array(task['object']['size'])/2
        payload_planes=np.c_[payload_normals,-payload_normals@payload_position-np.tile(payload_half,2)]
        extent=np.abs(payload_basis)@payload_half;lo,hi=payload_position-extent,payload_position+extent
        payload_near=near[np.all(box_hi[near]>lo,axis=1)&np.all(box_lo[near]<hi,axis=1)]
        for j in payload_near:
            b=obstacles[j]
            if b.id not in static_planes:static_planes[b.id]=box_planes(b)
            if convex_overlap(payload_planes,static_planes[b.id],tolerance=.001):
                hit={'frame':index,'action':row['action'],'link':'payload','obstacle':b.id}
                if not any(v['link']=='payload' and v['obstacle']==b.id for v in collisions):collisions.append(hit)
        for key,planes in dplanes.items():
            if np.all(dbounds[key][1]>lo) and np.all(dbounds[key][0]<hi) and convex_overlap(payload_planes,planes,tolerance=.001):
                if not any(v['link']=='payload' and v['obstacle']==key for v in collisions):collisions.append({'frame':index,'action':row['action'],'link':'payload','obstacle':key})
        for link_id,bounds in link_bounds.items():
            name,part=link_id.rsplit(':',1);part=int(part);lo,hi=bounds
            # Wheel rotation changes an enclosing rectangular box; exact convex
            # hulls below resolve its artificial penetration of the floor.
            indices=near[np.all(box_hi[near]>lo,axis=1)&np.all(box_lo[near]<hi,axis=1)]
            world=[]
            for j in indices:
                b=obstacles[j]
                if b.id not in static_planes:static_planes[b.id]=box_planes(b)
                world.append((b.id,static_planes[b.id]))
            world.extend((key,planes) for key,planes in dplanes.items()
                         if np.all(dbounds[key][1]>lo) and np.all(dbounds[key][0]<hi))
            for obstacle_id,planes in world:
                if convex_overlap(hulls[name][part],planes,tolerance=.001):
                    hit={'frame':index,'action':row['action'],'link':name,'obstacle':obstacle_id}
                    if not any(v['link']==name and v['obstacle']==obstacle_id for v in collisions):collisions.append(hit)
            if 'gripper_finger' not in name and np.all(hi>payload_position-extent) and np.all(lo<payload_position+extent):
                if convex_overlap(hulls[name][part],payload_planes,tolerance=.001):
                    if not any(v['link']==name and v['obstacle']=='payload' for v in collisions):collisions.append({'frame':index,'action':row['action'],'link':name,'obstacle':'payload'})
        # Cache local arm posture checks; wheel spin does not affect the arm.
        pose_key=tuple(round(q.get(n,0),5) for n in (*model.arm_names,'l_gripper_finger_joint','r_gripper_finger_joint'))
        if pose_key not in self_cache:
            found=[];names=list(link_bounds)
            for ia,a in enumerate(names):
                na,pa=a.rsplit(':',1);alo,ahi=link_bounds[a]
                for b in names[ia+1:]:
                    nb,pb=b.rsplit(':',1);blo,bhi=link_bounds[b]
                    if na==nb or frozenset((na,nb)) in ignored:continue
                    if np.any(ahi<=blo) or np.any(bhi<=alo):continue
                    if convex_overlap(hulls[na][int(pa)],hulls[nb][int(pb)],tolerance=.001):found.append((na,nb))
            self_cache[pose_key]=found
        for pair in self_cache[pose_key]:
            if not any(v['links']==list(pair) for v in self_hits):self_hits.append({'frame':index,'action':row['action'],'links':list(pair)})
        checked+=1
        if checked%100==0:print('fetch_audit',checked,'/',math.ceil(len(rows)/stride),'world_hits',len(collisions),'self_hits',len(self_hits),flush=True)
    if collisions:fail('robot_scene_collision')
    if self_hits:fail('robot_self_collision')
    final=rows[-1]['objects'][object_id]
    if final['holder'] is not None or final['support']!=task['target']['id'] or np.linalg.norm(np.array(final['position'])-task['destination'])>.003:fail('final_release')
    complete=stride==1 and checked==len(rows)
    return {'ok':not errors and complete and bool(reference),'diagnostic_ok':not errors,'errors':errors,
        'frames':len(rows),'checked_geometry_frames':checked,'stride':stride,
        'collisions':collisions,'self_collisions':self_hits,'max_attachment_error_m':max_attach,
        'max_lateral_slip_m':max_slip,'max_arm_joint_step':max_joint_step,
        'collision_model':'official_per_link_convex_hulls_vs_scene_OBBs',
        'contact_tolerance_m':.001,'continuous_arm_collision_verified':False,
        'robot_dynamics_verified':False,'grasp_dynamics_verified':False,
        'full_cross_building_task_verified':not errors and complete and bool(reference),
        'reference_route_and_actuators_verified':bool(reference),
        'wheel_support_checked':True,
        'scope':'articulated_kinematic_sampled_collision_audit'}
