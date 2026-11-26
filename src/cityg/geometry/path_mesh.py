"""Watertight path slabs, shared by road surfaces and long street strips."""
from __future__ import annotations

from cityg.geometry.model import GeometryPrimitive, Vec3
from cityg.paths import PlanarPath2D
from cityg.schemas import Point2D
from cityg.planning.road_paths import road_path_issues


def polygon_slab(primitive_id, owner_id, polygon, z, thickness, semantic, material,
                 *, collision=True, metadata=None):
    """Extrude a convex CCW polygon; coordinates are normalized for the IR transform."""
    n = len(polygon)
    vertices = [(p.x, p.y, z + dz) for dz in (-thickness / 2, thickness / 2) for p in polygon]
    faces = []
    for i in range(1, n - 1):
        faces.extend(((0, i + 1, i), (n, n + i, n + i + 1)))
    for i in range(n):
        j = (i + 1) % n
        faces.extend(((i, j, n + j), (i, n + j, n + i)))
    return inline_mesh(primitive_id, owner_id, vertices, faces, semantic, material,
                       collision=collision, metadata=metadata)


def inline_mesh(primitive_id, owner_id, vertices, faces, semantic, material,
                *, collision=True, metadata=None):
    low = [min(p[i] for p in vertices) for i in range(3)]
    high = [max(p[i] for p in vertices) for i in range(3)]
    size = [max(high[i] - low[i], 1e-6) for i in range(3)]
    center = [(high[i] + low[i]) / 2 for i in range(3)]
    normalized = [[(p[i] - center[i]) / size[i] for i in range(3)] for p in vertices]
    return GeometryPrimitive(
        primitive_id, owner_id, "path_mesh", Vec3(*center), Vec3(*size), 0.0,
        semantic, material, "roads", collision_enabled=collision,
        instance_key=primitive_id,
        metadata={**(metadata or {}), "mesh_vertices": normalized, "mesh_triangles": faces},
    )


def path_slab(primitive_id, owner_id, path: PlanarPath2D, width, z, thickness,
              semantic, material, *, offset=0.0, collision=True, metadata=None):
    left = path.offset_points(offset + width / 2)
    right = path.offset_points(offset - width / 2)
    # Each station: right-bottom, left-bottom, right-top, left-top.
    vertices = [(p.x, p.y, z + dz) for l, r in zip(left, right)
                for p, dz in ((r, -thickness/2), (l, -thickness/2), (r, thickness/2), (l, thickness/2))]
    faces = []
    for i in range(len(left) - 1):
        a, b = 4*i, 4*(i+1)
        for q in ((a+2, b+2, b+3, a+3), (a+1, b+1, b, a),
                  (a, b, b+2, a+2), (a+3, b+3, b+1, a+1)):
            faces.extend(((q[0], q[1], q[2]), (q[0], q[2], q[3])))
    end = 4 * (len(left) - 1)
    faces.extend(((0, 2, 3), (0, 3, 1), (end, end+1, end+3), (end, end+3, end+2)))
    return inline_mesh(primitive_id, owner_id, vertices, faces, semantic, material,
                       collision=collision, metadata={**(metadata or {}), "path_sweep": True})


def convex_hull(points):
    coords = sorted(set((p.x, p.y) for p in points))
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lower, upper = [], []
    for p in coords:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(coords):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return [Point2D(*p) for p in lower[:-1] + upper[:-1]]


def compile_path_roads(city, scene):
    """Compile an explicit path network without manufacturing semantic junctions.

    Unsplit crossings are rejected: a visible crossing must also be navigable.
    A planner must split roads at real junctions before invoking this compiler.
    """
    issues = list(road_path_issues(city.road_network.segments, city.iter_buildings()))
    if issues:
        raise ValueError(issues[0][2])
    paths = {r.id: PlanarPath2D(r.centerline) for r in city.road_network.segments}
    incident = {}
    for road in city.road_network.segments:
        incident.setdefault(road.start_junction_id, []).append(road)
        incident.setdefault(road.end_junction_id, []).append(road)
    patches = {}
    for road in city.road_network.segments:
        path = paths[road.id]
        trims = []
        for jid in (road.start_junction_id, road.end_junction_id):
            neighbors = incident[jid]
            trims.append(min(path.length * .22, max(r.width_m / 2 for r in neighbors)) if len(neighbors) > 1 else 0.0)
        start, end = trims[0], path.length - trims[1]
        for jid, station in ((road.start_junction_id, start), (road.end_junction_id, end)):
            if len(incident[jid]) > 1:
                patches.setdefault(jid, []).extend(path.point(station, side * road.width_m / 2) for side in (-1, 1))
        metadata = {"road_class": road.road_class, "lane_count": road.lane_count,
                    "directionality": road.directionality, "path_length_m": path.length,
                    "speed_limit_kph": road.speed_limit_kph, "parking_allowed": road.parking_allowed,
                    "median_width_m": road.median_width_m, "bike_lane": road.bike_lane,
                    "bus_lane": road.bus_lane, "turn_lane": road.turn_lane}
        scene.primitives.append(path_slab(road.id, road.id, path.slice(start, end), road.width_m,
                                         -.10, .20, "road_surface", "asphalt", metadata=metadata))
        if road.median_width_m > 0:
            scene.primitives.append(path_slab(f"{road.id}_median_00", road.id, path.slice(start, end),
                min(road.median_width_m, road.width_m-1), .015, .12, "road_median", "concrete"))
        if road.sidewalk_width_m <= 0:
            continue
        start += road.sidewalk_width_m if trims[0] else 0
        end -= road.sidewalk_width_m if trims[1] else 0
        if end - start < .2:
            continue
        # Keep shared miter vertices across pieces. Reject individual pieces
        # intruding into another carriageway, not an entire long sidewalk.
        sliced = path.slice(start, end)
        for side, sign in (("left", 1), ("right", -1)):
            pieces = []
            inner = sliced.offset_points(sign * road.width_m / 2)
            outer = sliced.offset_points(sign * (road.width_m / 2 + road.sidewalk_width_m))
            # Filter once per whole sidewalk, then once per short piece. Both
            # bounds include offset/miter vertices; exact probes stay unchanged.
            strip = inner + outer
            strip_bounds = (min(p.x for p in strip), min(p.y for p in strip),
                            max(p.x for p in strip), max(p.y for p in strip))
            candidates = [(paths[other.id], other.width_m / 2 + .08)
                          for other in city.road_network.segments
                          if other.id != road.id and paths[other.id].bounds_overlap(
                              strip_bounds, other.width_m / 2 + .08)]
            for i in range(len(inner) - 1):
                polygon = convex_hull([inner[i], inner[i+1], outer[i], outer[i+1]])
                probes = polygon + [Point2D((a.x+b.x)/2, (a.y+b.y)/2)
                                    for a, b in zip(polygon, polygon[1:]+polygon[:1])]
                bounds = (min(p.x for p in polygon), min(p.y for p in polygon),
                          max(p.x for p in polygon), max(p.y for p in polygon))
                if any(other.project(p).separation <= radius
                       for other, radius in candidates if other.bounds_overlap(bounds, radius)
                       for p in probes):
                    continue
                pieces.append(polygon_slab(f"{road.id}_sidewalk_{side}_{i:03d}", road.id,
                    polygon, .075, .15, "sidewalk", "sidewalk", metadata={"pedestrian": True,
                    "block_constrained": True, "intersection_clipped": True, "path_sweep": True}))
            if pieces:
                scene.primitives.append(merge_path_meshes(pieces, f"{road.id}_sidewalk_{side}_000"))
    for jid, points in patches.items():
        polygon = convex_hull(points)
        if len(polygon) >= 3:
            scene.primitives.append(polygon_slab(f"{jid}_road_patch", jid, polygon, -.10, .20,
                "junction_surface", "asphalt", metadata={"junction_id": jid,
                "incident_road_ids": sorted(r.id for r in incident[jid])}))


def merge_path_meshes(pieces, primitive_id):
    """Batch a road-side's clipped slabs into one draw call and one collider."""
    vertices, faces = [], []
    for piece in pieces:
        base = len(vertices)
        vertices.extend((v[0]*piece.size.x + piece.center.x,
                         v[1]*piece.size.y + piece.center.y,
                         v[2]*piece.size.z + piece.center.z)
                        for v in piece.metadata["mesh_vertices"])
        faces.extend(tuple(base+i for i in face) for face in piece.metadata["mesh_triangles"])
    first = pieces[0]
    metadata = {k: v for k, v in first.metadata.items() if k not in {"mesh_vertices", "mesh_triangles"}}
    return inline_mesh(primitive_id, first.owner_id, vertices, faces, first.semantic_class,
                       first.material_id, collision=first.collision_enabled, metadata=metadata)
