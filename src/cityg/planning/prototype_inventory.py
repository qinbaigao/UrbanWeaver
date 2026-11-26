"""Rank feasible-reference candidates against allocated primary furniture needs.

This is a preference, not an acceptance certificate. Missing functions still
go through bounded completion and the original floor-level requirement gate.
"""
from collections import Counter
from functools import lru_cache

from cityg.interior_requirements import inventory_for


def _inventory(library, key):
    design = library.materialize(key).design
    return Counter(item['category'] for group in design.groups for item in [group['anchor'], *group['members']])


def rooms_by_unmet_inventory(candidates, library, room_budget):
    """Spend scarce slots on quoted floor functions first. Recount after each room transaction."""
    if len(candidates) <= room_budget or not any(
            inventory_for(b, f.level, r.function) for b, f, r, _ in candidates):
        yield from candidates
        return
    pending = list(candidates)

    @lru_cache(maxsize=None)
    def reference_counts(key):
        return _inventory(library, key)

    while pending:
        needs = {}

        def score(row):
            building, floor, room, references = row
            key = (building.id, floor.id, room.function)
            if key not in needs:
                targets = inventory_for(building, floor.level, room.function)
                ids = {r.id for r in floor.rooms if r.function == room.function}
                placed = Counter(o.category for o in floor.objects if o.room_id in ids)
                needs[key] = {i['category']: i['min_count'] - placed[i['category']] for i in targets
                              if i['min_count'] > placed[i['category']]}
            missing = needs[key]
            if not missing:
                return 0
            return max(sum(min(counts[cat], n) / n for cat, n in missing.items()) / len(missing)
                       for counts in (reference_counts(c['prototype_id']) for c in references))

        # max retains agent/balanced order for equal scores.
        index = max(range(len(pending)), key=lambda idx: score(pending[idx]))
        yield pending.pop(index)



def prioritize_inventory(candidates, library, targets):
    """Stable within equal deficits, preserving agent preferences and diversity.

    Targets must already be allocated to this room; copying a floor target to
    every room would over-furnish the scene. Keep incomplete references as
    fallbacks when no complete reference is geometrically realizable.
    """
    if not targets:
        return list(candidates)
    scores = {}
    for candidate in candidates:
        key = candidate['prototype_id']
        if key not in scores:
            counts = _inventory(library, key)
            scores[key] = sum(max(0, target['min_count'] - counts[target['category']])
                              for target in targets)
    return sorted(candidates, key=lambda candidate: scores[candidate['prototype_id']])
