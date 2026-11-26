"""Bounded room dressing, applied AFTER massing conformance.

Accents are visual-only, explicitly supported by an existing wall/table primitive.
Unknown GLB surfaces are not inferred from bounding boxes. Embedded GLB materials
are preserved. No furniture positions or architectural geometry are changed.
"""
from collections import defaultdict
import math

from cityg.geometry.model import MaterialSpec, Vec3
from cityg.planning.room_design import PALETTES
from cityg.geometry.surface_dressing import compile_surface_items
from cityg.geometry.indoor_assets import preserve_indoor_proportions


def compile_room_appearance(compiler, city, scene):
    preserve_indoor_proportions(scene)
    owners, walls, floor_obstacles = defaultdict(list), defaultdict(list), defaultdict(list)
    for primitive in scene.primitives:
        owners[primitive.owner_id].append(primitive)
        if primitive.layer_id.startswith("floor:"):
            floor_obstacles[primitive.layer_id].append(primitive)
        if primitive.semantic_class == "interior_wall":
            for room_id in primitive.metadata.get("room_ids", []):
                walls[room_id].append(primitive)
    materials = {m.id for m in scene.materials}
    for building in city.iter_buildings():
        for floor in building.floors:
            from cityg.planning.interior_scope import floor_enabled
            if not floor_enabled(city,building,floor):continue
            for room in floor.rooms:
                design = room.metadata.get("room_design", {})
                if design.get("status") != "accepted" or not walls[room.id]:
                    continue
                palette = design.get("palette", "warm")
                for role, color in PALETTES[palette].items():
                    name = f"room_{palette}_{role}"
                    if name not in materials:
                        scene.materials.append(MaterialSpec(name, color, roughness=.78))
                        materials.add(name)
                for wall in walls[room.id]:
                    # A shared wall cannot simultaneously have two palettes.
                    if wall.metadata.get("room_ids") == [room.id]:
                        wall.material_id = f"room_{palette}_wall"
                from cityg.geometry.room_finishes import apply_room_finishes
                apply_room_finishes(compiler, building, floor, room, scene, walls[room.id])
                room_parts = []
                for obj in floor.objects:
                    if obj.room_id != room.id:
                        continue
                    parts = owners[obj.id]
                    room_parts.extend(parts)
                    for part in parts:
                        if part.metadata.get("resolved_asset"):
                            continue
                        if part.material_id in {"furniture_fabric", "furniture_blue", "furniture_warm"}:
                            part.material_id = f"room_{palette}_accent"
                        elif part.material_id == "furniture_wood":
                            part.material_id = f"room_{palette}_floor"
                    if design.get("tabletop") and not design.get("surface_items"):
                        tops = [p for p in parts if p.metadata.get("component") == "top"
                                and p.metadata.get("proxy_style") == "table"]
                        if tops:
                            top = tops[0]
                            scene.primitives.append(compiler._box(
                                f"{top.id}_books", obj.id,
                                Vec3(top.center.x, top.center.y, top.center.z+top.size.z/2+.035),
                                Vec3(min(.28, top.size.x*.4), min(.20, top.size.y*.4), .07),
                                top.rotation_z_deg, "room_decoration", f"room_{palette}_accent", top.layer_id,
                                collision_enabled=False, metadata={"room_ids":[room.id], "visual_only":True,
                                    "support_kind":"tabletop", "support_primitive_id":top.id}))
                compile_surface_items(compiler, floor, room, scene, owners,
                                      floor_obstacles[f"floor:{floor.id}"])
                if room.metadata.get('detail_tier')=='hero':
                    from cityg.planning.room_envelope import metric_envelope, envelope_context
                    from cityg.planning.furnishing_sufficiency import assess_furnishing, compiled_footprint_area
                    envelope=metric_envelope(building,floor,room)
                    report=assess_furnishing(room,floor.objects,area_m2=envelope.get('area_m2'),
                        surface_report=scene.metadata.get('room_surface_items',{}).get(room.id),
                        realized_footprint_m2=compiled_footprint_area(
                            [o for o in floor.objects if o.room_id==room.id],owners,
                            float(building.metadata.get('orientation_deg',0))))
                    report['envelope']=envelope_context(envelope)
                    if envelope['status']!='supported':
                        report.update(needs_review=True,major_footprint_ratio=None,area_m2=None)
                        report['reasons'].append('floor_geometry_needs_replanning')
                    scene.metadata.setdefault('room_furnishing_sufficiency',{})[room.id]=report
                if not design.get("wall_art") or not room_parts:
                    continue
                # Only use a solid wall segment, never span a doorway/header.
                candidates = [w for w in walls[room.id] if max(w.size.x,w.size.y)>1.1
                              and w.size.z>2.2 and "header" not in w.metadata.get("wall_role", "")]
                if not candidates:
                    continue
                wall = max(candidates, key=lambda w:max(w.size.x,w.size.y))
                angle = math.radians(wall.rotation_z_deg)
                nx,ny = (-math.sin(angle), math.cos(angle)) if wall.size.x>wall.size.y else (math.cos(angle),math.sin(angle))
                cx = sum(p.center.x for p in room_parts)/len(room_parts)
                cy = sum(p.center.y for p in room_parts)/len(room_parts)
                sign = 1 if (cx-wall.center.x)*nx+(cy-wall.center.y)*ny>=0 else -1
                offset = min(wall.size.x,wall.size.y)/2+.025
                center = Vec3(wall.center.x+nx*sign*offset, wall.center.y+ny*sign*offset, floor.elevation_m+1.65)
                # Tall furniture can hide or intersect the chosen wall art.
                if any(p.center.z+p.size.z/2>center.z-.25 and
                       math.hypot(p.center.x-center.x,p.center.y-center.y)<math.hypot(p.size.x,p.size.y)/2+.5
                       for p in room_parts):
                    continue
                size = Vec3(.8,.025,.5) if wall.size.x>wall.size.y else Vec3(.025,.8,.5)
                scene.primitives.append(compiler._box(
                    f"{room.id}_wall_art", room.id, center, size, wall.rotation_z_deg,
                    "room_decoration", f"room_{palette}_accent", f"floor:{floor.id}",
                    collision_enabled=False, metadata={"room_ids":[room.id], "visual_only":True,
                        "support_kind":"wall", "support_primitive_id":wall.id}))
