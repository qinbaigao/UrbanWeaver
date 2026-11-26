"""Bounded semantic reference edits before rotation and metric placement.

Never delete inventory or scale meshes. All outputs still require the ordinary
placement, circulation and compiled inventory gates; no proposal is approval.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import replace

from cityg.planning.interiors import ASSET_CATALOG
from cityg.planning.room_design import RoomDesign

DEFAULT_LIMITS = {'max_group_copies': 0, 'max_zone_moves': 0, 'max_asset_changes': 0}


def move_wall(policy, side):
    sides=('south','east','north','west'); old=policy.get('wall')
    if 'facing' in policy:
        if old not in sides: raise ValueError('Cannot rotate an ambiguous wall/facing contract')
        policy['facing']=sides[(sides.index(policy['facing'])+sides.index(side)-sides.index(old))%4]
    policy['wall']=side


def variation_limits(value=None):
    value = {**DEFAULT_LIMITS, **(value or {})}
    if set(value) != set(DEFAULT_LIMITS) or any(type(v) is not int or not 0 <= v <= 2 for v in value.values()):
        raise ValueError('Reference variation budgets must be integers in 0..2')
    return value


def asset_options(prototype, library):
    """Only library-pinned, same-function and same-role alternatives are offered."""
    result = {c: {a} for c, a in prototype.asset_bindings.items()}
    for key, record in library.rooms.items():
        if record['room_type'] != prototype.room_type:
            continue
        other = library.materialize(key)
        for category in result:
            if (category in other.asset_bindings and
                    other.asset_roles.get(category) == prototype.asset_roles.get(category)):
                result[category].add(other.asset_bindings[category])
    return {k: sorted(v) for k, v in result.items()}


def variation_context(prototype, library, limits):
    return {'budgets': variation_limits(limits),
            'coordinate_frame': 'unrotated_reference; runtime rotates exactly once',
            'zones': list(prototype.design.zones),
            'groups': [{'id': g['id'], 'zone': g['zone'], 'category': g['anchor']['category'],
                        'protected': g['id'] in prototype.design.protected_groups}
                       for g in prototype.design.groups],
            'asset_choices': asset_options(prototype, library)}


def personalize_design(prototype, adjustments, library, limits=None):
    limits = variation_limits(limits)
    if not isinstance(adjustments, dict) or set(adjustments) != {'group_copies', 'zone_positions', 'asset_choices'}:
        raise ValueError('Invalid design adjustment fields')
    for key, limit in [('group_copies', 'max_group_copies'), ('zone_positions', 'max_zone_moves'),
                       ('asset_choices', 'max_asset_changes')]:
        if not isinstance(adjustments[key], list) or len(adjustments[key]) > limits[limit]:
            raise ValueError('Reference adjustment exceeds budget: ' + key)
    data = deepcopy(prototype.design.to_dict())
    data['groups'] = list(data['groups'])
    data['surface_items'] = list(data['surface_items'])
    groups = {g['id']: g for g in data['groups']}
    zones = {z['id']: z for z in data['zones']}
    moved = set()
    for patch in adjustments['zone_positions']:
        if not isinstance(patch, dict) or set(patch) != {'zone_id', 'position'}:
            raise ValueError('Invalid zone position patch')
        zid = patch['zone_id']; position = patch['position']
        if zid not in zones or zid in moved or position not in ('north','south','east','west'):
            raise ValueError('Unknown/repeated zone or invalid position')
        if 'bounds_uv' in zones[zid] or any(g['zone'] == zid and g['id'] in data['protected_groups'] for g in groups.values()):
            raise ValueError('Explicit zone bounds and protected groups cannot move')
        moved.add(zid); zones[zid]['position'] = position
        for group in groups.values():
            if group['zone'] == zid:
                policy = group.get('placement', {})
                if policy.get('mode') == 'wall':
                    move_wall(policy,position)
    for patch in adjustments['group_copies']:
        if not isinstance(patch, dict) or set(patch) != {'source_group_id', 'new_group_id', 'zone_id'}:
            raise ValueError('Invalid group copy')
        source = groups.get(patch['source_group_id']); gid = patch['new_group_id']; zid = patch['zone_id']
        if source is None or gid in groups or zid not in zones or source['id'] in data['protected_groups']:
            raise ValueError('Unknown, protected or duplicate group')
        # Replication is for seating/work capacity, not beds, cupboards or random clutter.
        if source['anchor']['category'] not in {'desk', 'dining_table', 'meeting_table'}:
            raise ValueError('Only work/table functional groups may be replicated')
        if any(rel.get('required') and source['id'] in (rel['subject'],rel['target'])
               for rel in data['group_relations']):
            raise ValueError('A required cross-group relation cannot be replicated independently')
        copy = deepcopy(source); copy['id'] = gid; copy['zone'] = zid
        remap = {}
        for index, item in enumerate([copy['anchor'], *copy['members']]):
            remap[item['id']] = f'{gid}_item{index}'; item['id'] = remap[item['id']]
        if copy.get('placement', {}).get('mode') == 'wall':
            side = zones[zid]['position']
            if side not in ('north','south','east','west'): raise ValueError('Wall group requires a wall zone')
            move_wall(copy['placement'],side)
        data['groups'].append(copy)
        for index, prop in enumerate(prototype.design.surface_items):
            if prop['support_member_id'] in remap:
                data['surface_items'].append({**deepcopy(prop), 'id': f'{gid}_prop{index}',
                                              'support_member_id': remap[prop['support_member_id']]})
        groups[gid] = copy
    counts = Counter(item['category'] for g in data['groups'] for item in [g['anchor'], *g['members']])
    for item in data['furnishing_brief']['items']:
        item['minimum'] = max(item['minimum'], counts[item['category']])
        item['target'] = max(item['target'], counts[item['category']])
    bindings = deepcopy(prototype.asset_bindings); offered = asset_options(prototype, library); changed = set()
    for patch in adjustments['asset_choices']:
        if not isinstance(patch, dict) or set(patch) != {'category', 'asset_id'}:
            raise ValueError('Invalid asset patch')
        category = patch['category']; asset = patch['asset_id']
        if category in changed or asset not in offered.get(category, []):
            raise ValueError('Asset is not a same-function, same-role library alternative')
        changed.add(category); bindings[category] = asset
    return replace(prototype, design=RoomDesign.from_dict(data, ASSET_CATALOG), asset_bindings=bindings)


EMPTY_ADJUSTMENTS = {'group_copies': [], 'zone_positions': [], 'asset_choices': []}
