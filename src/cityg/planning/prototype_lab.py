"""Disposable representative rooms for reviewing parameterized prototypes."""
from copy import deepcopy
from dataclasses import replace
import math

from cityg.assets import AssetRegistry, AssetResolver
from cityg.geometry import GeometryCompiler
from cityg.planning.interiors import FloorDetailAgent
from cityg.planning.prototypes import reference_registry
from cityg.planning.room_envelope import metric_envelope
from cityg.schemas import (Bounds2D, Building, City, District, Door, Floor, Junction,
                           Parcel, Point2D, RoadNetwork, RoadSegment, Room)


def detached_registry(source):
    result = AssetRegistry()
    for record in source.list_all():
        result.register(replace(record, geometry_path=str(source.resolve_path(record.geometry_path).resolve()))
                        if record.geometry_path else record)
    return result


def make_lab(library, keys, cases=None):
    if not keys or len(keys) > 10:
        raise ValueError("Review batches contain 1..10 reference rooms")
    # Minimal connected lab: a single access road south of independent rooms.
    # Do not inherit an unrelated generated city's entrances or stale contracts.
    dimensions=[(cases or {}).get(key, library.rooms[key]['reference']) for key in keys]
    # Large halls need larger fixture parcels; preserve the original small-room
    # fixture coordinates and do not let independent examples overlap.
    spacing=max(24, max(d['width_m'] for d in dimensions)*2+8)
    center_y=max(22,12+max(d['depth_m'] for d in dimensions))
    north=max(42,center_y+max(d['depth_m'] for d in dimensions)+6)
    extent = spacing * len(keys) + 8
    road = RoadSegment('lab_road', 'lab_start', 'lab_end',
                       (Point2D(2, 5), Point2D(extent-2, 5)), width_m=6,
                       sidewalk_width_m=1, parking_allowed=False)
    district = District('lab_district', 'Prototype review lab', 'mixed_use',
                        Bounds2D(0, 10, extent, north))
    for index, key in enumerate(keys):
        cx = 4 + spacing/2 + index * spacing
        shell = Building(f'lab_building_{index:02d}', key, 'mixed_use',
                         Bounds2D(cx-5, center_y-5, cx+5, center_y+5), Point2D(cx, center_y-5))
        district.parcels.append(Parcel(f'lab_parcel_{index:02d}',
                                      Bounds2D(cx-spacing/2+1, 10, cx+spacing/2-1, north), [shell]))
    city = City('city_prototype_lab', 'CityG layout prototype review lab', Bounds2D(0, 0, extent, north+2),
                RoadNetwork([Junction('lab_start', road.centerline[0]),
                             Junction('lab_end', road.centerline[-1])], [road]), [district])
    targets = []
    for building, key in zip(city.iter_buildings(), keys):
        prototype = library.rooms[key]
        case = (cases or {}).get(key, prototype["reference"])
        if not library.compatible(key, room_type=prototype["room_type"],
                                  **{k: case[k] for k in ("width_m", "depth_m", "height_m")}):
            raise ValueError(f"Case is outside declared applicability: {key}")
        cx, cy = building.footprint.center.x, building.footprint.center.y
        building.metadata = {"massing_style": "bar", "orientation_deg": 0,
                             "highrise": {"enabled": False}, "prototype_review_fixture": True}
        # Invert the real compiler's bar projection, not an estimated room size.
        frame = GeometryCompiler._massing_frame(building)
        sx = (frame['max_x']-frame['min_x'])/building.footprint.width
        sy = (frame['max_y']-frame['min_y'])/building.footprint.depth
        width, depth = case["width_m"]/sx, (case["depth_m"]+2)/sy
        building.footprint = Bounds2D(cx-width/2, cy-depth/2, cx+width/2, cy+depth/2)
        building.entrance = Point2D(cx, cy-depth/2)
        building.vertical_connectors.clear()
        building.name = prototype["display_name"]
        # Fixture shells are not themselves candidate building prototypes.
        fid, rid, cid = f"{building.id}_floor_00", f"{key}_room", f"{key}_corridor"
        room = Room(rid, prototype["display_name"], prototype["room_type"],
                    Bounds2D(cx-width/2, cy-depth/2+2/sy, cx+width/2, cy+depth/2),
                    height_m=case["height_m"])
        room.metadata.update(detail_tier="hero", detail_level="hero",
                             layout_prototype_id=key, prototype_review_status="pending_review")
        if prototype.get('finishes'):
            room.metadata['room_finishes'] = deepcopy(prototype['finishes'])
        if prototype.get('decorations'):
            room.metadata['room_decorations'] = deepcopy(prototype['decorations'])
        corridor = Room(cid, "Review-lab entrance", "corridor",
                        Bounds2D(cx-width/2, cy-depth/2, cx+width/2, room.bounds.min_y),
                        height_m=case["height_m"])
        floor = Floor(fid, 0, 0, case["height_m"], rooms=[corridor, room], doors=[
            Door(f"{key}_entry", cid, None, building.entrance, 1.2, "exterior"),
            Door(f"{key}_door", rid, cid,
                 Point2D(room.bounds.min_x+width*case["door_fraction"], room.bounds.min_y),
                 case["door_width_m"]/sx)])
        building.floors = [floor]
        targets.append((key, building, floor, room))
        envelope = metric_envelope(building, floor, room)
        if envelope["status"] != "supported":
            raise ValueError(f"Invalid lab envelope: {key}: {envelope}")
        actual = envelope["bounds"]
        if abs(actual.width-case['width_m']) > 1e-6 or abs(actual.depth-case['depth_m']) > 1e-6:
            raise ValueError("Review room must match advertised physical dimensions")
        if abs(envelope['floor'].doors[0].width_m-case['door_width_m']) > 1e-6:
            raise ValueError("Review entrance must match advertised physical width")
    return city, targets


def populate_reference(city, target, library, source_registry):
    key, building, floor, room = target
    prototype = library.materialize(key)
    pinned = reference_registry(source_registry, prototype)
    detail = FloorDetailAgent(asset_resolver=AssetResolver(pinned, (), max_provider_calls=0),
                              program_overrides={room.id: prototype.program(room.id)})
    stats = detail.populate_rooms(city, {room.id}, seed=17)
    design = room.metadata.get('room_design', {})
    if design.get('status') != 'accepted' or stats['furnishing_non_degradation_gate_rejected_room_count']:
        raise ValueError(f"Reference did not realize its complete inventory: {key}")
    objects = [o for o in floor.objects if o.room_id == room.id]
    if any(o.asset_id != prototype.asset_bindings[o.category] for o in objects):
        raise ValueError("Reference asset silently substituted")
    room.metadata['layout_prototype_fingerprint'] = prototype.content_fingerprint
    return {'prototype_id': key, 'content_fingerprint': prototype.content_fingerprint,
            'room_id': room.id, 'major_count': len(objects), 'stats': stats,
            'constraint_checks': deepcopy(design['constraint_checks']),
            'asset_bindings': prototype.asset_bindings, 'prototype_only_asset_roles': prototype.asset_roles}


def compiled_containment_checks(scene, targets):
    """Validate the compiled major furniture, not only pre-compile proposals."""
    checks = []
    primitives = {}
    for primitive in scene.primitives:
        if primitive.semantic_class.startswith('furniture_'):
            primitives.setdefault(primitive.owner_id, []).append(primitive)
    for key, building, floor, room in targets:
        if building.metadata.get('orientation_deg', 0) != 0:
            raise ValueError('Review lab containment expects unrotated fixture shells')
        bounds = metric_envelope(building, floor, room)['bounds']
        for obj in floor.objects:
            if obj.room_id != room.id:
                continue
            parts = primitives.get(obj.id, [])
            inside = bool(parts)
            for p in parts:
                angle = math.radians(p.rotation_z_deg)
                for dx in (-p.size.x/2, p.size.x/2):
                    for dy in (-p.size.y/2, p.size.y/2):
                        x = p.center.x + dx*math.cos(angle)-dy*math.sin(angle)
                        y = p.center.y + dx*math.sin(angle)+dy*math.cos(angle)
                        inside &= bounds.min_x-1e-5 <= x <= bounds.max_x+1e-5 and bounds.min_y-1e-5 <= y <= bounds.max_y+1e-5
            checks.append({'prototype_id': key, 'object_id': obj.id, 'ok': bool(inside)})
    return checks


def compiled_open_plan_checks(scene, targets):
    """Independent post-compile audit of zoned furniture and clear aisles."""
    from cityg.geometry.room_decorations import box_bounds
    from cityg.planning.room_regions import region_bounds, reserved_bounds
    checks=[]
    for key,building,floor,room in targets:
        design=room.metadata.get('room_design',{})
        bounds=metric_envelope(building,floor,room)['bounds']
        zones={z['id']:region_bounds(bounds,z['bounds_uv']) for z in design.get('zones',[]) if 'bounds_uv' in z}
        if not zones and not design.get('reserved_areas'):
            continue
        areas=reserved_bounds(bounds,design.get('reserved_areas',[]))
        objects={o.id:o for o in floor.objects if o.room_id==room.id}
        for p in scene.primitives:
            obj=objects.get(p.owner_id)
            decor=(p.owner_id==room.id and p.metadata.get('decoration_kind') in {'floor_asset','rug'})
            if not decor and (obj is None or not p.semantic_class.startswith('furniture_')):
                continue
            actual=box_bounds(p)
            zone=zones.get(obj.metadata.get('zone_id')) if obj else None
            checks.append({'prototype_id':key,'primitive_id':p.id,
                'zone_contained':zone is None or zone.contains_bounds(actual,tolerance=1e-5),
                'aisles_clear':not any(a.overlaps_area(actual) for a in areas)})
    return [{**c,'ok':c['zone_contained'] and c['aisles_clear']} for c in checks]
