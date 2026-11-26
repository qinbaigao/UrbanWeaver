"""Compile a narrow interaction contract from actual, reviewed room geometry.

Offline candidate generation is deliberately deterministic. These receipts are
an R3/R4 integration probe, not evidence of LLM/VLM method superiority.
"""
from dataclasses import replace
import math

from cityg.geometry.surface_dressing import surfaces
from cityg.runtime.transport import Box, Surface, TransportTask, execute_script
from cityg.runtime.transport_validation import validate_trace


def point(v):
    return (v.x, v.y, v.z)


def primitive_box(p):
    return Box(p.id, point(p.center), point(p.size), p.rotation_z_deg)


def surface_record(s):
    return Surface(s.id, s.primitive_id, point(s.center), (s.width, s.depth), s.yaw)


def bind_room_task(scene, room, scene_sha256):
    """Pick a real cup on a verified top, never fake a free support annotation.

    The pantry mesh's bounding box includes inset support cavities. This first
    conservative box checker prefers a dining-table cup; cavities need separate
    collision geometry and are not exempted here.
    """
    table_ids = {s['id'] for s in room['table_surfaces']}
    parts = [p for p in scene.primitives
             if p.layer_id == 'floor:'+room['floor_id']]
    tops = {s.id: s for s in surfaces(parts, 'top')}
    candidates = sorted((p for p in parts
        if p.metadata.get('asset_category') in {'cup', 'mug'}
        and p.metadata.get('support_surface_id') in table_ids
        and room['room_id'] in p.metadata.get('room_ids', [])), key=lambda p:p.id)
    if not candidates:
        raise ValueError('No realized table cup; no implicit asset insertion')
    chosen = candidates[0]
    object_id = chosen.metadata['subentity_id']
    source_parts = [p for p in parts if p.metadata.get('subentity_id') == object_id]
    if len(source_parts) != 1:
        raise ValueError('Compound promoted objects require an explicit collision adapter')
    support = surface_record(tops[chosen.metadata['support_surface_id']])
    # Keep all intersecting local geometry, not merely objects owned by the room.
    # Include visual small props and walls even when their USD collider is off.
    local_radius = 6.0
    obstacles = tuple(primitive_box(p) for p in parts if p.id != chosen.id
        and (p.collision_enabled or p.metadata.get('surface_subentity')
             or p.semantic_class == 'interior_wall')
        and all(abs(a-b) <= local_radius+(abs(math.cos(math.radians(p.rotation_z_deg)))+
                abs(math.sin(math.radians(p.rotation_z_deg))))*max(p.size.x,p.size.y)/2
                for a,b in zip(point(p.center)[:2], support.center[:2])))
    # Fixed base on the side of the table. Subsequent planner validates occupancy
    # and reach; it must fail rather than silently disable either constraint.
    c, s = math.cos(math.radians(support.yaw)), math.sin(math.radians(support.yaw))
    dx = support.size[0]/2+.56
    table = next(p for p in parts if p.id == support.primitive_id)
    floor_z = table.center.z-table.size.z/2
    base_center = (support.center[0]+dx*c, support.center[1]+dx*s, floor_z+.75)
    base = Box('scripted_robot_base', base_center, (.65,.8,1.5), support.yaw)
    shoulder = (base_center[0], base_center[1], floor_z+1.15)
    box = replace(primitive_box(chosen), id=object_id)
    initial_destination = (*support.center[:2], support.center[2]+box.size[2]/2)
    task = TransportTask(scene_sha256, room['identity']['uid'], object_id,
        (chosen.id,), box, support, support, initial_destination,
        obstacles, base, shoulder)
    return task, {'room_id': room['room_id'], 'room_uid': room['identity']['uid'],
        'source_subentity_id': object_id, 'source_primitive_ids': [chosen.id],
        'source_support': support.id, 'task': 'same_room_table_relocation',
        'geometry_scope': 'all_local_floor_boxes_within_6m_plus_extent',
        'selection': 'real_dining_cup_not_original_cross_building_pantry_candidate',
        'scene_mutation': False}


def plan_relocation(task, *, max_candidates=20, authorized=True):
    """Bounded task-local replanning, independent evaluator always enabled.

    Source/room/support/base are locked. Only destination within the same
    support and a declared lift can vary. No furniture, wall or core edits.
    """
    if type(max_candidates) is not int or not 1 <= max_candidates <= 100:
        raise ValueError('Candidate budget must be 1..100')
    report = {'schema_version': 'cityg.interaction_planning_receipt.v1',
        'mode': 'offline_deterministic', 'scene_sha256': task.scene_sha256,
        'room_uid': task.room_uid, 'authorized': authorized,
        'locked': ['scene_geometry', 'room', 'object_identity', 'support', 'robot_base'],
        'mutable': ['destination_on_same_support', 'lift_height'],
        'budget': {'candidate_limit': max_candidates, 'candidates_used': 0,
                   'structural_input_blocks': 2, 'images': 0, 'model_calls': 0},
        'obligations': ['realized_identity', 'reviewed_support', 'free_destination',
                        'reachable_swept_path', 'persistent_single_object'],
        'attempts': [], 'verified_resolved': False,
        'method_claim': 'task_contract_and_local_replanning_probe_not_M1_M2_M3_ablation'}
    if not authorized:
        return None, None, {**report, 'status': 'needs_authorization'}
    # Proposed center is intentionally not privileged: existing cups often
    # occupy it. Candidate costs are displacement + a small lift penalty.
    c, s = math.cos(math.radians(task.target.yaw)), math.sin(math.radians(task.target.yaw))
    raw = []
    for fx in (-.65, 0, .65):
        for fy in (-.65, -.35, 0, .35, .65):
            x, y = fx*task.target.size[0]/2, fy*task.target.size[1]/2
            target = (task.target.center[0]+c*x-s*y,
                      task.target.center[1]+s*x+c*y,
                      task.target.center[2]+task.object_box.size[2]/2)
            if math.dist(target, task.object_box.center) < .15:
                continue
            for lift in (.25,.45):
                raw.append((math.dist(target,task.object_box.center)+lift*.1, target, lift))
    ordered = [(0, task.destination, .25)] + sorted(raw)
    accepted = []
    for _, target, lift in ordered[:max_candidates]:
        candidate = replace(task, destination=target)
        trace = execute_script(candidate, lift_m=lift)
        checked = validate_trace(candidate, trace)
        no_op = math.dist(target,task.object_box.center) < .15
        if no_op:
            checked = {**checked, 'ok':False, 'errors':checked['errors']+['relocation_too_small']}
        cost = checked['object_path_m']
        report['attempts'].append({'destination': list(target), 'lift_m':lift,
            'cost_object_path_m':cost, 'ok':checked['ok'], 'errors':checked['errors']})
        if checked['ok']:
            accepted.append((cost, len(report['attempts'])-1, candidate, trace, checked))
    report['budget']['candidates_used'] = len(report['attempts'])
    if not accepted:
        return None, None, {**report, 'status':'unresolved_within_budget'}
    _, index, candidate, trace, checked = min(accepted, key=lambda row:(row[0],row[1]))
    report.update(status='resolved', verified_resolved=True, selected_candidate=index,
                  independent_postcheck=checked, contract_sha256=candidate.fingerprint,
                  candidate_count_feasible=len(accepted))
    return candidate, trace, report
