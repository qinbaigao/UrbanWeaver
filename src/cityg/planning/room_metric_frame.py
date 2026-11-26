"""Plan reviewed furniture in realized metric rooms, not scaled template space.

Supports rectangular rooms clipped from multi-part and high-rise floor plates.
Unsupported/empty intersections fail closed rather than shrinking furniture.
"""
from copy import deepcopy
import math

from cityg.schemas import Point2D
from cityg.planning.room_groups import RoomDesignInfeasible


class MetricRoomInfeasible(RoomDesignInfeasible):
    """Do not fall back to dimension-distorting legacy placement."""


def restore_metric_object(obj, building, floor, room, envelope):
    """Read the same pose as the compiler, rejecting stale geometry bindings."""
    from cityg.planning.room_envelope import room_geometry_binding
    metric = obj.metadata.get('metric_room_placement')
    if not metric:
        if envelope['source'] == 'rectangular_shell_v1':
            return deepcopy(obj)
        raise MetricRoomInfeasible('missing metric pose for transformed room')
    b = building.footprint
    frame = envelope['frame']
    bounds = envelope['bounds']
    expected = {
        'canonical_binding': [obj.position.x,obj.position.y,obj.width_m,obj.depth_m,
                              obj.height_m,obj.rotation_deg,obj.asset_id],
        'source_room_geometry': room_geometry_binding(floor,room),
        'source_floor_vertical_extent': [floor.elevation_m,floor.height_m],
        'source_footprint': [b.min_x,b.min_y,b.max_x,b.max_y],
        'source_massing_parts': frame['parts'],
        'source_frame_bounds': [frame[k] for k in ('min_x','min_y','max_x','max_y')],
        'room_bounds': [bounds.min_x,bounds.min_y,bounds.max_x,bounds.max_y],
        'canonical_scale': envelope['scale'],
    }
    for key, value in expected.items():
        if metric.get(key) != value:
            raise MetricRoomInfeasible(f'stale metric pose binding: {key}')
    center, dims = metric.get('center', []), metric.get('dimensions_m', [])
    if (len(center)!=2 or len(dims)!=3 or
            not all(type(v) in (int,float) and math.isfinite(v) for v in [*center,*dims]) or
            min(dims)<=0):
        raise MetricRoomInfeasible('invalid metric pose dimensions')
    restored=deepcopy(obj)
    restored.position=Point2D(*center)
    restored.width_m,restored.depth_m,restored.height_m=dims
    return restored


def place_metric_room(detail, building, floor, room, program, seed):
    from cityg.planning.room_groups import place_room_design, RoomDesignInfeasible
    if building is None or detail.asset_resolver is None:
        return None
    from cityg.planning.room_envelope import metric_envelope
    envelope=metric_envelope(building,floor,room)
    if envelope['status']!='supported':
        raise MetricRoomInfeasible('Actual metric room unavailable: '+envelope['reason'])
    metric_room,metric_floor=envelope['room'],envelope['floor']
    for obj in floor.objects:
        if obj.room_id!=room.id:
            continue
        try:
            metric_floor.objects.append(restore_metric_object(obj,building,floor,room,envelope))
        except MetricRoomInfeasible:
            if obj.metadata.get('group_key') in program.design.protected_groups:
                raise
            # Unprotected legacy objects may be replaced, not used as pose priors.
    try:
        objects=place_room_design(detail,building,metric_floor,metric_room,program,seed,
                                  existing_objects=floor.objects)
    except RoomDesignInfeasible as exc:
        raise MetricRoomInfeasible(f"Actual metric room: {exc}") from exc
    for obj in objects:
        bind_metric_object(obj, building, floor, room, envelope)
    # The metric round trip is only for validation/placement. Preserve untouched
    # serialized poses and metadata exactly, including floating-point values.
    originals={o.id:o for o in floor.objects if o.room_id==room.id
               and o.metadata.get('group_key') in program.design.protected_groups}
    objects=[deepcopy(originals[o.id]) if o.id in originals else o for o in objects]
    return objects


def bind_metric_object(obj, building, floor, room, envelope):
    """Encode a physical furniture pose for canonical validation and rendering."""
    from cityg.planning.room_envelope import room_geometry_binding
    frame = envelope["frame"]
    bounds = building.footprint
    b = envelope["bounds"]
    sx, sy = envelope["scale"]
    ox, oy = envelope["offset"]
    if not math.isclose(obj.rotation_deg,round(obj.rotation_deg/90)*90,abs_tol=1e-6):
        raise MetricRoomInfeasible("Metric adapter currently requires quarter-turn local furniture")
    obj.metadata["metric_room_placement"]={"center":[obj.position.x,obj.position.y],
        "dimensions_m":[obj.width_m,obj.depth_m,obj.height_m],"canonical_scale":[sx,sy],
        "frame":"building_local_unrotated_metric","room_bounds":[b.min_x,b.min_y,b.max_x,b.max_y],
        "envelope_source":envelope['source'],
        "source_footprint":[bounds.min_x,bounds.min_y,bounds.max_x,bounds.max_y],
        "source_massing_parts":deepcopy(frame['parts']),
        "source_floor_vertical_extent":[floor.elevation_m,floor.height_m],
        "source_room_geometry":room_geometry_binding(floor,room),
        "source_frame_bounds":[frame[k] for k in ("min_x","min_y","max_x","max_y")]}
    obj.position=Point2D((obj.position.x-ox)/sx,(obj.position.y-oy)/sy)
    # Semantic boxes remain in the original City frame for validation and
    # editing. Compiler consumes the separate metric pose without re-scaling.
    swapped=round(obj.rotation_deg/90)%2
    obj.width_m/=sy if swapped else sx
    obj.depth_m/=sx if swapped else sy
    obj.metadata["metric_room_placement"]["canonical_binding"]=[obj.position.x,obj.position.y,
        obj.width_m,obj.depth_m,obj.height_m,obj.rotation_deg,obj.asset_id]
