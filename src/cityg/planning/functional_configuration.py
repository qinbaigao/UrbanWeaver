"""Agent-authored service targets, distinct from immutable user requirements.

Recipes describe activities, not area-to-count rules. A recommended capacity is
not certified until furniture is placed and the shared compiled gate passes.
"""
from collections import Counter, defaultdict
from dataclasses import replace
import math


RECIPES = {
    'workstation': {'anchor': 'desk', 'seat': 'office_chair', 'seats': [1], 'purpose': 'individual work'},
    'meeting': {'anchor': 'meeting_table', 'seat': 'meeting_chair', 'seats': [2, 4, 6, 8], 'purpose': 'shared meeting'},
    'dining': {'anchor': 'dining_table', 'seat': 'dining_chair', 'seats': [2, 4, 6], 'purpose': 'seated dining'},
    'lounge': {'anchor': 'sofa', 'companion': 'coffee_table', 'purpose': 'conversation and relaxation'},
    'documents': {'anchor': 'cabinet', 'purpose': 'shared document storage'},
    'reading': {'anchor': 'bookcase', 'purpose': 'reading material storage'},
    'service': {'anchor': 'kitchen_counter', 'purpose': 'preparation or service surface'},
    'washing': {'anchor': 'sink', 'purpose': 'washing'},
    'presentation': {'anchor': 'tv_console', 'purpose': 'presentation equipment support'},
}
PROFILES = {
    'office': ['workstation', 'documents', 'reading', 'meeting'],
    'open_office': ['workstation', 'documents', 'reading', 'meeting'],
    'meeting_room': ['meeting', 'documents', 'presentation'],
    'restaurant': ['dining', 'service', 'washing'],
    'break_room': ['dining', 'service', 'washing', 'documents'],
    'living_room': ['lounge', 'dining', 'reading', 'documents'],
}
PRIMARY = {'office': 'workstation', 'open_office': 'workstation', 'meeting_room': 'meeting',
           'restaurant': 'dining', 'break_room': 'dining', 'living_room': 'lounge'}


def options(value=None):
    config = {'enabled': False, 'max_rooms': 8, 'plan_calls': 2,
              'placement_calls': 2, 'reference_attempts': 4, **(value or {})}
    if set(config) != {'enabled', 'max_rooms', 'plan_calls', 'placement_calls', 'reference_attempts'}:
        raise ValueError('Unknown functional configuration option')
    if type(config['enabled']) is not bool:
        raise ValueError('Functional configuration enabled must be boolean')
    for key, high in [('max_rooms', 40), ('plan_calls', 2), ('placement_calls', 3)]:
        if type(config[key]) is not int or not 1 <= config[key] <= high:
            raise ValueError(f'Invalid functional configuration {key}')
    if type(config['reference_attempts']) is not int or not 0 <= config['reference_attempts'] <= 8:
        raise ValueError('reference_attempts must be 0..8')
    return config


def validate_plan(data, function):
    """No user-authority fields or invented furniture categories are accepted."""
    if not isinstance(data, dict) or set(data) != {'reason', 'bundles', 'intentional_open_space'}:
        raise ValueError('Plan needs reason, bundles and intentional_open_space only')
    for field in ('reason', 'intentional_open_space'):
        if not isinstance(data[field], str) or len(data[field]) > 1600:
            raise ValueError(f'Invalid {field}')
    if not data['reason'].strip() or not isinstance(data['bundles'], list) or not 1 <= len(data['bundles']) <= 6:
        raise ValueError('Explain service capacity and supply 1..6 activity bundles')
    seen = set(); size = 0
    for b in data['bundles']:
        if not isinstance(b, dict) or set(b) != {'recipe', 'minimum', 'recommended', 'maximum', 'seats_per_group', 'reason'}:
            raise ValueError('Bundle needs recipe, minimum, recommended, maximum, seats_per_group, reason')
        key = b['recipe']
        if key not in PROFILES.get(function, ()) or key in seen:
            raise ValueError('Unsupported or duplicate activity recipe')
        seen.add(key); recipe = RECIPES[key]
        if any(type(b[k]) is not int for k in ('minimum', 'recommended', 'maximum', 'seats_per_group')):
            raise ValueError('Capacity counts must be integers')
        if not 0 <= b['minimum'] <= b['recommended'] <= b['maximum'] <= 12 or b['recommended'] < 1:
            raise ValueError('Require 0 <= minimum <= recommended <= maximum <= 12')
        if b['seats_per_group'] not in recipe.get('seats', [0]):
            raise ValueError(f'{key}: seats_per_group must be one of {recipe.get("seats", [0])}; '
                             'non-seating recipes use 0, including lounge (sofa seats are not certified)')
        if not isinstance(b['reason'], str) or not 1 <= len(b['reason'].strip()) <= 600:
            raise ValueError('Each bundle needs a functional reason')
        size += b['recommended'] * (1 + b['seats_per_group'] + int('companion' in recipe))
    if PRIMARY[function] not in seen:
        raise ValueError('Primary room activity cannot be omitted')
    if size > 32 or sum(b['recommended'] for b in data['bundles']) > 16:
        raise ValueError('Recommended configuration exceeds 32 major objects or 16 groups; reduce soft capacity')
    return {**data, 'policy': 'functional_configuration_v1', 'source': 'room_agent',
            'authority': 'advisory_design_target_not_user_requirement',
            'capacity_certified': False}


def target_inventory(plan, tier='recommended'):
    counts = Counter()
    for b in plan['bundles']:
        recipe = RECIPES[b['recipe']]; n = b[tier]
        counts[recipe['anchor']] += n
        if 'seat' in recipe: counts[recipe['seat']] += n * b['seats_per_group']
        if 'companion' in recipe: counts[recipe['companion']] += n
    return dict(counts)


def paired_counts(objects, anchor_category, member_category, *, facing):
    """Assign each member to its nearest eligible anchor in the same group."""
    from cityg.planning.room_groups import _front
    groups = defaultdict(list)
    for obj in objects:
        groups[obj.metadata.get('group_key') or obj.metadata.get('group_id') or ('ungrouped:'+obj.id)].append(obj)
    counts = []
    for group in groups.values():
        anchors = [o for o in group if o.category == anchor_category]
        assigned = Counter()
        for obj in group:
            if obj.category != member_category:
                continue
            eligible = []
            for anchor in anchors:
                dx,dy = anchor.position.x-obj.position.x,anchor.position.y-obj.position.y
                gap_x = max(0,abs(dx)-(anchor.bounds.width+obj.bounds.width)/2)
                gap_y = max(0,abs(dy)-(anchor.bounds.depth+obj.bounds.depth)/2)
                if math.hypot(gap_x,gap_y) > 1.0:
                    continue
                if facing:
                    fx,fy = _front(obj)
                    if fx*dx+fy*dy <= 0:
                        continue
                eligible.append((math.hypot(dx,dy),anchor.id))
            if eligible:
                assigned[min(eligible)[1]] += 1
        counts.extend(assigned[o.id] for o in anchors)
    return counts


def evaluate_configuration(room, objects, plan):
    """Conservative realized group proxy; detached chairs never add capacity.

    Group identity, geometric proximity and seat facing are checked here.
    Door/use-space reachability is checked separately by the compiled gate.
    """
    physical = []
    for obj in objects:
        if obj.room_id == room.id:
            # Pair in the same realized metric frame as the compiler, including
            # rooms projected into a building massing envelope.
            metric = obj.metadata.get('metric_room_placement')
            if metric:
                from cityg.schemas import Point2D
                obj = replace(obj, position=Point2D(*metric['center']),
                              width_m=metric['dimensions_m'][0], depth_m=metric['dimensions_m'][1])
            physical.append(obj)
    rows = []
    for b in plan['bundles']:
        recipe = RECIPES[b['recipe']]; complete = 0; seats = 0
        category = recipe.get('seat', recipe.get('companion'))
        needed = min(recipe['seats']) if 'seat' in recipe else int(category is not None)
        counts = paired_counts(physical, recipe['anchor'], category, facing='seat' in recipe)
        complete = sum(count >= needed for count in counts)
        filled = sum(min(count, b['seats_per_group']) for count in sorted(counts, reverse=True)[:b['recommended']]
                     if count >= needed) if 'seat' in recipe else 0
        if 'seat' in recipe:
            seats = sum(counts)
        rows.append({'recipe': b['recipe'], 'complete_groups': complete,
                     'paired_seats': seats, 'recommended': b['recommended'],
                     'minimum': b['minimum'], 'maximum': b['maximum'],
                     'seats_per_group_target': b['seats_per_group'],
                     'seat_gap': max(0, b['recommended']*b['seats_per_group']-filled),
                     'gap': max(0, b['recommended']-complete)})
    score = sum(min(r['complete_groups'], r['recommended'],
                    r['recommended']-r['seat_gap']/r['seats_per_group_target'] if r['seats_per_group_target'] else float('inf'))
                for r in rows)
    return {'bundles': rows, 'fulfilled_group_targets': score,
            'recommended_groups': sum(r['recommended'] for r in rows),
            'recommendation_met': all(r['gap'] == 0 and r['seat_gap'] == 0 for r in rows),
            'geometry_scope': 'group pairing proxy; compiled access gate still required'}


def propose_configuration(service, building, floor, room, resolver, *, max_calls=2):
    from cityg.agents.context import ProgressiveContext
    from cityg.agents.hierarchy import _ProgressiveProgramAgent
    from cityg.interior_requirements import requirements_for
    from cityg.planning.interiors import ASSET_CATALOG, FloorDetailAgent
    from cityg.planning.room_envelope import metric_envelope, envelope_context
    from cityg.serialization import to_primitive
    env = metric_envelope(building, floor, room)
    if env['status'] != 'supported': raise ValueError('Unsupported metric room envelope')
    recipes = {key: RECIPES[key] for key in PROFILES[room.function]}
    categories = {v for r in recipes.values() for k, v in r.items() if k in ('anchor', 'seat', 'companion')}
    detail = FloorDetailAgent(asset_resolver=resolver); dimensions = {}
    for category in sorted(categories):
        asset = detail._resolve_asset(ASSET_CATALOG[category], room_type=room.function) or ASSET_CATALOG[category]
        dimensions[category] = [asset.width_m, asset.depth_m, asset.height_m]
    metric_context = envelope_context(env)
    metric_context.pop('canonical_area_m2', None)
    floor_rooms = []
    for sibling in floor.rooms:
        sibling_env = metric_envelope(building, floor, sibling)
        floor_rooms.append({'id': sibling.id, 'function': sibling.function,
            'realized_area_m2': sibling_env.get('area_m2'),
            'configuration': sibling.metadata.get('functional_configuration', {}).get('plan')})
    context = {'room_id': room.id, 'function': room.function, 'name': room.name,
               'metric_envelope': metric_context, 'recipes': recipes,
               'actual_asset_dimensions_m': dimensions,
               'user_floor_requirements': requirements_for(building, floor.level),
               'room_requirements': room.metadata.get('spatial_requirement'),
               'existing_design': room.metadata.get('room_design'),
               'existing_inventory': dict(Counter(o.category for o in floor.objects if o.room_id == room.id)),
               'floor_context': floor_rooms,
               'doors': [to_primitive(d) for d in env['floor'].doors if room.id in (d.room_a_id, d.room_b_id)]}
    agent = _ProgressiveProgramAgent(service, max_calls=max_calls); agent.name = 'room_function_configuration'
    import json
    context['output_example'] = {'reason': 'Explain service capacity using actual dimensions',
        'intentional_open_space': 'Preserve entry and circulation',
        'bundles': [{'recipe': PRIMARY[room.function], 'minimum': 1, 'recommended': 1, 'maximum': 1,
                     'seats_per_group': RECIPES[PRIMARY[room.function]].get('seats', [0])[0],
                     'reason': 'Example syntax only; choose counts for the actual room'}]}
    result = agent._run(ProgressiveContext(summary=context, sections=[], max_rounds=0),
        'You are the Room Agent planning service capacity jointly with the supplied floor context. '
        'Return action=final, detail_keys=[], program_json encoding '
        '{reason, intentional_open_space, bundles:[{recipe,minimum,recommended,maximum,seats_per_group,reason}]}. '
        'program_json must encode valid JSON with DOUBLE-QUOTED keys and strings, never a Python dict. '
        'Valid program_json syntax example: '+json.dumps(context['output_example'])+'. '
        'minimum/recommended/maximum are counts of COMPLETE GROUPS, not people, and all are soft design targets. '
        'Use 1..6 distinct offered recipes; always include the primary activity. '
        'Use ONLY metric_envelope.area_m2/width_m/depth_m for this room capacity; '
        'a user floor area is not the area of this room. '
        'State why occupancy and supporting functions suit this actual room and its floor. Small counts in existing layouts or user '
        'presence requirements are not ideal service capacity. Prefer complete repeated workstations or dining '
        'groups, not filler. Allow circulation, door swings, use space, wall openings and deliberate negative space. '
        'A meeting_room normally hosts one shared meeting table; choose seats for that session, not multiple '
        'independent meeting tables merely to occupy floor area. Additional tables need explicit functional justification. '
        'Respect user intent: do not duplicate a dedicated neighboring function without a reason; living rooms '
        'must not be filled as open offices; private offices retain their intended occupants. break_room can '
        'mean a staff pantry or a public cafe: distinguish them using the name and original requirements. '
        'Living rooms '
        'need dining only when appropriate to the brief and household, not automatically. No fabricated user '
        'constraints or architecture-code claims. For recipes without seats use seats_per_group=0. '
        '0<=minimum<=recommended<=maximum<=12; recommended>=1; recommended total <=32 objects and <=16 groups. '
        'Use actual asset sizes to justify realistic capacity; this is a proposal, not a fit certificate. '
        'Keep optional decor outside this plan. Do not change any hard requirement or room geometry.',
        lambda data: validate_plan(data, room.function))
    return result.program, result.attempts
