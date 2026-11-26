"""Keep furniture dimensions and intra-group poses during building site edits."""
from collections import defaultdict
from dataclasses import replace

from cityg.schemas import Point2D
from cityg.planning.interiors import FloorDetailAgent
from cityg.planning.room_constraints import circulation_check, group_relation_cost, placement_policy, wall_contact, wall_segments
from cityg.planning.room_envelope import metric_envelope
from cityg.planning.room_metric_frame import bind_metric_object, restore_metric_object
from cityg.planning.room_regions import region_bounds, reserved_bounds


class GroupCapacityError(ValueError):
    def __init__(self, room_id, key, required, available):
        self.required = required
        self.available = available
        super().__init__(f'{room_id}: insufficient capacity for furniture group {key}; '
                         f'required width/depth {required[0]:.3f}/{required[1]:.3f} m, '
                         f'available {available[0]:.3f}/{available[1]:.3f} m')


def reposition_groups(objects, before, room, floor):
    design = room.metadata.get('room_design', {})
    groups = defaultdict(list)
    for obj in objects:
        groups[obj.metadata.get('group_key') or obj.id].append(obj)
    bounds = room.bounds
    zones = {z['id']: region_bounds(bounds, z['bounds_uv']) for z in design.get('zones', []) if 'bounds_uv' in z}
    obstacles = reserved_bounds(bounds, design.get('reserved_areas', []))
    obstacles.extend(FloorDetailAgent()._door_clearance_zones(floor, room)[0])
    policies = {g['id']: placement_policy(g) for g in design.get('groups', [])}
    placed = []
    for key, group in groups.items():
        anchor = next((o for o in group if o.id == o.metadata.get('group_anchor_id')), group[0])
        region = zones.get(anchor.metadata.get('zone_id'), bounds.inset(.12))
        x, y = anchor.position.x, anchor.position.y
        lo = region.min_x + max(x-o.bounds.min_x for o in group)
        hi = region.max_x - max(o.bounds.max_x-x for o in group)
        bottom = region.min_y + max(y-o.bounds.min_y for o in group)
        top = region.max_y - max(o.bounds.max_y-y for o in group)
        if lo > hi or bottom > top:
            raise GroupCapacityError(room.id, key, (region.width+lo-hi, region.depth+bottom-top),
                                     (region.width, region.depth))
        aim_x = bounds.min_x + (x-before.min_x)*bounds.width/before.width
        aim_y = bounds.min_y + (y-before.min_y)*bounds.depth/before.depth
        xs = [min(hi,max(lo,aim_x)), *(lo+(hi-lo)*i/8 for i in range(9))]
        ys = [min(top,max(bottom,aim_y)), *(bottom+(top-bottom)*i/8 for i in range(9))]
        # Preserve the previous contact gap on a wall, including bed headboards.
        policy = policies.get(key, {})
        if policy.get('mode') == 'wall':
            side, gap = wall_contact(anchor,room,policy)
            _, old_gap = wall_contact(anchor,replace(room,bounds=before),policy)
            if side in ('west','east'):
                xs.insert(0,x+(old_gap-gap)*(1 if side=='west' else -1))
            else:
                ys.insert(0,y+(old_gap-gap)*(1 if side=='south' else -1))
        candidates = sorted(((px,py) for px in xs for py in ys),
                            key=lambda p:(p[0]-aim_x)**2+(p[1]-aim_y)**2)
        if key in design.get('protected_groups', []):
            candidates = [(x,y)]
        for px, py in candidates:
            moved = [replace(o, position=Point2D(o.position.x+px-x,o.position.y+py-y)) for o in group]
            if any(not region.contains_bounds(o.bounds) or any(o.bounds.overlaps_area(b) for b in obstacles)
                   for o in moved):
                continue
            if policy.get('mode') == 'wall':
                moved_anchor = next(o for o in moved if o.id == anchor.id)
                side, gap = wall_contact(moved_anchor,room,policy)
                if policy['wall'] not in ('auto',side) or not .12-1e-5 <= gap <= policy['max_gap_m']+1e-5:
                    continue
            if group_relation_cost(design.get('group_relations', []), [*placed,*moved]) is None:
                continue
            if policy.get('mode') == 'wall':
                tangent = moved_anchor.position.x if side in ('north','south') else moved_anchor.position.y
                wall = next((w for w in wall_segments(floor,room) if w['side']==side
                             and w['start'] <= tangent <= w['end']), None)
                if wall is None:
                    continue
                moved_anchor.metadata['wall_binding'] = {
                    **moved_anchor.metadata.get('wall_binding',{}), **wall, 'gap_m': round(gap,6)}
            if design.get('status') == 'accepted' and len(placed) + len(moved) == len(objects):
                if not circulation_check([*placed, *moved], room, floor, bounds)['ok']:
                    continue
            placed.extend(moved)
            obstacles.extend(o.bounds for o in moved)
            break
        else:
            raise ValueError(f'{room.id}: no feasible placement for furniture group {key}')
    return placed


def translate_object(obj, shift):
    moved = replace(obj,position=Point2D(obj.position.x+shift.x,obj.position.y+shift.y))
    wall = moved.metadata.get('wall_binding')
    if wall and all(k in wall for k in ('start','end','boundary','side')):
        horizontal = wall['side'] in ('north','south')
        tangent, normal = (shift.x,shift.y) if horizontal else (shift.y,shift.x)
        moved.metadata['wall_binding'] = {**wall,'start':wall['start']+tangent,
                                         'end':wall['end']+tangent,'boundary':wall['boundary']+normal}
    return moved


def adapt_furniture(old_building, building, old_floor, floor, old_room, room, objects, shift, resizing):
    metric = [bool(o.metadata.get('metric_room_placement')) for o in objects]
    if not resizing and not any(metric):
        return [translate_object(o,shift) for o in objects]
    if any(metric) and not all(metric):
        if resizing:
            raise ValueError(f'{room.id}: incompatible furniture coordinate frames for re-layout')
        # A rigid move also supports legacy and metric objects sharing one room.
        return [adapt_furniture(old_building,building,old_floor,floor,old_room,room,[o],shift,False)[0]
                for o in objects]
    if all(metric):
        original = metric_envelope(old_building, old_floor, old_room)
        updated = metric_envelope(building, floor, room)
        if original['status'] != 'supported' or updated['status'] != 'supported':
            raise ValueError(f'{room.id}: no supported metric envelope for existing furniture')
        physical = [restore_metric_object(o,old_building,old_floor,old_room,original) for o in objects]
        if resizing:
            physical = reposition_groups(physical,original['bounds'],updated['room'],updated['floor'])
        else:
            physical = [translate_object(o,shift) for o in physical]
        for o in physical:
            bind_metric_object(o, building, floor, room, updated)
        return physical
    return reposition_groups(objects,old_room.bounds,room,floor)


def compiled_furniture_preserved(before, after, objects, shift=None):
    """Check the metric dimensions of each visible furniture primitive."""
    import math
    owners = {o.id for o in objects}
    def visible(scene):
        return {p.id:p for p in scene.primitives if p.owner_id in owners
                and p.semantic_class.startswith('furniture_')}
    old, new = visible(before), visible(after)
    if set(old) != set(new):
        raise ValueError('Site edit changed compiled furniture instances')
    for key, a in old.items():
        b = new[key]
        previous = (a.size.x, a.size.y, a.size.z, a.rotation_z_deg)
        current = (b.size.x, b.size.y, b.size.z, b.rotation_z_deg)
        if shift is not None:
            previous += (a.center.x+shift.x, a.center.y+shift.y, a.center.z)
            current += (b.center.x,b.center.y,b.center.z)
        if not all(math.isclose(x,y,abs_tol=1e-5) for x,y in zip(previous,current)):
            raise ValueError(f'Site edit changed compiled furniture dimensions or rigid pose: {key}')
    return len(old)
