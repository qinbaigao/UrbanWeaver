"""Sidewalks and furniture clearances in the road's physical right of way."""
from collections import defaultdict
from dataclasses import asdict, replace

from cityg.geometry.geography import polygon_mesh, primitive_footprint
from cityg.geometry.model import GeometryPrimitive, Vec3
from cityg.paths import PlanarPath2D
from cityg.polygons import box_shape, geos, line_shape, polygon_parts, river_shape
from cityg.schemas import Point2D
from cityg.validation.walking_geometry import STREET_OBSTACLES, pedestrian_obstacle


def complete_sidewalks(city, primitives):
    """Fill missing pieces of each side strip up to actual carriageway boundaries."""
    try:
        s = geos()
    except RuntimeError:
        return 0
    roads = city.road_network.segments
    voids = [
        primitive_footprint(p)
        for p in primitives
        if p.semantic_class in {"road_surface", "junction_surface"}
    ]
    voids += [box_shape(b.footprint) for b in city.iter_buildings()]
    voids += [river_shape(r, "banks") for r in city.rivers]
    rights = s.STRtree([line_shape(r.centerline).buffer(r.width_m / 2 + 0.01) for r in roads])
    sidewalks = [primitive_footprint(p) for p in primitives if p.semantic_class == "sidewalk"]
    excluded = s.STRtree(voids + sidewalks)
    bounds = box_shape(city.bounds)
    added = []
    for index, road in enumerate(roads):
        if road.sidewalk_width_m <= 0:
            continue
        line = line_shape(road.centerline)
        for sign, side in ((1, "left"), (-1, "right")):

            def strip(width):
                return line.buffer(sign * width, single_sided=True, join_style="mitre")

            edge = road.width_m / 2
            band = strip(edge + road.sidewalk_width_m).difference(strip(edge)).intersection(bounds)
            foreign = [rights.geometries[i] for i in rights.query(band) if i != index]
            nearby = [*foreign, *excluded.geometries.take(excluded.query(band))]
            remainder = band.difference(
                s.union_all([*nearby, *(g for g in added if g.intersects(band))])
            )
            # Reject slivers that cannot accommodate even one pedestrian.
            pieces = [p for p in polygon_parts(remainder) if not p.buffer(-0.25).is_empty]
            for n, shape in enumerate(pieces):
                mesh = polygon_mesh(
                    f"{road.id}_sidewalk_{side}_infill_{n}",
                    road.id,
                    shape,
                    0.15,
                    0.15,
                    "sidewalk",
                    "sidewalk",
                    collision=True,
                    metadata={
                        "pedestrian": True,
                        "sidewalk_infill": True,
                        "block_constrained": True,
                        "intersection_clipped": True,
                    },
                )
                primitives.append(mesh)
                added.append(shape)
    return len(added)


def sidewalk_plan(city, primitives):
    """Reserve a continuous strip on each supported street side before furnishing."""
    try:
        s = geos()
    except RuntimeError:
        return {}, {}
    roads = {r.id: r for r in city.road_network.segments}
    by_road = defaultdict(list)
    for item in primitives:
        if item.semantic_class == "sidewalk":
            by_road[item.owner_id].append(primitive_footprint(item))
    support = {k: s.union_all(v) for k, v in by_road.items()}
    lanes = {}
    for key, walk in support.items():
        road = roads[key]
        line = line_shape(road.centerline)
        offset = road.width_m / 2 + min(0.95, road.sidewalk_width_m)
        for sign, side in ((1, "left"), (-1, "right")):
            band = line.buffer(sign * offset, single_sided=True, join_style="mitre")
            lanes[f"{key}/{side}"] = walk.intersection(band)
    return support, lanes


def network_components(primitives, lanes):
    """Index paved street-side, landing and frontage geometry by connected component."""
    if not lanes:
        return {}
    s = geos()
    nodes = dict(lanes)
    surfaces = []
    for p in primitives:
        if p.semantic_class in {"sidewalk", "curb_ramp", "group_access_path", "frontage_connector"}:
            shape = primitive_footprint(p)
            surfaces.append(shape)
            if p.semantic_class != "sidewalk":
                nodes[p.id] = shape
        if "crossing_passage_xy" in p.metadata:
            passage = s.Polygon(p.metadata["crossing_passage_xy"])
            surfaces.append(passage)
            nodes[p.id] = passage
    # Component IDs describe paved topology; clearance is checked on final geometry.
    parts = polygon_parts(s.union_all(surfaces, grid_size=1e-7))
    tree = s.STRtree(parts)
    return {
        "component_count": len(parts),
        "node_components": {
            key: sorted(
                int(i) for i in tree.query(g) if tree.geometries[i].intersection(g).area > 1e-6
            )
            for key, g in nodes.items()
        },
    }


def reserve_walkways(city, primitives, plan=None):
    """Fit roadside fixtures around continuous strips, entrances and ramp mouths.

    The candidate support point must stay on its road's sidewalk or on a
    neighbouring ground-level planting verge (trees only). Reject candidates that
    enter other streets, buildings, entrance paths or other assets.
    """
    try:
        s = geos()
    except RuntimeError:
        return {}
    from shapely.affinity import translate

    roads = {r.id: r for r in city.road_network.segments}
    paths = {k: PlanarPath2D(r.centerline) for k, r in roads.items()}
    support, lanes = plan if plan is not None else sidewalk_plan(city, primitives)
    barriers, reservations, occupied = [], [], []
    groups = defaultdict(list)
    for p in primitives:
        kind = p.semantic_class
        if kind in {"road_surface", "junction_surface", "river_water"}:
            barriers.append(primitive_footprint(p))
        if kind in {"curb_ramp", "frontage_connector", "group_access_path"}:
            reservations.append(primitive_footprint(p))
        meta = p.metadata
        role = meta.get("street_asset")
        if p.owner_id in roads and role in {"tree", "street_light", "bench", "bin"}:
            # Mesh parts of one tree or light share the same placement station.
            key = (
                (meta.get("placement_side"), meta["longitudinal_m"])
                if "longitudinal_m" in meta
                else p.id
            )
            groups[p.owner_id, role, key].append(p)
        elif kind in STREET_OBSTACLES:
            occupied.append(pedestrian_obstacle(asdict(p)))
    reservations.extend(lanes.values())
    barriers.extend(
        primitive_footprint(p)
        for p in primitives
        if p.semantic_class == "floor_slab" and abs(p.center.z) <= p.size.z / 2
    )
    barriers.extend(box_shape(b.footprint) for b in city.iter_buildings())
    barriers.extend(river_shape(r, "banks") for r in city.rivers)
    protected = s.STRtree(barriers + reservations)
    fixed = s.STRtree(occupied)
    city_land = box_shape(city.bounds)
    shapes = {
        key: s.union_all([pedestrian_obstacle(asdict(p)) for p in group])
        for key, group in groups.items()
    }
    original = s.STRtree(list(shapes.values()))
    keys = list(groups)
    placed = defaultdict(list)
    removed = set()
    resolved = set()
    stats = defaultdict(int)
    for key, parts in groups.items():
        owner, role, _ = key
        shape = shapes[key]
        if shape.is_empty or not len(protected.query(shape, predicate="intersects")):
            continue
        p = parts[0]
        path = paths[owner]
        pos = path.project(Point2D(p.center.x, p.center.y))
        sign = 1 if pos.lateral >= 0 else -1
        road = roads[owner]
        edge = road.width_m / 2 + road.sidewalk_width_m
        walk = support.get(owner, s.GeometryCollection())
        success = False
        for extra in (-0.30, 0.45, 1.15, 1.95, 2.75) if role == "tree" else (-0.3,):
            for shift in (0.0, 1.5, -1.5, 3.0, -3.0):
                station = pos.distance + shift
                if not 0 < station < path.length:
                    continue
                at = path.point(station, sign * (edge + extra))
                point = s.Point(at.x, at.y)
                # Outboard planting requires a continuous connection to the
                # sidewalk edge and land inside the city at the planting station.
                edge_at = path.point(station, sign * (edge - 0.12))
                if not walk.covers(s.Point(edge_at.x, edge_at.y)):
                    continue
                if not walk.covers(point) and not (extra > 0 and city_land.covers(point)):
                    continue
                dx, dy = at.x - p.center.x, at.y - p.center.y
                candidate = translate(shape, dx, dy)
                if role == "tree" and extra > 0:
                    # The planting bed occupies ground even for an off-centre trunk.
                    candidate = candidate.union(point.buffer(0.4))
                    if not city_land.covers(candidate):
                        continue
                if len(protected.query(candidate, predicate="intersects")) or len(
                    fixed.query(candidate, predicate="intersects")
                ):
                    continue
                if any(
                    keys[i] != key and keys[i] not in resolved
                    for i in original.query(candidate, predicate="intersects")
                ):
                    continue
                # Nearby moved fixtures can belong to different roads at a junction.
                cells = [
                    (i, j)
                    for i in range(int(candidate.bounds[0] // 8), int(candidate.bounds[2] // 8) + 1)
                    for j in range(int(candidate.bounds[1] // 8), int(candidate.bounds[3] // 8) + 1)
                ]
                if any(candidate.intersects(g) for cell in cells for g in placed[cell]):
                    continue
                bed_id = None
                if role == "tree" and extra > 0:
                    bed_id = f"{p.id}_planting_bed"
                    primitives.append(
                        GeometryPrimitive(
                            bed_id,
                            owner,
                            "cylinder",
                            Vec3(at.x, at.y, 0.025),
                            Vec3(0.8, 0.8, 0.05),
                            0,
                            "street_planting_bed",
                            "planting_soil",
                            "roads",
                            instance_key="unit_cylinder",
                            collision_enabled=False,
                            metadata={"road_id": owner},
                        )
                    )
                for part in parts:
                    if bed_id:
                        part.metadata.update(
                            placement_domain="street_planting_verge", planting_bed_id=bed_id
                        )
                    part.center = Vec3(part.center.x + dx, part.center.y + dy, part.center.z)
                    if "longitudinal_m" in part.metadata:
                        part.metadata["longitudinal_m"] = round(station, 3)
                for cell in cells:
                    placed[cell].append(candidate)
                stats[f"{role}_relocated"] += 1
                success = True
                break
            if success:
                break
        resolved.add(key)
        if not success:
            removed.update(p.id for p in parts)
            stats[f"{role}_omitted"] += 1
    primitives[:] = [p for p in primitives if p.id not in removed]
    return dict(stats)


def connect_actual_doors(city, primitives):
    """Tie a planned frontage to a displaced, compiled ground-floor doorway."""
    try:
        s = geos()
    except RuntimeError:
        return {}
    doors = {p.owner_id: p for p in primitives if p.semantic_class in {"door", "open_passage"}}
    carriageways = s.STRtree(
        [
            primitive_footprint(p)
            for p in primitives
            if p.semantic_class in {"road_surface", "junction_surface", "river_water"}
        ]
    )
    plates = defaultdict(list)
    for part in primitives:
        if part.semantic_class == "floor_slab" and abs(part.center.z) <= part.size.z / 2:
            plates[part.owner_id].append(primitive_footprint(part))
    ground = {k: s.union_all(v) for k, v in plates.items()}
    ids = list(ground)
    buildings_index = s.STRtree(list(ground.values()))
    buildings = {b.id: b for b in city.iter_buildings()}
    status = {bid: "no_compiled_frontage" for bid in buildings}
    for idx, p in enumerate(primitives):
        if p.semantic_class != "frontage_connector":
            continue
        bid = p.metadata.get("building_id")
        building = buildings.get(bid)
        if not building:
            continue
        portals = [
            doors[d.id]
            for f in building.floors
            if f.level == 0
            for d in f.doors
            if d.room_b_id is None and d.id in doors
        ]
        if len(portals) != 1:
            status[bid] = "no_unique_compiled_entrance"
            continue
        door = s.Point(portals[0].center.x, portals[0].center.y)
        old = primitive_footprint(p)
        if old.distance(door) < 1e-7:
            status[bid] = "aligned"
            continue
        target = old.representative_point()
        if door.distance(target) > 24:
            status[bid] = "outside_frontage_range"
            continue
        # A straight strip or a single turn may fit the setback. A candidate
        # traversing a building, river or traffic lane is always rejected.
        a, b = door.coords[0], target.coords[0]
        fid = next(f.id for f in building.floors if f.level == 0)
        plate = ground.get(fid, s.GeometryCollection())
        # Exterior doors can be centred in the thickness of the wall. Only
        # the real door aperture within the outer 15 cm can be a threshold.
        portal = portals[0]
        if "aperture_size_m" in portal.metadata:
            portal = replace(portal, size=Vec3(*portal.metadata["aperture_size_m"]))
        threshold = (
            primitive_footprint(portal)
            .buffer(0.10, join_style="mitre")
            .intersection(plate.difference(plate.buffer(-0.15)))
        )
        for points in ([a, b], [a, (a[0], b[1]), b], [a, (b[0], a[1]), b]):
            line = s.LineString(points)
            strip = line.buffer(0.65, cap_style="square", join_style="mitre")
            obstacles = s.union_all(
                [
                    *carriageways.geometries.take(carriageways.query(strip)),
                    *(
                        ground[ids[i]].difference(threshold) if ids[i] == fid else ground[ids[i]]
                        for i in buildings_index.query(strip)
                    ),
                ]
            )
            if line.intersects(obstacles.buffer(-1e-6)):
                continue
            strip = strip.difference(obstacles).intersection(box_shape(city.bounds))
            parts = [
                g
                for g in polygon_parts(strip)
                if g.distance(door) < 1e-7
                and g.intersection(old).area > 0.1
                and not g.buffer(-0.25).is_empty
            ]
            if not parts:
                continue
            mesh = polygon_mesh(
                p.id,
                p.owner_id,
                old.union(parts[0]),
                p.center.z + p.size.z / 2,
                p.size.z,
                p.semantic_class,
                p.material_id,
                collision=True,
                metadata={**p.metadata, "compiled_entrance_id": portals[0].owner_id},
            )
            primitives[idx] = mesh
            opening = threshold.intersection(parts[0])
            if opening.area > 1e-6 and opening.distance(door) < 1e-7:
                primitives.append(
                    polygon_mesh(
                        f"{p.id}_threshold",
                        p.owner_id,
                        opening,
                        0.19,
                        0.035,
                        "entrance_threshold",
                        p.material_id,
                        collision=True,
                        metadata={"exterior_door_id": portals[0].owner_id},
                    )
                )
            status[bid] = "connected_to_compiled_entrance"
            break
        else:
            status[bid] = "no_clear_frontage_strip"
    return status
