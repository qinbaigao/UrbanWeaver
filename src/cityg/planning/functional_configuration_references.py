"""Small placement fallbacks for an Agent's activity plan, not density presets."""
from collections import Counter
from copy import deepcopy
from dataclasses import replace

from cityg.planning.functional_configuration import PRIMARY, target_inventory
from cityg.planning.functional_seeds import inventory_programs


def configuration_references(room, objects, plan):
    """Preserve category inventory; never silently strip support dressing.

    Try a near-target primary capacity before dropping to half capacity.
    These are proposals only, subject to normal geometry/transaction guards.
    """
    old = room.metadata.get('room_design', {})
    if old.get('surface_items') or old.get('protected_groups'):
        return
    retained = Counter(o.category for o in objects if o.room_id == room.id)
    lower = deepcopy(plan)
    for b in lower['bundles']: b['recommended'] = max(b['minimum'], 1)
    # Keep the primary purpose and supporting storage/service, defer a new
    # secondary seating area before reducing the primary working capacity.
    focused = deepcopy(plan)
    focused['bundles'] = [b for b in focused['bundles']
                         if b['recipe'] == PRIMARY[room.function] or b['seats_per_group'] == 0]
    intermediate = deepcopy(focused)
    for bundle in intermediate['bundles']:
        if bundle['recipe'] == PRIMARY[room.function]:
            # Keep three quarters of repeated activity groups (8 -> 6, 4 -> 3).
            bundle['recommended'] = max(1, (3 * bundle['recommended'] + 3) // 4)
    compact = deepcopy(focused)
    for b in compact['bundles']:
        b['recommended'] = max(1, (b['recommended']+1)//2)
    seen = set(); variants = []
    for reason, candidate in [('recommended', plan), ('primary_and_support', focused),
                              ('intermediate_primary', intermediate), ('reduced_repetition', compact), ('lower_service_target', lower)]:
        counts = retained | Counter(target_inventory(candidate))
        key = tuple(sorted(counts.items()))
        if key in seen: continue
        seen.add(key)
        inventory = [{'category': k, 'min_count': v} for k, v in counts.items()]
        variants.append((reason, list(inventory_programs(room, inventory))))
    for orientation in range(2):
        for reason, programs in variants:
            if orientation >= len(programs): continue
            program = programs[orientation]
            design = replace(program.design, palette=old.get('palette', program.design.palette),
                             intent='Realize Agent activity targets with bounded metric grouping: '+reason,
                             tabletop=old.get('tabletop', False), wall_art=old.get('wall_art', False))
            yield reason, replace(program, style=old.get('style', program.style), design=design)
