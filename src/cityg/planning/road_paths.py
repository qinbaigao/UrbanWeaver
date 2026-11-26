"""Geometric feasibility checks for explicit curved-road networks."""
from __future__ import annotations

from cityg.paths import PlanarPath2D


def road_path_issues(roads, buildings=()):
    """Yield (code, entity_id, message); legacy straight networks are unchanged."""
    if not any(len(road.centerline) > 2 for road in roads):
        return
    paths = {}
    buildings = tuple(buildings)
    for road in roads:
        try:
            path = PlanarPath2D(road.centerline)
            path.validate_corridor(road.width_m / 2 + road.sidewalk_width_m)
            paths[road.id] = path
            if len(road.centerline) > 2:
                for building in buildings:
                    if path.intersects_bounds(building.footprint, road.width_m/2 + road.sidewalk_width_m):
                        yield ("road_building_overlap", road.id,
                               f"Curved road corridor {road.id} overlaps building envelope {building.id}")
        except ValueError as exc:
            yield "invalid_road_path", road.id, str(exc)
    for index, road in enumerate(roads):
        if road.id not in paths:
            continue
        for other in roads[index+1:]:
            if other.id not in paths:
                continue
            for s, t, _ in paths[road.id].intersections(paths[other.id], include_endpoints=True):
                def endpoint(r, distance):
                    if abs(distance) < 1e-6:
                        return r.start_junction_id
                    if abs(distance - paths[r.id].length) < 1e-6:
                        return r.end_junction_id
                    return None
                first, second = endpoint(road, s), endpoint(other, t)
                if first is None or first != second:
                    yield ("unsplit_road_crossing", road.id,
                           f"Unsplit road crossing: {road.id}, {other.id}; add a shared junction")
                    break
