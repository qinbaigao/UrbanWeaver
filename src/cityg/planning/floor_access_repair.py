"""Bounded floor revisions grounded in compiled pedestrian breakpoints."""

from copy import deepcopy
from dataclasses import asdict, replace

from shapely.affinity import affine_transform, rotate

from cityg.planning.spatial_layout import shared_boundary
from cityg.polygons import polygon_parts
from cityg.schemas import Point2D
from cityg.serialization import to_primitive
from cityg.transactions import MutationProposal, accept_candidate, refresh_local_overlay
from cityg.validation.floor_access import CIRCULATION
from cityg.validation.walking_geometry import PedestrianScene
from cityg.walking_requirements import bind_endpoint


def _canonical(access, shape):
    if not access.projection:
        return shape
    frame, _, sx, sy, ox, oy = access.projection
    c = access.building.footprint.center
    local = rotate(shape, -frame["rotation"], origin=(c.x, c.y))
    return affine_transform(local, [1 / sx, 0, 0, 1 / sy, -ox / sx, -oy / sy])


def _locked(room):
    return any(
        room.metadata.get(k)
        for k in (
            "locked",
            "protected",
            "room_design",
            "room_finishes",
            "room_decorations",
            "layout_prototype_id",
            "joint_room_plan",
            "floor_repartition",
            "spatial_requirement",
        )
    )


def _door_candidates(access, room, door, corridor, plate):
    edge = shared_boundary(room.bounds, corridor.bounds)
    if edge is None:
        return
    axis, normal, start, end = edge

    def point(t):
        return (t, normal) if axis == "x" else (normal, t)

    span = access.s.LineString([point(start), point(end)])
    # Both jambs must lie on supported floor, away from the corners.
    support = span.intersection(plate.buffer(-0.35))
    lines = [support] if support.geom_type == "LineString" else getattr(support, "geoms", ())
    for line in lines:
        if line.geom_type != "LineString" or line.length < door.width_m + 0.5:
            continue
        margin = door.width_m / 2 + 0.22
        for fraction in (0.5, 0.2, 0.8):
            p = line.interpolate(margin + fraction * (line.length - 2 * margin))
            if p.distance(access.s.Point(door.position.x, door.position.y)) < 0.1:
                continue
            yield {"kind": "move_room_door", "doors": {door.id: {"x": p.x, "y": p.y}}, "bounds": {}}


def _extend_band(access, corridor, axis, side, value):
    # Move a shared partition and its door openings together. Furniture stays in place.
    old_field = side + "_" + axis
    other_field = ("max" if side == "min" else "min") + "_" + axis
    old = getattr(corridor.bounds, old_field)
    transverse = "y" if axis == "x" else "x"
    edited = {corridor.id: replace(corridor.bounds, **{old_field: value})}
    for r in access.floor.rooms:
        if r.id == corridor.id:
            continue
        box = r.bounds
        if not box.overlaps_area(edited[corridor.id]):
            continue
        if (
            _locked(r)
            or r.function in CIRCULATION
            or abs(getattr(box, other_field) - old) > 1e-5
            or getattr(box, "min_" + transverse) < getattr(corridor.bounds, "min_" + transverse) - 1e-5
            or getattr(box, "max_" + transverse) > getattr(corridor.bounds, "max_" + transverse) + 1e-5
        ):
            return None
        revised = replace(box, **{other_field: value})
        if min(revised.width, revised.depth) < 2.4 or revised.area < 0.55 * box.area:
            return None
        if any(
            not revised.contains_bounds(o.bounds) for o in access.floor.objects if o.room_id == r.id
        ):
            return None
        edited[r.id] = revised
    if len(edited) == 1:
        return None
    doors = {}
    for d in access.floor.doors:
        if not {d.room_a_id, d.room_b_id}.intersection(edited):
            continue
        if (
            d.room_b_id is not None
            and corridor.id in (d.room_a_id, d.room_b_id)
            and abs(getattr(d.position, axis) - old) < 1e-5
        ):
            doors[d.id] = asdict(replace(d.position, **{axis: value}))
        p = Point2D(**doors[d.id]) if d.id in doors else d.position
        if any(
            not edited[rid].contains_point(p) for rid in (d.room_a_id, d.room_b_id) if rid in edited
        ):
            return None
    return {
        "kind": "extend_corridor_at_slab_turn",
        "bounds": {k: asdict(v) for k, v in edited.items()},
        "doors": doors,
    }


def _branch_candidates(access, corridor, failure):
    """Carve a shallow return corridor to an exterior door beyond the original band."""
    exits = {d.id: d for d in access.floor.doors if d.room_b_id is None and d.room_a_id == corridor.id}
    exit_id = next(
        (
            f.get("door_id")
            for f in failure.get("failures", [])
            if f.get("code") == "door_outside_realized_space" and f.get("door_id") in exits
        ),
        None,
    )
    if not exit_id:
        return
    door = exits[exit_id]
    p = _canonical(access, access.s.Point(access.door_center(exit_id)))
    for donor in access.floor.rooms:
        edge = shared_boundary(donor.bounds, corridor.bounds)
        if donor.function in CIRCULATION or _locked(donor) or not edge:
            continue
        axis, normal, lo, hi = edge
        extent = donor.bounds
        along = getattr(p, axis)
        if not extent.contains_point(Point2D(p.x, p.y), tolerance=0.1):
            continue
        for side, sign in (("min", 1), ("max", -1)):
            outside = getattr(extent, side + "_" + axis)
            for margin in (1.4, 2.4):
                split = along + sign * margin
                width = (split - outside) * sign
                if width < 1.4 or width > 0.45 * (hi - lo):
                    continue
                other = "max" if side == "min" else "min"
                branch = replace(extent, **{other + "_" + axis: split})
                private = replace(extent, **{side + "_" + axis: split})
                if not branch.contains_point(door.position) or min(private.width, private.depth) < 2.4:
                    continue
                if any(
                    not private.contains_bounds(o.bounds)
                    for o in access.floor.objects
                    if o.room_id == donor.id
                ):
                    continue
                if any(
                    donor.id in (d.room_a_id, d.room_b_id) and not private.contains_point(d.position)
                    for d in access.floor.doors
                ):
                    continue
                branch_id = donor.id + "_access_branch"
                passage_id = branch_id + "_passage"
                if branch_id in access.rooms or any(d.id == passage_id for d in access.floor.doors):
                    continue
                # Place the new public-to-public passage where both sides have slab support.
                line = access.s.LineString(
                    [
                        (getattr(branch, k + "_" + axis), normal)
                        if axis == "x"
                        else (normal, getattr(branch, k + "_" + axis))
                        for k in ("min", "max")
                    ]
                )
                supported = line.intersection(_canonical(access, access.surfaces[0]).buffer(-0.7))
                segments = (
                    [supported]
                    if supported.geom_type == "LineString"
                    else getattr(supported, "geoms", ())
                )
                for segment in segments:
                    if segment.length < 1.6 or segment.geom_type != "LineString":
                        continue
                    entry = segment.interpolate(0.5, normalized=True)
                    yield {
                        "kind": "turn_corridor_to_entrance",
                        "bounds": {donor.id: asdict(private)},
                        "doors": {},
                        "branch": {
                            "id": branch_id,
                            "bounds": asdict(branch),
                            "exit_id": door.id,
                            "corridor_id": corridor.id,
                            "passage_id": passage_id,
                            "position": {"x": entry.x, "y": entry.y},
                        },
                    }


def proposals(access, room, failure):
    floor = access.floor
    if any(
        f["code"]
        in {
            "exterior_only_envelope",
            "needs_vertical_route",
            "missing_compiled_floor_plate",
            "missing_or_impassable_portal",
        }
        for f in failure.get("failures", [])
    ):
        return []
    if (
        room.metadata.get("locked")
        or room.metadata.get("protected")
        or floor.metadata.get("floor_repartition")
    ):
        return []
    rooms = access.rooms
    door = next((d for d in floor.doors if d.id == failure["door_id"]), None)
    other = (door.room_b_id if door and door.room_a_id == room.id else door.room_a_id) if door else None
    corridor = rooms.get(other)
    if corridor is None or corridor.function not in CIRCULATION or _locked(corridor):
        return []
    plate = _canonical(access, access.surfaces[0])
    # Even if the first recorded failure is at the room door, independently check the
    # exit. Moving an interior door cannot bring an exterior portal inside a fixed band.
    exits = [d for d in floor.doors if d.room_b_id is None]
    exit_failure = None
    if len(exits) == 1 and exits[0].room_a_id == corridor.id and exits[0].id in access.scene.portals:
        exit_failure = access.threshold(corridor, exits[0].id)
    outside_exit = exit_failure and exit_failure["code"] == "door_outside_realized_space"
    if outside_exit:
        failure = {**failure, "failures": [exit_failure, *failure.get("failures", [])]}
    door_moves = [] if outside_exit else list(_door_candidates(access, room, door, corridor, plate))
    if floor.metadata.get("spatial_layout", {}).get("status") == "accepted" or _locked(room):
        return door_moves
    band_moves = []
    axis = "y" if corridor.bounds.width >= corridor.bounds.depth else "x"
    index = 1 if axis == "y" else 0
    turns = {
        round(v[index], 5)
        for part in polygon_parts(plate)
        for ring in [part.exterior, *part.interiors]
        for v in ring.coords
    }
    for side, sign in (("min", -1), ("max", 1)):
        edge = getattr(corridor.bounds, side + "_" + axis)
        for turn in sorted(turns, key=lambda v: abs(v - edge)):
            for clearance in (1.2, 2.2):
                value = turn + sign * clearance
                if sign * (value - edge) < 0.3:
                    continue
                move = _extend_band(access, corridor, axis, side, value)
                if move and move not in band_moves:
                    band_moves.append(move)
    disconnected = any(f["code"] == "floor_plate_disconnected" for f in failure.get("failures", []))
    branches = list(_branch_candidates(access, corridor, failure))
    return (branches + (band_moves + door_moves if disconnected else door_moves + band_moves))[:12]


def _checks(access):
    verified = set()
    standing = set()
    for room in access.floor.rooms:
        if room.function in CIRCULATION:
            continue
        verified.update(d["door_id"] for d in access.audit(room)["doors"] if d["status"] == "verified")
        try:
            access.approach(room)
            standing.add(room.id)
        except ValueError:
            pass
    return verified, standing


def _apply(city, floor_id, choice):
    from cityg.schemas import Bounds2D

    floor = next(f for f in city.iter_floors() if f.id == floor_id)
    for r in floor.rooms:
        if r.id in choice["bounds"]:
            r.bounds = Bounds2D(**choice["bounds"][r.id])
            if "realized_area_m2" in r.metadata:
                r.metadata["realized_area_m2"] = r.bounds.area
    for d in floor.doors:
        if d.id in choice["doors"]:
            d.position = Point2D(**choice["doors"][d.id])
    if branch := choice.get("branch"):
        from cityg.schemas import Room, Door

        floor.rooms.append(
            Room(
                branch["id"],
                "Entrance corridor",
                "corridor",
                Bounds2D(**branch["bounds"]),
                floor.height_m,
                metadata={"corridor_role": "entrance_return"},
            )
        )
        exit_door = next(d for d in floor.doors if d.id == branch["exit_id"])
        exit_door.room_a_id = branch["id"]
        floor.doors.append(
            Door(
                branch["passage_id"],
                branch["corridor_id"],
                branch["id"],
                Point2D(**branch["position"]),
                1.2,
                interactive=False,
            )
        )
        floor.metadata["spatial_layout"] = {
            **floor.metadata.get("spatial_layout", {}),
            "status": "accepted",
            "family": "entrance_return",
            "open_boundaries": [[branch["corridor_id"], branch["id"]]],
        }
    return city


def _protected_geometry(access):
    owners = {c.id for c in access.building.vertical_connectors}
    owners.update(d.id for d in access.floor.doors if d.room_b_id is None)
    owners.update(o.id for o in access.floor.objects)
    return {
        p["id"]: (p["center"], p["size"], p["rotation_z_deg"])
        for p in access.scene.primitives
        if p["owner_id"] in owners
    }


def repair_floor_access(city, manifest, compiler, bindings, walks, *, select=None):
    """Return a detached approved city and trace. Failed hypotheses never edit the input."""
    current = city
    scene = PedestrianScene(manifest)
    targets = {}
    for w in walks:
        for side in ("start", "end"):
            try:
                b, f, r = bind_endpoint(city, bindings, w[side])
            except ValueError:
                continue
            if r is not None:
                targets[(b.id, f.id, r.id)] = None
    trace = []
    for bid, fid, rid in targets:
        b = next(b for b in current.iter_buildings() if b.id == bid)
        f = next(f for f in b.floors if f.id == fid)
        access = scene.realized_floor(b, f)
        room = access.rooms[rid]
        report = access.audit(room)
        if not report["doors"]:
            trace.append(
                dict(
                    building_id=bid,
                    floor_id=fid,
                    room_id=rid,
                    status="unresolved",
                    reason="no_planned_room_door",
                    attempts=[],
                )
            )
        bad = [d for d in report["doors"] if d["status"] != "verified"]
        for missed in bad:
            if any(
                d["status"] == "verified" and d["door_id"] == missed["door_id"]
                for d in access.audit(room)["doors"]
            ):
                continue
            choices = proposals(access, room, missed)
            row = {
                "building_id": bid,
                "floor_id": fid,
                "room_id": rid,
                "breakpoint": missed,
                "attempts": [],
                "status": "unresolved",
            }
            trace.append(row)
            scope = current.metadata.get("interior_scope", {})
            if f.level in scope.get("access_dependency_levels", {}).get(bid, []):
                row["reason"] = "access_dependency_only"
                continue
            if not choices:
                row["reason"] = "no_compatible_candidate"
                continue
            order = list(range(len(choices)))
            if select:
                plate = _canonical(access, access.surfaces[0])
                row["geometry"] = {
                    "frame": "canonical planning metres; breakpoint.door_xy_m is world XY",
                    "room_id": rid,
                    "floor_id": fid,
                    "corridor_bounds": {
                        r.id: asdict(r.bounds) for r in f.rooms if r.function in CIRCULATION
                    },
                    "actual_portals": {
                        d.id: list(
                            _canonical(access, access.s.Point(access.door_center(d.id))).coords[0]
                        )
                        for d in access.floor.doors
                        if d.id in access.scene.portals
                        and (d.room_b_id is None or d.id == missed["door_id"])
                    },
                    "room_function": room.function,
                    "room_bounds": asdict(room.bounds),
                    "slab_rings": [
                        {
                            "exterior": [[round(x, 2), round(y, 2)] for x, y in p.exterior.coords],
                            "holes": [list(ring.coords) for ring in p.interiors],
                        }
                        for p in polygon_parts(plate)
                    ],
                }
                preferred = select(row, choices)
                if preferred in order:
                    order.remove(preferred)
                    order.insert(0, preferred)
            preserved, standing = _checks(access)
            locked_geometry = _protected_geometry(access)
            proposal = MutationProposal.bind(
                current,
                [fid],
                source="validation_repair",
                kind="floor_access",
                proposal_id=f"floor_access_{missed['door_id']}_{next(n.version for n in current.world_program.nodes if n.entity_id == fid)}",
            )
            for idx in order:
                choice = choices[idx]
                attempt = {"candidate": idx, "kind": choice["kind"]}
                row["attempts"].append(attempt)
                try:
                    draft = _apply(deepcopy(current), fid, choice)
                    subset = to_primitive(compiler.compile(draft, building_ids={bid}))
                    subset_scene = PedestrianScene(subset)
                    db = next(b for b in draft.iter_buildings() if b.id == bid)
                    df = next(f for f in db.floors if f.id == fid)
                    da = subset_scene.realized_floor(db, df)
                    revised_geometry = _protected_geometry(da)
                    if locked_geometry != revised_geometry:
                        attempt["changed_protected_primitives"] = sorted(
                            k
                            for k in locked_geometry.keys() | revised_geometry.keys()
                            if locked_geometry.get(k) != revised_geometry.get(k)
                        )
                        raise ValueError("compiled exterior portal, core or furniture changed")
                    new, available = _checks(da)
                    if (
                        missed["door_id"] not in new
                        or rid not in available
                        or not preserved <= new
                        or not standing <= available
                    ):
                        attempt["door_check"] = next(
                            d
                            for d in da.audit(da.rooms[rid])["doors"]
                            if d["door_id"] == missed["door_id"]
                        )
                        attempt["lost_doors"] = sorted(preserved - new)
                        attempt["lost_room_access"] = sorted(standing - available)
                        raise ValueError("target route unverified or another room lost access")

                    def revise(candidate):
                        _apply(candidate, fid, choice)
                        refresh_local_overlay(current, candidate, [fid])
                        return candidate

                    accepted = accept_candidate(current, proposal, revise)
                except ValueError as exc:
                    attempt["reason"] = str(exc)
                    continue
                current = accepted.city
                # Other buildings retain their full-manifest evidence. Only replace this floor's cached audit.
                scene.floor_access[fid] = access = da
                room = access.rooms[rid]
                row.update(
                    status="accepted",
                    choice=choice,
                    changed_ids=accepted.report["changed_entity_ids"],
                    witness=next(
                        d for d in da.audit(room)["doors"] if d["door_id"] == missed["door_id"]
                    ),
                )
                break
    return current, trace


def compile_with_access_replanning(city, backend, directory, *, select, preserve_requirements):
    """Validate the full-city candidate before publishing it through the normal USD backend."""
    from cityg.walking_requirements import assess

    contract = city.metadata["walking_contract"]
    bindings, walks = contract["bindings"], contract["requirements"]
    compiler = backend.geometry_compiler
    original_scene = compiler.compile(city)
    original_manifest = to_primitive(original_scene)
    candidate, trace = repair_floor_access(
        city, original_manifest, compiler, bindings, walks, select=select
    )
    revised_scene = original_scene
    accepted = [r for r in trace if r["status"] == "accepted"]
    if accepted:
        try:
            proposed = compiler.compile(candidate)
            geometry = backend.geometry_validator.validate(candidate, proposed)
            if not geometry.ok:
                raise ValueError(str(geometry.errors[:2]))
            manifest = to_primitive(proposed)
            original_rows = assess(city, bindings, walks, original_manifest)
            after = assess(candidate, bindings, walks, manifest)
            for old, new in zip(original_rows, after):
                if old["status"] == "satisfied" and new["status"] != "satisfied":
                    raise ValueError("Previously satisfied walking requirement lost: " + old["id"])
            verified = {
                (v["floor_id"], v["room_id"], d["door_id"])
                for r in after
                for v in r.get("floor_access", {}).values()
                for d in v["doors"]
                if d["status"] == "verified"
            }
            if any(
                (r["floor_id"], r["room_id"], r["breakpoint"]["door_id"]) not in verified
                for r in accepted
            ):
                raise ValueError("Full compilation did not reproduce local door witness")
            if preserve_requirements:
                preserve_requirements(candidate, original_manifest, manifest)
            revised_scene = proposed
        except ValueError as exc:
            for r in accepted:
                r.update(status="rolled_back", reason=str(exc))
            candidate = city
    artifacts = backend.compile(candidate, directory, _scene_override=revised_scene)
    return candidate, artifacts, trace
