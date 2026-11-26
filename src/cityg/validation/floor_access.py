"""Post-compile pedestrian evidence for individual ground-floor room doors."""

from collections import deque
from functools import cached_property

from shapely.affinity import affine_transform, rotate

from cityg.envelopes import envelope_config
from cityg.planning.room_envelope import massing_projection
from cityg.polygons import box_shape, polygon_parts
from cityg.validation.walking_geometry import RADIUS, footprint, surface_path, xy


CIRCULATION = {"corridor", "hallway", "lobby", "foyer", "entrance_hall"}


WALKING_BARRIERS = {
    "interior_wall",
    "exterior_wall",
    "collision_envelope",
    "stair_tread",
    "elevator_shaft",
    "elevator_cabin",
    "elevator_landing_door",
    "elevator_cabin_door",
}


class FloorAccess:
    """Search doorway-to-doorway legs inside their assigned circulation spaces."""

    def __init__(self, scene, building, floor):
        self.scene, self.building, self.floor = scene, building, floor
        self.s = scene.s
        self.rooms = {r.id: r for r in floor.rooms}
        self.entrance = "nav_entrance_" + building.id
        self.by_node = {"nav_" + r.id: r for r in floor.rooms}
        self.domains = {}
        self.reports = {}
        self.projection = (
            massing_projection(building, floor) if building.metadata.get("massing_style") else None
        )

    @cached_property
    def surfaces(self):
        slabs, barriers, exit_apertures = [], [], []
        self.barrier_ids = []
        level = self.floor.elevation_m
        floor_layer = "floor:" + self.floor.id
        exits = {d for _, d in self.scene.door_links[self.entrance]}
        for p in self.scene.primitives:
            if p.get("metadata", {}).get("viewer_room_only") and not p.get("collision_enabled", True):
                # Section caps exist only while a single room is isolated in the viewer.
                continue
            kind = p["semantic_class"]
            if kind == "floor_slab" and p["owner_id"] == self.floor.id:
                slabs.append(footprint(p))
            elif p["owner_id"] in exits and kind in ("door", "open_passage"):
                # Permit the pedestrian disc to straddle an open exterior threshold.
                aperture = p.get("metadata", {}).get("aperture_size_m")
                portal = dict(p, size=dict(zip(("x", "y", "z"), aperture))) if aperture else p
                exit_apertures.append(footprint(portal).buffer(RADIUS + 1e-6))
            elif p["layer_id"] == floor_layer or (
                p["owner_id"] == self.floor.id and kind in ("exterior_wall", "collision_envelope")
            ):
                if kind not in WALKING_BARRIERS and not kind.startswith("furniture_"):
                    continue
                z, h = p["center"]["z"] - level, p["size"]["z"]
                if z - h / 2 < 1.8 and z + h / 2 > 0.05:
                    barriers.append(footprint(p))
                    self.barrier_ids.append(p["id"])
        # Round world-frame seams before erosion so abutting rotated slabs share an edge.
        plate = self.s.union_all(slabs, grid_size=1e-8)
        supported = plate.union(self.s.union_all(exit_apertures)).buffer(-RADIUS)
        free = supported.difference(self.s.union_all(barriers).buffer(RADIUS))
        self.barrier_index = self.s.STRtree(barriers)
        return plate, free

    def space(self, room):
        if room.id not in self.domains:
            bounds = box_shape(room.bounds)
            if self.projection:
                frame, _, sx, sy, ox, oy = self.projection
                center = self.building.footprint.center
                bounds = rotate(
                    affine_transform(bounds, [sx, 0, 0, sy, ox, oy]),
                    frame["rotation"],
                    origin=(center.x, center.y),
                )
            plate, free = self.surfaces
            raw = plate.buffer(1e-7).intersection(bounds.buffer(1e-7))
            self.domains[room.id] = raw, raw.intersection(free)
        return self.domains[room.id]

    def threshold(self, room, door):
        point = self.s.Point(xy(self.scene.portals[door]["center"]))
        raw, free = self.space(room)
        if not raw.covers(point):
            return dict(
                code="door_outside_realized_space",
                space_id=room.id,
                door_id=door,
                door_xy_m=list(point.coords[0]),
                distance_to_space_m=round(point.distance(raw), 4) if not raw.is_empty else None,
            )
        if not free.covers(point):
            indices = self.barrier_index.query(point, predicate="dwithin", distance=RADIUS)
            return dict(
                code="door_clearance_blocked",
                space_id=room.id,
                door_id=door,
                door_xy_m=list(point.coords[0]),
                obstacle_ids=sorted(self.barrier_ids[i] for i in indices),
            )
        return None

    def door_center(self, door):
        return xy(self.scene.portals[door]["center"])

    def corridor_route(self, room, door, neighbor):
        queue = deque([(neighbor, door, [door], [self.door_center(door)])])
        visited = {(neighbor, door)}
        failures = []
        while queue:
            node, incoming, doors, path = queue.popleft()
            if node == self.entrance:
                # A displaced exterior portal inside the mass is not an exit.
                # Use the compiler's 15 cm allowance for a wall-centred threshold.
                if self.surfaces[0].boundary.distance(self.s.Point(path[-1])) > 0.15 + 1e-7:
                    failures.append(dict(code="exit_inside_floor_plate", door_id=incoming))
                    continue
                return {"status": "verified", "door_ids": doors, "polyline_xy_m": path}
            space = self.by_node.get(node)
            if space is None or space.function not in CIRCULATION:
                failures.append(
                    dict(
                        code="no_public_circulation",
                        door_id=incoming,
                        space_id=node.removeprefix("nav_"),
                    )
                )
                continue
            raw, free = self.space(space)
            for nxt, outgoing in self.scene.door_links[node]:
                if outgoing == incoming or nxt == "nav_" + room.id or (nxt, outgoing) in visited:
                    continue
                target = self.by_node.get(nxt)
                if nxt != self.entrance and (not target or target.function not in CIRCULATION):
                    continue
                failure = self.threshold(space, incoming) or self.threshold(space, outgoing)
                if failure is None:
                    a, b = self.door_center(incoming), self.door_center(outgoing)
                    try:
                        leg = surface_path(free, a, b)
                    except ValueError:
                        parts = polygon_parts(raw)
                        connected = any(
                            p.covers(self.s.Point(a)) and p.covers(self.s.Point(b)) for p in parts
                        )
                        failure = dict(
                            code="walkable_corridor_disconnected"
                            if connected
                            else "floor_plate_disconnected",
                            space_id=space.id,
                            raw_components=len(parts),
                            walkable_components=len(polygon_parts(free)),
                        )
                if failure:
                    failures.append(dict(**failure, incoming_door=incoming, outgoing_door=outgoing))
                    continue
                visited.add((nxt, outgoing))
                queue.append((nxt, outgoing, doors + [outgoing], path + leg[1:]))
        return {"status": "unverified", "failures": failures or [dict(code="no_compiled_exit_chain")]}

    def audit(self, room):
        if room.id in self.reports:
            return self.reports[room.id]
        doors = [d for d in self.floor.doors if room.id in (d.room_a_id, d.room_b_id)]
        node = "nav_" + room.id
        links = set(self.scene.door_links[node])
        rows = []
        for door in doors:
            other = door.room_b_id if room.id == door.room_a_id else door.room_a_id
            neighbor = self.entrance if other is None else "nav_" + other
            if envelope_config(self.building):
                failure = dict(code="exterior_only_envelope")
            elif self.floor.level != 0:
                failure = dict(code="needs_vertical_route")
            elif (neighbor, door.id) not in links or node not in self.scene.nodes:
                failure = dict(code="missing_or_impassable_portal")
            elif self.surfaces[0].is_empty:
                failure = dict(code="missing_compiled_floor_plate")
            else:
                failure = self.threshold(room, door.id)
            result = (
                {"status": "unverified", "failures": [failure]}
                if failure
                else self.corridor_route(room, door.id, neighbor)
            )
            rows.append({"door_id": door.id, **result})
        report = dict(
            building_id=self.building.id,
            floor_id=self.floor.id,
            room_id=room.id,
            doors=rows,
            status="verified" if rows and all(r["status"] == "verified" for r in rows) else "unverified",
        )
        if not rows:
            report["reason"] = "no_planned_room_door"
        self.reports[room.id] = report
        return report

    def approach(self, room):
        report = self.audit(room)
        paths = [r for r in report["doors"] if r["status"] == "verified"]
        if not paths:
            reason = next(
                (f["code"] for r in report["doors"] for f in r["failures"]), report.get("reason")
            )
            raise ValueError(f"No verified corridor from {room.id} to building entrance: {reason}")
        raw, free = self.space(room)
        node = xy(self.scene.nodes["nav_" + room.id]["position"])
        if not free.covers(self.s.Point(node)):
            parts = polygon_parts(free.intersection(raw.buffer(-RADIUS)))
            if not parts:
                raise ValueError("No standing point in " + room.id)
            node = max(parts, key=lambda part: part.area).representative_point().coords[0]
        for path in paths:
            try:
                leg = surface_path(free, node, path["polyline_xy_m"][0])
            except ValueError:
                continue
            return leg + path["polyline_xy_m"][1:], path["door_ids"]
        raise ValueError("Room standing point disconnected from verified doors in " + room.id)
