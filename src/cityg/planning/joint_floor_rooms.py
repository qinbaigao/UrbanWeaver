"""Bounded room-reference-aware partitions of empty rectangular floor regions.

Metric dimensions, no asset scaling. Keep the old room ID on the remainder
containing ALL old doors. Optional new side circulation never replaces an old
corridor or core. Unfurnished remainders are explicit, not prototype successes.
"""
from cityg.schemas import Bounds2D, Door, Point2D, Room
from cityg.planning.prototype_adaptation import door_side, SIDES


def frontage_interval(record, depth, height):
    fit = record['applicability']
    if not fit['depth_m'][0] <= depth <= fit['depth_m'][1] or height < fit['min_height_m']:
        return None
    lo = max(fit['width_m'][0], fit['area_m2'][0]/depth, fit['aspect_ratio'][0]*depth)
    hi = min(fit['width_m'][1], fit['area_m2'][1]/depth, fit['aspect_ratio'][1]*depth)
    return (lo, hi) if lo <= hi else None


def _holds_doors(bounds, doors):
    # Test boundary AND corner clearance; containment of the center is not enough.
    try:
        for door in doors:
            door_side(type('MetricRoom', (), {'bounds': bounds})(), door)
        return True
    except ValueError:
        return False


def joint_split(room, envelope, corridor_id, seam, library, reference, opt, variation):
    axis, edge, _, _ = seam; b = envelope['bounds']; old_doors = envelope['floor'].doors
    lo, hi, depth = (b.min_x, b.max_x, b.depth) if axis == 'x' else (b.min_y, b.max_y, b.width)
    records = [r for _, r in sorted(library.rooms.items()) if r['room_type'] == room.function]
    reference_id=reference['id']
    hints={hint for space in reference['spaces'] if space['function']==room.function
           for hint in space.get('room_reference_hints',[])}
    if not records:
        return None
    cap = opt['max_children_per_room']; minimum = opt['min_room_width_m']
    original_aspect = max(b.width/b.depth, b.depth/b.width)

    def rectangle(a, z, v0=None, v1=None):
        if axis == 'x':
            return Bounds2D(a, b.min_y if v0 is None else v0, z, b.max_y if v1 is None else v1)
        return Bounds2D(b.min_x if v0 is None else v0, a, b.max_x if v1 is None else v1, z)

    def sensible(q, coarse=False):
        # A retained coarse remainder may be large, but never more slender than
        # the source. Prototype cells must obey both library and metric bounds.
        limit = max(opt['max_room_aspect'], original_aspect) if coarse else opt['max_room_aspect']
        return min(q.width, q.depth) >= minimum and max(q.width/q.depth, q.depth/q.width) <= limit+1e-6

    def assemble(cells, record, anchor, spine=None):
        if not _holds_doors(cells[anchor], old_doors):
            return None
        sx, sy = envelope['scale']; ox, oy = envelope['offset']
        children = []; new_doors = []; fitted = 0
        cid = room.id+'_access' if spine is not None else corridor_id
        for i, q in enumerate(cells):
            role = 'coarse_remainder' if i == anchor else 'prototype_room'
            rid = room.id if i == anchor else room.id+f'_part_{i:02d}'
            if spine == i:
                role = 'access_corridor'; rid = cid
            if role == 'access_corridor':
                t = q.center.x if axis == 'x' else q.center.y
                pos = Point2D(t, edge) if axis == 'x' else Point2D(edge, t)
                dest = corridor_id
            elif i != anchor:
                if spine is None:
                    side = ('south' if abs(edge-q.min_y)<1e-5 else 'north') if axis == 'x' else (
                        'west' if abs(edge-q.min_x)<1e-5 else 'east')
                else:
                    s = cells[spine]
                    side = ('east' if s.center.x > q.center.x else 'west') if axis == 'x' else (
                        'north' if s.center.y > q.center.y else 'south')
                turns = SIDES.index(side)
                w, d = (q.depth, q.width) if turns % 2 else (q.width, q.depth)
                if not library.compatible(record['id'], room_type=room.function, width_m=w, depth_m=d, height_m=room.height_m):
                    return None
                f = record['reference']['door_fraction']
                t = f if side in ('south', 'east') else 1-f
                pos = (Point2D(q.min_x+t*q.width, q.min_y if side=='south' else q.max_y)
                       if side in ('south','north') else
                       Point2D(q.max_x if side=='east' else q.min_x, q.min_y+t*q.depth))
                dest = cid; fitted += 1
            canonical = Bounds2D((q.min_x-ox)/sx, (q.min_y-oy)/sy, (q.max_x-ox)/sx, (q.max_y-oy)/sy)
            plan = {'role': role, 'parent_function': room.function}
            if role == 'prototype_room':
                plan.update(prototype_id=record['id'], prototype_fingerprint=library.content_fingerprint(record['id']))
            children.append(Room(rid, room.name+f' · {i+1}', 'corridor' if role=='access_corridor' else room.function,
                canonical, room.height_m, metadata={
                    'floor_repartition': {'source_room_id': room.id, 'reference_id': reference_id},
                    'joint_room_plan': plan, 'detail_tier': 'preview'}))
            if i != anchor:
                physical_width = .9 if role=='access_corridor' else record['reference']['door_width_m']
                side = door_side(type('MetricRoom', (), {'bounds': q})(), Door('check',rid,dest,pos,physical_width))
                scale = sx if side in ('south','north') else sy
                new_doors.append(Door(rid+'_entry',rid,dest,Point2D((pos.x-ox)/sx,(pos.y-oy)/sy),physical_width/scale))
        return (children, new_doors) if fitted else None

    proposals = []
    def rank(proposal):
        count, deformation, key, _ = proposal
        return count, key in hints, deformation, key
    for record in records:
        interval = frontage_interval(record, depth, room.height_m)
        if interval is None:
            continue
        low, high = interval
        # Equal cells cover the full source if feasible; preserving old door
        # poses can leave the old-ID cell unbound, while all new cells are bound.
        for n in range(2, cap+1):
            width = (hi-lo)/n
            if low <= width <= high:
                cells = [rectangle(lo+i*width, lo+(i+1)*width) for i in range(n)]
                anchors = [i for i,q in enumerate(cells) if _holds_doors(q,old_doors)]
                if len(anchors)==1 and all(sensible(q) for q in cells):
                    try: result = assemble(cells,record,anchors[0])
                    except ValueError: result = None
                    if result: proposals.append((n-1, 0, record['id'], result))
        # A few fine rooms + explicit remainder; never distort all cells to
        # compensate for one fixed entrance. Candidate widths stay in the library.
        nominal = min(high,max(low,record['reference']['width_m']))
        for width in sorted({nominal, max(low,nominal*(1-variation)), min(high,nominal*(1+variation))}):
            for n in range(1, cap):
                if n*width >= hi-lo-minimum:
                    continue
                for reverse in (False,True):
                    boundary = hi-n*width if reverse else lo+n*width
                    rem = rectangle(lo,boundary) if reverse else rectangle(boundary,hi)
                    start = boundary if reverse else lo
                    cells = [rectangle(start+i*width,start+(i+1)*width) for i in range(n)] + [rem]
                    if not sensible(rem,True) or not all(sensible(q) for q in cells[:-1]):
                        continue
                    try: result = assemble(cells,record,n)
                    except ValueError: result = None
                    if result: proposals.append((n, -abs(width-nominal), record['id'], result))
    if proposals:
        return max(proposals,key=rank)[3]
    if not opt['allow_secondary_corridor']:
        return None
    # Deep plates: a side strip of rooms served by a NEW local access spine.
    # The original room/door remains on the large remainder next to that strip.
    v0,v1 = (b.min_y,b.max_y) if axis=='x' else (b.min_x,b.max_x)
    for record in records:
        fit=record['applicability']; nominal=record['reference']['depth_m']
        depths=sorted({min(fit['depth_m'][1],max(fit['depth_m'][0], nominal*f))
                       for f in (1,1-variation,1+variation)})
        for strip in depths:
            interval=frontage_interval(record,strip,room.height_m)
            if interval is None: continue
            for n in range(1,cap-1):
                width=depth/n
                if not interval[0] <= width <= interval[1]: continue
                for reverse in (False,True):
                    spine_width=opt['secondary_corridor_width_m']
                    if strip+spine_width+minimum >= hi-lo: continue
                    a,z=(hi-strip,hi) if reverse else (lo,lo+strip)
                    s0,s1=(a-spine_width,a) if reverse else (z,z+spine_width)
                    rem=rectangle(lo,s0) if reverse else rectangle(s1,hi)
                    cells=[rectangle(a,z,v0+i*width,v0+(i+1)*width) for i in range(n)]
                    if not sensible(rem,True) or not all(sensible(q) for q in cells):continue
                    cells.extend([rectangle(s0,s1),rem])
                    try: result=assemble(cells,record,n+1,spine=n)
                    except ValueError: result=None
                    if result: proposals.append((n,-abs(strip-nominal),record['id'],result))
    return max(proposals,key=rank)[3] if proposals else None
