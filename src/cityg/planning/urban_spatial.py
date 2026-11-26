"""Bounded metric realization of Agent-authored spatial requirements."""
from dataclasses import replace
import random

from cityg.schemas import Bounds2D
from cityg.urban_requirements import matches, measure, rank


def assign_sites(spec, sites, allocation, network, rivers):
    if not spec.urban_requirements:
        return list(range(len(sites))), {'status': 'not_requested'}
    from cityg.polygons import river_shape, road_shape
    slots = [z for z, count in allocation for _ in range(count)]
    water = [river_shape(r) for r in rivers]
    roads = [road_shape(r) for r in network.segments]
    bounds = Bounds2D(0, 0, spec.width_m, spec.depth_m)
    def score(order):
        entities = [{'id': f'building_{i:03d}', 'zone': z.name, 'function': z.function,
            'center': (sites[j].bounds.center.x, sites[j].bounds.center.y),
            'area': sites[j].bounds.inset(spec.parcel_setback_m).area}
            for i, (z, j) in enumerate(zip(slots, order))]
        return measure(spec.urban_requirements, entities, bounds, river_shapes=water, road_shapes=roads)
    order = list(range(len(sites))); before = score(order); best = rank(before)
    budget = 2048; evaluations = 1; changes = []
    # Swaps preserve functional counts and assign each parcel exactly once.
    pairs = [(i,j) for i in range(len(order)) for j in range(i+1,len(order))]
    random.Random(spec.seed).shuffle(pairs)
    for sweep in range(4):
        changed = False
        for i, j in pairs:
            if evaluations >= budget or best == (0, 0, 0): break
            candidate = list(order); candidate[i],candidate[j] = candidate[j],candidate[i]
            result = score(candidate); evaluations += 1; candidate_rank = rank(result)
            if candidate_rank < best:
                order, best, changed = candidate, candidate_rank, True
                changes.append({'slots': [i,j], 'rank': list(best)})
        if not changed or evaluations >= budget: break
    return order, {'status': 'bounded_assignment', 'before': before, 'after': score(order),
        'evaluations': evaluations, 'budget': budget, 'swaps': changes,
        'measurement_scope': 'parcel centres and buildable area; final building geometry rechecked'}


def fit_building(spec, index, function, zone, parcel, entrance_side, original):
    """Fit an unfurnished building BEFORE entrances, floors and cores exist."""
    entity = {'id': f'building_{index:03d}', 'function': function, 'zone': zone}
    area_rules = [r for r in spec.urban_requirements if r['relation'] == 'min_footprint_area'
                  and matches(entity, r['subject'])]
    if not area_rules: return original
    from cityg.urban_requirements import UrbanPlanningConflict
    inner = parcel.inset(spec.parcel_setback_m)
    hard = max([r['threshold'] for r in area_rules if r['strength']=='hard']+[0])
    desired = max(r['threshold'] for r in area_rules)
    if hard > inner.area + 1e-6:
        raise UrbanPlanningConflict(f"{entity['id']}: footprint capacity {inner.area:.2f} < required {hard}",
            {'building_id':entity['id'],'required_area_m2':hard,'available_area_m2':inner.area,
             'action':'reassign a larger parcel or explicitly revise requirements'})
    desired = min(inner.area, max(original.area, desired))
    if original.area >= desired-1e-6: return original
    # Preserve the selected street edge; rebuild all children from this plate.
    w = min(inner.width, max(6., desired**.5)); d = desired/w
    if d > inner.depth: d=inner.depth; w=desired/d
    x=inner.center.x-w/2; y=inner.center.y-d/2
    if entrance_side=='west':x=inner.min_x
    if entrance_side=='east':x=inner.max_x-w
    if entrance_side=='south':y=inner.min_y
    if entrance_side=='north':y=inner.max_y-d
    return Bounds2D(x,y,x+w,y+d)
