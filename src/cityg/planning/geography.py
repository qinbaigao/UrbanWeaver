"""Land-first deterministic realization of a high-level waterfront intent."""
from __future__ import annotations

from dataclasses import dataclass, replace, field
import math

from cityg.paths import PlanarPath2D, sample_cubic_bezier
from cityg.polygons import (box_shape, geos, inscribed_bounds, line_intervals,
                            polygon_parts, river_shape, road_shape, shape_record)
from cityg.schemas import Bounds2D, Bridge, Junction, Point2D, River, RoadNetwork


@dataclass
class GeographyLayout:
    network: RoadNetwork
    rivers: list
    bridges: list
    plots: list
    sites: list
    landscape_sites: list
    recovery: dict = field(default_factory=dict)


def _geographic_warp(spec):
    """Legacy polygonal layouts only; adaptive streets never use this field."""
    amplitude = min(spec.width_m * .045, 18.0) * spec.layout_irregularity
    def warp(p):
        return Point2D(p.x + amplitude * math.sin(math.pi*p.y/spec.depth_m)
                       * math.sin(math.pi*p.x/spec.width_m), p.y)
    return warp


def _warp_network(spec, network, warp=None):
    warp = warp or _geographic_warp(spec)
    roads = []
    for road in network.segments:
        path = PlanarPath2D(road.centerline)
        # Preserve every original vertex and every semantic road endpoint.
        stations = sorted(set(path.stations) | {path.length*i/max(1, math.ceil(path.length/3))
                            for i in range(math.ceil(path.length/3)+1)})
        roads.append(replace(road, centerline=tuple(warp(path.point(s)) for s in stations)))
    return RoadNetwork([Junction(j.id, warp(j.position)) for j in network.junctions], roads), warp


def plan_geography(spec, original_network):
    """Bounded topology/parcel recovery; never modify the requested CitySpec."""
    from cityg.urban_requirements import UrbanPlanningConflict
    trials = []; dry_land_failure = False
    variants = [(False, False), (False, True)]
    if spec.road_pattern == 'landscape_adaptive': variants += [(True, True)]
    for compact, capacity_split in variants:
        # Splitting parcels cannot help when the road skeleton itself did not fit.
        if dry_land_failure and not compact and capacity_split:
            continue
        try:
            result = _plan_geography(spec, original_network, compact=compact, capacity_split=capacity_split)
            trials.append({'compact_streets':compact,'capacity_split':capacity_split,'status':'accepted'})
            result.recovery = {'attempts':trials,'status':'unchanged' if len(trials)==1 else 'recovered',
                'spec_changed':False,'river_parameters_changed':False,'building_count_changed':False}
            return result
        except ValueError as exc:
            trials.append({'compact_streets':compact,'capacity_split':capacity_split,'status':'rejected','error':str(exc)})
            if 'Insufficient dry land' in str(exc) and not compact:
                dry_land_failure = True
    raise UrbanPlanningConflict('No feasible geography found within bounded topology/parcel candidates',
        {'attempts':trials,'not_a_proof_of_infeasibility':True,'spec_changed':False})


def _plan_geography(spec, original_network, *, compact=False, capacity_split=False):
    from cityg.planning.baseline import _ParcelSite
    s = geos()
    warp = _geographic_warp(spec)
    city_bounds = Bounds2D(0, 0, spec.width_m, spec.depth_m)
    extent = box_shape(city_bounds)
    rivers = []
    adaptive = spec.road_pattern == 'landscape_adaptive'
    if adaptive:
        from cityg.planning.adaptive_streets import adaptive_streets
        network, rivers = adaptive_streets(spec, original_network, compact=compact)
    elif spec.river_mode != "none":
        ymin = min(j.position.y for j in original_network.junctions)
        xs = sorted({j.position.x for j in original_network.junctions if abs(j.position.y-ymin) < 1e-6})
        a, b = min(zip(xs, xs[1:]), key=lambda ab: abs(sum(ab)/2-spec.width_m/2))
        center = (a+b)/2
        bend = min((b-a)*.19, spec.width_m*.055)
        curve = sample_cubic_bezier(Point2D(center-bend*.3, 0),
            Point2D(center+bend, spec.depth_m/3), Point2D(center-bend, spec.depth_m*2/3),
            Point2D(center+bend*.3, spec.depth_m), max_step_m=2.5)
        rivers.append(River("river_000", "Meandering river", tuple(warp(p) for p in curve),
                            spec.river_width_m, spec.river_bank_width_m, spec.river_setback_m))
    # Legacy layouts retain their old field; the adaptive topology above has
    # independent river and street geometry. Never warp allocated buildings.
    if not adaptive:
        network, _ = _warp_network(spec, original_network, warp)
    bridges = []
    for road in network.segments:
        path = PlanarPath2D(road.centerline)
        for river in rivers:
            # Cover banks and the first 3 m of bank-side footway as well as water.
            span_shape = river_shape(river, "banks").buffer(3.0)
            for a, b in line_intervals(path, span_shape):
                if not line_intervals(path.slice(a, b), river_shape(river)):
                    continue
                if a < road.width_m or path.length-b < road.width_m:
                    raise ValueError(f"River crossing too close to a road junction: {road.id}; enlarge the site or narrow the river")
                bridges.append(Bridge(f"bridge_{len(bridges):03d}", road.id, river.id, a, b))
    reserved = s.union_all([road_shape(r, .8) for r in network.segments]
                          + [river_shape(r, "reserve") for r in rivers])
    free = extent.difference(reserved)
    candidates = polygon_parts(free)
    # Enough independent plots for the requested building count; subdivisions
    # operate on actual polygons, never their bounding boxes.
    minimum = max(18.0, spec.parcel_setback_m*2 + 12)
    candidates.sort(key=lambda p: (-p.area, p.centroid.x, p.centroid.y))
    attempts = 0
    while len([p for p in candidates if p.area > minimum**2]) < spec.building_count and attempts < spec.building_count*3:
        attempts += 1
        largest = max(candidates, key=lambda p: p.area)
        x0, y0, x1, y1 = largest.bounds
        if x1-x0 > y1-y0:
            cutters = (s.box(x0-1, y0-1, (x0+x1)/2, y1+1), s.box((x0+x1)/2, y0-1, x1+1, y1+1))
        else:
            cutters = (s.box(x0-1, y0-1, x1+1, (y0+y1)/2), s.box(x0-1, (y0+y1)/2, x1+1, y1+1))
        children = [piece for cutter in cutters for piece in polygon_parts(largest.intersection(cutter))]
        if len(children) < 2:
            break
        candidates.remove(largest)
        candidates.extend(children)
    candidates.sort(key=lambda p: (-p.area, p.centroid.x, p.centroid.y))
    plots, sites, landscape = [], [], []
    roads_shape = s.MultiLineString([[(p.x, p.y) for p in r.centerline] for r in network.segments])
    def frontage_score(bounds):
        points = [(bounds.min_x, bounds.center.y), (bounds.max_x, bounds.center.y),
                  (bounds.center.x, bounds.min_y), (bounds.center.x, bounds.max_y)]
        distance = min(roads_shape.distance(s.Point(x, y)) for x, y in points)
        # Reserve several metres for the setback and changes in tangent across
        # the building frontage. Keep the maximum-area feasible rectangle.
        return (distance <= max(8., 20.-spec.parcel_setback_m), bounds.area, -distance)
    for polygon in candidates:
        bounds = inscribed_bounds(polygon.buffer(-.4), min_size=minimum,
            score=frontage_score if spec.road_pattern == 'landscape_adaptive' else None
        ) if len(sites) < spec.building_count else None
        if bounds is None:
            landscape.append(polygon)
            continue
        index = len(sites)
        # Choose a frontage on the same dry parcel rather than orienting toward
        # whichever road lies across the river. Full access is checked downstream.
        midpoints = {"west": Point2D(bounds.min_x, bounds.center.y), "east": Point2D(bounds.max_x, bounds.center.y),
                     "south": Point2D(bounds.center.x, bounds.min_y), "north": Point2D(bounds.center.x, bounds.max_y)}
        paths = [PlanarPath2D(r.centerline) for r in network.segments]
        side = min(midpoints, key=lambda k: min(p.project(midpoints[k]).separation for p in paths))
        sites.append(_ParcelSite(bounds, f"polygon_block_{index:03d}", 1, 0, (side,)))
        plots.append(polygon)
    split_trials = 0
    while capacity_split and len(sites) < spec.building_count and split_trials < 64:
        accepted = False
        for parent_index in sorted(range(len(plots)), key=lambda i:-plots[i].area):
            polygon = plots[parent_index]; x0,y0,x1,y1=polygon.bounds
            for axis in ('x','y'):
                if split_trials >= 64: break
                split_trials += 1
                if axis=='x':
                    cutters=[s.box(x0-1,y0-1,(x0+x1)/2,y1+1),s.box((x0+x1)/2,y0-1,x1+1,y1+1)]
                else:
                    cutters=[s.box(x0-1,y0-1,x1+1,(y0+y1)/2),s.box(x0-1,(y0+y1)/2,x1+1,y1+1)]
                children=[p for cutter in cutters for p in polygon_parts(polygon.intersection(cutter))]
                if len(children)!=2:continue
                fitted=[inscribed_bounds(p.buffer(-.4),min_size=minimum,score=frontage_score) for p in children]
                if any(b is None or not frontage_score(b)[0] for b in fitted):continue
                new_sites=[]
                for b in fitted:
                    mids={'west':Point2D(b.min_x,b.center.y),'east':Point2D(b.max_x,b.center.y),
                          'south':Point2D(b.center.x,b.min_y),'north':Point2D(b.center.x,b.max_y)}
                    side=min(mids,key=lambda k:roads_shape.distance(s.Point(mids[k].x,mids[k].y)))
                    new_sites.append(_ParcelSite(b,'capacity_split',1,0,(side,)))
                plots[parent_index:parent_index+1]=children
                sites[parent_index:parent_index+1]=new_sites
                accepted=True;break
            if accepted:break
        if not accepted:break
    if len(sites) != spec.building_count:
        raise ValueError(f"Only {len(sites)} safe polygonal building envelopes fit; requested {spec.building_count}. Enlarge the city or reduce the count/river reserve")
    if spec.road_pattern == 'landscape_adaptive':
        # Keep district allocations spatially coherent rather than grouping
        # unrelated parcels by their area rank.
        paired = sorted(zip(sites, plots), key=lambda sp: (sp[0].bounds.center.x, sp[0].bounds.center.y))
        sites, plots = [p[0] for p in paired], [p[1] for p in paired]
    sites=[replace(site,urban_block_id=f'polygon_block_{i:03d}') for i,site in enumerate(sites)]
    landscape_sites = [{"id": f"landscape_{i:03d}", "style": "park", "density_tier": "standard",
                        **shape_record(p)} for i, p in enumerate(landscape) if p.area > 30]
    return GeographyLayout(network, rivers, bridges, plots, sites, landscape_sites)
