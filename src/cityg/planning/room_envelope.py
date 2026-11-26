"""Shared, conservative metric envelope for furnishing and agent context.

Rectangular intersections of the active massing union are supported. A concave
or disconnected intersection is reported, never silently filled by its AABB.
No geometry or door is mutated here.
"""
from dataclasses import replace
from copy import deepcopy

from cityg.schemas import Bounds2D, Point2D


def room_geometry_binding(floor, room):
    return {'bounds':[room.bounds.min_x,room.bounds.min_y,room.bounds.max_x,room.bounds.max_y],
            'height_m':room.height_m,
            'doors':sorted([[d.id,d.position.x,d.position.y,d.width_m]
                            for d in floor.doors if room.id in (d.room_a_id,d.room_b_id)])}


def massing_projection(building, floor):
    """Map planned room bounds into the unrotated, realized massing frame."""
    from cityg.geometry.compiler import GeometryCompiler

    frame = GeometryCompiler._massing_frame(building)
    bounds = building.footprint
    realized = floor.metadata.get('realized_floor_plate', {}).get('source') == 'highrise_massing_outline_v1'
    sx = 1. if realized else (frame['max_x']-frame['min_x'])/bounds.width
    sy = 1. if realized else (frame['max_y']-frame['min_y'])/bounds.depth
    ox = 0. if realized else bounds.center.x+frame['min_x']-bounds.min_x*sx
    oy = 0. if realized else bounds.center.y+frame['min_y']-bounds.min_y*sy
    return frame, realized, sx, sy, ox, oy


def metric_envelope(building, floor, room):
    from cityg.geometry.compiler import GeometryCompiler
    from cityg.geometry.model import GeometryScene
    from cityg.envelopes import envelope_config
    if envelope_config(building):
        return {'status':'unavailable','source':'active_massing_intersection_v1',
                'canonical_area_m2':room.bounds.area,'reason':'exterior_only_envelope',
                'floor_feedback':'Polygon/leaning exterior envelopes have no supported interior contract yet.'}
    if not building.metadata.get('massing_style'):
        # The compiler does not conform rectangular-shell interiors to its
        # default massing helper. Reusing that helper here invents a shrink.
        b=building.footprint
        if building.metadata.get('orientation_deg',0):
            return {'status':'unavailable','reason':'rotated_plain_shell_needs_explicit_contract'}
        if not b.contains_bounds(room.bounds):
            return {'status':'unavailable','reason':'room_outside_rectangular_shell'}
        doors=[deepcopy(d) for d in floor.doors if room.id in (d.room_a_id,d.room_b_id)]
        if any(not room.bounds.contains_point(d.position,tolerance=.01) for d in doors):
            return {'status':'unavailable','reason':'projected_door_outside_room'}
        part={'min_x':-b.width/2,'max_x':b.width/2,'min_y':-b.depth/2,'max_y':b.depth/2,'height_scale':1.}
        return {'status':'supported','source':'rectangular_shell_v1','bounds':room.bounds,
                'canonical_area_m2':room.bounds.area,'area_m2':room.bounds.area,
                'scale':[1.,1.],'offset':[0.,0.],
                'frame':{**part,'rotation':0.,'cos':1.,'sin':0.,'parts':[part]},
                'room':deepcopy(room),'floor':replace(floor,rooms=[deepcopy(room)],objects=[],doors=doors),
                'floor_feedback':None}
    compiler = GeometryCompiler()
    frame, realized, sx, sy, ox, oy = massing_projection(building, floor)
    bounds = building.footprint
    def point(p):
        return Point2D(p.x*sx+ox, p.y*sy+oy)
    lo, hi = point(Point2D(room.bounds.min_x,room.bounds.min_y)), point(Point2D(room.bounds.max_x,room.bounds.max_y))
    top = max(f.elevation_m+f.height_m for f in building.floors)
    parts = compiler._frame_at_height(frame, floor.elevation_m+room.height_m, top)['parts']
    rectangles = []
    for part in parts:
        x0, y0 = max(lo.x,bounds.center.x+part['min_x']), max(lo.y,bounds.center.y+part['min_y'])
        x1, y1 = min(hi.x,bounds.center.x+part['max_x']), min(hi.y,bounds.center.y+part['max_y'])
        if x1-x0>1e-6 and y1-y0>1e-6:
            rectangles.append(Bounds2D(x0,y0,x1,y1))
    result = {'status':'unavailable', 'source':'active_massing_intersection_v1',
              'canonical_area_m2':room.bounds.area, 'scale':[sx,sy], 'offset':[ox,oy],
              'frame':frame, 'floor_feedback':None}
    if not rectangles:
        return {**result, 'reason':'room_outside_active_floor_plate',
                'floor_feedback':'Repartition the floor; no usable room remains after massing clipping.'}
    xs=sorted({v for r in rectangles for v in (r.min_x,r.max_x)})
    ys=sorted({v for r in rectangles for v in (r.min_y,r.max_y)})
    area=sum((x1-x0)*(y1-y0) for x0,x1 in zip(xs,xs[1:]) for y0,y1 in zip(ys,ys[1:])
             if any(r.min_x <= (x0+x1)/2 <= r.max_x and r.min_y <= (y0+y1)/2 <= r.max_y for r in rectangles))
    actual=Bounds2D(xs[0],ys[0],xs[-1],ys[-1])
    if abs(actual.area-area)>1e-5 or min(actual.width,actual.depth)<=.5:
        return {**result, 'reason':'non_rectangular_or_narrow_realized_room', 'area_m2':area,
                'floor_feedback':'Needs polygon-aware floor/room replanning; do not fill the bounding rectangle.'}
    # Obtain the same door projection as the compiler, not an independently
    # clamped guess. Reject a projected entrance that no longer belongs here.
    door_scene=GeometryScene('envelope','z_up')
    for door in floor.doors:
        if room.id in (door.room_a_id,door.room_b_id):
            compiler._compile_door(floor,door,door_scene)
    primitives={p.owner_id:p for p in door_scene.primitives if p.semantic_class=='door'}
    doors=[]
    for door in floor.doors:
        if room.id not in (door.room_a_id,door.room_b_id):
            continue
        primitive=primitives.get(door.id)
        if primitive is None:
            return {**result, 'reason':'missing_compiled_door'}
        if realized:
            x,y,_,w,d=compiler._fit_rect_to_massing_parts(
                primitive.center.x-bounds.center.x,primitive.center.y-bounds.center.y,
                primitive.size.x,primitive.size.y,frame,primitive.center.z+primitive.size.z/2,top)
        else:
            x,y,w,d,_=compiler._door_fit_geometry(building,primitive,frame,top,
                                                 required_top_z=floor.elevation_m+floor.height_m)
        pos=Point2D(x+bounds.center.x,y+bounds.center.y)
        if not (actual.min_x-.25<=pos.x<=actual.max_x+.25 and actual.min_y-.25<=pos.y<=actual.max_y+.25):
            return {**result, 'reason':'projected_door_outside_room',
                    'floor_feedback':'Repair room/door binding at floor level before furnishing.'}
        doors.append(replace(door,position=pos,width_m=max(w,d)))
    metric_room=replace(room,bounds=actual,metadata=deepcopy(room.metadata))
    metric_floor=replace(floor,rooms=[metric_room],objects=[],doors=doors)
    return {**result, 'status':'supported', 'area_m2':area, 'bounds':actual,
            'room':metric_room,'floor':metric_floor,
            'floor_feedback':('Review unusually large private-room assignment, not just its furniture count.'
                              if room.function in {'bedroom','kitchen'} and area>60 else None)}


def envelope_context(envelope):
    """Small JSON-safe disclosure; no whole scene or compiler internals."""
    keys=('status','source','reason','canonical_area_m2','area_m2','floor_feedback')
    result={k:envelope[k] for k in keys if k in envelope}
    if envelope['status']=='supported':
        b=envelope['bounds']
        result.update(width_m=b.width,depth_m=b.depth,
                      bounds={k:getattr(b,k) for k in ('min_x','min_y','max_x','max_y')})
    return result
