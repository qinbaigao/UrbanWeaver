"""Place pinned decor on realized walls/floors without moving accepted furniture.

Floor assets must preserve the same conservative circulation check as furniture.
Rugs deliberately allow furniture overlap, but never cross the room/door approach.
Wall art uses a full solid wall segment, not a guessed rectangular room boundary.
No asset acquisition or production approval happens inside the compiler.
"""
from copy import deepcopy
from dataclasses import replace
import math

from cityg.geometry.model import Vec3
from cityg.geometry.surface_dressing import overlaps, _rotate
from cityg.planning.room_constraints import circulation_check
from cityg.planning.room_decorations import validate_decorations
from cityg.planning.room_envelope import metric_envelope
from cityg.planning.room_regions import reserved_bounds
from cityg.schemas import InteriorObject, Point2D, Bounds2D


def _metric_objects(floor, room):
    result = []
    for obj in floor.objects:
        if obj.room_id != room.id:
            continue
        pose = obj.metadata.get('metric_room_placement')
        if not pose:
            raise ValueError('Room decorations require metric furniture placements')
        item = deepcopy(obj)
        item.position = Point2D(*pose['center'])
        item.width_m, item.depth_m, item.height_m = pose['dimensions_m']
        result.append(item)
    return result


def compile_room_decorations(compiler, building, floor, room, scene):
    requests = room.metadata.get('room_decorations', [])
    if not requests:
        return
    validate_decorations(requests)
    report = {'requested': len(requests), 'placed': 0, 'items': [], 'skipped': [],
              'window_status': 'deferred_until_shared_facade_opening_contract'}
    scene.metadata.setdefault('room_decorations', {})[room.id] = report
    envelope = metric_envelope(building, floor, room)
    if envelope['status'] != 'supported':
        report['skipped'] = [{'id': q['id'], 'reason': 'unsupported_realized_envelope'} for q in requests]
        return
    bounds = envelope['bounds']
    reservations=reserved_bounds(bounds, room.metadata.get('room_design',{}).get('reserved_areas', []))
    yaw = float(building.metadata.get('orientation_deg', 0))
    origin = building.footprint.center
    def local(p):
        dx, dy = _rotate(p.center.x-origin.x, p.center.y-origin.y, -yaw)
        return replace(p, center=Vec3(origin.x+dx, origin.y+dy, p.center.z),
                       rotation_z_deg=p.rotation_z_deg-yaw)
    def world(p):
        dx, dy = _rotate(p.center.x-origin.x, p.center.y-origin.y, yaw)
        return replace(p, center=Vec3(origin.x+dx, origin.y+dy, p.center.z),
                       rotation_z_deg=p.rotation_z_deg+yaw)
    room_parts = [local(p) for p in scene.primitives
                  if room.id in p.metadata.get('room_ids', [])]
    walls = [p for p in room_parts if p.semantic_class == 'interior_wall' and p.primitive_type == 'box'
             and not p.metadata.get('room_wall_finish') and p.size.z > 1.2
             and p.metadata.get('wall_role') != 'door_header']
    furniture_ids = {o.id for o in floor.objects if o.room_id == room.id}
    obstacles = [local(p) for p in scene.primitives if p.owner_id in furniture_ids
                 and p.semantic_class.startswith('furniture_')]
    metric_objects = _metric_objects(floor, room)
    doors = envelope['floor'].doors
    def door_clear(p):
        # Conservative space for door leaf and approach, including thin rugs.
        return not any(box_bounds(p).overlaps_area(Bounds2D(
            d.position.x-d.width_m/2-.2, d.position.y-d.width_m/2-.2,
            d.position.x+d.width_m/2+.2, d.position.y+d.width_m/2+.2)) for d in doors)
    for request in requests:
        record = compiler.asset_registry.get(request['asset_id']) if compiler.asset_registry else None
        expected = {'wall_asset':'wall', 'floor_asset':'floor', 'rug':'floor_overlay'}[request['kind']]
        if (record is None or not record.geometry_path
                or not compiler.asset_registry.resolve_path(record.geometry_path).is_file()
                or record.metadata.get('decoration_review_version') != 1
                or record.metadata.get('placement_kind') != expected
                or record.environment != 'indoor'
                or room.function not in record.room_types):
            raise ValueError(f'Missing or unreviewed pinned decoration asset: {request["asset_id"]}')
        w, d, h = record.dimensions_m
        if not all(math.isfinite(v) and v > 0 for v in (w, d, h)):
            raise ValueError('Invalid decoration physical dimensions')
        name = f'{room.id}_decor_{request["id"]}'
        meta = {'room_ids':[room.id], 'decoration_id':request['id'], 'decoration_kind':request['kind'],
                'resolved_asset':True, 'asset_id':record.asset_id, 'asset_source':record.source,
                'asset_license':record.license_id, 'asset_metadata':record.metadata,
                'asset_geometry_path':str(compiler.asset_registry.resolve_path(record.geometry_path)),
                'asset_category':record.category}
        def mesh(x, y, z, angle=0, **extra):
            p = compiler._mesh(name, room.id, Vec3(x,y,z), Vec3(w,d,h), angle,
                'room_decoration', 'furniture_wood', f'floor:{floor.id}',
                instance_key=f'asset_{record.asset_id}', metadata={**meta, **extra})
            p.collision_enabled = request['kind'] == 'floor_asset'
            return p
        candidates = []
        if request['kind'] == 'rug':
            anchor = next((o for o in metric_objects if o.metadata.get('design_member_id') == request['anchor_member_id']), None)
            if anchor:
                # Place below the furniture plane, not through chair/table legs.
                for angle in (anchor.rotation_deg, anchor.rotation_deg+90):
                    p = mesh(anchor.position.x, anchor.position.y, floor.elevation_m-h/2+.002,
                        angle, anchor_object_id=anchor.id, visual_only=True, floor_overlay=True)
                    box = box_bounds(p)
                    if box.width > bounds.width-.16 or box.depth > bounds.depth-.16:
                        continue
                    x = min(max(anchor.position.x,bounds.min_x+.08+box.width/2),bounds.max_x-.08-box.width/2)
                    y = min(max(anchor.position.y,bounds.min_y+.08+box.depth/2),bounds.max_y-.08-box.depth/2)
                    if math.hypot(x-anchor.position.x,y-anchor.position.y) <= .85:
                        candidates.append(replace(p,center=Vec3(x,y,p.center.z)))
        elif request['kind'] == 'floor_asset':
            for side in request['walls']:
                for t in (.15,.85,.3,.7,.5):
                    x = bounds.min_x+w/2+.15 if side == 'west' else bounds.max_x-w/2-.15 if side == 'east' else bounds.min_x+(w/2+.15)+(bounds.width-w-.3)*t
                    y = bounds.min_y+d/2+.15 if side == 'south' else bounds.max_y-d/2-.15 if side == 'north' else bounds.min_y+(d/2+.15)+(bounds.depth-d-.3)*t
                    candidates.append(mesh(x,y,floor.elevation_m+h/2))
        else:
            # Reviewed frames have their front along local X, thickness along X.
            if record.metadata.get('orientation',{}).get('canonical_forward_axis') not in {'+X','-X'} or w > .15:
                raise ValueError('Wall decor needs a reviewed thin-X frame')
            ranked = sorted(walls, key=lambda p: (request['walls'].index(wall_side(p,bounds))
                            if wall_side(p,bounds) in request['walls'] else 99, p.id))
            for wall in ranked:
                side = wall_side(wall, bounds)
                if side not in request['walls'] or min(abs(wall.rotation_z_deg % 90),abs(wall.rotation_z_deg % 90-90)) > 1e-5:
                    continue
                nx,ny = {'north':(0,-1),'south':(0,1),'west':(1,0),'east':(-1,0)}[side]
                horizontal = side in {'north','south'}
                span = wall.size.x if horizontal else wall.size.y
                if span < d+.25:
                    continue
                thickness = wall.size.y if horizontal else wall.size.x
                angle = math.degrees(math.atan2(ny,nx)) - (180 if record.metadata['orientation']['canonical_forward_axis']=='-X' else 0)
                for z in (1.85,2.15,1.55):
                    if floor.elevation_m+z+h/2 > wall.center.z+wall.size.z/2-.12 or floor.elevation_m+z-h/2 < wall.center.z-wall.size.z/2+.12:
                        continue
                    for t in (0,-.25,.25,-.4,.4):
                        shift = (span-d-.25)*t
                        candidates.append(mesh(wall.center.x+nx*(thickness/2+w/2+.012)+(shift if horizontal else 0),
                            wall.center.y+ny*(thickness/2+w/2+.012)+(0 if horizontal else shift),
                            floor.elevation_m+z,angle,support_kind='wall', support_primitive_id=wall.id,
                            viewer_room_only=wall.metadata.get('viewer_room_only',False),visual_only=True))
        chosen = None
        access = None
        for p in candidates:
            if not bounds.inset(.01).contains_bounds(box_bounds(p)):
                continue
            if request['kind'] != 'wall_asset' and not door_clear(p):
                continue
            if request['kind'] != 'wall_asset' and any(a.overlaps_area(box_bounds(p)) for a in reservations):
                continue
            if request['kind'] != 'rug' and any(overlaps(p,other,gap=.08) for other in obstacles):
                continue
            if request['kind'] == 'floor_asset':
                obj = InteriorObject(name,room.id,record.category,record.asset_id,Point2D(p.center.x,p.center.y),w,d,h)
                access = circulation_check([*metric_objects,obj],envelope['room'],envelope['floor'],bounds.inset(.08))
                if not access['ok']:
                    continue
                metric_objects.append(obj)
            chosen = p
            break
        if chosen is None:
            report['skipped'].append({'id':request['id'], 'reason':'no_safe_realized_support_or_clearance'})
            continue
        scene.primitives.append(world(chosen))
        if request['kind'] != 'rug':
            obstacles.append(chosen)
        report['placed'] += 1
        report['items'].append({'id':request['id'], 'primitive_id':chosen.id, 'asset_id':record.asset_id,
            'kind':request['kind'], 'support_primitive_id':chosen.metadata.get('support_primitive_id'),
            'contained':True, 'circulation':access if request['kind']=='floor_asset' else None})


def box_bounds(primitive):
    a = math.radians(primitive.rotation_z_deg)
    w = abs(math.cos(a))*primitive.size.x + abs(math.sin(a))*primitive.size.y
    d = abs(math.sin(a))*primitive.size.x + abs(math.cos(a))*primitive.size.y
    return Bounds2D(primitive.center.x-w/2,primitive.center.y-d/2,
                    primitive.center.x+w/2,primitive.center.y+d/2)


def wall_side(wall, bounds):
    distances = {'north':abs(wall.center.y-bounds.max_y),'south':abs(wall.center.y-bounds.min_y),
                 'east':abs(wall.center.x-bounds.max_x),'west':abs(wall.center.x-bounds.min_x)}
    return min(distances, key=distances.get)
