"""Read-only cross-level preflight. Candidates are NOT accepted layouts.

In particular, floor references currently promise neither arbitrary scaling
nor core relocation, and room references currently declare south entrances.
Report those gaps before an agent tries to materialize the hierarchy.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import math

from cityg.planning.floor_prototypes import box, connection_segment
from cityg.planning.prototypes import fingerprint
from cityg.planning.room_envelope import metric_envelope
from cityg.envelopes import envelope_config
from cityg.schemas import Room


def core_contract(record):
    return {'plate': [record['reference'][k] for k in ('width_m','depth_m')],
            'cores': sorted(({'stack_key': c['stack_key'], 'kind': c['kind'],
                'bounds_m': c['bounds_m'], 'landing_m': c['min_landing_m']}
                for c in record['cores']), key=lambda c:c['stack_key'])}


def can_stack_unchanged(a, b):
    """Exact native core/plate match only, not a structural/egress approval."""
    return core_contract(a) == core_contract(b)


def room_reference_preflight(record, room_library):
    rows=[]
    for space in record['spaces']:
        if space['function']=='corridor':continue
        bounds=box(space['bounds_m']);doors=[]
        for c in record['connections']:
            if space['id'] not in (c['a'],c['b']):continue
            axis,edge,lo,hi=connection_segment(record,c)
            side=('south' if abs(edge-bounds.min_y)<1e-6 else 'north') if axis=='x' else (
                'west' if abs(edge-bounds.min_x)<1e-6 else 'east')
            doors.append({'side':side,'width_m':hi-lo,'kind':c['kind']})
        # Exterior entrances can also belong to a non-circulation space.
        if record['entry']['space']==space['id']:
            doors.append({'side':record['entry']['side'],'width_m':record['entry']['width_m'],'kind':'exterior'})
        hints=space.get('room_reference_hints',[])
        candidates=[];rejected=[]
        keys=list(dict.fromkeys([*hints,*sorted(room_library.rooms)]))
        for key in keys:
            template=room_library.rooms[key]
            if key not in hints and template['room_type']!=space['function']:continue
            reasons=[]
            if template['room_type']!=space['function']:reasons.append('function_mismatch')
            if not room_library.compatible(key,room_type=template['room_type'],width_m=bounds.width,
                    depth_m=bounds.depth,height_m=record['reference']['height_m']):
                reasons.append('outside_metric_applicability')
            if len(doors)!=1:reasons.append('multiple_or_missing_entrances_need_adapter')
            elif doors[0]['side'] not in template['applicability']['door_walls']:
                reasons.append('door_orientation_needs_adapter')
            item={'prototype_id':key,'hinted':key in hints,'reasons':reasons}
            (rejected if reasons else candidates).append(item)
        rows.append({'space_id':space['id'],'function':space['function'],
            'width_m':bounds.width,'depth_m':bounds.depth,'doors':doors,
            'candidates':candidates,'rejected':rejected,
            'status':'requires_metric_placement' if candidates else 'needs_room_adapter_or_new_reference',
            'placement_executed':False})
    return rows


def floor_candidates(building, floor, library, hints=(), variation_limit=.2):
    """Compare references against the *active* massing, not the parcel AABB.

    The variation limit only narrows proposals. No partition, asset, door or
    stair geometry is scaled by this function.
    """
    if type(variation_limit) not in (int,float) or not math.isfinite(variation_limit) or not 0<=variation_limit<=.3:
        raise ValueError('variation_limit must be finite and within [0, .3]')
    # Match the compiler's rectangular-shell branch. Its massing helpers can
    # derive a default silhouette even when no massing transform is compiled.
    if not building.metadata.get('massing_style') and not envelope_config(building):
        actual=building.footprint
    else:
        probe=Room('prototype_envelope_probe','Envelope probe','corridor',building.footprint,floor.height_m)
        envelope=metric_envelope(building,floor,probe)
        if envelope['status']!='supported':
            return {'status':'unsupported_active_outline','reason':envelope.get('reason'),
                    'candidates':[],'rejected':[],'placement_executed':False}
        actual=envelope['bounds']
    functions={building.function}
    if building.function=='mixed_use':functions={'residential','commercial','public_service'}
    candidates=[];rejected=[]
    for key,r in library.floors.items():
        ref=r['reference'];sx,sy=actual.width/ref['width_m'],actual.depth/ref['depth_m']
        reasons=[]
        if r['function'] not in functions:reasons.append('function_mismatch')
        if max(abs(sx-1),abs(sy-1))>variation_limit+1e-8:reasons.append('outside_partition_adjustment_budget')
        if floor.height_m+1e-6<ref['height_m']:reasons.append('reference_height_requires_adaptation')
        item={'prototype_id':key,'hinted':key in hints,'reference_scale_to_plate':[sx,sy],
            'reasons':reasons,'required_next_steps':['repartition_and_validate',
                'bind_building_entrance','preserve_existing_core_stack','solve_room_inventory'],
            'score':round(abs(math.log(sx))+abs(math.log(sy))+(0 if key in hints else .2),6)}
        (rejected if reasons else candidates).append(item)
    candidates.sort(key=lambda r:(r['score'],r['prototype_id']))
    return {'status':'candidate_only' if candidates else 'needs_floor_adapter_or_new_reference',
        'frame':'active_building_local_outline','actual_plate_m':[actual.width,actual.depth],
        'height_m':floor.height_m,'variation_limit':variation_limit,'candidates':candidates,
        'rejected':rejected,'placement_executed':False}


def integration_preflight(city, floor_library, *, max_buildings=3, max_floors=2, variation_limit=.2):
    """Small, deterministic audit; input city and all library records stay intact."""
    if type(max_buildings) is not int or not 1<=max_buildings<=10:raise ValueError('Select 1..10 buildings')
    if type(max_floors) is not int or not 1<=max_floors<=3:raise ValueError('Select 1..3 floors per building')
    hints=city.metadata.get('urban_layout_prototype',{}).get('floor_reference_hints',[])
    # Largest plates are the most useful first adaptation fixtures. Report this
    # bias: the result is not an unbiased city-wide compatibility benchmark.
    buildings=sorted(city.iter_buildings(),key=lambda b:(-b.footprint.area,b.id))[:max_buildings]
    rows=[]
    for building in buildings:
        floors=sorted(building.floors,key=lambda f:f.level)
        count=min(max_floors,len(floors))
        indices=sorted({round(i*(len(floors)-1)/max(1,count-1)) for i in range(count)})
        for index in indices:
            floor=floors[index]
            rows.append({'building_id':building.id,'floor_id':floor.id,'level':floor.level,
                'building_function':building.function,**floor_candidates(building,floor,floor_library,hints,variation_limit)})
    room_rows={key:room_reference_preflight(r,floor_library.room_library) for key,r in floor_library.floors.items()}
    stacks=defaultdict(list)
    for key,r in floor_library.floors.items():stacks[fingerprint(core_contract(r))].append(key)
    return {'schema_version':1,'stage':'read_only_cross_level_preflight','production_enabled':False,
        'city_id':city.id,'urban_prototype':deepcopy(city.metadata.get('urban_layout_prototype',{})),
        'sampling':'largest_canonical_plates; lowest/highest selected levels; not a benchmark',
        'scene_modified':False,'layout_applied':False,'llm_used':False,'vlm_used':False,
        'floor_candidates':rows,'floor_to_room':room_rows,'native_stack_groups':list(stacks.values()),
        'summary':{'sampled_buildings':len(buildings),'sampled_floors':len(rows),
            'floors_with_candidates':sum(bool(r['candidates']) for r in rows),
            'floor_status_counts':dict(Counter(r['status'] for r in rows)),
            'floor_rejection_reasons':dict(Counter(reason for row in rows
                for candidate in row['rejected'] for reason in candidate['reasons'])),
            'room_spaces_audited':sum(len(r) for r in room_rows.values()),
            'room_spaces_with_prefilter_candidates':sum(bool(s['candidates']) for r in room_rows.values() for s in r),
            'room_rejection_reasons':dict(Counter(reason for rooms in room_rows.values() for s in rooms
                for candidate in s['rejected'] for reason in candidate['reasons']))},
        'limitations':['No floor plan or furniture was instantiated by this check.',
            'Candidate matching is not approval, collision checking, egress compliance, or core alignment to an existing building.',
            'Arbitrary outline adaptation and multi-door/rotated room adapters still require implementation and compiled verification.']}
