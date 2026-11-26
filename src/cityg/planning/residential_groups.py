"""Curated, exterior-only parcel replacement with apartment and townhouse rows.

This is an explicit scene edit, not a new default for generated cities. Exact
parcel/road/water reservations decide feasibility; all new entities get fresh IDs.
"""
from collections import Counter
from copy import deepcopy
import math
import random
import re

from cityg.planning.baseline import BaselineCityPlanner
from cityg.polygons import box_shape, geos, parcel_shape, river_shape, road_shape
from cityg.schemas import Bounds2D, CitySpec

KEY = 'residential_groups_v1'


class ExactFootprintPlanner(BaselineCityPlanner):
    def _layout_footprint(self, spec, rng, index, function, parcel_bounds, entrance_side):
        return parcel_bounds


def group_layout(parcel, kind):
    """Three separated slabs or two genuinely attached four-unit rows."""
    b = parcel.bounds
    if min(b.width, b.depth) < 85:
        return []
    if kind == 'apartments':
        w, d = min(76., b.width - 36), 17.
        ys = [b.min_y + b.depth * t for t in (.21, .5, .79)]
        return [(Bounds2D(b.center.x-w/2, y-d/2, b.center.x+w/2, y+d/2), row, 0)
                for row, y in enumerate(ys)]
    if kind != 'townhouses':
        raise ValueError('Unknown residential group: ' + kind)
    w, d = 10.5, 15.
    return [(Bounds2D(b.center.x-2*w+unit*w, y-d/2,
                     b.center.x-2*w+(unit+1)*w, y+d/2), row, unit)
            for row, y in enumerate([b.min_y+b.depth*.31, b.min_y+b.depth*.69])
            for unit in range(4)]


def select_parcels(city, apartment_count=6, townhouse_count=4):
    s = geos()
    reserved = s.union_all([road_shape(r, 2.) for r in city.road_network.segments] +
                          [river_shape(r, 'reserve') for r in city.rivers])
    # Conservatively exclude parcels named anywhere in custom transit/site data.
    special = repr(city.metadata.get('metro_entrances', {})) + repr(city.metadata.get('construction_sites', {}))
    candidates = [p for p in city.iter_parcels() if len(p.buildings) == 1
                  and p.buildings[0].function == 'residential'
                  and 2 <= len(p.buildings[0].floors) <= 9
                  and not p.buildings[0].metadata.get('height_contract', {}).get('landmark')
                  and p.id not in special]
    chosen = []
    for kind, count in [('apartments', apartment_count), ('townhouses', townhouse_count)]:
        feasible = []
        for p in candidates:
            if any(p.id == other.id for other, _ in chosen):
                continue
            layout = group_layout(p, kind)
            if not layout:
                continue
            shape = parcel_shape(p).buffer(-5).difference(reserved)
            if all(shape.covers(box_shape(b).buffer(2)) for b, _, _ in layout):
                feasible.append(p)
        for _ in range(count):
            if not feasible:
                raise ValueError(f'Not enough safe parcels for {kind}; no partial edit committed')
            def score(p):
                c = p.bounds.center
                spread = min((math.dist((c.x, c.y), (q.bounds.center.x, q.bounds.center.y))
                              for q, _ in chosen), default=400.)
                edge = math.dist((c.x, c.y), (city.bounds.center.x, city.bounds.center.y))
                return spread + (.25*edge if kind == 'townhouses' else .008*p.bounds.area)
            selected = max(sorted(feasible, key=lambda p:p.id), key=score)
            chosen.append((selected, kind)); feasible.remove(selected)
    return [(p.id, kind) for p, kind in chosen]


def replace_residential_groups(source, apartment_count=6, townhouse_count=4, seed=20261017):
    scope = source.metadata.get('interior_scope', {})
    if scope.get('policy') != 'prototype_exterior_only' or any(scope.get('building_levels', {}).values()):
        raise ValueError('Residential grouping requires an exterior-only scene')
    if source.metadata.get(KEY):
        raise ValueError('Already grouped; start from the retained pre-edit source')
    selected = select_parcels(source, apartment_count, townhouse_count)
    city = deepcopy(source)
    parcels = {p.id:p for p in city.iter_parcels()}
    # Include retired identities and site replacement IDs; never recycle a label.
    used = set(re.findall(r'building_(\d+)', repr(city.metadata)))
    used.update(b.id.removeprefix('building_') for b in city.iter_buildings() if re.fullmatch(r'building_\d+', b.id))
    used.update(re.findall(r'building_(\d+)', repr(city.world_program)))
    index = max(map(int, used), default=-1)+1
    planner = ExactFootprintPlanner(); records = []
    for group_index, (pid, kind) in enumerate(selected):
        parcel = parcels[pid]; old_ids = [b.id for b in parcel.buildings]
        layout = group_layout(parcel, kind); buildings = []
        style = ['residential_balcony_v1', 'residential_brick_v1', 'residential_sage_v1'][group_index % 3]
        palette = ['pearl_gray', 'cool_gray', 'muted_sage', 'slate_blue'][group_index % 4]
        for footprint, row, unit in layout:
            floors = (5+group_index % 2+(row == 1)) if kind == 'apartments' else 2+group_index % 2
            spec = CitySpec(building_count=1, min_floors=floors, max_floors=floors, rooms_per_floor=2, seed=seed)
            b = planner._make_building(spec, random.Random(f'{seed}:{pid}:{row}:{unit}'), index,
                                      'residential', footprint, ('south',), pid)
            b.metadata = {k:v for k,v in b.metadata.items() if k in {'entrance_side', 'height_contract', 'highrise'}}
            b.name = f'{"Apartment" if kind == "apartments" else "Townhouse"} {pid} · {row+1}-{unit+1}'
            b.metadata.update(prototype_id='residential_slab', orientation_deg=0.,
                facade_style_override=style, facade_colorway=palette,
                roof_finish=['concrete_gray', 'graphite', 'cool_membrane'][group_index % 3],
                roof_texture='fine_concrete' if kind == 'apartments' else 'original',
                residential_group={'version':KEY, 'kind':kind, 'parcel_id':pid, 'row':row, 'unit':unit,
                    'party_sides':(['west'] if unit>0 else [])+(['east'] if unit<3 else []) if kind=='townhouses' else []},
                roof_program={'profile':'solar' if kind == 'apartments' and group_index % 2 else 'quiet'}, exterior_only=True)
            buildings.append(b); index += 1
        for b in buildings:
            group = b.metadata['residential_group']
            group['neighbors'] = {side:next(other.id for other in buildings
                if other.metadata['residential_group']['row'] == group['row'] and
                other.metadata['residential_group']['unit'] == group['unit']+delta)
                for side, delta in [('west', -1), ('east', 1)] if side in group['party_sides']}
        parcel.buildings = buildings
        records.append({'parcel_id':pid, 'kind':kind, 'removed_buildings':old_ids,
                        'building_ids':[b.id for b in buildings], 'floors':[len(b.floors) for b in buildings],
                        'facade_style':style, 'palette':palette})
    values = [len(b.floors) for b in city.iter_buildings()]; hist = Counter(values)
    city.metadata.setdefault('height_plan', {}).update(realized_min_floors=min(values),
        realized_max_floors=max(values), realized_mean_floors=sum(values)/len(values),
        realized_floor_histogram={str(k):v for k,v in sorted(hist.items())})
    report = {'version':KEY, 'seed':seed, 'parcels':records, 'before_buildings':sum(1 for _ in source.iter_buildings()),
              'after_buildings':len(values), 'interiors_generated':False}
    city.metadata[KEY] = report
    from cityg.planning.group_access import plan_group_access
    plan_group_access(city)
    return city, report
