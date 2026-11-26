"""Bounded topology-first rectangular floor solver.

Solves only an explicit semantic program.  Geometry and doors share the same
rectangles; all hard requirements are rechecked before a transaction commits.
No object count reduction or hidden relaxation is used to claim success.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import itertools
import math

from cityg.planning.spatial_program import FloorSpatialProgram, SpaceRequirement
from cityg.schemas import Bounds2D, Door, Floor, Point2D, Room


class SpatialLayoutInfeasible(ValueError):
    pass


def shared_boundary(a: Bounds2D, b: Bounds2D):
    """axis along wall, normal coordinate, start and end; None for corners."""
    for first, second, axis, start, end in (
        (a.max_y, b.min_y, "x", max(a.min_x, b.min_x), min(a.max_x, b.max_x)),
        (a.min_y, b.max_y, "x", max(a.min_x, b.min_x), min(a.max_x, b.max_x)),
        (a.max_x, b.min_x, "y", max(a.min_y, b.min_y), min(a.max_y, b.max_y)),
        (a.min_x, b.max_x, "y", max(a.min_y, b.min_y), min(a.max_y, b.max_y)),
    ):
        if abs(first - second) < 1e-6 and end - start > 1e-6:
            return axis, first, start, end
    return None


def _merge(program):
    parents = {s.key: s.key for s in program.spaces}

    def find(key):
        while parents[key] != key:
            key = parents[key]
        return key

    for s in program.spaces:
        for target in s.merge_with:
            parents[find(target)] = find(s.key)
    buckets = {}
    for s in program.spaces:
        buckets.setdefault(find(s.key), []).append(s)
    aliases = {s.key: members[0].key for members in buckets.values() for s in members}
    aliases["circulation"] = "circulation"
    result = []
    for members in buckets.values():
        first = members[0]
        via = {aliases[s.access_via] for s in members} - {first.key}
        if len(via) != 1:
            raise SpatialLayoutInfeasible("merged spaces have incompatible access anchors")
        def refs(name):
            return tuple(sorted({aliases[k] for s in members for k in getattr(s, name)} - {first.key}))
        if any(aliases[k] == first.key for s in members for k in s.separate_from):
            raise SpatialLayoutInfeasible("merged spaces are required to remain separate")
        result.append(replace(
            first, target_area_m2=sum(s.target_area_m2 for s in members),
            min_area_m2=sum(s.min_area_m2 for s in members),
            max_area_m2=sum(s.max_area_m2 for s in members),
            capacity=sum(s.capacity for s in members), access_via=next(iter(via)),
            daylight="required" if any(s.daylight == "required" for s in members) else first.daylight,
            near_entrance=any(s.near_entrance for s in members),
            adjacent_to=refs("adjacent_to"), separate_from=refs("separate_from"), merge_with=(),
        ))
    return result, aliases


def _allocate(total, weights, lower, upper):
    """Bounded proportional allocation, without silently violating minimums."""
    if any(lo > hi+1e-6 for lo,hi in zip(lower,upper)):
        raise SpatialLayoutInfeasible('A room has an empty feasible width interval; revise topology or hard bounds')
    if total < sum(lower) - 1e-6 or total > sum(upper) + 1e-6:
        raise SpatialLayoutInfeasible(
            f"area/width budget cannot satisfy space bounds: available frontage={total:.3f}m, "
            f"sum minimum widths={sum(lower):.3f}m, sum maximum widths={sum(upper):.3f}m, "
            f"per-space width intervals={list(zip(lower, upper))}. "
            "Space area ranges must collectively cover the entire band; each interval must be nonempty.")
    low, high = 0.0, max(u / w for u, w in zip(upper, weights)) + 1
    for _ in range(70):
        scale = (low + high) / 2
        values = [min(u, max(l, w * scale)) for w, l, u in zip(weights, lower, upper)]
        if sum(values) < total:
            low = scale
        else:
            high = scale
    return [min(u, max(l, w * high)) for w, l, u in zip(weights, lower, upper)]


def _width_interval(s, depth, total_width, min_width, max_aspect, max_depth):
    enclosed = s.enclosure == 'closed'
    if depth < min_width-1e-6 or (enclosed and depth > max_depth+1e-6):
        raise SpatialLayoutInfeasible(
            f'room depth outside geometry contract for {s.key}: actual band depth={depth:.3f}m, '
            f'minimum width/depth={min_width:.3f}m, maximum enclosed depth={max_depth:.3f}m. '
            'Access groups divide the band into anchor and child strips; BOTH must fit.')
    return (max(min_width,s.min_area_m2/depth,depth/max_aspect if enclosed else 0),
            min(s.max_area_m2/depth,depth*max_aspect if enclosed else total_width))


def _strip(rect, spaces, min_width, max_aspect, max_depth):
    if not spaces:
        raise SpatialLayoutInfeasible("empty room band")
    depth = rect.depth
    lower, upper = [], []
    for s in spaces:
        lo,hi = _width_interval(s,depth,rect.width,min_width,max_aspect,max_depth)
        lower.append(lo); upper.append(hi)
    widths = _allocate(rect.width, [s.target_area_m2 for s in spaces], lower, upper)
    x, boxes = rect.min_x, {}
    for s, width in zip(spaces, widths):
        boxes[s.key] = Bounds2D(x, rect.min_y, x + width, rect.max_y)
        x += width
    return boxes


def _groups(spaces, family):
    if family == "double_loaded":
        if any(s.access_via != "circulation" for s in spaces):
            raise SpatialLayoutInfeasible("double_loaded requires direct circulation access")
        return [[s] for s in spaces]
    roots = [s for s in spaces if s.access_via == "circulation"]
    result = [[r] + [s for s in spaces if s.access_via == r.key] for r in roots]
    if sum(map(len, result)) != len(spaces):
        raise SpatialLayoutInfeasible("only one-level access groups are currently supported")
    if family == "residential_clusters":
        for group in result:
            if len(group) > 1 and (not group[0].group or any(s.group != group[0].group for s in group)):
                raise SpatialLayoutInfeasible("dwelling rooms must share an explicit group")
    if family == "open_office" and not any(s.enclosure == "open" for s in roots):
        raise SpatialLayoutInfeasible("open_office requires an open anchor")
    return result


def _place_band(rect, groups, near_min_y, min_width, max_aspect, max_depth, variant):
    pseudo = []
    for group in groups:
        anchor,*children=group
        if not children:
            pseudo.append(anchor); continue
        fraction=anchor.target_area_m2/sum(s.target_area_m2 for s in group)
        front=rect.depth*min(.70,max(.25,fraction+variant))
        front=min(rect.depth-min_width,max(min_width,front))
        back=rect.depth-front
        lo,hi=_width_interval(anchor,front,rect.width,min_width,max_aspect,max_depth)
        intervals=[_width_interval(s,back,rect.width,min_width,max_aspect,max_depth) for s in children]
        lo=max(lo,sum(q[0] for q in intervals)); hi=min(hi,sum(q[1] for q in intervals))
        if lo>hi+1e-6:
            raise SpatialLayoutInfeasible(f'access group {anchor.key} has no feasible frontage: '
                f'min={lo:.3f}m max={hi:.3f}m; revise child count, weights or topology')
        pseudo.append(replace(anchor,target_area_m2=sum(s.target_area_m2 for s in group),
            min_area_m2=lo*rect.depth,max_area_m2=hi*rect.depth,enclosure='open'))
    cells = _strip(rect, pseudo, min_width, max_aspect, max_depth)
    boxes = {}
    for group in groups:
        anchor, *children = group
        cell = cells[anchor.key]
        if not children:
            boxes.update(_strip(cell, [anchor], min_width, max_aspect, max_depth))
            continue
        # Anchor shares the public spine; children form a private rear strip.
        # Area ratios determine depth; a few bounded alternatives aid feasibility.
        fraction = anchor.target_area_m2 / sum(s.target_area_m2 for s in group)
        anchor_depth = cell.depth * min(.70, max(.25, fraction + variant))
        anchor_depth = min(cell.depth - min_width, max(min_width, anchor_depth))
        cut = cell.min_y + anchor_depth if near_min_y else cell.max_y - anchor_depth
        front = Bounds2D(cell.min_x, cell.min_y if near_min_y else cut,
                         cell.max_x, cut if near_min_y else cell.max_y)
        back = Bounds2D(cell.min_x, cut if near_min_y else cell.min_y,
                        cell.max_x, cell.max_y if near_min_y else cut)
        boxes.update(_strip(front, [anchor], min_width, max_aspect, max_depth))
        boxes.update(_strip(back, children, min_width, max_aspect, max_depth))
    return boxes


def solve_spatial_floor(program: FloorSpatialProgram, *, floor_id, level, height,
                        footprint, corridor_depth, core_bounds, entrance,
                        min_width=2.4, max_aspect=2.8, max_depth=12.0, circulation_axis='x'):
    from cityg.planning.interior_frame import InteriorFrame
    frame=InteriorFrame(circulation_axis)
    if frame.axis=='y':
        return frame.floor(solve_spatial_floor(program,floor_id=floor_id,level=level,height=height,
            footprint=frame.bounds(footprint),corridor_depth=corridor_depth,
            core_bounds=frame.bounds(core_bounds) if core_bounds else None,entrance=frame.point(entrance),
            min_width=min_width,max_aspect=max_aspect,max_depth=max_depth))
    program.validate()
    spaces, aliases = _merge(program)
    groups = _groups(spaces, program.family)
    center = core_bounds.center.y if core_bounds else footprint.center.y
    low, high = center - corridor_depth / 2, center + corridor_depth / 2
    if core_bounds:
        low, high = min(low, core_bounds.min_y), max(high, core_bounds.max_y)
    corridor = Bounds2D(footprint.min_x, low, footprint.max_x, high)
    if not footprint.contains_bounds(corridor) or (core_bounds and not corridor.contains_bounds(core_bounds)):
        raise SpatialLayoutInfeasible("core/circulation does not fit the actual plate")
    north = Bounds2D(footprint.min_x, high, footprint.max_x, footprint.max_y)
    south = Bounds2D(footprint.min_x, footprint.min_y, footprint.max_x, low)
    if min(north.depth, south.depth) < min_width:
        raise SpatialLayoutInfeasible("insufficient room depth around fixed circulation/core")
    usable_area = north.area + south.area
    minimum_area = sum(s.min_area_m2 for s in spaces)
    maximum_area = sum(s.max_area_m2 for s in spaces)
    if not minimum_area-1e-6 <= usable_area <= maximum_area+1e-6:
        raise SpatialLayoutInfeasible(
            f"floor area budget infeasible: usable={usable_area:.2f}m2, "
            f"sum min_area_m2={minimum_area:.2f}, sum max_area_m2={maximum_area:.2f}. "
            "Increase/decrease space count or area ranges to cover the full usable plate.")
    # Direct-access single cells always span one of these two room bands.
    # Name intrinsically impossible cells before enumerating many partitions.
    for group in groups:
        if len(group) != 1:
            continue
        space = group[0]
        if all(space.max_area_m2 < band.depth*min_width-1e-6 for band in (north, south)):
            raise SpatialLayoutInfeasible(
                f"space {space.key} maximum area={space.max_area_m2:.2f}m2 is smaller than "
                f"minimum width {min_width:.2f}m x band depth {min(north.depth,south.depth):.2f}m. "
                "Revise this space's area bounds, the global minimum width, or its supported access group.")

    # Candidate assignments differ in side, sequence and anchor depth.  Bounded
    # deterministic search, not LLM-generated raw coordinates or random jitter.
    orders = [groups, list(reversed(groups)),
              sorted(groups, key=lambda g: -sum(s.target_area_m2 for s in g))]
    best, errors, attempts = None, set(), 0
    for order in orders:
        for split in range(1, len(order)):
            for variant in (0.0, -.10, .10):
                attempts += 1
                try:
                    boxes = _place_band(north, order[:split], True, min_width, max_aspect, max_depth, variant)
                    boxes.update(_place_band(south, order[split:], False, min_width, max_aspect, max_depth, variant))
                    result = _assemble(program, spaces, aliases, boxes, corridor, footprint,
                                       floor_id, level, height, entrance)
                    # Compare to a common area-budget scale. Sum(log(area/target))
                    # wrongly rewards concentrating all excess area in one room.
                    scale = (footprint.area-corridor.area) / sum(s.target_area_m2 for s in spaces)
                    deviations = [abs(boxes[s.key].area/(s.target_area_m2*scale)-1) for s in spaces]
                    score = sum(d*d for d in deviations) + max(deviations)**2
                    for s in spaces:
                        if s.near_entrance:
                            p = boxes[s.key].center
                            score += .25 * math.hypot(p.x - entrance.x, p.y - entrance.y) / max(footprint.width, footprint.depth)
                        if s.daylight == "preferred" and not _facade(boxes[s.key], footprint):
                            score += 1
                    if best is None or score < best[0]:
                        best = score, result
                except SpatialLayoutInfeasible as exc:
                    errors.add(str(exc))
    if best is None:
        samples = sorted(errors)[:3]
        raise SpatialLayoutInfeasible(("; ".join(samples) +
            (f"; {len(errors)-3} additional candidate failures omitted" if len(errors)>3 else ''))
            or "need at least two independent access groups")
    floor = best[1]
    floor.metadata["spatial_layout"].update(candidate_count=attempts, objective=round(best[0], 5),
        target_area_scale=round((footprint.area-corridor.area)/sum(s.target_area_m2 for s in spaces), 4))
    return floor


def _facade(box, plate):
    return any(abs(a-b) < 1e-6 for a,b in zip(
        (box.min_x, box.min_y, box.max_x, box.max_y),
        (plate.min_x, plate.min_y, plate.max_x, plate.max_y)))


def _assemble(program, spaces, aliases, boxes, corridor, plate, floor_id, level, height, entrance):
    ids = {key: f"{floor_id}_space_{key}" for key in boxes}
    ids["circulation"] = f"{floor_id}_corridor"
    boxes = {**boxes, "circulation": corridor}
    rooms = [Room(ids["circulation"], "Public circulation", "corridor", corridor,
                  height_m=height, metadata={"corridor_role": "central"})]
    doors, graph = [], []
    for s in spaces:
        box = boxes[s.key]
        if not plate.contains_bounds(box) or not s.min_area_m2 - 1e-5 <= box.area <= s.max_area_m2 + 1e-5:
            raise SpatialLayoutInfeasible(f"area/boundary requirement failed: {s.key}")
        if s.daylight == "required" and not _facade(box, plate):
            raise SpatialLayoutInfeasible(f"facade access required: {s.key}")
        for target in s.adjacent_to:
            if not shared_boundary(box, boxes[target]):
                raise SpatialLayoutInfeasible(f"required adjacency failed: {s.key}/{target}")
        for target in s.separate_from:
            if shared_boundary(box, boxes[target]):
                raise SpatialLayoutInfeasible(f"required separation failed: {s.key}/{target}")
        rooms.append(Room(ids[s.key], s.key.replace("_", " ").title(), s.function, box,
                          height_m=height, metadata={
                              "space_requirement_keys": [k for k,v in aliases.items() if v == s.key],
                              "space_group_id": f"{floor_id}_{s.group}" if s.group else ids[s.key],
                              "unit_id": f"{floor_id}_{s.group}" if s.group and program.family == "residential_clusters" else None,
                              "space_kind": "open_plan" if s.enclosure == "open" else "enclosed_room",
                              "open_plan": s.enclosure == "open", "requires_facade": s.daylight == "required",
                              "spatial_requirement": asdict(s), "realized_area_m2": box.area,
                          }))
        shared = shared_boundary(box, boxes[s.access_via])
        if shared is None or shared[3] - shared[2] < 1.5:
            raise SpatialLayoutInfeasible(f"door cannot fit access edge: {s.key}/{s.access_via}")
        axis, boundary, start, end = shared
        point = Point2D((start+end)/2, boundary) if axis == "x" else Point2D(boundary, (start+end)/2)
        doors.append(Door(f"{ids[s.key]}_door", ids[s.key], ids[s.access_via], point))
        graph.append({"from": s.key, "to": s.access_via, "door_id": doors[-1].id})
    for a, b in itertools.combinations(rooms, 2):
        if a.bounds.overlaps_area(b.bounds):
            raise SpatialLayoutInfeasible("room overlap")
    if abs(sum(r.bounds.area for r in rooms) - plate.area) > 1e-4:
        raise SpatialLayoutInfeasible("incomplete floor coverage")
    if level == 0:
        # Do not pretend that a north/south entrance is on the horizontal spine.
        owners = [r for r in rooms if r.bounds.contains_point(entrance) and min(
            abs(entrance.x-r.bounds.min_x), abs(entrance.x-r.bounds.max_x),
            abs(entrance.y-r.bounds.min_y), abs(entrance.y-r.bounds.max_y)) < 1e-5]
        if not owners:
            raise SpatialLayoutInfeasible("exterior entrance outside realized plate")
        owner = min(owners, key=lambda r: (r.function != "corridor", -r.bounds.area))
        # Require corner clearance on the actual owning edge, not a shifted door.
        tangent = (entrance.y-owner.bounds.min_y, owner.bounds.max_y-entrance.y) if abs(entrance.x-plate.min_x)<1e-5 or abs(entrance.x-plate.max_x)<1e-5 else (entrance.x-owner.bounds.min_x, owner.bounds.max_x-entrance.x)
        if min(tangent) < 1.0:
            raise SpatialLayoutInfeasible("exterior entrance too close to a partition")
        doors.append(Door(f"{floor_id}_entrance", owner.id, None, entrance, width_m=1.6, door_type="exterior"))
    return Floor(floor_id, level, level*height, height, rooms, doors, metadata={
        "layout_topology": program.family, "layout_template": program.family,
        "spatial_layout": {"status": "accepted", "version": 1, "family": program.family,
                           "requirements": asdict(program), "bindings": {k: ids[v] for k,v in aliases.items()},
                           "access_graph": graph, "realized_room_count": len(spaces),
                           "merged_space_count": len(program.spaces)-len(spaces)},
    })
