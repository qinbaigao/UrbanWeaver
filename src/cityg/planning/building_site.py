"""Transactional building translation, exterior resizing and rectangular room adaptation."""
from copy import deepcopy
from dataclasses import asdict
import math

from cityg.schemas import Bounds2D, Point2D


class SiteConstraintConflict(ValueError):
    """A footprint candidate violates an existing city-space constraint."""


class CompiledSiteConflict(ValueError):
    """A proposed footprint failed its candidate-specific geometry checks."""


def footprint_bounds(building, area, aspect, request):
    old = building.footprint
    width, depth = old.width, old.depth
    if not (math.isclose(area, old.area, rel_tol=1e-12) and
            math.isclose(aspect, width/depth, rel_tol=1e-12)):
        width = math.sqrt(area*aspect)
        depth = area/width
    x = old.center.x + request.get('offset_x_m', 0)
    y = old.center.y + request.get('offset_y_m', 0)
    return Bounds2D(x-width/2, y-depth/2, x+width/2, y+depth/2)


class SiteLimits:
    def __init__(self, city, building, parcel):
        from cityg.polygons import parcel_shape, box_shape, river_shape, road_shape
        self.allowed = parcel_shape(parcel).buffer(-city.metadata.get('parcel_setback_m', 4.))
        self.obstacles = ([river_shape(r, 'reserve') for r in city.rivers]
                          + [road_shape(r) for r in city.road_network.segments]
                          + [box_shape(b.footprint) for b in city.iter_buildings() if b.id != building.id])

    def violation(self, bounds):
        from cityg.polygons import box_shape
        shape = box_shape(bounds)
        if not self.allowed.covers(shape):
            return 'Requested footprint exceeds parcel/setback; city-level reassignment required'
        if any(shape.intersection(obstacle).area > 1e-6 for obstacle in self.obstacles):
            return 'Requested footprint intersects road, water reserve or another building'
        return None


def adapt_building_site(city, building_id, request, *, exterior_only=False, coordination=None):
    from cityg.subtree_transactions import _entity, _descendants, _old_subtree_ids, _commit
    from cityg.envelopes import envelope_config
    from cityg.interior_requirements import evaluate_requirements, requirements_for
    if set(request)-{'area_m2','aspect_ratio','offset_x_m','offset_y_m'} or not request:
        raise ValueError('Site adaptation takes area_m2, aspect_ratio, offset_x_m, offset_y_m only')
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in request.values()):
        raise ValueError('Site adjustment values must be finite numbers')
    b=_entity(city,building_id)
    from cityg.schemas import Building
    if not isinstance(b,Building):raise ValueError('Site adaptation requires a building ID')
    ids=_descendants(city,building_id)
    if any(n.locked and n.entity_id in ids for n in city.world_program.nodes):
        raise ValueError('Site adaptation would change locked entities')
    protected = [b, *b.floors, *b.vertical_connectors,
                 *(r for f in b.floors for r in f.rooms), *(o for f in b.floors for o in f.objects),
                 *(d for f in b.floors for d in f.doors)]
    if any(getattr(e, 'metadata', {}).get(key) for e in protected for key in ('protected', 'locked')):
        raise ValueError('Site adaptation would change protected or locked entities')
    parent=next(p for p in city.iter_parcels() if any(q.id==b.id for q in p.buildings))
    old=b.footprint; area=request.get('area_m2',old.area); aspect=request.get('aspect_ratio',old.width/old.depth)
    if area<=0 or ('aspect_ratio' in request and not .25<=aspect<=4):
        raise ValueError('Invalid area/aspect ratio')
    resizing = not (math.isclose(area,old.area,rel_tol=1e-12) and
                    math.isclose(aspect,old.width/old.depth,rel_tol=1e-12))
    from cityg.planning.highrise import HighRisePolicy
    from cityg.planning.interior_scope import floor_enabled
    complex_shell = (HighRisePolicy.is_highrise(len(b.floors)) or envelope_config(b) or
                     b.metadata.get('massing_style','bar') != 'bar' or abs(b.metadata.get('orientation_deg',0))>1e-6)
    has_interiors = any((floor_enabled(city,b,f) and not exterior_only) or f.objects or
                        any(r.metadata.get('room_design') for r in f.rooms) for f in b.floors)
    joint = resizing and complex_shell and has_interiors and coordination is not None
    if joint and (envelope_config(b) or abs(b.metadata.get('orientation_deg',0))>1e-6 or exterior_only):
        raise ValueError('Coordinated resizing requires an axis-aligned interior-capable massing')
    if resizing and complex_shell and has_interiors and not joint:
        raise ValueError('Detailed interiors require rectangular low-rise geometry for resizing')
    if resizing and b.metadata.get('transport_core_retrofit'):
        raise ValueError('Resizing a protected transport retrofit requires a new core plan')
    bounds = footprint_bounds(b, area, aspect, request)
    reason = SiteLimits(city, b, parent).violation(bounds)
    if reason:
        raise SiteConstraintConflict(reason)
    w, d = bounds.width, bounds.depth
    cx, cy = bounds.center.x, bounds.center.y
    def point(p):return Point2D(bounds.min_x+(p.x-old.min_x)*w/old.width,
                               bounds.min_y+(p.y-old.min_y)*d/old.depth)
    def rectangle(r):
        a=point(Point2D(r.min_x,r.min_y));z=point(Point2D(r.max_x,r.max_y))
        return Bounds2D(a.x,a.y,z.x,z.y)
    candidate=deepcopy(city); target=_entity(candidate,building_id)
    target.footprint=bounds;target.entrance=point(b.entrance)
    for connector in target.vertical_connectors:connector.bounds=rectangle(connector.bounds)
    shift = Point2D(cx-old.center.x,cy-old.center.y)
    from cityg.planning.site_furniture import adapt_furniture
    if 'footprint' in target.metadata.get('interior_layout_contract', {}):
        target.metadata['interior_layout_contract']['footprint'] = asdict(bounds)
    if target.metadata.get('transport_core_retrofit'):
        retrofit = target.metadata['transport_core_retrofit']
        retrofit['band'] = asdict(rectangle(Bounds2D(**retrofit['band'])))
    if 'floor_plate_contract' in target.metadata and resizing:
        target.metadata['floor_plate_contract'] = HighRisePolicy.floor_plate_contract(
            bounds,len(target.floors),target.metadata.get('highrise',{}).get('massing_variant'),
            orientation_deg=target.metadata.get('orientation_deg',0))
    for previous, f in zip(b.floors, target.floors):
        if (joint and HighRisePolicy.is_highrise(len(b.floors))
                and f.metadata.get('realized_floor_plate', {}).get('source') != 'highrise_massing_outline_v1'):
            raise ValueError('Coordinated tower resizing requires a realized plate on every level')
        for r in f.rooms:
            r.bounds = rectangle(r.bounds)
            if 'realized_area_m2' in r.metadata:
                r.metadata['realized_area_m2'] = r.bounds.area
            requirement = r.metadata.get('spatial_requirement') or {}
            if resizing and not joint and not (requirement.get('min_area_m2',0)-1e-5 <= r.bounds.area
                                 <= requirement.get('max_area_m2',math.inf)+1e-5):
                raise ValueError(f'{r.id}: room area violates its floor layout requirement')
        for door in f.doors:door.position=point(door.position)
        if f.metadata.get('core_bounds'):
            f.metadata['core_bounds']=asdict(rectangle(Bounds2D(**f.metadata['core_bounds'])))
        plate = f.metadata.get('realized_floor_plate') or {}
        if plate.get('bounds'):
            realized = rectangle(Bounds2D(**plate['bounds']))
            if joint and plate.get('source') == 'highrise_massing_outline_v1':
                actual = HighRisePolicy.floor_plate_bounds(bounds, len(b.floors), f.level, plate['massing_variant'])
                if any(abs(getattr(realized, key)-value) > 1e-5 for key, value in asdict(actual).items()):
                    raise ValueError(f'{f.id}: transformed floor differs from the active tower plate')
            plate.update(bounds=asdict(realized),area_m2=round(realized.area,3))
        from cityg.planning.site_coordination import CapacityConflict, capacity
        from cityg.planning.room_envelope import metric_envelope

        def refurnish():
            updated = {}
            for old_room, room in zip(previous.rooms, f.rooms):
                objects = [o for o in f.objects if o.room_id == room.id]
                required = room.metadata.get('spatial_requirement')
                if joint and (objects or required):
                    env = metric_envelope(target, f, room)
                    if env['status'] != 'supported':
                        raise ValueError(f'{room.id}: unsupported active plate: {env["reason"]}')
                    capacity(room, env['bounds'])
                if objects:
                    try:
                        moved = adapt_furniture(b, target, previous, f, old_room, room,
                                                deepcopy(objects), shift, resizing)
                    except ValueError as exc:
                        if joint and ('insufficient capacity' in str(exc) or 'no feasible placement' in str(exc)):
                            raise CapacityConflict(room.id, str(exc)) from exc
                        raise
                    updated.update((o.id, o) for o in moved)
            return [updated[o.id] for o in f.objects]

        try:
            f.objects = refurnish()
        except CapacityConflict as conflict:
            if not joint or not floor_enabled(candidate,target,f):
                raise
            f.objects = coordination.revise(target, f, conflict, refurnish)
        for room in f.rooms:
            if 'realized_area_m2' in room.metadata:
                room.metadata['realized_area_m2'] = room.bounds.area
    if any(q.metadata.get('group_access') for q in parent.buildings):
        from cityg.planning.group_access import plan_group_access
        plan_group_access(candidate)
    target.metadata['site_coverage_ratio']=bounds.area/parent.bounds.area
    target.metadata['site_adaptation']={'before':asdict(old),'after':asdict(bounds),'request':dict(request),
        'operation':'resize' if resizing else 'translate',
        'preserved':['entity_ids','functions','floor_heights','door_widths'], 'furniture_scaled':False}
    if joint:
        target.metadata['site_adaptation']['coordination'] = {
            'exchanges': coordination.exchanges, 'revised_floors': coordination.revised_floors}
    if any(r['status']!='satisfied' for r in evaluate_requirements(candidate,requirements_for(target))):
        raise ValueError('Site adaptation violates existing interior requirements')
    return _commit(candidate,building_id,'building_site',_old_subtree_ids(city,building_id),
        producer='building_site_adaptation',metadata=target.metadata['site_adaptation'])


class BuildingSitePlanner:
    def replace(self, city, building_id, spec=None, *, details=None, exterior_only=False, **options):
        from cityg.subtree_transactions import _details_spec
        request = {**_details_spec(details), **(spec or {})}
        if options.get('service') is not None:
            from cityg.planning.site_coordination import coordinated_edit
            return coordinated_edit(city, building_id, request, options['service'], options['model_id'],
                                    exterior_only, finish=options.get('finish'))
        if options.get('finish'):
            return options['finish'](adapt_building_site(city, building_id, request, exterior_only=exterior_only))
        return adapt_building_site(city, building_id, request, exterior_only=exterior_only)
