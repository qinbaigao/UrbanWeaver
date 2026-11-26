"""Deterministic floor-detail planning and procedural indoor asset contracts.

The module deliberately separates semantic intent (``FurnishingProgram``) from
metric placement (``FloorDetailAgent``). RoomProgramAgent authors the former,
while this dependency-free implementation remains the reproducible fallback.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from copy import deepcopy
from cityg.planning.room_design import RoomDesign

from cityg.assets import AssetResolver
from cityg.planning.furnishing_gate import furnishing_non_degradation_check
from cityg.schemas import Bounds2D, Building, City, Floor, InteriorObject, Point2D, Room


@dataclass(frozen=True)
class AssetSpec:
    id: str
    category: str
    width_m: float
    depth_m: float
    height_m: float
    semantic_class: str
    material_id: str
    proxy_style: str
    front_axis: str = "+Y"
    orientation_confidence: str = "default"
    head_axis: str | None = None


@dataclass(frozen=True)
class ObjectRequest:
    category: str
    count: int
    placement: str
    required: bool = True


@dataclass(frozen=True)
class SpatialRelation:
    """A semantic relation that the metric placer may realize locally.

    The relation deliberately refers to semantic categories rather than object
    IDs.  This keeps the LLM contract stable when a request asks for several
    chairs or desks; the deterministic placer resolves the first compatible
    instance and validates the resulting geometry.
    """

    subject_category: str
    relation: str
    target_category: str
    distance_m: float = 1.0
    required: bool = False

    def validate(self, catalog: dict[str, AssetSpec]) -> None:
        allowed = {"near", "in_front_of", "beside", "faces", "against_wall"}
        if self.subject_category not in catalog:
            raise ValueError(f"Unknown relation subject category: {self.subject_category}")
        if self.target_category not in catalog and self.target_category not in {"wall", "door"}:
            raise ValueError(f"Unknown relation target category: {self.target_category}")
        if self.relation not in allowed:
            raise ValueError(f"Unknown spatial relation: {self.relation}")
        if not 0.0 <= self.distance_m <= 5.0:
            raise ValueError("Spatial relation distance_m must be within [0, 5]")


@dataclass(frozen=True)
class FurnishingProgram:
    room_id: str
    room_type: str
    style: str
    density: float
    requests: tuple[ObjectRequest, ...]
    relations: tuple[SpatialRelation, ...] = ()
    design: RoomDesign | None = None

    @property
    def requested_major_count(self) -> int:
        if self.design is not None:
            return sum(1 + len(g["members"]) for g in self.design.groups)
        return sum(item.count for item in self.requests)

    def validate(self, catalog: dict[str, AssetSpec]) -> None:
        if self.design is not None:
            self.design.validate(catalog)
        if not 0.0 <= self.density <= 1.0:
            raise ValueError("Furnishing density must be within [0, 1]")
        for request in self.requests:
            if request.category not in catalog:
                raise ValueError(f"Unknown indoor asset category: {request.category}")
            if request.count < 0:
                raise ValueError("Object request count must be non-negative")
            if request.placement not in {"wall_back", "wall_side", "center", "grid"}:
                raise ValueError(f"Unknown placement strategy: {request.placement}")
        for relation in self.relations:
            relation.validate(catalog)


def _asset(
    category: str,
    size: tuple[float, float, float],
    semantic: str,
    material: str,
    proxy_style: str,
    front_axis: str = "+Y",
) -> AssetSpec:
    return AssetSpec(
        id=f"procedural::{category}::v1",
        category=category,
        width_m=size[0],
        depth_m=size[1],
        height_m=size[2],
        semantic_class=semantic,
        material_id=material,
        proxy_style=proxy_style,
        front_axis=front_axis,
    )


ASSET_CATALOG: dict[str, AssetSpec] = {
    item.category: item
    for item in (
        _asset("desk", (1.40, 0.70, 0.75), "furniture_table", "furniture_wood", "table"),
        _asset("office_chair", (0.58, 0.58, 1.00), "furniture_seating", "furniture_blue", "chair", "-Y"),
        _asset("cabinet", (1.10, 0.45, 1.80), "furniture_storage", "furniture_wood_dark", "cabinet"),
        _asset("meeting_table", (2.20, 1.10, 0.75), "furniture_table", "furniture_wood", "table"),
        _asset("meeting_chair", (0.54, 0.54, 0.92), "furniture_seating", "furniture_blue", "chair", "-Y"),
        _asset("sofa", (2.10, 0.88, 0.88), "furniture_seating", "furniture_fabric", "sofa", "-Y"),
        _asset("coffee_table", (1.10, 0.62, 0.42), "furniture_table", "furniture_wood", "table"),
        _asset("tv_console", (1.60, 0.42, 0.62), "furniture_storage", "furniture_wood_dark", "cabinet"),
        _asset("bed", (1.65, 2.05, 0.72), "furniture_bed", "furniture_fabric", "bed", "-Y"),
        _asset("bedside_table", (0.48, 0.44, 0.52), "furniture_table", "furniture_wood", "cabinet"),
        _asset("wardrobe", (1.55, 0.58, 2.05), "furniture_storage", "furniture_wood_dark", "cabinet"),
        _asset("bookcase", (1.10, 0.38, 1.85), "furniture_storage", "furniture_wood", "rack"),
        _asset("kitchen_counter", (2.10, 0.62, 0.92), "furniture_fixture", "furniture_wood", "counter"),
        _asset("dining_table", (1.45, 0.82, 0.75), "furniture_table", "furniture_wood", "table"),
        _asset("dining_chair", (0.50, 0.50, 0.90), "furniture_seating", "furniture_warm", "chair", "-Y"),
        _asset("toilet", (0.42, 0.70, 0.78), "furniture_fixture", "ceramic", "toilet"),
        _asset("sink", (0.62, 0.48, 0.86), "furniture_fixture", "ceramic", "sink"),
        _asset("refrigerator", (0.65, 0.70, 1.80), "furniture_equipment", "furniture_metal", "cabinet"),
        _asset("oven", (0.60, 0.65, 0.90), "furniture_equipment", "furniture_metal", "cabinet"),
        _asset("shower", (0.90, 0.90, 2.00), "furniture_fixture", "ceramic", "box"),
        _asset("storage_rack", (1.80, 0.55, 2.00), "furniture_storage", "furniture_metal", "rack"),
        _asset("reception_desk", (2.20, 0.72, 1.08), "furniture_table", "furniture_wood", "counter"),
        _asset("waiting_bench", (1.65, 0.62, 0.88), "furniture_seating", "furniture_blue", "sofa", "-Y"),
        _asset("workbench", (1.85, 0.78, 0.90), "furniture_table", "furniture_metal", "table"),
        _asset("machine_tool", (1.20, 0.95, 1.55), "furniture_equipment", "furniture_metal", "machine"),
        _asset("control_console", (1.45, 0.66, 1.18), "furniture_equipment", "furniture_metal", "console"),
        _asset("equipment_cabinet", (0.82, 0.72, 1.95), "furniture_equipment", "furniture_metal", "cabinet"),
        _asset("checkout_counter", (1.75, 0.68, 1.02), "furniture_table", "furniture_wood", "counter"),
        _asset("display_shelf", (1.55, 0.62, 1.65), "furniture_storage", "furniture_wood", "rack"),
    )
}


ROOM_TEMPLATES: dict[str, tuple[ObjectRequest, ...]] = {
    "living_room": (
        ObjectRequest("sofa", 1, "wall_back"),
        ObjectRequest("coffee_table", 1, "center"),
        ObjectRequest("tv_console", 1, "wall_side"),
    ),
    "bedroom": (
        ObjectRequest("bed", 1, "wall_back"),
        ObjectRequest("bedside_table", 1, "wall_back", False),
        ObjectRequest("wardrobe", 1, "wall_side"),
    ),
    "kitchen": (
        ObjectRequest("kitchen_counter", 1, "wall_back"),
        ObjectRequest("dining_table", 1, "center", False),
        ObjectRequest("dining_chair", 2, "grid", False),
    ),
    "bathroom": (
        ObjectRequest("toilet", 1, "wall_back"),
        ObjectRequest("sink", 1, "wall_side"),
    ),
    "restroom": (
        ObjectRequest("toilet", 2, "wall_back"),
        ObjectRequest("sink", 1, "wall_side"),
    ),
    "study": (
        ObjectRequest("desk", 1, "wall_back"),
        ObjectRequest("office_chair", 1, "center"),
        ObjectRequest("bookcase", 1, "wall_side"),
    ),
    "office": (
        ObjectRequest("desk", 2, "grid"),
        ObjectRequest("office_chair", 2, "grid"),
        ObjectRequest("cabinet", 1, "wall_back", False),
    ),
    "open_office": (
        ObjectRequest("desk", 4, "grid"),
        ObjectRequest("office_chair", 4, "grid"),
        ObjectRequest("cabinet", 2, "wall_back", False),
    ),
    "meeting_room": (
        ObjectRequest("meeting_table", 1, "center"),
        ObjectRequest("meeting_chair", 4, "grid", False),
    ),
    "reception": (
        ObjectRequest("reception_desk", 1, "wall_back"),
        ObjectRequest("waiting_bench", 2, "wall_side", False),
    ),
    "break_room": (
        ObjectRequest("kitchen_counter", 1, "wall_back"),
        ObjectRequest("dining_table", 1, "center"),
        ObjectRequest("dining_chair", 2, "grid", False),
    ),
    "service_hall": (
        ObjectRequest("reception_desk", 1, "wall_back"),
        ObjectRequest("waiting_bench", 2, "wall_side", False),
    ),
    "waiting_room": (ObjectRequest("waiting_bench", 3, "grid"),),
    "equipment_room": (
        ObjectRequest("equipment_cabinet", 2, "wall_back"),
        ObjectRequest("control_console", 1, "wall_side", False),
    ),
    "storage": (ObjectRequest("storage_rack", 3, "wall_side"),),
    "service_room": (
        ObjectRequest("storage_rack", 2, "wall_side"),
        ObjectRequest("equipment_cabinet", 1, "wall_back", False),
    ),
    "workshop": (
        ObjectRequest("workbench", 2, "grid"),
        ObjectRequest("machine_tool", 1, "wall_back"),
    ),
    "control_room": (
        ObjectRequest("control_console", 2, "wall_back"),
        ObjectRequest("office_chair", 2, "grid", False),
    ),
    "utility_room": (ObjectRequest("equipment_cabinet", 3, "wall_back"),),
    "shop": (
        ObjectRequest("display_shelf", 3, "grid"),
        ObjectRequest("checkout_counter", 1, "wall_back"),
    ),
}


FALLBACK_TEMPLATE = (
    ObjectRequest("desk", 1, "wall_back"),
    ObjectRequest("office_chair", 1, "center", False),
)


class FloorDetailAgent:
    """Compile room-type programs into collision-aware canonical objects."""

    wall_clearance_m = 0.32
    object_clearance_m = 0.16
    door_depth_clearance_m = 1.35
    door_side_clearance_m = 0.35

    def __init__(
        self,
        catalog: dict[str, AssetSpec] | None = None,
        asset_resolver: AssetResolver | None = None,
        program_overrides: dict[str, FurnishingProgram] | None = None,
    ) -> None:
        self.catalog = catalog or ASSET_CATALOG
        self.asset_resolver = asset_resolver
        self.program_overrides = dict(program_overrides or {})

    def populate(self, city: City, *, seed: int) -> dict[str, int | float]:
        requested = placed = furnished_rooms = 0
        for building in city.iter_buildings():
            for floor in building.floors:
                floor.objects.clear()
                for room in floor.rooms:
                    room.object_ids.clear()
                from cityg.planning.interior_scope import floor_enabled
                if not floor_enabled(city,building,floor):
                    continue
                for room in floor.rooms:
                    if room.function == "corridor":
                        continue
                    program = self.program_for(room)
                    program.validate(self.catalog)
                    requested += program.requested_major_count
                    objects = self._place_program(building, floor, room, program, seed)
                    floor.objects.extend(objects)
                    room.object_ids.extend(item.id for item in objects)
                    placed += len(objects)
                    furnished_rooms += bool(objects)

        room_count = sum(
            room.function != "corridor" for room in city.iter_rooms()
        )
        return {
            "planner": "deterministic_floor_detail_v1",
            "asset_backend": "local_registry_then_provider"
            if self.asset_resolver is not None
            else "procedural_proxy",
            "catalog_size": len(self.catalog),
            "requested_object_count": requested,
            "placed_object_count": placed,
            "furnished_room_count": furnished_rooms,
            "furnishable_room_count": room_count,
            "furnished_room_ratio": round(furnished_rooms / room_count, 6)
            if room_count
            else 0.0,
        }

    def populate_rooms(
        self, city: City, room_ids: set[str] | list[str] | tuple[str, ...], *, seed: int
    ) -> dict[str, int | float]:
        """Repopulate only the requested rooms, preserving the rest of the city.

        This is the commit primitive used by visual review.  A room refinement
        must not silently clear objects from unrelated rooms on the same floor.
        """
        wanted = set(room_ids)
        requested = placed = furnished_rooms = matched = gate_rejected = 0
        for building in city.iter_buildings():
            for floor in building.floors:
                for room in floor.rooms:
                    if room.id not in wanted or room.function == "corridor":
                        continue
                    matched += 1
                    before_objects = [obj for obj in floor.objects if obj.room_id == room.id]
                    before_metadata = deepcopy(room.metadata)
                    program = self.program_for(room)
                    program.validate(self.catalog)
                    requested += program.requested_major_count
                    try:
                        objects = self._place_program(building, floor, room, program, seed)
                    except Exception:
                        room.metadata = before_metadata
                        raise
                    gate = furnishing_non_degradation_check(before_objects, objects, room)
                    if not gate["ok"]:
                        rejected_design = room.metadata.get("room_design")
                        room.metadata = before_metadata
                        room.metadata["room_design_rejected"] = {"gate": gate, "proposal": rejected_design}
                        gate_rejected += 1
                        placed += len(before_objects)
                        furnished_rooms += bool(before_objects)
                    else:
                        floor.objects[:] = [obj for obj in floor.objects if obj.room_id != room.id]
                        floor.objects.extend(objects)
                        room.object_ids[:] = [item.id for item in objects]
                        room.metadata.pop("room_design_rejected", None)
                        placed += len(objects)
                        furnished_rooms += bool(objects)
        return {
            "requested_room_count": len(wanted),
            "matched_room_count": matched,
            "requested_object_count": requested,
            "placed_object_count": placed,
            "furnished_room_count": furnished_rooms,
            "furnishing_non_degradation_gate_rejected_room_count": gate_rejected,
        }

    def program_for(self, room: Room) -> FurnishingProgram:
        override = self.program_overrides.get(room.id)
        if override is not None:
            return override
        requests = ROOM_TEMPLATES.get(room.function, FALLBACK_TEMPLATE)
        requested_area = sum(
            self.catalog[item.category].width_m
            * self.catalog[item.category].depth_m
            * item.count
            for item in requests
        )
        density = min(1.0, requested_area / max(room.bounds.area, 1e-6))
        return FurnishingProgram(
            room_id=room.id,
            room_type=room.function,
            style="functional_neutral",
            density=round(density, 6),
            requests=requests,
        )

    def _place_program(
        self,
        building: Building,
        floor: Floor,
        room: Room,
        program: FurnishingProgram,
        seed: int,
    ) -> list[InteriorObject]:
        if program.design is not None:
            from cityg.planning.room_groups import place_room_design, RoomDesignInfeasible
            try:
                from cityg.planning.room_metric_frame import place_metric_room, MetricRoomInfeasible
                objects = place_metric_room(self, building, floor, room, program, seed)
                if objects is None:
                    objects = place_room_design(self, building, floor, room, program, seed)
                room.metadata["room_design"] = {"status": "accepted", "version": 3,
                    "style": program.style, "density": program.density,
                    **program.design.to_dict(), "object_count": len(objects),
                    "constraint_checks": {"wall_bindings":True, "category_use_spaces":True,
                                          "functional_regions":True, "reserved_areas_clear":True,
                                          "door_to_use_space_connectivity":True,
                                          "furnishing_contract":program.design.furnishing_brief is not None,
                                          "geometry_source":(objects[0].metadata['metric_room_placement']['envelope_source'] if objects and
                                              objects[0].metadata.get('metric_room_placement') else "planned_rectangle"),
                                          "clearance_width_m":.55}}
                return objects
            except RoomDesignInfeasible as exc:
                if isinstance(exc, MetricRoomInfeasible) or program.design.protected_groups or any(obj.room_id==room.id for obj in floor.objects):
                    # Refinement is transactional: never bypass a failed wall,
                    # access or protected-group contract through legacy layout.
                    raise
                room.metadata["room_design"] = {"status": "fallback", "reason": str(exc),
                                                "requested_design": program.design.to_dict()}
                if not program.requests:
                    from dataclasses import replace
                    program = replace(program, requests=ROOM_TEMPLATES.get(room.function, FALLBACK_TEMPLATE))
        else:
            room.metadata.pop("room_design", None)
        usable = room.bounds.inset(self.wall_clearance_m)
        if usable.width <= 0.5 or usable.depth <= 0.5:
            return []
        door_zones, front_is_min_y = self._door_clearance_zones(floor, room)
        occupied: list[Bounds2D] = []
        result: list[InteriorObject] = []
        serial = 0
        for request in program.requests:
            asset = self.catalog[request.category]
            for request_index in range(request.count):
                resolved = self._resolve_asset(asset, room_type=room.function, style=program.style)
                if resolved is not None:
                    asset = resolved
                rng = random.Random(
                    f"{seed}:{building.id}:{floor.id}:{room.id}:{asset.id}:{request_index}"
                )
                placement = self._find_placement(
                    room,
                    usable,
                    asset,
                    request.placement,
                    occupied,
                    door_zones,
                    front_is_min_y,
                    rng,
                )
                if placement is None:
                    continue
                position, rotation, bounds, scale = placement
                obj = InteriorObject(
                    id=f"{room.id}_object_{serial:02d}_{asset.category}",
                    room_id=room.id,
                    category=asset.category,
                    asset_id=asset.id,
                    position=position,
                    width_m=asset.width_m * scale,
                    depth_m=asset.depth_m * scale,
                    height_m=asset.height_m * scale,
                    rotation_deg=rotation,
                    metadata={
                        "planner": "FloorDetailAgent",
                        "placement_strategy": request.placement,
                        "asset_scale": scale,
                        "front_axis": asset.front_axis,
                        "orientation_confidence": asset.orientation_confidence,
                        "required": request.required,
                        "room_type": room.function,
                    },
                )
                result.append(obj)
                occupied.append(bounds)
                serial += 1
        self._apply_relations(
            result,
            program.relations,
            usable,
            occupied,
            door_zones,
        )
        return result

    def _apply_relations(
        self,
        objects: list[InteriorObject],
        relations: tuple[SpatialRelation, ...],
        usable: Bounds2D,
        occupied: list[Bounds2D],
        door_zones: list[Bounds2D],
    ) -> None:
        """Apply safe semantic relations after coarse placement.

        Relations are intentionally a post-placement refinement rather than a
        second free-form solver.  If a requested move would leave the room,
        block a door, or collide with another object, the original placement is
        retained and the relation is recorded as unsatisfied in object metadata.
        This preserves the deterministic fallback for ordinary rooms.
        """
        if not relations or not objects:
            return
        for relation in relations:
            subject = next(
                (item for item in objects if item.category == relation.subject_category),
                None,
            )
            target = next(
                (item for item in objects if item.category == relation.target_category),
                None,
            )
            if subject is None or (target is None and relation.target_category != "wall"):
                continue
            original_position = subject.position
            original_rotation = subject.rotation_deg
            original_bounds = subject.bounds
            relation_ok = False
            if relation.relation == "faces" and target is not None:
                dx = target.position.x - subject.position.x
                dy = target.position.y - subject.position.y
                if abs(dx) + abs(dy) > 1e-6:
                    subject.rotation_deg = self._rotation_for_front(
                        str(subject.metadata.get("front_axis", "+Y")), math.degrees(math.atan2(dy, dx)))
                    relation_ok = self._relation_position_valid(
                        subject, objects, usable, door_zones
                    )
            elif relation.relation == "against_wall":
                # The base request already supports wall_back/wall_side.  Keep
                # this relation as a validated semantic annotation.
                relation_ok = min(abs(subject.bounds.min_x-usable.min_x),abs(subject.bounds.max_x-usable.max_x),
                                  abs(subject.bounds.min_y-usable.min_y),abs(subject.bounds.max_y-usable.max_y)) <= .35
            elif target is not None:
                dx = subject.position.x - target.position.x
                dy = subject.position.y - target.position.y
                length = math.hypot(dx, dy)
                if length < 1e-6:
                    dx, dy, length = 0.0, 1.0, 1.0
                ux, uy = dx / length, dy / length
                distance = relation.distance_m
                if relation.relation == "in_front_of":
                    distance = max(0.7, distance)
                    offset = {"+X":0,"+Y":90,"-X":180,"-Y":-90}.get(target.metadata.get("front_axis", "+Y"),90)
                    angle = math.radians(target.rotation_deg+offset)
                    ux, uy = math.cos(angle), math.sin(angle)
                elif relation.relation == "beside":
                    distance = max(0.45, distance)
                    offset = {"+X":0,"+Y":90,"-X":180,"-Y":-90}.get(target.metadata.get("front_axis", "+Y"),90)
                    angle = math.radians(target.rotation_deg+offset-90)
                    ux, uy = math.cos(angle), math.sin(angle)
                target_half = max(target.width_m, target.depth_m) / 2.0
                subject_half = max(subject.width_m, subject.depth_m) / 2.0
                subject.position = Point2D(
                    target.position.x + ux * (target_half + subject_half + distance),
                    target.position.y + uy * (target_half + subject_half + distance),
                )
                relation_ok = self._relation_position_valid(
                    subject, objects, usable, door_zones
                )
            if not relation_ok:
                subject.position = original_position
                subject.rotation_deg = original_rotation
            subject.metadata.setdefault("spatial_relations", []).append(
                {
                    "relation": relation.relation,
                    "target_category": relation.target_category,
                    "distance_m": relation.distance_m,
                    "satisfied": relation_ok,
                }
            )
            # Keep the occupied list coherent for subsequent relation checks.
            if relation_ok:
                for index, bounds in enumerate(occupied):
                    if bounds == original_bounds:
                        occupied[index] = subject.bounds
                        break

    def _relation_position_valid(
        self,
        subject: InteriorObject,
        objects: list[InteriorObject],
        usable: Bounds2D,
        door_zones: list[Bounds2D],
    ) -> bool:
        bounds = subject.bounds
        # Same micrometre tolerance as the geometry predicates: a quarter-turn
        # or translated wall contact must not fail from floating-point roundoff.
        if not usable.contains_bounds(bounds):
            return False
        expanded = Bounds2D(
            bounds.min_x - self.object_clearance_m,
            bounds.min_y - self.object_clearance_m,
            bounds.max_x + self.object_clearance_m,
            bounds.max_y + self.object_clearance_m,
        )
        for other in objects:
            if other is subject:
                continue
            if expanded.overlaps_area(other.bounds):
                return False
        return not any(expanded.overlaps_area(zone) for zone in door_zones)

    def _resolve_asset(self, asset: AssetSpec, *, room_type: str, style: str = "functional_neutral", support_kinds=(), preferred_asset_id=None) -> AssetSpec | None:
        if self.asset_resolver is None:
            return None
        record = None
        if preferred_asset_id is not None:
            # An already accepted instance can have a prototype-local role
            # (e.g. an office chair in a living-room workspace). Do not rerun
            # global room tags and silently replace it with a primitive.
            record = self.asset_resolver.registry.get(preferred_asset_id)
            if record is None or not record.has_geometry or record.metadata.get('runtime_enabled') is False:
                raise ValueError(f'Previously used room asset is unavailable: {preferred_asset_id}')
            if support_kinds:
                kinds={s.get('kind') for s in record.metadata.get('room_support_surfaces',[])
                       if s.get('verified') is True and (s.get('kind')!='shelves' or s.get('clearance_fraction',0)>0)}
                if not set(support_kinds)<=kinds:
                    raise ValueError(f'Existing asset {preferred_asset_id} lacks requested verified supports {sorted(set(support_kinds)-kinds)}')
        if record is None and support_kinds:
            # Choose a compatible, actually annotated support before placement;
            # never paint a tabletop onto an arbitrary mesh bounding box.
            candidates=self.asset_resolver.registry.search(asset.category,category=asset.category,
                environment='indoor',room_type=room_type,require_geometry=True,limit=100)
            for candidate,_ in candidates:
                kinds={s.get('kind') for s in candidate.metadata.get('room_support_surfaces',[])
                       if s.get('verified') is True and (s.get('kind')!='shelves' or s.get('clearance_fraction',0)>0)}
                if set(support_kinds)<=kinds:
                    record=candidate
                    break
        record = record or self.asset_resolver.resolve(
            (
                f"{style} {asset.category.replace('_', ' ')}, physically plausible "
                f"proportions, realistic materials, {room_type.replace('_', ' ')} interior"
            ),
            category=asset.category,
            dimensions_m=(asset.width_m, asset.depth_m, asset.height_m),
            environment="indoor",
            room_type=room_type,
        )
        if record is None:
            return None
        dimensions = record.dimensions_m or (asset.width_m, asset.depth_m, asset.height_m)
        orientation = record.metadata.get("orientation", {})
        front_axis = (
            orientation.get("canonical_forward_axis")
            or record.metadata.get("front_axis")
            or asset.front_axis
        )
        if front_axis not in {"+X", "-X", "+Y", "-Y"}:
            front_axis = asset.front_axis
        return AssetSpec(
            id=record.asset_id,
            category=asset.category,
            width_m=dimensions[0],
            depth_m=dimensions[1],
            height_m=dimensions[2],
            semantic_class=asset.semantic_class,
            material_id=record.material_id or asset.material_id,
            proxy_style=asset.proxy_style,
            front_axis=front_axis,
            orientation_confidence=str(
                orientation.get("orientation_confidence")
                or record.metadata.get("orientation_confidence")
                or "inferred"
            ),
            head_axis=(orientation.get("head_axis") or record.metadata.get("head_axis"))
                if (orientation.get("head_axis") or record.metadata.get("head_axis")) in {"+X","-X","+Y","-Y"} else None,
        )

    def _find_placement(
        self,
        room: Room,
        usable: Bounds2D,
        asset: AssetSpec,
        strategy: str,
        occupied: list[Bounds2D],
        door_zones: list[Bounds2D],
        front_is_min_y: bool,
        rng: random.Random,
    ) -> tuple[Point2D, float, Bounds2D, float] | None:
        mirror = rng.random() < 0.5
        scales = (1.0, 0.9, 0.8)
        for scale in scales:
            for fx, depth_fraction, rotation in self._candidate_pattern(strategy):
                if mirror:
                    fx = 1.0 - fx
                width = asset.width_m * scale
                depth = asset.depth_m * scale
                if strategy == "wall_back":
                    # The back wall is opposite the room frontage.  Point the
                    # asset's declared front into the room rather than using
                    # one hard-coded zero-degree rotation.
                    target_angle = -90.0 if front_is_min_y else 90.0
                    rotation = self._rotation_for_front(asset.front_axis, target_angle)
                elif strategy == "wall_side":
                    # ``fx`` identifies the left/right side wall after the
                    # deterministic mirror.  Face away from that wall.
                    target_angle = 0.0 if fx < 0.5 else 180.0
                    rotation = self._rotation_for_front(asset.front_axis, target_angle)
                angle = int(round(rotation)) % 180
                footprint_width, footprint_depth = (
                    (depth, width) if angle == 90 else (width, depth)
                )
                if footprint_width > usable.width or footprint_depth > usable.depth:
                    continue
                x = (
                    usable.min_x
                    + footprint_width / 2
                    + fx * (usable.width - footprint_width)
                )
                # Current floor layouts are double-loaded: depth=0 is the corridor
                # frontage and depth=1 is the quiet/back wall.
                if front_is_min_y:
                    y = (
                        usable.min_y
                        + footprint_depth / 2
                        + depth_fraction * (usable.depth - footprint_depth)
                    )
                else:
                    y = (
                        usable.max_y
                        - footprint_depth / 2
                        - depth_fraction * (usable.depth - footprint_depth)
                    )
                bounds = Bounds2D(
                    x - footprint_width / 2,
                    y - footprint_depth / 2,
                    x + footprint_width / 2,
                    y + footprint_depth / 2,
                )
                expanded = Bounds2D(
                    bounds.min_x - self.object_clearance_m,
                    bounds.min_y - self.object_clearance_m,
                    bounds.max_x + self.object_clearance_m,
                    bounds.max_y + self.object_clearance_m,
                )
                if any(expanded.overlaps_area(item) for item in occupied):
                    continue
                if any(expanded.overlaps_area(zone) for zone in door_zones):
                    continue
                return Point2D(x, y), rotation, bounds, scale
        return None

    @staticmethod
    def _rotation_for_front(front_axis: str, target_angle: float) -> float:
        """Rotate a canonical asset front axis toward a room-facing vector."""

        source_angles = {"+X": 0.0, "+Y": 90.0, "-X": 180.0, "-Y": -90.0}
        source = source_angles.get(front_axis, 90.0)
        return (target_angle - source) % 360.0

    @staticmethod
    def _candidate_pattern(strategy: str) -> tuple[tuple[float, float, float], ...]:
        if strategy == "wall_back":
            return tuple((x, 0.98, 0.0) for x in (0.5, 0.18, 0.82, 0.34, 0.66))
        if strategy == "wall_side":
            return (
                (0.02, 0.55, 90.0),
                (0.98, 0.55, 90.0),
                (0.02, 0.82, 90.0),
                (0.98, 0.82, 90.0),
                (0.02, 0.28, 90.0),
                (0.98, 0.28, 90.0),
            )
        if strategy == "center":
            return (
                (0.50, 0.56, 0.0),
                (0.30, 0.58, 0.0),
                (0.70, 0.58, 0.0),
                (0.50, 0.76, 0.0),
                (0.50, 0.34, 0.0),
            )
        return tuple(
            (x, depth, 0.0)
            for depth in (0.62, 0.84, 0.38)
            for x in (0.22, 0.50, 0.78, 0.08, 0.92)
        )

    def _door_clearance_zones(
        self, floor: Floor, room: Room
    ) -> tuple[list[Bounds2D], bool]:
        zones: list[Bounds2D] = []
        relevant = [
            door
            for door in floor.doors
            if door.room_a_id == room.id or door.room_b_id == room.id
        ]
        front_is_min_y = True
        for door in relevant:
            distances = {
                "min_y": abs(door.position.y - room.bounds.min_y),
                "max_y": abs(door.position.y - room.bounds.max_y),
                "min_x": abs(door.position.x - room.bounds.min_x),
                "max_x": abs(door.position.x - room.bounds.max_x),
            }
            side = min(distances, key=distances.get)
            if door is relevant[0]:
                front_is_min_y = side == "min_y"
            half = door.width_m / 2 + self.door_side_clearance_m
            depth = self.door_depth_clearance_m
            if side == "min_y":
                zones.append(
                    Bounds2D(
                        door.position.x - half,
                        room.bounds.min_y,
                        door.position.x + half,
                        min(room.bounds.max_y, room.bounds.min_y + depth),
                    )
                )
            elif side == "max_y":
                zones.append(
                    Bounds2D(
                        door.position.x - half,
                        max(room.bounds.min_y, room.bounds.max_y - depth),
                        door.position.x + half,
                        room.bounds.max_y,
                    )
                )
            elif side == "min_x":
                zones.append(
                    Bounds2D(
                        room.bounds.min_x,
                        door.position.y - half,
                        min(room.bounds.max_x, room.bounds.min_x + depth),
                        door.position.y + half,
                    )
                )
            else:
                zones.append(
                    Bounds2D(
                        max(room.bounds.min_x, room.bounds.max_x - depth),
                        door.position.y - half,
                        room.bounds.max_x,
                        door.position.y + half,
                    )
                )
        return zones, front_is_min_y


def asset_spec(category: str) -> AssetSpec:
    try:
        return ASSET_CATALOG[category]
    except KeyError as error:
        raise ValueError(f"Unknown procedural indoor asset: {category}") from error
