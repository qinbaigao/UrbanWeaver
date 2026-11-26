"""Metric room-design constraints, independent of LLMs and rendering.

Rectangular planning-frame walls and conservative AABB use envelopes. Navigation
is a finite-resolution clearance test, not building-code/robot certification.
"""
from collections import deque
import math

from cityg.schemas import Bounds2D, Point2D


AXIS_ANGLES = {"+X": 0, "+Y": 90, "-X": 180, "-Y": -90}
WALL_DEFAULTS = {"bed", "wardrobe", "cabinet", "bookcase", "tv_console",
                 "storage_rack", "equipment_cabinet", "kitchen_counter", "refrigerator", "oven", "shower"}
STORAGE = {"wardrobe", "cabinet", "bookcase", "tv_console", "storage_rack",
           "equipment_cabinet", "kitchen_counter", "refrigerator", "oven"}
CHAIRS = {"office_chair", "meeting_chair", "dining_chair"}


# Both placement and post-placement reachability use the same wall-face clearance.
ROOM_WALL_INSET_M = 0.12

def direction(obj, axis=None):
    angle = math.radians(obj.rotation_deg + AXIS_ANGLES[axis or obj.metadata.get("front_axis", "+Y")])
    return math.cos(angle), math.sin(angle)


def contact_axis(obj, contact="auto"):
    if contact == "head" or (contact == "auto" and obj.category == "bed"):
        return obj.metadata.get("head_axis", "+Y")
    front = obj.metadata.get("front_axis", "+Y")
    return {"+X":"-X", "-X":"+X", "+Y":"-Y", "-Y":"+Y"}[front]


def placement_policy(group):
    policy = {"mode":"auto", "wall":"auto", "contact":"auto", "max_gap_m":.20,
              **group.get("placement", {})}
    if policy["mode"] == "auto":
        policy["mode"] = "wall" if group["anchor"]["category"] in WALL_DEFAULTS else "free"
    return policy


def wall_segments(floor, room):
    """Expose stable wall IDs and door-free spans in the canonical room frame."""
    b = room.bounds
    spans = {"north":(b.min_x,b.max_x,b.max_y), "south":(b.min_x,b.max_x,b.min_y),
             "east":(b.min_y,b.max_y,b.max_x), "west":(b.min_y,b.max_y,b.min_x)}
    holes = {side:[] for side in spans}
    for door in floor.doors:
        if room.id not in (door.room_a_id,door.room_b_id):
            continue
        side = min(spans, key=lambda s:abs((door.position.y if s in ("north","south") else door.position.x)-spans[s][2]))
        tangent = door.position.x if side in ("north","south") else door.position.y
        holes[side].append((tangent-door.width_m/2-.12,tangent+door.width_m/2+.12))
    result = []
    for side, (start,end,boundary) in spans.items():
        available = [(start,end)]
        for lo,hi in sorted(holes[side]):
            available = [(a,min(z,lo)) for a,z in available if a<lo] + [(max(a,hi),z) for a,z in available if z>hi]
        for i,(a,z) in enumerate(available):
            if z-a>.1:
                result.append({"id":f"{room.id}:wall:{side}:{i}", "side":side,
                               "start":a, "end":z, "boundary":boundary,
                               "geometry_source":"planned_rectangle"})
    return result


def wall_contact(obj, room, policy):
    cx,cy = direction(obj,contact_axis(obj,policy.get("contact","auto")))
    side = ("east" if cx>0 else "west") if abs(cx)>abs(cy) else ("north" if cy>0 else "south")
    b,r = obj.bounds,room.bounds
    gap = {"north":r.max_y-b.max_y,"south":b.min_y-r.min_y,
           "east":r.max_x-b.max_x,"west":b.min_x-r.min_x}[side]
    return side,gap


def _strip(obj, axis, depth, width=None):
    dx,dy = axis
    bounds = obj.bounds
    extent = (abs(dx)*bounds.width+abs(dy)*bounds.depth)/2
    width = width or (abs(dy)*bounds.width+abs(dx)*bounds.depth)
    x,y = obj.position.x+dx*(extent+depth/2),obj.position.y+dy*(extent+depth/2)
    sx,sy = abs(dx)*depth+abs(dy)*width,abs(dy)*depth+abs(dx)*width
    return Bounds2D(x-sx/2,y-sy/2,x+sx/2,y+sy/2)


def use_envelopes(obj):
    """Return alternative access regions; bed needs at least one usable side."""
    front = direction(obj)
    if obj.category == "bed":
        right = (front[1],-front[0])
        # Meshes may face local X or Y. Local depth is not necessarily the
        # head-to-foot length; measure along the semantic front in room space.
        length = abs(front[0])*obj.bounds.width + abs(front[1])*obj.bounds.depth
        return [_strip(obj,right,.60,min(length,1.2)),
                _strip(obj,(-right[0],-right[1]),.60,min(length,1.2))]
    if obj.category in CHAIRS:
        width = abs(front[1])*obj.bounds.width + abs(front[0])*obj.bounds.depth
        return [_strip(obj,(-front[0],-front[1]),.65,max(.55,width))]
    if obj.category in {"sofa","waiting_bench"}:
        return [_strip(obj,front,.45),_strip(obj,(front[1],-front[0]),.55),
                _strip(obj,(-front[1],front[0]),.55)]
    if obj.category in {"desk","meeting_table","dining_table","coffee_table","workbench","bedside_table"}:
        return [_strip(obj,axis,.55) for axis in (front,(-front[0],-front[1]),
                                                 (front[1],-front[0]),(-front[1],front[0]))]
    depth = .75 if obj.category in STORAGE else .55
    return [_strip(obj,front,depth)]


def usable_envelopes(obj, objects, usable):
    # Tables are approached through their chairs; a coffee table can be shared
    # with its sofa. Do not exempt cabinet opening or chair pull-back spaces.
    table = obj.category in {"desk","meeting_table","dining_table","coffee_table","workbench"}
    result = []
    for area in use_envelopes(obj):
        if not usable.contains_bounds(area):
            continue
        blockers = [other for other in objects if other.id!=obj.id and not (
            table and other.metadata.get("group_id")==obj.metadata.get("group_id"))]
        if not any(area.overlaps_area(other.bounds) for other in blockers):
            result.append(area)
    return result


def group_relation_cost(relations, objects):
    anchors = {o.metadata.get("group_key"):o for o in objects if o.id==o.metadata.get("group_anchor_id")}
    cost = 0.0
    for rule in relations:
        a,b = anchors.get(rule["subject"]),anchors.get(rule["target"])
        if a is None or b is None:
            continue
        dx,dy = b.position.x-a.position.x,b.position.y-a.position.y
        distance = math.hypot(dx,dy)
        penalty = max(0,rule["min_distance_m"]-distance,distance-rule["max_distance_m"])
        if rule["relation"] == "faces":
            fx,fy = direction(a)
            cosine = (fx*dx+fy*dy)/max(distance,1e-6)
            penalty += max(0,.94-cosine)*3
        elif rule["relation"] == "aligned":
            fx,fy = direction(a)
            penalty += max(0,abs(fx*dy-fy*dx)-.25)
        if rule["required"] and penalty>1e-6:
            return None
        cost += penalty*penalty
    return cost


def circulation_check(objects, room, floor, usable, *, width_m=.55, step_m=.25):
    """Conservative 4-connected graph for a square clearance footprint.

    Every door approach and each furniture access region must touch the same
    component. With no door, only within-room connectivity can be established.
    """
    half = width_m/2
    inner = usable.inset(half)
    if inner.width<=0 or inner.depth<=0:
        return {"ok":False, "reason":"room narrower than circulation footprint"}
    nx = max(1,math.ceil(inner.width/step_m)); ny = max(1,math.ceil(inner.depth/step_m))
    # Very large room inputs must not create an unbounded navigation grid.
    if (nx+1)*(ny+1)>20000:
        return {"ok":False, "reason":"circulation grid budget exceeded"}
    dx,dy = inner.width/nx,inner.depth/ny
    def point(i,j): return Point2D(inner.min_x+i*dx,inner.min_y+j*dy)
    inflated = [Bounds2D(o.bounds.min_x-half,o.bounds.min_y-half,
                         o.bounds.max_x+half,o.bounds.max_y+half) for o in objects]
    def free(p): return not any(b.contains_point(p,tolerance=-1e-6) for b in inflated)
    nodes = {(i,j):point(i,j) for i in range(nx+1) for j in range(ny+1) if free(point(i,j))}
    if not nodes: return {"ok":False, "reason":"no traversable floor area"}
    doors = [d for d in floor.doors if room.id in (d.room_a_id,d.room_b_id)]
    door_nodes = []
    for door in doors:
        if door.width_m<width_m:
            return {"ok":False, "reason":"door narrower than circulation footprint"}
        target = min(nodes,key=lambda n:math.hypot(nodes[n].x-door.position.x,nodes[n].y-door.position.y))
        if math.hypot(nodes[target].x-door.position.x,nodes[target].y-door.position.y)>width_m+.3:
            return {"ok":False, "reason":f"blocked door approach: {door.id}"}
        door_nodes.append(target)
    start = door_nodes[0] if door_nodes else next(iter(nodes))
    queue,seen = deque([start]),{start}
    while queue:
        i,j = queue.popleft()
        for nxt in ((i-1,j),(i+1,j),(i,j-1),(i,j+1)):
            if nxt not in nodes or nxt in seen: continue
            # Check the whole cardinal edge, not just endpoints, so even a
            # thin divider between samples remains an obstacle.
            a,b = nodes[(i,j)],nodes[nxt]
            segment = Bounds2D(min(a.x,b.x)-half,min(a.y,b.y)-half,
                               max(a.x,b.x)+half,max(a.y,b.y)+half)
            if any(segment.overlaps_area(o.bounds) for o in objects): continue
            seen.add(nxt); queue.append(nxt)
    if any(n not in seen for n in door_nodes):
        return {"ok":False, "reason":"door approaches are disconnected"}
    for obj in objects:
        if obj.category in {"desk","meeting_table","dining_table"} and any(
            o.category in CHAIRS and o.metadata.get("group_id")==obj.metadata.get("group_id") for o in objects):
            # The chair's reachable pull-back region is the table's access.
            continue
        areas = usable_envelopes(obj,objects,usable)
        if not any(area.contains_point(nodes[n]) for area in areas for n in seen):
            return {"ok":False, "reason":f"unreachable use space: {obj.id}"}
    return {"ok":True,"reason":"door approaches and use spaces connected",
            "door_count":len(doors),"entrance_verified":bool(doors),"clearance_width_m":width_m,
            "grid_step_m":step_m,"reachable_nodes":len(seen)}
