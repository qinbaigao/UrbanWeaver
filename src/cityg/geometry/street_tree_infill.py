"""Modest tree-only infill along existing streets; no new beds or parcel gardens."""
from collections import Counter
from dataclasses import replace
import math
import random

from cityg.geometry.dense_greenery import obstacle_index, PLANTS
from cityg.geometry.geography import primitive_footprint
from cityg.geometry.model import Vec3
from cityg.geometry.urban_greenbelts import PlantBank, SpacingGrid
from cityg.paths import PlanarPath2D
from cityg.polygons import geos, parcel_shape, road_shape

KEY = 'street_tree_infill'
VERSION = 'roadside_canopy_v1'
# Short runs of related trees, with secondary species; not a random forest.
PALETTES = (
    ('island', 'island', 'small_tree', 'jacaranda'),
    ('small_tree', 'jacaranda', 'island', 'small_tree'),
    ('island', 'small_tree', 'pine', 'island'),
    ('small_tree', 'island', 'medium_fir', 'fir'),
)


def compile_street_tree_infill(compiler, city, scene):
    plan = city.metadata.get(KEY)
    if not plan or not plan.get('enabled', True):
        return {'status': 'not_requested'}
    density = float(plan.get('density', 1))
    if plan.get('version', VERSION) != VERSION or not math.isfinite(density) or not .25 <= density <= 2:
        raise ValueError('Unknown street-tree infill version or density outside [0.25, 2]')
    base = [p for p in scene.primitives if p.metadata.get(KEY) != VERSION]
    previous = [p for p in scene.primitives if p.metadata.get(KEY) == VERSION]
    s = geos()
    construction = {r['parcel_id'] for r in city.metadata.get('construction_sites', {}).get('sites', [])}
    parcels = [p for p in city.iter_parcels() if p.buildings and p.id not in construction]
    shapes = [parcel_shape(p) for p in parcels]
    parcel_index = s.STRtree(shapes)
    # Existing soil beds may receive a tree, but neither beds nor their plants
    # are changed. Trunk clearance is checked separately from canopy overhang.
    obstacles = obstacle_index(city, [p for p in base if p.semantic_class != 'parcel_planting_bed'],
                               include_vegetation=False)
    roads = city.road_network.segments
    road_index = s.STRtree([road_shape(r, 10) for r in roads])
    crowns, stems, low = SpacingGrid(), SpacingGrid(), SpacingGrid()
    baseline = 0
    for p in base:
        category = p.metadata.get('asset_category')
        if category not in PLANTS:
            continue
        radius = max(p.size.x, p.size.y) / 2
        x, y = p.center.x, p.center.y
        if category in {'street_tree', 'park_tree'}:
            crowns.add(x, y, radius)
            stems.add(x, y, 2.8)
            point = s.Point(x, y)
            if (any(shapes[i].covers(point) for i in parcel_index.query(point))
                    and any(road_index.geometries[i].covers(point) for i in road_index.query(point))):
                baseline += 1
        else:
            low.add(x, y, min(radius, 2))
    # Around 18% extra roadside trees at the default setting, not a doubling of
    # all city vegetation. Clearance may result in fewer feasible additions.
    target = min(850, max(40, round(baseline * .18 * density)))
    degrees = Counter(j for r in roads for j in (r.start_junction_id, r.end_junction_id))
    junctions = []
    for r in roads:
        for jid, point in ((r.start_junction_id, r.centerline[0]), (r.end_junction_id, r.centerline[-1])):
            if degrees[jid] >= 3:
                junctions.append(s.Point(point.x, point.y).buffer(max(11, r.width_m/2+r.sidewalk_width_m+4)))
    junction_index = s.STRtree(junctions)
    free_cache = {}
    bank = PlantBank(compiler)
    additions = []
    per_road = Counter()

    def road_candidates(road):
        path = PlanarPath2D(road.centerline)
        seed = compiler._parcel_seed(road.id, VERSION, str(plan.get('seed', 20261017)))
        rng = random.Random(seed)
        palette = PALETTES[seed % len(PALETTES)]
        outer = road.width_m/2 + road.sidewalk_width_m
        step = 10.5 if road.road_class in {'arterial', 'collector'} else 9.5
        quota = max(2, math.ceil(path.length/40)) * 2
        count = 0
        for n in range(max(0, math.ceil((path.length-24)/step))):
            station = 12 + n*step + rng.uniform(-1.2, 1.2)
            if station > path.length-12:
                continue
            for side in (-1, 1):
                if count >= quota:
                    return
                tag = palette[(int(station/35) + (1 if side > 0 else 0)) % len(palette)]
                height = rng.uniform(6.5, 9.5) if tag not in {'pine', 'fir'} else rng.uniform(5.5, 7.5)
                prefix = f'{road.id}_tree_infill_{n:03d}_{"left" if side > 0 else "right"}'
                template = bank.make(city.id, prefix, 0, 0, height, tag, True, rng, {})
                if template is None:
                    continue
                radius = max(template.size.x, template.size.y)/2
                accepted = None
                for inset in (radius+1, radius+2.2, radius+3.8):
                    if inset > 9:
                        continue
                    point = path.point(station, side*(outer+inset))
                    x, y = point.x, point.y
                    if not stems.clear(x, y, 2.8) or not crowns.clear(x, y, radius, .75):
                        continue
                    if not low.clear(x, y, .4, .7):
                        continue
                    root = s.Point(x, y)
                    for i in parcel_index.query(root):
                        if not shapes[i].covers(root):
                            continue
                        parcel = parcels[i]
                        if i not in free_cache:
                            hits = obstacles.query(shapes[i])
                            free_cache[i] = shapes[i].buffer(-.5).difference(s.union_all(obstacles.geometries.take(hits)))
                            s.prepare(free_cache[i])
                        item = replace(template, owner_id=parcel.id, center=Vec3(x, y, template.center.z),
                            semantic_class='street_tree_asset', metadata={**template.metadata,
                                KEY: VERSION, 'planting_system': VERSION, 'street_asset': 'tree',
                                'placement_domain': 'parcel_roadside',
                                'road_id': road.id, 'parcel_id': parcel.id, 'road_station_m': station,
                                'road_side': 'left' if side > 0 else 'right', 'roadside_inset_m': inset})
                        footprint = primitive_footprint(item)
                        if not free_cache[i].covers(footprint):
                            continue
                        if any(junction_index.geometries[j].intersects(footprint)
                               for j in junction_index.query(footprint)):
                            continue
                        accepted = item
                        break
                    if accepted is not None:
                        break
                if accepted is not None:
                    crowns.add(accepted.center.x, accepted.center.y, radius)
                    stems.add(accepted.center.x, accepted.center.y, 2.8)
                    count += 1
                    yield accepted

    # Round robin prevents the early streets in the input from using the whole
    # city budget. Both road sides are considered, including curved segments.
    active = [(r.id, iter(road_candidates(r))) for r in sorted(roads, key=lambda r:r.id)]
    while active and len(additions) < target:
        remaining = []
        for road_id, candidates in active:
            if len(additions) >= target:
                break
            item = next(candidates, None)
            if item is not None:
                additions.append(item)
                per_road[road_id] += 1
                remaining.append((road_id, candidates))
        active = remaining
    retained = [p for p in previous if p.metadata.get('road_id') not in per_road]
    scene.primitives = base + retained + additions
    report = {'version': VERSION, 'density': density, 'existing_roadside_trees': baseline,
        'target_new_trees': target, 'new_asset_instances': len(additions),
        'new_trees_by_road': dict(per_road), 'changed_roads': len(per_road),
        'asset_counts': dict(Counter(p.metadata['asset_id'] for p in additions)),
        'side_counts': dict(Counter(p.metadata['road_side'] for p in additions)),
        'retained_previous_instances': len(retained), 'existing_primitives_modified': 0,
        'new_soil_beds': 0, 'new_low_plants': 0,
        'scope': 'tree-only infill within 9 m of street/sidewalk outer edges on occupied parcels; no park/hill/garden changes',
        'simulation_note': 'visual tree meshes only; no new trunk colliders or traffic-code certification'}
    scene.metadata[KEY] = report
    return report
