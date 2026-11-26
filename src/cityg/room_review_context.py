"""Compact, metric evidence at the room VLM boundary (not cached verdicts)."""
from copy import deepcopy


ROOM_PROMPT = (
    'Inspect these local room snapshots. Some are normal: return issues=[] when no defect is supported. '
    'First describe actual visible content in summary, then compare with intended_design. '
    'metric_geometry is current state in room-local metres, not pixels or intended positions. '
    'Keep observations separate from expectations. IDs are opaque, not compass directions. '
    'max_gap_m measures the furniture contact edge to the wall, NEVER its center to the wall. '
    'A back-contact placement does not imply a corner placement. '
    'Roof/wall cutaways are intentional; occlusion is not absence. A chair tucked under its desk '
    'is not necessarily a collision or blocked door. Use actual clearance, not shared alignment. '
    'Bind each issue to the exact room and affected target_object_ids/target_group_ids. '
    'Affected objects are evidence, NOT permission to edit; independent checks determine editable groups. '
    'Use room_object_outside for boundary violations, room_access_blocked for obstructed access, '
    'room_group_misaligned for a violated accepted wall/facing requirement. Do not invent requirements. '
    'Unverified appearance/collision concerns remain suggestions (unspecified or room_style_incoherent). '
    'Propose minimal corrections without removing required inventory or weakening accepted constraints. '
    'Omitted geometry is unknown, not absent; request inspection in suggested_action when uncertain. '
    'compiled_inventory_by_view certifies compiled category presence only, not visibility or correct mesh appearance.'
)


def compact_room_context(building, floor, room, *, max_objects=64):
    from cityg.planning.room_envelope import metric_envelope
    from cityg.planning.room_metric_frame import restore_metric_object, MetricRoomInfeasible
    from cityg.planning.room_constraints import direction
    from cityg.validation.visual_grounding import front_verified
    design = room.metadata.get('room_design', {})
    result = {'room_id': room.id, 'function': room.function,
              'geometry_status': 'unknown', 'omitted_geometry_is_unknown': True}
    result['intended_design'] = {
        'status': design.get('status'),
        'groups': [{k: deepcopy(g[k]) for k in ('id', 'anchor', 'placement') if k in g}
                   for g in design.get('groups', [])],
        'group_relations': deepcopy(design.get('group_relations', [])),
        'inventory': [{k: i[k] for k in ('category', 'minimum', 'target') if k in i}
                      for i in (design.get('furnishing_brief') or {}).get('items', [])]}
    try:
        env = metric_envelope(building, floor, room)
        if env['status'] != 'supported':
            return {**result, 'reason': env.get('reason', 'unsupported_envelope')}
        objects = [restore_metric_object(o, building, floor, room, env)
                   for o in floor.objects if o.room_id == room.id]
    except (ValueError, KeyError, TypeError, MetricRoomInfeasible) as error:
        return {**result, 'reason': type(error).__name__}
    bb = env['bounds']
    point = lambda p: [round(p.x-bb.min_x, 4), round(p.y-bb.min_y, 4)]
    bounds = lambda q: [round(q.min_x-bb.min_x, 4), round(q.min_y-bb.min_y, 4),
                        round(q.max_x-bb.min_x, 4), round(q.max_y-bb.min_y, 4)]
    result.update(geometry_status='certified_metric', total_objects=len(objects),
                  objects_truncated=len(objects)>max_objects)
    result['metric_geometry'] = {
        'frame': {'origin': 'room southwest corner', 'x': 'east', 'y': 'north', 'units': 'metres'},
        'room_bounds_xyxy': bounds(bb), 'room_height_m': room.height_m,
        'doors': [{'door_id': d.id, 'center_xy': point(d.position), 'width_m': d.width_m}
                  for d in env['floor'].doors if room.id in (d.room_a_id, d.room_b_id)],
        'objects': [{'object_id': o.id, 'group_id': o.metadata.get('group_key'),
                     'category': o.category, 'center_xy': point(o.position),
                     'bounds_xyxy': bounds(o.bounds), 'height_m': o.height_m,
                     'verified_front_xy': list(direction(o)) if front_verified(o) else None}
                    for o in objects[:max_objects]]}
    return result


def compact_review_request(prompt, context, batch):
    """Drop duplicate/foreign context only for fully supported room-only batches.

    Legacy plans and mixed outdoor batches retain their established protocol.
    Large rooms explicitly mark partial evidence; they never imply absent objects.
    """
    if not batch or not all(v.get('kind') == 'room_interior' and
                           'compact_room' in v.get('semantic_context', {}) for v in batch):
        return prompt, context
    keep = ('scene_id', 'pending_issue_checks', 'room_group_bindings', 'view_ids',
            'view_kinds', 'allowed_entity_ids', 'view_entity_ids', 'compiled_inventory_by_view',
            'unready_entity_ids', 'cutaway_entity_ids', 'proxy_only_entity_ids')
    compact = {k: context[k] for k in keep if k in context}
    compact['room_input_protocol'] = 'metric_local_v1'
    compact['rooms'] = {v['semantic_context']['compact_room']['room_id']:
                        v['semantic_context']['compact_room'] for v in batch}
    compact['image_evidence'] = [{k: row[k] for k in
                                ('image_index', 'view_id', 'target_entity_ids', 'renderer_status')}
                               for row in context['image_evidence']]
    compact['allowed_entity_ids'] = sorted(compact['rooms'])
    return ROOM_PROMPT, compact
