"""Room service evidence on the final compiled inventory, independent of its producer."""
from collections import Counter

from cityg.planning.functional_configuration import paired_counts
from cityg.planning.room_constraints import ROOM_WALL_INSET_M, circulation_check
from cityg.planning.room_envelope import metric_envelope
from cityg.planning.room_metric_frame import restore_metric_object


def _activity(function, objects, allocated):
    counts = Counter(o.category for o in objects)

    def paired(anchor, seat, minimum):
        groups = paired_counts(objects, anchor, seat, facing=True)
        # Allocated counts can span tables. Explicit single-table requests
        # have a separate floor-level seating contract in the requirement ledger.
        return max(groups, default=0) >= minimum and sum(groups) >= allocated.get(seat, 0)

    if function in {'open_office', 'office', 'coworking'}:
        desks = paired_counts(objects, 'desk', 'office_chair', facing=True)
        return sum(n >= 1 for n in desks) >= max(1, allocated.get('desk', 0)) and sum(desks) >= max(
            1, allocated.get('office_chair', 0))
    if function == 'meeting_room':
        return paired('meeting_table', 'meeting_chair', 2)
    if function in {'break_room', 'restaurant'}:
        return paired('dining_table', 'dining_chair', 2) or (
            function == 'break_room' and not {'dining_chair', 'dining_table'}.intersection(allocated)
            and counts['kitchen_counter'] and counts['cabinet'])
    if function == 'reading_room':
        return (paired('dining_table', 'dining_chair', 2)
                or paired('desk', 'office_chair', 1)) and counts['bookcase']
    if function == 'living_room':
        return max(paired_counts(objects, 'sofa', 'coffee_table', facing=False), default=0) >= 1
    if function == 'bedroom':
        return counts['bed'] and (counts['wardrobe'] or counts['bedside_table'])
    if function in {'restroom', 'bathroom'}:
        return counts['toilet'] and counts['sink']
    if function == 'kitchen':
        return counts['kitchen_counter'] and counts['sink']
    if function == 'storage':
        return counts['storage_rack'] + counts['cabinet'] >= 2
    if function == 'reception':
        return ((counts['waiting_bench'] or counts['sofa']) and
                any(counts[key] for key in ('bookcase', 'reception_desk', 'coffee_table', 'dining_table'))
                or paired('reception_desk', 'office_chair', 1))
    if function == 'shop':
        return (counts['display_shelf'] or counts['bookcase'] or counts['dining_table']) and counts['checkout_counter']
    return False


def room_service(building, floor, room, targets):
    envelope = metric_envelope(building, floor, room)
    if envelope['status'] != 'supported':
        return {'ok': False, 'reason': 'unsupported_room_envelope'}
    try:
        physical = [restore_metric_object(o, building, floor, room, envelope)
                    for o in floor.objects if o.room_id == room.id]
    except ValueError as exc:
        return {'ok': False, 'reason': str(exc)}
    counts = Counter(o.category for o in physical)
    allocated = {i['category']: i['min_count'] for i in targets}
    missing = {key: n-counts[key] for key, n in allocated.items() if counts[key] < n}
    if missing:
        return {'ok': False, 'reason': 'allocated_inventory_missing', 'missing': missing}
    if not _activity(room.function, physical, allocated):
        return {'ok': False, 'reason': 'incomplete_functional_group'}
    access = circulation_check(physical, envelope['room'], envelope['floor'],
                               envelope['bounds'].inset(ROOM_WALL_INSET_M))
    return {'ok': bool(access['ok'] and access.get('entrance_verified')),
            'reason': access['reason'] if access.get('door_count', 1) else 'no_verified_entrance',
            'inventory': dict(counts)}


def coverage(report, rows, city):
    accepted = [r for r in rows if r['service']['ok']]
    target = report['options']['max_rooms']
    named = {b.id for b in city.iter_buildings() if b.metadata.get('interior_layout_contract', {}).get('requirements')
             and b.id in report['authorized_levels']}
    represented = named.intersection(r['building_id'] for r in accepted)
    required_buildings = min(len(named), target)
    return {'target_rooms': target, 'verified_rooms': len(accepted),
            'verified_room_ids': [r['room_id'] for r in accepted],
            'prototype_rooms': len(report['rooms']), 'unrepresented_target_buildings': sorted(named - represented),
            'required_target_buildings': required_buildings,
            'target_met': len(accepted) >= target and len(represented) >= required_buildings}
