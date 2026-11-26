"""Conservative runtime contracts for individually reviewed indoor meshes."""
import math

from cityg.assets import choose_asset_variant
from cityg.geometry.model import Vec3

AXIS_ANGLES = {"+X": 0, "+Y": 90, "-X": 180, "-Y": -90}


def surface_asset(compiler, category, room_type, key, *, supports=None, front_angle=90):
    registry = getattr(compiler, "asset_registry", None)
    if registry is None:
        return None
    candidates = registry.search(category, category=category, limit=100, require_geometry=True,
                                 environment="indoor", room_type=room_type)
    candidates = [(record, score) for record, score in candidates
        if record.metadata.get("runtime_enabled") is True
        and record.metadata.get("indoor_annotation_version") == 1
        and record.metadata.get("placement_kind") == "surface"
        and record.metadata.get("orientation", {}).get("orientation_confidence") == "reviewed"
        and record.metadata.get("orientation", {}).get("canonical_forward_axis") in AXIS_ANGLES
        and record.dimensions_m and all(math.isfinite(v) and v > 0 for v in record.dimensions_m)]
    if supports is not None:
        def fits(record):
            relative=math.radians(front_angle-AXIS_ANGLES[record.metadata['orientation']['canonical_forward_axis']])
            x,y,z=record.dimensions_m
            w=abs(math.cos(relative))*x+abs(math.sin(relative))*y
            d=abs(math.sin(relative))*x+abs(math.cos(relative))*y
            return any(w+2*(.015 if s.kind=='shelves' else .025)<=s.width and
                       d+2*(.015 if s.kind=='shelves' else .025)<=s.depth and
                       (s.clearance_m is None or z+.003<=s.clearance_m) for s in supports)
        candidates=[(record,score) for record,score in candidates if fits(record)]
    return choose_asset_variant(candidates, key, max_triangle_count=120000)


def preserve_indoor_proportions(scene):
    """Shrink uniformly inside an already conformed box, preserving its bottom.

    Never enlarge/reposition into adjacent furniture. Applied before support
    dressing so normalized annotations use the actual final mesh size.
    """
    for primitive in scene.primitives:
        meta = primitive.metadata.get("asset_metadata", {})
        dimensions = meta.get("physical_dimensions_m")
        if (not primitive.metadata.get("resolved_asset") or meta.get("indoor_annotation_version") != 1
                or not dimensions or not primitive.semantic_class.startswith("furniture_")):
            continue
        if len(dimensions) != 3 or any(not math.isfinite(v) or v <= 0 for v in dimensions):
            raise ValueError("Invalid reviewed indoor dimensions")
        before = primitive.size
        factor = min(1., before.x/dimensions[0], before.y/dimensions[1], before.z/dimensions[2])
        size = Vec3(*(v*factor for v in dimensions))
        primitive.center = Vec3(primitive.center.x, primitive.center.y,
                                primitive.center.z-before.z/2+size.z/2)
        primitive.size = size
        primitive.metadata.update(indoor_uniform_scale=factor, indoor_proportions_preserved=True)
        if factor < .9:
            scene.metadata.setdefault("indoor_asset_fit_warnings", []).append({
                "primitive_id":primitive.id,"asset_id":primitive.metadata.get("asset_id"),
                "scale":factor,"reason":"legacy_or_irregular_frame_requires_metric_room_replanning"})
