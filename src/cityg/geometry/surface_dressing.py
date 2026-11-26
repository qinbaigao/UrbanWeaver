"""Resolve support-scoped small objects against compiled furniture geometry.

Runs after rotation/massing conformance. Nothing is placed from canonical room
fractions or from an unreviewed GLB bounding-box top. Children retain parent
ownership for isolation/incremental export, with a separate stable subentity ID.
"""
from dataclasses import dataclass
import math

from cityg.geometry.model import Vec3
from cityg.planning.surface_items import SURFACE_CATALOG
from cityg.geometry.indoor_assets import surface_asset, AXIS_ANGLES


@dataclass(frozen=True)
class Support:
    id: str
    primitive_id: str
    center: Vec3  # top of the support, not center of its solid slab
    width: float
    depth: float
    yaw: float
    kind: str
    reviewed_mesh: bool = False
    clearance_m: float | None = None


def _rotate(x, y, yaw):
    a = math.radians(yaw)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def surfaces(parts, kind):
    result = []
    for p in parts:
        if p.metadata.get("resolved_asset"):
            # Optional registry annotation, normalized in the actual mesh box:
            # center in [-.5,.5], size in (0,1], Z is the support plane.
            annotations = p.metadata.get("asset_metadata", {}).get("room_support_surfaces", [])
            if not isinstance(annotations, list):
                continue
            seen = set()
            for data in annotations[:16]:
                if not isinstance(data, dict) or data.get("verified") is not True or data.get("kind") != kind:
                    continue
                name = data.get("id")
                center, size = data.get("center"), data.get("size")
                if (not isinstance(name, str) or not name or name in seen
                        or not isinstance(center, list) or len(center) != 3
                        or not isinstance(size, list) or len(size) != 2):
                    continue
                if any(type(v) not in (int, float) or not math.isfinite(v) for v in center + size):
                    continue
                if (any(abs(v) > .5 for v in center) or any(not 0 < v <= 1 for v in size)
                        or abs(center[0])+size[0]/2 > .5 or abs(center[1])+size[1]/2 > .5):
                    continue
                seen.add(name)
                clearance = data.get("clearance_fraction")
                if clearance is not None:
                    if type(clearance) not in (int, float) or not math.isfinite(clearance) or clearance <= 0:
                        continue
                    clearance *= p.size.z
                elif kind == "shelves":
                    # A mesh box hides shelf cavities; an unknown upper slab
                    # cannot safely be ignored just because the lower one is verified.
                    continue
                dx, dy = _rotate(center[0]*p.size.x, center[1]*p.size.y, p.rotation_z_deg)
                result.append(Support(f"{p.id}:{name}", p.id,
                    Vec3(p.center.x+dx, p.center.y+dy, p.center.z+center[2]*p.size.z),
                    size[0]*p.size.x, size[1]*p.size.y, p.rotation_z_deg, kind, True, clearance))
            continue
        component = p.metadata.get("component", "")
        style = p.metadata.get("proxy_style")
        # Clipped/mesh-converted slabs do not necessarily retain a rectangular
        # support region. Skip rather than bridging an absent corner.
        if p.primitive_type != "box" or p.metadata.get("massing_clipped"):
            continue
        match = ((kind == "top" and component == "top" and style in {"table", "cabinet", "counter"})
                 or (kind == "shelves" and component.startswith("shelf_") and style == "rack"))
        if match:
            result.append(Support(p.id, p.id,
                Vec3(p.center.x, p.center.y, p.center.z+p.size.z/2),
                p.size.x, p.size.y, p.rotation_z_deg, kind))
    return sorted(result, key=lambda s: (s.center.z, s.id))


def overlaps(a, b, gap=.008):
    """Separating-axis test for yaw boxes, with exact vertical separation."""
    if abs(a.center.z-b.center.z) >= (a.size.z+b.size.z)/2 - 1e-6:
        return False
    axes = [_rotate(1, 0, p.rotation_z_deg) for p in (a, b)]
    axes += [(-x[1], x[0]) for x in axes[:]]
    for x, y in axes:
        radii = []
        for p in (a, b):
            ux, uy = _rotate(1, 0, p.rotation_z_deg)
            radii.append(abs(x*ux+y*uy)*p.size.x/2 + abs(-x*uy+y*ux)*p.size.y/2)
        if abs((a.center.x-b.center.x)*x+(a.center.y-b.center.y)*y) >= sum(radii)+gap:
            return False
    return True


def _parts(category, size):
    """Small honest procedural proxies; no asset downloading/generation here."""
    w, d, h = size
    if category == "monitor":
        return [("base", 0, 0, .012, w*.45, d, .024, "furniture_metal"),
                ("stand", 0, d*.25, h*.35, .035, .035, h*.65, "furniture_metal"),
                ("screen", 0, d*.25, h*.70, w, .035, h*.6, "furniture_blue")]
    if category == "desk_lamp":
        return [("base", 0, 0, .012, w, d, .024, "furniture_metal"),
                ("stem", 0, 0, h*.45, .018, .018, h*.85, "furniture_metal"),
                ("shade", 0, 0, h*.90, w, d, h*.20, "ceramic")]
    if category == "small_plant":
        return [("pot", 0, 0, h*.22, w*.65, d*.65, h*.44, "ceramic"),
                ("foliage", 0, 0, h*.69, w, d, h*.62, "furniture_fabric")]
    if category == "book_stack":
        return [(f"book_{i}", 0, 0, h*(i+.5)/3, w, d, h/3,
                 ("furniture_blue", "ceramic", "furniture_warm")[i]) for i in range(3)]
    return [(category, 0, 0, h/2, w, d, h, SURFACE_CATALOG[category].material)]


def compile_surface_items(compiler, floor, room, scene, owners, obstacles):
    design = room.metadata.get("room_design", {})
    requests = design.get("surface_items", [])
    if not requests:
        return
    objects = {o.metadata.get("design_member_id"): o for o in floor.objects if o.room_id == room.id}
    report = {"requested": sum(i["count"] for i in requests), "placed": 0,
              "representation": "static_visual_subentities", "items": [], "skipped": []}
    occupied = []
    for request in requests:
        obj = objects.get(request["support_member_id"])
        parts = owners.get(obj.id, []) if obj else []
        available = surfaces(parts, request["surface"])
        spec = SURFACE_CATALOG[request["category"]]
        # Use semantic furniture front, not arbitrary world compass directions.
        front = {"+X": 0, "+Y": 90, "-X": 180, "-Y": -90}.get(
            obj.metadata.get("front_axis") if obj else None, 90)
        for number in range(request["count"]):
            child_id = f"{room.id}_surface_{request['id']}_{number:02d}"
            record = surface_asset(compiler, request["category"], room.function, child_id,
                                   supports=available,front_angle=front)
            size = record.dimensions_m if record else spec.size
            child_front = AXIS_ANGLES[record.metadata["orientation"]["canonical_forward_axis"]] if record else -90
            chosen = None
            # Round-robin shelves, then fall back to others if one is blocked.
            ordered = available[number % len(available):] + available[:number % len(available)] if available else []
            for support in ordered:
                yaw = support.yaw + front - child_front
                if support.clearance_m is not None and size[2]+.003 > support.clearance_m:
                    continue
                relative = math.radians(yaw-support.yaw)
                w = abs(math.cos(relative))*size[0]+abs(math.sin(relative))*size[1]
                d = abs(math.sin(relative))*size[0]+abs(math.cos(relative))*size[1]
                margin = .015 if support.kind == "shelves" else .025
                xmax, ymax = (support.width-w)/2-margin, (support.depth-d)/2-margin
                if xmax < 0 or ymax < 0:
                    continue
                direction = {"front": front, "back": front+180, "left": front+90,
                             "right": front-90, "spread": 0}[request["placement"]]
                tx, ty = _rotate(1, 0, direction) if request["placement"] != "spread" else (0, 0)
                grid = [(x/4, y/4) for x in range(-4, 5) for y in range(-4, 5)]
                grid.sort(key=lambda p: ((p[0]-tx)**2+(p[1]-ty)**2, p))
                for nx, ny in grid:
                    lx, ly = nx*xmax, ny*ymax
                    dx, dy = _rotate(lx, ly, support.yaw)
                    center = Vec3(support.center.x+dx, support.center.y+dy, support.center.z+size[2]/2)
                    if center.z+size[2]/2 > floor.elevation_m+room.height_m-.10:
                        continue
                    envelope = compiler._box(child_id, obj.id, center, Vec3(*size), yaw,
                                             "room_decoration", spec.material, f"floor:{floor.id}")
                    # For reviewed mesh shelves the full mesh box encloses the
                    # cavity, so trust its annotation instead of treating that
                    # box as solid. Other furniture/walls still block placement.
                    if any(overlaps(envelope, p) for p in obstacles + occupied
                           if p.id != support.primitive_id):
                        continue
                    chosen = (support, envelope, lx, ly)
                    break
                if chosen:
                    break
            if chosen is None:
                report["skipped"].append({"id": child_id, "support_member_id": request["support_member_id"],
                    "reason": "no_verified_surface" if not available else "surface_full_or_obstructed"})
                continue
            support, envelope, lx, ly = chosen
            occupied.append(envelope)
            metadata = {"room_ids": [room.id], "visual_only": True, "surface_subentity": True,
                "subentity_id": child_id, "parent_object_id": obj.id,
                "support_member_id": request["support_member_id"], "surface_request_id": request["id"],
                "support_kind": "tabletop" if support.kind == "top" else "shelf",
                "support_primitive_id": support.primitive_id, "support_surface_id": support.id,
                "support_local_xy_m": [lx, ly], "asset_category": request["category"],
                "procedural_surface_proxy": record is None, "group_key": obj.metadata.get("group_key")}
            if record:
                metadata.update(resolved_asset=True, asset_id=record.asset_id, asset_source=record.source,
                    asset_license=record.license_id, asset_metadata=record.metadata,
                    asset_geometry_path=str(compiler.asset_registry.resolve_path(record.geometry_path)),
                    object_front_axis=record.metadata["orientation"]["canonical_forward_axis"])
                primitive = compiler._mesh(child_id, obj.id, envelope.center, envelope.size,
                    envelope.rotation_z_deg, "room_decoration", spec.material, f"floor:{floor.id}",
                    instance_key=f"asset_{record.asset_id}", metadata=metadata)
                primitive.collision_enabled = False
                scene.primitives.append(primitive)
            else:
                for name, dx, dy, z, w, d, h, material in _parts(request["category"], size):
                    ox, oy = _rotate(dx, dy, envelope.rotation_z_deg)
                    scene.primitives.append(compiler._box(f"{child_id}_{name}", obj.id,
                        Vec3(envelope.center.x+ox, envelope.center.y+oy, support.center.z+z),
                        Vec3(w, d, h), envelope.rotation_z_deg, "room_decoration", material,
                        f"floor:{floor.id}", collision_enabled=False, metadata={**metadata, "component": name}))
            report["placed"] += 1
            report["items"].append({"id": child_id, "category": request["category"],
                "parent_object_id": obj.id, "support_surface_id": support.id,
                "local_xy_m": [lx, ly], "bottom_z_m": support.center.z,
                "asset_id": record.asset_id if record else None, "dimensions_m": list(size),
                "rotation_deg": envelope.rotation_z_deg, "clearance_m": support.clearance_m})
    scene.metadata.setdefault("room_surface_items", {})[room.id] = report
