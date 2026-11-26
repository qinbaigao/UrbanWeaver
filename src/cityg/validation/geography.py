"""Hard water/bridge/parcel constraints, independent of any language model."""
from __future__ import annotations

import math

from cityg.paths import PlanarPath2D
from cityg.polygons import box_shape, geos, line_shape, parcel_shape, river_shape, road_shape


def validate_geography(city, report):
    s = geos()
    rivers, roads = {r.id: r for r in city.rivers}, {r.id: r for r in city.road_network.segments}
    valid_rivers, water, reserve = {}, {}, {}
    for river in city.rivers:
        try:
            values = (river.width_m, river.bank_width_m, river.setback_m, river.water_elevation_m, river.bed_elevation_m)
            if not all(math.isfinite(v) for v in values) or river.width_m < 4 or river.bank_width_m < 2 or river.setback_m < 3:
                raise ValueError("Invalid river dimensions")
            if not river.bed_elevation_m < river.water_elevation_m < -.75:
                raise ValueError("River bed must be below recessed water, below land")
            path = PlanarPath2D(river.centerline)
            path.validate_corridor(river.width_m/2+river.bank_width_m)
            if not line_shape(path.points).intersects(box_shape(city.bounds)):
                raise ValueError("River does not intersect the city")
            valid_rivers[river.id] = river
            water[river.id] = river_shape(river)
            reserve[river.id] = river_shape(river, "reserve")
        except (ValueError, TypeError) as exc:
            report.add("error", "invalid_river", str(exc), river.id)
    for i, first in enumerate(valid_rivers):
        for second in list(valid_rivers)[i+1:]:
            if reserve[first].intersection(reserve[second]).area > 1e-5:
                report.add("error", "unsupported_river_confluence", "Intersecting river reserves require a confluence planner", first)
    spans = {}
    for bridge in city.bridges:
        try:
            road, river = roads.get(bridge.road_id), valid_rivers.get(bridge.river_id)
            if road is None or river is None:
                raise ValueError("Bridge references a missing/invalid road or river")
            values = (bridge.start_m,bridge.end_m,bridge.deck_elevation_m,bridge.structural_depth_m,bridge.min_clearance_m)
            if not all(math.isfinite(v) for v in values):
                raise ValueError("Bridge dimensions must be finite")
            path = PlanarPath2D(road.centerline)
            if not 0 <= bridge.start_m < bridge.end_m <= path.length:
                raise ValueError("Bridge interval is outside its road")
            if abs(bridge.deck_elevation_m) > 1e-6:
                raise ValueError("Only same-grade bridges (deck_elevation_m=0) are supported; elevated bridges need approaches")
            if bridge.structural_depth_m <= .2 or bridge.min_clearance_m <= 0:
                raise ValueError("Invalid bridge depth or clearance")
            clearance = bridge.deck_elevation_m-bridge.structural_depth_m-river.water_elevation_m
            if clearance < bridge.min_clearance_m:
                raise ValueError("Bridge underside does not meet water clearance")
            from cityg.geometry.geography import bridge_shape
            shape = bridge_shape(bridge, road)
            if not shape.intersects(water[river.id]):
                raise ValueError("Bridge does not cross its referenced river")
            for old, old_shape in spans.get((road.id,river.id), []):
                if shape.intersection(old_shape).area > 1e-5:
                    raise ValueError(f"Duplicate/overlapping bridge span: {old.id}")
            spans.setdefault((road.id,river.id), []).append((bridge, shape))
        except (ValueError, TypeError) as exc:
            report.add("error", "invalid_bridge", str(exc), bridge.id)
    road_footprints = []
    valid_roads = []
    for road in city.road_network.segments:
        try:
            PlanarPath2D(road.centerline)
            footprint = road_shape(road)
        except (ValueError, TypeError):
            continue  # ordinary road validation reports malformed centerlines
        road_footprints.append(footprint)
        valid_roads.append(road)
        for river_id in valid_rivers:
            crossing = footprint.intersection(water[river_id])
            supported = s.union_all([p for _, p in spans.get((road.id, river_id), [])])
            if crossing.difference(supported.buffer(1e-6)).area > 1e-4:
                report.add("error", "unbridged_road_crossing", f"Road corridor crosses {river_id} without full bridge coverage", road.id)
    road_union = s.union_all(road_footprints)
    reserve_union = s.union_all(list(reserve.values()))
    parcels = []
    for parcel in city.iter_parcels():
        try:
            shape = parcel_shape(parcel)
            if parcel.boundary:
                if max(abs(a-b) for a,b in zip(shape.bounds, (parcel.bounds.min_x,parcel.bounds.min_y,parcel.bounds.max_x,parcel.bounds.max_y))) > 1e-5:
                    raise ValueError("Parcel bounds are stale relative to its polygon")
                if shape.intersection(road_union).area > 1e-4:
                    report.add("error", "parcel_on_road", "Polygonal parcel intrudes into a road corridor", parcel.id)
                if shape.intersection(reserve_union).area > 1e-4:
                    report.add("error", "parcel_in_river_reserve", "Parcel enters the water/bank reserve", parcel.id)
                for old, other in parcels:
                    if shape.intersection(other).area > 1e-4:
                        report.add("error", "polygon_parcel_overlap", f"Parcel overlaps {old}", parcel.id)
                parcels.append((parcel.id, shape))
            for building in parcel.buildings:
                footprint = box_shape(building.footprint)
                if not shape.buffer(1e-6).covers(footprint):
                    report.add("error", "building_outside_polygon", "Building exceeds the actual parcel polygon or enters a hole", building.id)
                if footprint.intersection(reserve_union).area > 1e-4:
                    report.add("error", "building_in_river_reserve", "Building enters the river setback", building.id)
                if valid_rivers and valid_roads:
                    nearest = min(valid_roads, key=lambda r: PlanarPath2D(r.centerline).project(building.entrance).separation)
                    projection = PlanarPath2D(nearest.centerline).project(building.entrance).point
                    access = line_shape((building.entrance, projection))
                    if access.intersection(s.union_all(list(water.values()))).length > 1e-4:
                        report.add("error", "entrance_crosses_water", "Entrance access cannot walk through water to its assigned road", building.id)
        except (ValueError, TypeError) as exc:
            report.add("error", "invalid_parcel_polygon", str(exc), parcel.id)
    report.metrics.update({"river_count":len(city.rivers),"bridge_count":len(city.bridges),
                           "polygon_parcel_count":len(parcels)})


def validate_geography_geometry(city, scene, report):
    by_id = {p.id: p for p in scene.primitives}
    for river in city.rivers:
        for suffix in ("bed", "water", "banks", "promenade"):
            primitive = by_id.get(f"{river.id}_{suffix}")
            if primitive is None:
                report.add("error", "missing_river_geometry", f"Missing river {suffix}", river.id)
        water = by_id.get(f"{river.id}_water")
        if water is not None and water.collision_enabled:
            report.add("error", "solid_water_surface", "Water cannot masquerade as a walkable solid", river.id)
    for bridge in city.bridges:
        deck = by_id.get(f"{bridge.id}_deck")
        if deck is None or not deck.collision_enabled:
            report.add("error", "missing_bridge_deck", "Bridge needs a collidable deck", bridge.id)
        elif abs(deck.center.z-deck.size.z/2 - (bridge.deck_elevation_m-bridge.structural_depth_m)) > 1e-5:
            report.add("error", "bridge_deck_elevation_mismatch", "Bridge mesh disagrees with its structural depth", bridge.id)
        edges = [e for e in scene.navigation.edges if e.bridge_id == bridge.id and e.traversal == "bridge"]
        if not edges or abs(sum(e.distance_m for e in edges) - (bridge.end_m-bridge.start_m)) > 1e-4:
            report.add("error", "bridge_navigation_gap", "Bridge traversal must cover its exact road interval", bridge.id)
    valid_ids = {b.id for b in city.bridges}
    for edge in scene.navigation.edges:
        if edge.bridge_id is not None and edge.bridge_id not in valid_ids:
            report.add("error", "dangling_navigation_bridge", "Navigation edge references a missing bridge", edge.id)
