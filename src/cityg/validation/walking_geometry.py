"""Ground-level pedestrian witnesses on compiled floor plates and pedestrian surfaces."""
from collections import defaultdict, deque
import math

from cityg.polygons import geos, polygon_parts

from cityg.geometry.vegetation_clearance import (
    PEDESTRIAN_HEAD_Z as HEAD_Z, PEDESTRIAN_RADIUS as RADIUS, tree_bounds,
)

PAVING = {
    "sidewalk",
    "curb_ramp",
    "parcel_walkway",
    "frontage_connector",
    "entrance_landing",
    "river_promenade",
    "metro_access_path",
    "metro_forecourt",
    "group_access_path",
}
STREET_OBSTACLES = {
    "street_light_asset",
    "bench",
    "street_bin",
    "street_tree_asset",
    "street_tree_trunk",
    "street_tree_canopy",
    "street_light",
    "parcel_tree_asset",
    "parcel_shrub_asset",
    "parcel_plant_asset",
    "parcel_planting_bed",
    "parcel_flower_mass",
    "parcel_shrub",
    "median_planter",
    "median_shrub",
    "bollard",
    "small_sign",
    "vehicle_body",
    "city_bus_body",
    "street_planter",
    "frontage_planter",
    "frontage_vegetation",
    "frontage_sign",
    "loading_bollard",
    "vehicle_asset",
    "bicycle_rack",
    "bridge_parapet",
    "fire_hydrant",
    "cafe_table",
    "cafe_chair",
    "parcel_site_asset",
    "bus_shelter",
    "pedestrian_asset",
}


def footprint(p):
    from shapely.affinity import rotate

    s = geos()
    c, d = p["center"], p["size"]
    meta = p.get("metadata", {})
    if "mesh_triangles" in meta:
        vertices = [(c["x"] + v[0] * d["x"], c["y"] + v[1] * d["y"]) for v in meta["mesh_vertices"]]
        faces = [s.Polygon([vertices[i] for i in tri]) for tri in meta["mesh_triangles"]]
        shape = s.union_all([f for f in faces if f.area > 1e-10])
        if p["semantic_class"] == "sidewalk" and (meta.get("curb_openings_cut") or meta.get("sidewalk_infill")):
            # A remeshed slab and its original frontage connector use different
            # local frames. Resolve roundoff where their projected edges meet.
            shape = shape.buffer(1e-9, join_style="mitre")
    elif p["primitive_type"] == "path_mesh":
        raise ValueError("Missing projected triangle mesh for " + p["id"])
    else:
        shape = s.box(c["x"] - d["x"] / 2, c["y"] - d["y"] / 2, c["x"] + d["x"] / 2, c["y"] + d["y"] / 2)
    return rotate(shape, p.get("rotation_z_deg", 0), origin=(c["x"], c["y"]))


def pedestrian_obstacle(p):
    """Project only geometry occupying the ground-level pedestrian height band."""
    from shapely.affinity import rotate

    c, d = p["center"], p["size"]
    if c["z"] - d["z"] / 2 > HEAD_Z or c["z"] + d["z"] / 2 < 0:
        return geos().GeometryCollection()
    if p["semantic_class"] in {"street_tree_asset", "parcel_tree_asset"}:
        bounds = tree_bounds(p.get("metadata", {}).get("asset_geometry_path"), c["z"], d["z"])
        if bounds is not None:
            x0, y0, x1, y1 = bounds
            box = geos().box(c["x"] + x0 * d["x"], c["y"] + y0 * d["y"],
                             c["x"] + x1 * d["x"], c["y"] + y1 * d["y"])
            return rotate(box, p.get("rotation_z_deg", 0), origin=(c["x"], c["y"]))
    return footprint(p)


def surface_path(domain, start, end):
    """Use adjacent constrained triangles; simplify only along covered segments."""
    s = geos()
    component = next(
        (p for p in polygon_parts(domain) if p.covers(s.Point(start)) and p.covers(s.Point(end))), None
    )
    if component is None:
        raise ValueError("Endpoints disconnected on the compiled walkable surfaces")
    if start == end or component.covers(s.LineString([start, end])):
        return [start, end]
    triangles = list(s.constrained_delaunay_triangles(component).geoms)
    links = defaultdict(list)
    for i, t in enumerate(triangles):
        ring = list(t.exterior.coords)
        for a, b in zip(ring, ring[1:]):
            links[tuple(sorted((a, b)))].append(i)
    adj = defaultdict(list)
    for (a, b), pair in links.items():
        if len(pair) == 2:
            i, j = pair
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            adj[i].append((j, mid))
            adj[j].append((i, mid))
    origins = [i for i, t in enumerate(triangles) if t.covers(s.Point(start))]
    goals = {i for i, t in enumerate(triangles) if t.covers(s.Point(end))}
    parents = {i: None for i in origins}
    queue = deque(origins)
    while queue:
        i = queue.popleft()
        if i in goals:
            points = [end]
            while parents[i] is not None:
                i, mid = parents[i]
                points.append(mid)
            points.append(start)
            points.reverse()
            out = [start]
            index = 0
            while index < len(points) - 1:
                j = index + 1
                while j + 1 < len(points) and component.covers(s.LineString([out[-1], points[j + 1]])):
                    j += 1
                if not component.covers(s.LineString([out[-1], points[j]])):
                    raise ValueError("Triangulated candidate leaves the walkable surface")
                out.append(points[j])
                index = j
            return out
        for j, mid in adj[i]:
            if j not in parents:
                parents[j] = (i, mid)
                queue.append(j)
    raise ValueError("No connected triangle path on compiled surfaces")


def xy(p):
    return (p["x"], p["y"])


class PedestrianScene:
    def __init__(self, manifest):
        self.s = geos()
        self.primitives = manifest["primitives"]
        nav = manifest["navigation"]
        self.nodes = {n["id"]: n for n in nav["nodes"]}
        self.door_links = defaultdict(list)
        self.portals = {
            p["owner_id"]: p for p in self.primitives if p["semantic_class"] in ("door", "open_passage")
        }
        machines = {m["id"]: m for m in manifest.get("state_machines", [])}
        for edge in nav["edges"]:
            if edge["traversal"] != "door" or edge["width_m"] < 2 * RADIUS:
                continue
            door = edge["id"].removeprefix("nav_door_")
            if door not in self.portals:
                continue
            portal = self.portals[door]
            aperture = portal.get("metadata", {}).get("aperture_size_m")
            width = max(aperture[:2]) if aperture else max(portal["size"]["x"], portal["size"]["y"])
            if width < 2 * RADIUS:
                continue
            machine = edge.get("condition_state_machine_id")
            if portal["semantic_class"] == "door" and not machine:
                continue
            if machine:
                m = machines.get(machine)
                if not m:
                    continue
                reachable = {m["initial_state"]}
                for _ in m["states"]:
                    reachable.update(
                        t["to_state"] for t in m["transitions"] if t["from_state"] in reachable
                    )
                if not any(m["states"][k].get("nav_passable") for k in reachable):
                    continue
            a, b = edge["start_node_id"], edge["end_node_id"]
            self.door_links[a].append((b, door))
            self.door_links[b].append((a, door))
        self.street = None
        self.floor_access = {}

    def realized_floor(self, building, floor):
        from cityg.validation.floor_access import FloorAccess

        if floor.id not in self.floor_access:
            self.floor_access[floor.id] = FloorAccess(self, building, floor)
        return self.floor_access[floor.id]

    def approach(self, building, floor, room):
        entrance = "nav_entrance_" + building.id
        if room is None:
            candidates = {d for _, d in self.door_links[entrance]}
            if len(candidates) != 1:
                raise ValueError("Exterior doorway missing or ambiguous for " + building.id)
            door = candidates.pop()
            return [xy(self.portals[door]["center"])], [door]
        return self.realized_floor(building, floor).approach(room)

    def outdoors(self):
        if self.street is None:
            s = self.s
            pavement = []
            crossings = defaultdict(list)
            passages = {}
            blockers = []
            self.decks = {}
            water = []
            buildings = []
            thresholds = []
            for p in self.primitives:
                kind = p["semantic_class"]
                if kind in PAVING:
                    pavement.append(footprint(p))
                elif kind == "entrance_threshold" and p["metadata"].get("exterior_door_id") in self.portals:
                    thresholds.append(footprint(p))
                    pavement.append(thresholds[-1])
                elif kind == "crosswalk":
                    side = p.get("metadata", {}).get("junction_side")
                    if side:
                        key = (p["owner_id"], side)
                        crossings[key].append(footprint(p))
                        if "crossing_passage_xy" in p["metadata"]:
                            passages[key] = s.Polygon(p["metadata"]["crossing_passage_xy"])
                elif kind == "bridge_deck":
                    self.decks[p["owner_id"]] = footprint(p)
                elif kind == "river_water":
                    water.append(footprint(p))
                elif kind == "floor_slab" and abs(p["center"]["z"]) <= p["size"]["z"]/2:
                    buildings.append(footprint(p))
                elif kind in STREET_OBSTACLES:
                    blockers.append(pedestrian_obstacle(p))
            pavement += [passages[key] if key in passages else s.union_all(stripes).convex_hull
                         for key, stripes in crossings.items()]
            self.water = s.union_all(water)
            self.street = s.union_all(pavement).difference(
                self.water.difference(s.union_all(list(self.decks.values())))
            )
            self.street = self.street.difference(s.union_all(blockers).buffer(RADIUS))
            # Retain the threshold line but prohibit shortcuts through ground plates.
            self.street = self.street.difference(s.union_all(buildings).buffer(-1e-6).difference(s.union_all(thresholds)))
        return self.street

    def endpoint_path(self, binding, space):
        building, floor, room = binding
        if space not in ("frontage_path", "sidewalk"):
            return self.approach(building, floor, room)
        connectors = [
            p
            for p in self.primitives
            if p["semantic_class"] == "frontage_connector"
            and p.get("metadata", {}).get("building_id") == building.id
        ]
        if len(connectors) != 1:
            raise ValueError("No unique compiled frontage path for " + building.id)
        connector = connectors[0]
        area = footprint(connector)
        local = area
        target = area
        if space == "sidewalk":
            sidewalk = self.s.union_all([
                footprint(p) for p in self.primitives
                if p["semantic_class"] == "sidewalk" and p["owner_id"] == connector["owner_id"]
            ])
            # Require a standing point inside the sidewalk and a continuous local
            # route from the building's compiled door, even at a fragmented seam.
            near = sidewalk.intersection(area.buffer(3 * RADIUS))
            local = area.union(near)
            target = near.intersection(sidewalk.buffer(-RADIUS))
        door, _ = self.approach(building, floor, None)
        components = polygon_parts(local.intersection(self.outdoors()))
        reachable = [part for part in components if part.covers(self.s.Point(door[-1]))]
        candidates = polygon_parts(target.intersection(self.s.union_all(reachable)))
        if not candidates:
            raise ValueError("No accessible " + space + " on the frontage of " + building.id)
        return [max(candidates, key=lambda p: p.area).representative_point().coords[0]], []

    def witness(self, city, endpoints, request):
        from cityg.polygons import box_shape

        (b1, f1, r1), (b2, f2, r2) = endpoints
        start, end = request["start"], request["end"]
        if b1.id == b2.id and (r1 is None) == (r2 is None):
            raise ValueError("Expected distinct buildings or an indoor-to-outdoor route")
        if b1.id == b2.id and start["building"] != end["building"]:
            raise ValueError("Distinct building labels collapsed onto the same building")
        try:
            left, doors1 = self.endpoint_path(endpoints[0], start["space"])
        except ValueError as exc:
            raise ValueError(f"Start access ({b1.id}): {exc}") from exc
        try:
            right, doors2 = self.endpoint_path(endpoints[1], end["space"])
        except ValueError as exc:
            raise ValueError(f"Destination access ({b2.id}): {exc}") from exc
        try:
            street = surface_path(self.outdoors(), left[-1], right[-1])
        except ValueError as exc:
            raise ValueError(f"Outdoor connection ({b1.id} to {b2.id}): {exc}") from exc
        line = self.s.LineString(street)
        # Touching a bridge on the near bank is insufficient. A water segment
        # must be carried by one deck from one dry-land component to another.
        land = polygon_parts(box_shape(city.bounds).difference(self.water))
        wet = line.intersection(self.water)
        segments = [wet] if wet.geom_type == "LineString" else getattr(wet, "geoms", ())
        bridges = set()
        for segment in segments:
            if segment.geom_type != "LineString" or segment.length < 0.01:
                continue
            a, b = (self.s.Point(segment.coords[k]) for k in (0, -1))
            if not any(
                x.distance(a) < 1e-6 and y.distance(b) < 1e-6 for x in land for y in land if x != y
            ):
                continue
            bridges.update(bid for bid, deck in self.decks.items() if deck.buffer(1e-7).covers(segment))
        if request["via_bridge"] and not bridges:
            raise ValueError("No water crossing over a compiled bridge on this witness")
        if request["opposite_banks"]:
            sides = [
                {i for i, p in enumerate(land) if p.covers(self.s.Point(point))}
                for point in (left[-1], right[-1])
            ]
            if not all(sides) or sides[0] & sides[1]:
                raise ValueError("Opposite banks not established by final river geometry")
        route = left + street[1:] + list(reversed(right))[1:]
        return {
            "building_ids": [b1.id, b2.id],
            "room_ids": [r.id if r else None for r in (r1, r2)],
            "door_ids": [doors1, doors2],
            "bridge_ids": sorted(bridges),
            "polyline_xy_m": route,
            "length_m": sum(math.dist(a, b) for a, b in zip(route, route[1:])),
            "scope": "ground-level planar pedestrian surface witness; operable doors assumed open; static obstacle clearance, no dynamics",
        }
