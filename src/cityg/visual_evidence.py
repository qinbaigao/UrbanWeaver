"""Target-local compiled facts for visual review; no rejected-candidate leakage."""
from collections import Counter


def room_visual_contract(building, floor, room):
    """Current typed constraints, not unrotated prototype prose or cached checks."""
    from copy import deepcopy
    from dataclasses import asdict
    from cityg.planning.room_constraints import direction
    from cityg.validation.visual_grounding import front_verified
    design=room.metadata.get('room_design',{})
    current={key:deepcopy(design.get(key,[])) for key in
             ('zones','groups','group_relations','reserved_areas','protected_groups')}
    current['status']=design.get('status')
    current['intent']='Current '+room.function+' room. Use typed placement constraints; identifiers are opaque.'
    # Original design.intent and brief prose remain in the canonical scene for
    # provenance, but do not contaminate the current geometric inspection task.
    current['furnishing_brief']={key:deepcopy((design.get('furnishing_brief') or {}).get(key))
                               for key in ('occupants','items')}
    for item in current['furnishing_brief'].get('items') or []:
        item.pop('purpose',None)
    objects=[o for o in floor.objects if o.room_id==room.id]
    from cityg.room_review_context import compact_room_context
    return {'room_id':room.id,'room_design':current,'reference_prose_omitted':True,
            'compact_room':compact_room_context(building,floor,room),
            'coordinate_frame':{'kind':'canonical_unrotated_building_frame','units':'metres',
                'north':'+Y','east':'+X','building_scene_yaw_deg':building.metadata.get('orientation_deg',0),
                'rotation_origin':asdict(building.footprint.center)},
            'actual_room_bounds':asdict(room.bounds),
            'actual_furniture':[{'object_id':o.id,'group_id':o.metadata.get('group_key'),
                'category':o.category,'bounds':asdict(o.bounds),'position':asdict(o.position),
                'front_direction_xy':list(direction(o)) if front_verified(o) else None,
                'orientation_verified':front_verified(o)} for o in objects[:64]],
            'actual_furniture_total':len(objects),'actual_furniture_truncated':len(objects)>64}


def compiled_inventory_facts(view):
    """Exact category query over a bound observation snapshot, not pixel truth.

    No inference from names, category aliases or partial canonical lists. The
    fingerprint identifies this evidence payload, not a fresh scene revision.
    Existing version/commit gates remain responsible for stale-plan rejection.
    """
    import hashlib
    import json
    context=view.get('semantic_context',{})
    target=context.get('room_id')
    facts={'room_id':target,'status':'unknown','counts':None,
           'scope':'compiled major furniture joined to canonical categories; excludes surface decor',
           'proves_visible_or_usable':False,'scene_freshness_verified':False}
    if (view.get('kind')!='room_interior' or not target or
            target not in view.get('target_entity_ids',[]) or
            context.get('room_geometry_source')!='compiled_manifest'):
        return {**facts,'reason':'missing_compiled_room_binding'}
    objects=context.get('actual_furniture')
    compiled=context.get('compiled_object_ids')
    if (not isinstance(objects,list) or not isinstance(compiled,list) or
            context.get('actual_furniture_truncated') is not False or
            context.get('actual_furniture_total')!=len(objects)):
        return {**facts,'reason':'incomplete_inventory'}
    ids=[r.get('object_id') for r in objects if isinstance(r,dict)]
    if (len(ids)!=len(objects) or any(not isinstance(x,str) or not x for x in ids+compiled)
            or len(set(ids))!=len(ids) or len(set(compiled))!=len(compiled)
            or not set(compiled)<=set(ids) or any(not isinstance(r.get('category'),str)
                or not r['category'] for r in objects)):
        return {**facts,'reason':'unresolved_or_duplicate_object_binding'}
    compiled_set=set(compiled)
    counts=dict(sorted(Counter(r['category'] for r in objects if r['object_id'] in compiled_set).items()))
    payload={'room_id':target,'objects':objects,'compiled_object_ids':compiled}
    return {**facts,'status':'complete_snapshot','counts':counts,
            'compiled_major_object_count':len(compiled),
            'canonical_not_compiled_ids':sorted(set(ids)-compiled_set),
            'snapshot_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(),
            'absence_rule':'An unlisted exact category has zero compiled major objects in this snapshot only.'}


def capture_signature(status):
    """Identify the loaded view that the renderer actually applied."""
    import hashlib
    import json
    if not render_evidence_ready(status):
        return None
    applied = status.get('view_status') or {}
    camera = applied.get('camera') or {}
    canvas = status.get('capture_canvas') or {}
    if not all(camera.get(k) is not None for k in ('camera_position','look_at','up','fov_deg')):
        return None
    if not all(canvas.get(k) for k in ('width','height')):
        return None
    framing = [camera, canvas, applied.get('selected_entities'), applied.get('render_profile'),
               applied.get('hierarchy_display'), applied.get('floor_camera_preset'), applied.get('room_camera_preset')]
    return hashlib.sha256(json.dumps(framing,sort_keys=True).encode()).hexdigest()


def render_evidence_ready(status):
    """Only a complete, explicitly signalled render supports an auto repair."""
    return (status.get('ready') is True and status.get('signal_available') is True
            and not any(status.get(key,0) for key in ('failed','fallback','pending','timed_out',
                'material_textures_failed','material_textures_pending'))
            and status.get('geometry_streaming',{}).get('ready') is True
            and not status.get('geometry_streaming',{}).get('failed',0))


def batch_evidence_constraints(views, statuses):
    """Rules derived from actual capture metadata, independent of VLM claims."""
    targets={t for v in views for t in v.get('target_entity_ids',[])}
    ready={t for v in views if render_evidence_ready(statuses.get(v['view_id'],{}))
           for t in v.get('target_entity_ids',[])}
    exterior={t for v in views if not v.get('auto_cutaway') and v.get('mode') not in {'room','floor'}
              for t in v.get('target_entity_ids',[])}
    cutaway={t for v in views if v.get('auto_cutaway') for t in v.get('target_entity_ids',[])}
    proxy=set(); detail=set()
    for view in views:
        status=statuses.get(view['view_id'],{})
        profile=status.get('render_profile',status.get('view_status',{}).get('render_profile'))
        simplified=(profile=='navigation' or
                    (profile=='review' and view.get('kind')=='global'))
        if simplified:
            proxy.update(view.get('target_entity_ids',[]))
        elif render_evidence_ready(status):
            detail.update(view.get('target_entity_ids',[]))
    return {'unready_entity_ids':sorted(targets-ready),
            'cutaway_entity_ids':sorted(cutaway-exterior),
            'proxy_only_entity_ids':sorted(proxy-detail)}


def proxy_detail_issue(issue, context, entity_id=None):
    """Loaded proxy boxes are valid layout evidence, not asset-detail evidence."""
    target=entity_id if entity_id is not None else issue.entity_id
    return target in context.get('proxy_only_entity_ids',[]) and (
        issue.category in {'facade','landscape','population','lighting'}
        or (issue.category=='road' and issue.issue_code!='cross_section_conflict')
        or bool(issue.asset_requests))


def prototype_review_context(city, manifest, views):
    buildings={b.id:b for b in city.iter_buildings()}
    floors={f.id:(b,f) for b in buildings.values() for f in b.floors}
    rooms={r.id:(b,f,r) for b,f in floors.values() for r in f.rooms}
    primitives=manifest['primitives']; evidence=[]; allowed=set(); furnishing={}; manual=set(); cutaway=set()
    import json
    signatures={}
    for view in views:
        signature=json.dumps({k:view.get(k) for k in ('mode','floor_camera_preset','room_camera_preset','camera_position','look_at')},sort_keys=True)
        for target in view.get('target_entity_ids',[]):signatures.setdefault(target,set()).add(signature)
    for index,view in enumerate(views):
        targets=view.get('target_entity_ids',[]); allowed.update(targets)
        row={'image_index':index+1,'view_id':view['view_id'],'target_entity_ids':targets,
             'kind':view['kind'],'camera_mode':view.get('mode'),
             'auto_cutaway':view.get('auto_cutaway',False),'entities':[]}
        if view.get('auto_cutaway'):cutaway.update(targets)
        for target in targets:
            if target in rooms:
                b,f,r=rooms[target]; entities=[r]
            elif target in floors:
                b,f=floors[target]; entities=f.rooms
                counts=Counter(p['semantic_class'] for p in primitives if p['layer_id']=='floor:'+f.id)
                row['compiled_floor_counts']=dict(counts)
                if len(signatures[target])<2: manual.add(target)
            elif target in buildings:
                row['entities'].append({'id':target,'function':buildings[target].function,'type':'building'})
                continue
            else:
                continue
            for room in entities:
                detailed=bool(room.metadata.get('layout_prototype_id') or room.metadata.get('room_design',{}).get('status')=='accepted')
                objects=[o for o in f.objects if o.room_id==room.id]
                row['entities'].append({'id':room.id,'type':'room','function':room.function,
                    'furnishing_expected':detailed,'major_object_count':len(objects),
                    'prototype_id':room.metadata.get('layout_prototype_id'),
                    'partition_role':room.metadata.get('joint_room_plan',{}).get('role'),
                    'door_ids':[d.id for d in f.doors if room.id in (d.room_a_id,d.room_b_id)]})
                allowed.add(room.id); furnishing[room.id]=detailed
                if view.get('auto_cutaway'):cutaway.add(room.id)
            furnishing[target]=any(furnishing[r.id] for r in entities)
        row['capture_limits']={
            'outdoor_instance_sampling':view.get('render_profile')=='prototype_capture',
            'shadows_are_not_partition_boundaries':True,
            'cutaway_hides_walls_roofs_and_out_of_scope_geometry':bool(view.get('auto_cutaway')),
            'empty_unfurnished_rooms_are_intentional':True,
            'compiled_counts_are_supporting_evidence_not_visual_quality_certification':True}
        evidence.append(row)
    return {'scene_id':city.id,'allowed_entity_ids':sorted(allowed),'image_evidence':evidence,
            'furnishing_expected_by_entity':furnishing,'single_view_floor_ids':sorted(manual),
            'cutaway_entity_ids':sorted(cutaway)}
