"""Review-only repartitioning around an immutable circulation skeleton.

Floor references supply target room frontage, not replacement core geometry.
Opt-in joint planning additionally uses room dimensions and local access spines.
Only empty, rectangular rooms directly served by retained corridors are split.
All original doors, circulation rooms and connector stacks are immutable. This
is deliberately not an arbitrary polygon/whole-template transplant solver.
"""
from copy import deepcopy
from itertools import combinations
import math
from statistics import median

from cityg.ccwp import build_world_program
from cityg.planning.floor_prototypes import box
from cityg.planning.prototype_adaptation import door_side
from cityg.planning.room_envelope import metric_envelope
from cityg.planning.spatial_layout import shared_boundary
from cityg.schemas import Bounds2D, Door, Point2D, Room
from cityg.validation import CityValidator


def options(value):
    defaults = dict(enabled=False, max_floors=2, max_splits_per_floor=2,
                    max_children_per_room=6, min_room_width_m=2.4,
                    max_room_aspect=2.8, target_building_ids=[], levels=[0, 1],
                    joint_room_planning=False, allow_secondary_corridor=True,
                    secondary_corridor_width_m=1.8, preferred_reference_ids=[])
    if not isinstance(value, dict) or set(value) - defaults.keys():
        raise ValueError('Unknown floor_repartition options')
    result = {**defaults, **value}
    for key in ('enabled','joint_room_planning','allow_secondary_corridor'):
        if type(result[key]) is not bool:
            raise ValueError('floor_repartition.'+key+' must be boolean')
    for key, lo, hi in [('max_floors', 1, 6), ('max_splits_per_floor', 1, 8),
                        ('max_children_per_room', 2, 8)]:
        if type(result[key]) is not int or not lo <= result[key] <= hi:
            raise ValueError('Invalid floor repartition budget: ' + key)
    for key, lo, hi in [('min_room_width_m', 2.4, 6), ('max_room_aspect', 1.5, 3),
                        ('secondary_corridor_width_m',1.5,3)]:
        v = result[key]
        if type(v) not in (int, float) or not math.isfinite(v) or not lo <= v <= hi:
            raise ValueError('Invalid metric constraint: ' + key)
    if (not isinstance(result['levels'], list) or not result['levels'] or
            any(type(v) is not int or not 0 <= v <= 100 for v in result['levels'])):
        raise ValueError('levels must be a nonempty list of floor levels')
    ids = result['target_building_ids']
    if not isinstance(ids, list) or any(not isinstance(v, str) or not v for v in ids):
        raise ValueError('target_building_ids must contain building IDs')
    if not isinstance(result['preferred_reference_ids'], list) or any(
            not isinstance(v, str) for v in result['preferred_reference_ids']):
        raise ValueError('preferred_reference_ids must contain floor reference IDs')
    return result


def _envelopes(building, floor):
    result = {}
    for room in floor.rooms:
        env = metric_envelope(building, floor, room)
        if env['status'] != 'supported':
            raise ValueError('Unsupported room envelope: ' + room.id)
        sx, sy = env['scale']; ox, oy = env['offset']; b = room.bounds
        affine = Bounds2D(b.min_x*sx+ox, b.min_y*sy+oy, b.max_x*sx+ox, b.max_y*sy+oy)
        if any(abs(getattr(affine, k)-getattr(env['bounds'], k)) > 1e-5
               for k in ('min_x', 'min_y', 'max_x', 'max_y')):
            raise ValueError('Clipped floor needs polygon-aware repartitioning')
        # Includes exterior doors: a legacy entrance falsely bound to a remote
        # corridor is not silently moved or rebound to make this pass.
        for door in env['floor'].doors:
            door_side(env['room'], door)
        result[room.id] = env
    return result


def _reference(library, building, floor, preferred=()):
    functions = {r.function for r in floor.rooms if r.function != 'corridor'}
    permitted = {building.function} if building.function != 'mixed_use' else {
        'residential', 'commercial', 'public_service'}
    records = [r for r in library.floors.values() if r['function'] in permitted]
    if not records:
        raise ValueError('No semantic floor reference')
    # No misleading claim of global template fit: this reuses only same-function
    # room frontage priors; original functions and vertical zoning survive.
    def rank(record):
        public = [s for s in record['spaces'] if s['function'] == 'corridor']
        direct = {s['function'] for s in record['spaces'] if s['function'] != 'corridor'
                  and any(shared_boundary(box(s['bounds_m']), box(p['bounds_m'])) for p in public)}
        return (-len(functions & direct), -len(functions & {s['function'] for s in record['spaces']}),
                record['id'] not in preferred, record['id'])
    return min(records, key=rank)


def _cuts(lo, hi, count, minimum, blocked, variation):
    step = (hi-lo)/count
    values = [lo]
    for i in range(1, count):
        ideal = lo+i*step
        candidates = [ideal, *[v for pair in blocked for v in pair]]
        valid = [v for v in candidates if abs(v-ideal) <= step*variation+1e-6
                 and v-values[-1] >= minimum-1e-6 and hi-v >= (count-i)*minimum-1e-6
                 and not any(a+1e-6 < v < b-1e-6 for a, b in blocked)]
        if not valid:
            return None
        values.append(min(valid, key=lambda v: (abs(v-ideal), v)))
    return [*values, hi]


def _split(building, floor, room, envs, reference, opt, variation, room_library=None):
    if room.function == 'corridor' or room.object_ids or any(o.room_id == room.id for o in floor.objects):
        return None
    # Do not invalidate unit membership or previously solved/design-bound rooms.
    if any(room.metadata.get(k) for k in ('room_design', 'unit_id', 'functional_zones',
                                        'floor_repartition', 'spatial_requirement',
                                        'room_decorations', 'room_finishes', 'surface_items')):
        return None
    doors = [d for d in floor.doors if room.id in (d.room_a_id, d.room_b_id)]
    interior = [d for d in doors if d.room_b_id is not None]
    if len(interior) != 1:
        return None
    door = interior[0]
    cid = door.room_b_id if door.room_a_id == room.id else door.room_a_id
    corridor = next((r for r in floor.rooms if r.id == cid and r.function == 'corridor'), None)
    if corridor is None:
        return None
    e = envs[room.id]; b = e['bounds']; cb = envs[cid]['bounds']
    shared = shared_boundary(b, cb)
    if not shared:
        return None
    axis, edge, start, end = shared
    lo, hi, depth = (b.min_x, b.max_x, b.depth) if axis == 'x' else (b.min_y, b.max_y, b.width)
    if abs(start-lo) > 1e-5 or abs(end-hi) > 1e-5:
        return None  # source must have full-frontage access; joint mode can branch
    if opt['joint_room_planning']:
        from cityg.planning.joint_floor_rooms import joint_split
        # No fallback that claims joint success while producing zero matching
        # rooms. A rejected region remains unchanged and can be reviewed later.
        return joint_split(room,e,cid,shared,room_library,reference,opt,variation)
    widths = []
    for space in reference['spaces']:
        if space['function'] != room.function:
            continue
        sb = box(space['bounds_m'])
        for public in reference['spaces']:
            if public['function'] != 'corridor':
                continue
            seam = shared_boundary(sb, box(public['bounds_m']))
            if seam:
                widths.append(seam[3]-seam[2])
    if not widths:
        return None
    minimum = max(opt['min_room_width_m'], depth/opt['max_room_aspect'])
    if depth < opt['min_room_width_m']:
        return None
    target = max(minimum, median(widths))
    preferred = max(2, round((hi-lo)/target))
    counts = range(2, min(opt['max_children_per_room'], int((hi-lo)/minimum))+1)
    counts = sorted(counts, key=lambda n: (abs(n-preferred), n))
    metric_doors = e['floor'].doors
    # Protect the entire opening plus corner clearance, not just its center.
    blocked = []
    for d in metric_doors:
        tangent = d.position.x if axis == 'x' else d.position.y
        margin = d.width_m/2+.2
        blocked.append((tangent-margin, tangent+margin))
    sx, sy = e['scale']; ox, oy = e['offset']
    for count in counts:
        # Avoid splitting an already reference-sized room merely because n>=2.
        if hi-lo < target*1.5:
            continue
        cuts = _cuts(lo, hi, count, minimum, blocked, variation)
        if cuts is None:
            continue
        boxes = [Bounds2D(a, b.min_y, z, b.max_y) if axis == 'x' else
                 Bounds2D(b.min_x, a, b.max_x, z) for a, z in zip(cuts, cuts[1:])]
        if any(max(q.width/q.depth, q.depth/q.width) > opt['max_room_aspect']+1e-6 for q in boxes):
            continue
        # Every pre-existing door keeps its endpoint IDs as well as pose. This
        # excludes cuts that separate an old exterior door from its internal one.
        owners = [i for i, q in enumerate(boxes) if all(q.contains_point(d.position) for d in metric_doors)]
        if len(owners) != 1:
            continue
        anchor = owners[0]; children = []; new_doors = []
        for i, q in enumerate(boxes):
            rid = room.id if i == anchor else room.id+f'_part_{i:02d}'
            canonical = Bounds2D((q.min_x-ox)/sx, (q.min_y-oy)/sy, (q.max_x-ox)/sx, (q.max_y-oy)/sy)
            children.append(Room(rid, room.name+f' · {i+1}', room.function, canonical, room.height_m,
                metadata={'floor_repartition': {'source_room_id': room.id, 'reference_id': reference['id']},
                          'detail_tier': 'preview'}))
            if i != anchor:
                t = (cuts[i]+cuts[i+1])/2
                pos = Point2D((t-ox)/sx, (edge-oy)/sy) if axis == 'x' else Point2D((edge-ox)/sx, (t-oy)/sy)
                new_doors.append(Door(rid+'_entry', rid, cid, pos, width_m=.9/(sx if axis == 'x' else sy)))
        return children, new_doors
    return None


def validate_repartition(building, original, proposed):
    """Semantic locks, exact per-parent coverage and realized door topology."""
    if any(getattr(original, k) != getattr(proposed, k) for k in ('id', 'level', 'elevation_m', 'height_m')):
        raise ValueError('Floor identity/elevation/height changed')
    old = {r.id: r for r in original.rooms}; new = {r.id: r for r in proposed.rooms}
    if len(new) != len(proposed.rooms) or len({d.id for d in proposed.doors}) != len(proposed.doors):
        raise ValueError('Duplicate repartition entity IDs')
    new_doors = {d.id: d for d in proposed.doors}
    if any(new_doors.get(d.id) != d for d in original.doors):
        raise ValueError('Existing door contract changed')
    if original.objects != proposed.objects:
        raise ValueError('Existing inventory changed')
    for room in proposed.rooms:
        if room.id not in old and room.metadata.get('floor_repartition', {}).get('source_room_id') not in old:
            raise ValueError('New room has no original partition parent')
    for rid, r in old.items():
        children = [q for q in proposed.rooms if q.metadata.get('floor_repartition', {}).get('source_room_id') == rid]
        if not children:
            if new.get(rid) != r:
                raise ValueError('Protected room changed')
            continue
        if r.function == 'corridor' or r.object_ids or any(o.room_id == rid for o in original.objects):
            raise ValueError('Cannot subdivide circulation or occupied room')
        if (rid not in new or any((q.function != r.function and not (
                    q.id != rid and q.function == 'corridor' and
                    q.metadata.get('joint_room_plan',{}).get('role') == 'access_corridor'))
                    or q.height_m != r.height_m or not r.bounds.contains_bounds(q.bounds, tolerance=1e-6) for q in children)
                or abs(sum(q.bounds.area for q in children)-r.bounds.area) > 1e-5):
            raise ValueError('Incomplete parent-room coverage')
    if any(a.bounds.overlaps_area(b.bounds) for a, b in combinations(proposed.rooms, 2)):
        raise ValueError('Overlapping room partitions')
    envs = _envelopes(building, proposed)
    graph = {rid: set() for rid in new}
    for d in proposed.doors:
        if d.room_b_id is None:
            continue
        if d.room_a_id not in new or d.room_b_id not in new:
            raise ValueError('Dangling door endpoint')
        if not shared_boundary(envs[d.room_a_id]['bounds'], envs[d.room_b_id]['bounds']):
            raise ValueError('Nonadjacent door endpoints')
        graph[d.room_a_id].add(d.room_b_id); graph[d.room_b_id].add(d.room_a_id)
    public = [r.id for r in proposed.rooms if r.function == 'corridor']
    if not public:
        raise ValueError('Missing circulation skeleton')
    reached = {public[0]}; queue = list(reached)
    while queue:
        for rid in graph[queue.pop()] - reached:
            reached.add(rid); queue.append(rid)
    if reached != set(new):
        raise ValueError('Disconnected floor access graph')
    return {'coverage': True, 'door_locks': True, 'circulation_preserved': True,
            'all_rooms_reachable': True, 'realized_door_corners': True}


def propose_floor(building, floor, library, opt, variation=.2):
    if type(variation) not in (int, float) or not math.isfinite(variation) or not 0 <= variation <= .3:
        raise ValueError('Invalid cut variation budget')
    if floor.metadata.get('floor_repartition'):
        raise ValueError('Floor already repartitioned; explicit replanning required')
    if floor.metadata.get('dwelling_units'):
        raise ValueError('Private unit topology requires a unit-aware adapter')
    for core in building.vertical_connectors:
        if core.from_level <= floor.level <= core.to_level and not any(
                r.function == 'corridor' and r.bounds.contains_bounds(core.bounds, tolerance=1e-5)
                for r in floor.rooms):
            raise ValueError('Core must be contained in the immutable circulation skeleton')
    envs = _envelopes(building, floor)
    ref = _reference(library, building, floor, opt.get('preferred_reference_ids', []))
    result = deepcopy(floor); changes = []
    for room in sorted(floor.rooms, key=lambda r: (-envs[r.id]['bounds'].area, r.id)):
        if len(changes) >= opt['max_splits_per_floor']:
            break
        split = _split(building, floor, room, envs, ref, opt, variation, library.room_library)
        if split is None:
            continue
        children, doors = split
        known = {r.id for r in result.rooms} - {room.id}
        if any(r.id in known for r in children):
            raise ValueError('Generated room ID collision')
        index = next(i for i, r in enumerate(result.rooms) if r.id == room.id)
        result.rooms[index:index+1] = children; result.doors.extend(doors)
        changes.append({'source_room_id': room.id, 'child_ids': [r.id for r in children]})
    if not changes:
        raise ValueError('No safe reference-guided subdivision')
    bindings=[]
    if opt['joint_room_planning']:
        from cityg.planning.prototype_adaptation import room_candidates
        for room in result.rooms:
            plan=room.metadata.get('joint_room_plan',{})
            if plan.get('role')=='prototype_room':
                matches=[c for c in room_candidates(library.room_library,building,result,room)
                         if c['prototype_id']==plan['prototype_id']]
                if not matches:
                    raise ValueError('Joint room binding does not fit realized envelope/doors')
                bindings.append({'room_id':room.id,**matches[0]})
        if not bindings:raise ValueError('Joint plan must create compatible room candidates')
    prior = deepcopy(result.metadata.get('spatial_layout'))
    result.metadata['spatial_layout'] = {'status': 'accepted', 'family': 'locked_skeleton_repartition',
        'open_boundaries': deepcopy((prior or {}).get('open_boundaries', []))}
    result.metadata['floor_repartition'] = {'source_reference_id': ref['id'],
        'reference_fingerprint': library.content_fingerprint(ref['id']),
        'reference_usage': ('joint_room_dimensions_and_access' if bindings else 'same_function_frontage_priors_only'),
        'joint_room_bindings':bindings, 'production_approved': False,
        'previous_spatial_layout': prior, 'replacements': changes}
    checks = validate_repartition(building, floor, result)
    return result, {'reference_id': ref['id'], 'replacements': changes,
                    'before_rooms': len(floor.rooms), 'after_rooms': len(result.rooms), 'checks': checks,
                    'joint_room_bindings':bindings,
                    'added_corridors':sum(r.metadata.get('joint_room_plan',{}).get('role')=='access_corridor' for r in result.rooms)}


def _compiled_locks(scene, building, floor):
    owners = {d.id for d in floor.doors} | {c.id for c in building.vertical_connectors}
    return {p.id: (p.owner_id, p.semantic_class, p.center, p.size, p.rotation_z_deg)
            for p in scene.primitives if p.owner_id in owners}


def _check_compiled_access(scene, building, original, proposed):
    """New corridor openings must not open straight into a compiled core."""
    from cityg.geometry.room_decorations import box_bounds
    from cityg.geometry.model import Vec3
    from dataclasses import replace
    yaw = building.metadata.get('orientation_deg', 0)
    c, s = math.cos(math.radians(-yaw)), math.sin(math.radians(-yaw))
    origin = building.footprint.center
    core_ids = {v.id for v in building.vertical_connectors}
    boxes = []
    for p in scene.primitives:
        if p.owner_id not in core_ids or p.layer_id != 'floor:'+proposed.id:
            continue
        x, y = p.center.x-origin.x, p.center.y-origin.y
        local = replace(p, center=Vec3(origin.x+c*x-s*y, origin.y+s*x+c*y, p.center.z),
                        rotation_z_deg=p.rotation_z_deg-yaw)
        boxes.append(box_bounds(local))
    envs = _envelopes(building, proposed)
    public = [envs[r.id]['bounds'] for r in proposed.rooms if r.function == 'corridor']
    if any(not any(q.contains_bounds(core, tolerance=1e-5) for q in public) for core in boxes):
        raise ValueError('Compiled core outside preserved circulation space')
    old_ids = {d.id for d in original.doors}
    compiled_doors = {p.owner_id for p in scene.primitives if p.semantic_class == 'door'}
    for d in proposed.doors:
        if d.id in old_ids:
            continue
        if d.id not in compiled_doors:
            raise ValueError('New doorway was not compiled')
        e = envs[d.room_a_id]; q = envs[d.room_b_id]['bounds']
        md = next(v for v in e['floor'].doors if v.id == d.id)
        side = door_side(e['room'], md); x, y = md.position.x, md.position.y
        half = md.width_m/2+.15
        if side in ('south', 'north'):
            direction = 1 if q.center.y > y else -1
            access = Bounds2D(x-half, min(y,y+direction*.8), x+half, max(y,y+direction*.8))
        else:
            direction = 1 if q.center.x > x else -1
            access = Bounds2D(min(x,x+direction*.8), y-half, max(x,x+direction*.8), y+half)
        if not q.contains_bounds(access, tolerance=1e-5) or any(access.overlaps_area(core) for core in boxes):
            raise ValueError('New door access conflicts with core/circulation clearance')
    # An isolated upper-floor scope must not pass just because its local room
    # graph is connected. Require a path from the actual city road graph too.
    adjacency = {n.id: set() for n in scene.navigation.nodes}
    for edge in scene.navigation.edges:
        adjacency[edge.start_node_id].add(edge.end_node_id)
        adjacency[edge.end_node_id].add(edge.start_node_id)
    outdoors = [n.id for n in scene.navigation.nodes if n.node_type == 'outdoor_junction']
    reached = set(outdoors[:1]); queue = list(reached)
    while queue:
        for node in adjacency[queue.pop()] - reached:
            reached.add(node); queue.append(node)
    room_ids = {r.id for r in proposed.rooms}
    nodes = [n for n in scene.navigation.nodes if n.owner_id in room_ids]
    if {n.owner_id for n in nodes} != room_ids or any(n.id not in reached for n in nodes):
        raise ValueError('Repartitioned floor is not reachable from outdoors')


def repartition_city(source, library, compiler, config, *, variation=.2, progress=None, target_levels=None):
    """Detached, per-floor compile/rollback transactions; no source writes."""
    opt = options(config); city = deepcopy(source)
    report = {'enabled': opt['enabled'], 'mode': 'locked_skeleton_repartition',
              'attempts': [], 'accepted': [], 'selected_levels': {}, 'llm_used': False}
    if not opt['enabled']:
        return city, report
    ids = {b.id for b in city.iter_buildings()}
    if set(opt['target_building_ids'])-ids:
        raise ValueError('Unknown target building ID')
    for building in city.iter_buildings():
        if opt['target_building_ids'] and building.id not in opt['target_building_ids']:
            continue
        for index, floor in enumerate(building.floors):
            if target_levels is not None and floor.level not in target_levels.get(building.id, []):
                continue
            if len(report['accepted']) >= opt['max_floors']:
                break
            if floor.level not in opt['levels']:
                continue
            row = {'building_id': building.id, 'floor_id': floor.id, 'level': floor.level}
            metadata, program = deepcopy(city.metadata), city.world_program
            try:
                proposed, evidence = propose_floor(building, floor, library, opt, variation)
                if progress:
                    progress('floor_attempt', floor.id, evidence['after_rooms'])
                if city.metadata.get('interior_scope') is not None:
                    scope = city.metadata['interior_scope']
                    levels = scope['building_levels'].get(building.id, [])
                    # Materialize access dependencies, not just the selected
                    # upper floor. Their plans/contents are never repartitioned.
                    access_levels = {f.level for f in building.floors if 0 <= f.level <= floor.level}
                    scope['building_levels'][building.id] = sorted(set(levels) | access_levels)
                    row['access_scope_added_levels'] = sorted(access_levels - set(levels))
                # Use identical compile scope on both sides of the transaction.
                city.world_program = build_world_program(city, producer='locked_floor_baseline', seed=17)
                before = compiler.compile(city, building_ids={building.id})
                locks = _compiled_locks(before, building, floor)
                building.floors[index] = proposed
                city.world_program = build_world_program(city, producer='locked_floor_repartition', seed=17)
                validation = CityValidator().validate(city)
                if not validation.ok:
                    raise ValueError('Semantic validation failed: '+str(validation.to_dict()['issues'][:3]))
                after = compiler.compile(city, building_ids={building.id})
                if _compiled_locks(after, building, floor) != locks:
                    raise ValueError('Compiled entrance/door/core geometry changed')
                _check_compiled_access(after, building, floor, proposed)
                if not any(p.semantic_class == 'interior_wall' and p.layer_id == 'floor:'+floor.id for p in after.primitives):
                    raise ValueError('Repartition walls were not compiled')
                row.update(evidence, status='accepted', compiled_locks_preserved=True,
                           new_door_core_clearance_verified=True, outdoor_reachability_verified=True)
                report['accepted'].append(row)
                report['selected_levels'].setdefault(building.id, []).append(floor.level)
                if progress:
                    progress('floor_accepted', floor.id, evidence['after_rooms'])
            except ValueError as exc:
                building.floors[index] = floor; city.metadata = metadata; city.world_program = program
                row.update(status='rejected', reason=str(exc))
            report['attempts'].append(row)
    return city, report
