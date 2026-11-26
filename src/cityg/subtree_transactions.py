"""Atomic replacement of structural CityG subtrees.

The ordinary :class:`cityg.repair.PatchEngine` intentionally has a small
surface: it can edit fields on entities that already exist.  Structural edits
such as changing the number of rooms or floors need a different boundary.  A
subtree transaction copies the city, replaces one complete subtree, rebuilds
the CCWP overlay, validates the result, and only then returns the copy.

The planners in this module are deliberately deterministic.  An LLM (or a
caller) supplies semantic intent in ``spec``; geometry, IDs, circulation and
containment are resolved here.  This keeps generated plans reproducible and
prevents a model from emitting dangling room/door references.
"""

from __future__ import annotations

import math
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from cityg.ccwp import build_world_program, entity_index
from cityg.schemas import (
    Bounds2D,
    Building,
    City,
    District,
    Door,
    Floor,
    InteriorObject,
    Parcel,
    Point2D,
    RoadSegment,
    Room,
    VerticalConnector,
    ProvenanceRecord,
)
from cityg.validation import CityValidator, ValidationReport


@dataclass(frozen=True)
class SubtreeTransactionResult:
    """Result of a successful structural replacement."""

    city: City
    root_id: str
    subtree_kind: str
    replaced_ids: tuple[str, ...]
    created_ids: tuple[str, ...]
    removed_ids: tuple[str, ...]
    validation: ValidationReport
    metadata: Mapping[str, Any]


def _entity(city: City, entity_id: str) -> Any:
    item = entity_index(city).get(str(entity_id))
    if item is None:
        raise ValueError(f"unknown subtree root: {entity_id}")
    return item


def _refresh_world_program(city: City, *, producer: str, changed_ids: set[str]) -> None:
    """Rebuild CCWP while retaining versions/locks/provenance for stable IDs."""

    previous = city.world_program
    old_nodes = {node.entity_id: node for node in previous.nodes}
    current_entity_ids = set(entity_index(city))
    old_provenance = {
        record.id: deepcopy(record)
        for record in previous.provenance
        if record.entity_id in current_entity_ids
    }
    program = build_world_program(city, producer=producer, seed=None)
    history = dict(old_provenance)
    for record in program.provenance:
        history.setdefault(record.id, record)
    # Removing rooms/objects also removes their provenance records.  Prune
    # parent links and node provenance lists so CCWP validation never sees a
    # reference to an entity that the replacement intentionally deleted.
    for record in history.values():
        record.parent_record_ids = [item for item in record.parent_record_ids if item in history]
    program.provenance = list(history.values())
    for node in program.nodes:
        old = old_nodes.get(node.entity_id)
        if old is not None:
            node.version = old.version + (1 if node.entity_id in changed_ids else 0)
            node.locked = old.locked
            node.provenance_ids = [item for item in old.provenance_ids if item in history]
        if node.entity_id in changed_ids:
            provenance_id = f"prov_subtree__{producer}__{node.entity_id}__{node.version}"
            if provenance_id not in history:
                record = ProvenanceRecord(
                    id=provenance_id,
                    entity_id=node.entity_id,
                    producer=producer,
                    operation="subtree_replace",
                    parent_record_ids=list(node.provenance_ids),
                )
                program.provenance.append(record)
                history[provenance_id] = record
            if provenance_id not in node.provenance_ids:
                node.provenance_ids.append(provenance_id)
    city.world_program = program


def _commit(candidate: City, root_id: str, kind: str, old_ids: set[str], *, producer: str,
            metadata: Mapping[str, Any], changed_ids: set[str] | None = None,
            validate: bool = True) -> SubtreeTransactionResult:
    """Validate a candidate and produce a stable diff summary."""

    new_ids = set(entity_index(candidate))
    current_subtree = _descendants(candidate, root_id)
    changed = set(changed_ids or current_subtree) | ({root_id} if root_id in new_ids else set())
    _refresh_world_program(candidate, producer=producer, changed_ids=changed)
    report = CityValidator().validate(candidate) if validate else ValidationReport()
    if validate and not report.ok:
        errors = "; ".join(issue.message for issue in report.errors[:3])
        raise ValueError(f"{kind} subtree replacement failed validation: {errors}")
    created = tuple(sorted((new_ids - old_ids) & set(current_subtree)))
    removed = tuple(sorted((old_ids - new_ids)))
    replaced = tuple(sorted(changed & new_ids))
    return SubtreeTransactionResult(
        city=candidate,
        root_id=root_id,
        subtree_kind=kind,
        replaced_ids=replaced,
        created_ids=created,
        removed_ids=removed,
        validation=report,
        metadata=dict(metadata),
    )


def _descendants(city: City, root_id: str) -> set[str]:
    """Canonical hierarchy descendants (including ``root_id``)."""

    result = {root_id}
    changed = True
    hierarchy = {entity.id: parent for entity, _, parent in city.iter_entities()}
    while changed:
        changed = False
        for entity_id, parent_id in hierarchy.items():
            if entity_id not in result and parent_id in result:
                result.add(entity_id)
                changed = True
    return result


def _old_subtree_ids(city: City, root_id: str) -> set[str]:
    return _descendants(city, root_id)


def _number(value: Any, default: int | None = None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _details_spec(details: Any) -> dict[str, Any]:
    if isinstance(details, Mapping):
        return dict(details)
    text = str(details or "")
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        parsed = None
    if isinstance(parsed, Mapping):
        return dict(parsed)
    # English thousands separators are not decimal points or list separators.
    # Preserve the actual quantity before the conservative language fallback.
    text = re.sub(r'\b\d{1,3}(?:,\d{3})+\b', lambda m:m.group().replace(',',''), text)
    result: dict[str, Any] = {}
    def number_for(kind: str, unit: str) -> int | None:
        # Prefer an explicit target (“to 10 floors”, “改为14个房间”) over a
        # current-count statement (“currently 7 floors”).
        target = re.search(
            rf"(?:\bto\b|改为|改成|变为|设置为|目标为)\s*(?:(?:contain|have|strictly|exactly|严格|恰好)\s*)*(\d+)\s*(?:个|间)?\s*(?:{unit})",
            text,
            re.I,
        )
        if target:
            return int(target.group(1))
        direct = re.search(
            rf"(?:(?:{kind})\s*[:=：]?\s*(\d+)|(?:exactly\s*)?(\d+)\s*(?:个|间)?\s*(?:{unit}))",
            text,
            re.I,
        )
        if direct:
            return int(next(group for group in direct.groups() if group is not None))
        # “Increase floor count from 7 to 10” has no unit immediately after
        # the target in some model responses, so capture the final number.
        increase = re.search(rf"(?:{kind}).*?\b(?:to|=)\s*(\d+)\b", text, re.I)
        return int(increase.group(1)) if increase else None

    room_count = number_for("room_count|rooms?|房间数|房间",
                            r"(?:(?:independent|separate|private|non[- ]corridor)\s+)*(?:rooms?|offices?|bedrooms?)\b|(?:(?:独立|单独|非走廊)\s*)*(?:房间|办公室|卧室)")
    if room_count is not None:
        result["room_count"] = room_count
    floor_count = number_for("floor_count|floors?|层数|楼层数", "floors?|层")
    if floor_count is not None:
        result["floor_count"] = floor_count
    # Preserve a small, deterministic vocabulary for natural-language urban
    # function changes.  Free-form details often say “mixed residential and
    # public service” rather than emitting a JSON ``function`` field.
    lowered = text.lower()
    if ("mixed residential" in lowered and "public service" in lowered) or (
        "混合住宅" in text and "公共服务" in text
    ):
        result["function"] = "mixed_use_residential_public_service"
    else:
        function_patterns = (
            ("public_service", ("public service", "公共服务")),
            ("mixed_use", ("mixed-use", "mixed use", "混合功能")),
            ("residential", ("residential", "住宅")),
            ("commercial", ("commercial", "商业")),
            ("office", ("office", "办公")),
        )
        for value, patterns in function_patterns:
            if any(pattern in lowered or pattern in text for pattern in patterns):
                result["function"] = value
                break
    return result


def _bounds_from(value: Any, fallback: Bounds2D) -> Bounds2D:
    if isinstance(value, Bounds2D):
        return value
    if isinstance(value, Mapping):
        return Bounds2D(float(value["min_x"]), float(value["min_y"]),
                        float(value["max_x"]), float(value["max_y"]))
    return fallback


def _room_functions(spec: Mapping[str, Any], building_function: str, existing: list[Room]) -> tuple[str, ...]:
    values = spec.get("room_functions", spec.get("functions", spec.get("room_function_cycle")))
    if values is None and spec.get('function') == 'office':
        values = ['office']
    if isinstance(values, str):
        values = re.split(r"[,，/、\s]+", values)
    if isinstance(values, (list, tuple)):
        normalized = [str(item).strip().lower().replace(" ", "_") for item in values if str(item).strip()]
        if normalized:
            return tuple(normalized)
    source = [room.function for room in existing if room.function != "corridor"]
    return tuple(source[:8] or {"residential": ("living_room", "bedroom", "kitchen", "bathroom"),
                                 "office": ("open_office", "meeting_room", "break_room", "restroom"),
                                 "commercial": ("shop", "storage", "restroom"),
                                 "mixed_use": ("shop", "office", "storage", "restroom")}.get(building_function,
                                                                                         ("open_plan", "storage")))


class FloorSubtreePlanner:
    """Replace one realized floor's rooms, doors and objects atomically."""

    def replace(self, city: City, floor_id: str, spec: Mapping[str, Any] | None = None,
                *, details: Any = None, seed: int = 0, validate: bool = True,
                **options: Any) -> SubtreeTransactionResult:
        spec = {**_details_spec(details), **dict(spec or {}), **options}
        source = _entity(city, floor_id)
        if not isinstance(source, Floor):
            raise ValueError(f"FloorSubtreePlanner requires a floor root, got {type(source).__name__}")
        old_ids = _old_subtree_ids(city, floor_id)
        candidate = deepcopy(city)
        floor = _entity(candidate, floor_id)
        assert isinstance(floor, Floor)
        parent = next((building for building in candidate.iter_buildings() if floor in building.floors), None)
        if parent is None:
            raise ValueError(f"floor {floor_id} is not attached to a building")
        requested = _number(spec.get("room_count"), None)
        existing_non_corridor = [room for room in floor.rooms if room.function != "corridor"]
        count = requested if requested is not None else len(existing_non_corridor)
        if not 1 <= count <= 64:
            raise ValueError('Requested room_count is outside the supported range 1..64; not silently clamped')
        functions = _room_functions(spec, parent.function, existing_non_corridor)
        corridor = next((room for room in floor.rooms if room.function == "corridor" and
                         room.metadata.get("corridor_role", "central") == "central"), None)
        plate = _bounds_from(floor.metadata.get("realized_floor_plate", {}).get("bounds")
                             if isinstance(floor.metadata.get("realized_floor_plate"), Mapping) else None,
                             parent.footprint)
        if corridor is None:
            corridor_depth = min(4.0, max(2.4, plate.depth * 0.18))
            corridor = Room(f"{floor.id}_corridor", "Main corridor", "corridor",
                            Bounds2D(plate.min_x, plate.center.y - corridor_depth / 2,
                                     plate.max_x, plate.center.y + corridor_depth / 2),
                            metadata={"space_kind": "circulation", "corridor_role": "central"})
        else:
            corridor = deepcopy(corridor)
        corridor.object_ids = []
        north = math.ceil(count / 2)
        south = count - north
        reused = [room.id for room in existing_non_corridor]
        used_room_ids = set(reused) | {corridor.id}
        rooms = [corridor]
        doors: list[Door] = []
        room_index = 0
        for side, side_count in (("north", north), ("south", south)):
            if side_count <= 0:
                continue
            depth = max(2.0, (plate.max_y - corridor.bounds.max_y) if side == "north"
                         else (corridor.bounds.min_y - plate.min_y))
            width = plate.width / side_count
            for index in range(side_count):
                if room_index < len(reused):
                    room_id = reused[room_index]
                else:
                    suffix = room_index
                    room_id = f"{floor.id}_room_{suffix:02d}"
                    while room_id in used_room_ids:
                        suffix += 1
                        room_id = f"{floor.id}_room_{suffix:02d}"
                used_room_ids.add(room_id)
                min_y, max_y = ((corridor.bounds.max_y, plate.max_y) if side == "north"
                                else (plate.min_y, corridor.bounds.min_y))
                bounds = Bounds2D(plate.min_x + width * index, min_y,
                                  plate.min_x + width * (index + 1), max_y)
                function = functions[room_index % len(functions)]
                room = Room(room_id, function.replace("_", " ").title(), function, bounds,
                            height_m=floor.height_m,
                            metadata={"subtree_replaced": True, "layout_source": "floor_subtree_planner_v1",
                                      "programmed_room_index": room_index,
                                      "space_kind": "enclosed_room", "requires_facade": True})
                rooms.append(room)
                door_y = bounds.min_y if side == "north" else bounds.max_y
                doors.append(Door(f"{room_id}_door", room_id, corridor.id,
                                  Point2D(bounds.center.x, door_y)))
                room_index += 1
        if floor.level == 0:
            doors.append(Door(f"{floor.id}_entrance", corridor.id, None, parent.entrance,
                              width_m=1.6, door_type="exterior"))
        floor.rooms = rooms
        floor.doors = doors
        # Replacing the spatial partition invalidates all old furniture.  The
        # caller may run FloorDetailAgent afterwards, but stale object IDs are
        # never carried into a new room layout.
        floor.objects = []
        floor.metadata = {**floor.metadata, "subtree_transaction": "floor_v1",
                          "room_count": count, "room_functions": list(functions)}
        return _commit(candidate, floor_id, "floor", old_ids,
                       producer="cityg_floor_subtree_planner",
                       metadata={"room_count": count, "preserved_room_ids": reused[:count], "seed": seed},
                       validate=validate)

    apply = replace


class BuildingSubtreePlanner:
    """Replace a building's floor stack and vertical circulation atomically."""

    def replace(self, city: City, building_id: str, spec: Mapping[str, Any] | None = None,
                *, details: Any = None, seed: int = 0, **options: Any) -> SubtreeTransactionResult:
        spec = {**_details_spec(details), **dict(spec or {}), **options}
        source = _entity(city, building_id)
        if not isinstance(source, Building):
            raise ValueError(f"BuildingSubtreePlanner requires a building root, got {type(source).__name__}")
        old_ids = _old_subtree_ids(city, building_id)
        candidate = deepcopy(city)
        building = _entity(candidate, building_id)
        assert isinstance(building, Building)
        old_count = len(building.floors)
        value = spec.get("floor_count", old_count)
        try:
            floor_count = int(value)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("floor_count must be an integer within 1..128; not silently clamped") from None
        if (isinstance(value, bool) or not 1 <= floor_count <= 128
                or (not isinstance(value, str) and value != floor_count)):
            raise ValueError("floor_count must be an integer within 1..128; not silently clamped")
        if "function" in spec:
            building.function = str(spec["function"])
        if "footprint" in spec:
            building.footprint = _bounds_from(spec["footprint"], building.footprint)
        if "entrance" in spec and isinstance(spec["entrance"], Mapping):
            building.entrance = Point2D(float(spec["entrance"]["x"]), float(spec["entrance"]["y"]))
        template = list(building.floors) or [Floor(f"{building.id}_floor_00", 0, 0.0, 3.0)]
        floors: list[Floor] = []
        elevation = template[0].elevation_m
        for level in range(floor_count):
            base = deepcopy(template[min(level, len(template) - 1)])
            base.id = f"{building.id}_floor_{level:02d}"
            base.level = level
            # Lobbies and upper storeys need not have the same height. A
            # level*height formula overlaps/slips floors after a tall lobby.
            base.elevation_m = elevation
            elevation += base.height_m
            # A copied template may still contain IDs belonging to another
            # level.  Clear those IDs before the CCWP rebuild; the floor
            # realization pass below will create canonical room/door IDs.
            if level >= len(template):
                for room_index, room in enumerate(base.rooms):
                    room.id = f"{base.id}_room_{room_index:02d}"
                    room.object_ids = []
                for door_index, door in enumerate(base.doors):
                    door.id = f"{base.id}_door_{door_index:02d}"
                    door.room_a_id = base.rooms[0].id if base.rooms else base.id
                    door.room_b_id = None
                base.objects = []
            floors.append(base)
        building.floors = floors
        # Connector IDs are stable where possible; all connectors serve the
        # complete realized stack and remain inside the footprint.
        connectors = deepcopy(building.vertical_connectors)
        if not connectors:
            core_w = min(5.0, max(2.0, building.footprint.width * .16))
            core_d = min(5.0, max(2.0, building.footprint.depth * .16))
            core = Bounds2D(building.footprint.center.x - core_w / 2,
                            building.footprint.center.y - core_d / 2,
                            building.footprint.center.x + core_w / 2,
                            building.footprint.center.y + core_d / 2)
            connectors = [VerticalConnector(f"{building.id}_stairs_00", "stairs", core, 0, floor_count - 1),
                          VerticalConnector(f"{building.id}_stairs_01", "stairs", core, 0, floor_count - 1),
                          VerticalConnector(f"{building.id}_elevator_00", "elevator", core.inset(.35), 0, floor_count - 1, True)]
        building.vertical_connectors = [
            VerticalConnector(item.id, item.connector_type,
                              _bounds_from(item.bounds, building.footprint), 0, floor_count - 1,
                              item.interactive, dict(item.metadata)) for item in connectors
        ]
        # Height contracts are part of the building subtree contract.  Keep
        # the old band when possible, but update realized_floors so validation
        # cannot observe stale skyline metadata.
        if isinstance(building.metadata.get("height_contract"), dict):
            contract = dict(building.metadata["height_contract"])
            contract["realized_floors"] = floor_count
            contract["recommended_floors"] = floor_count if contract.get("landmark") else contract.get("recommended_floors", floor_count)
            contract["min_floors"] = min(int(contract.get("min_floors", 1)), floor_count)
            contract["max_floors"] = max(int(contract.get("max_floors", floor_count)), floor_count)
            building.metadata["height_contract"] = contract
        # Realize every floor before the public building commit.  An
        # intermediate floor stack with copied template doors can be
        # temporarily disconnected, so it must never be exposed as a
        # transaction result.  The planners still validate each private
        # intermediate copy; the caller sees one all-or-nothing building edit.
        current = candidate
        for floor in list(_entity(current, building_id).floors):
            floor_result = FloorSubtreePlanner().replace(current, floor.id, spec, seed=seed, validate=False)
            current = floor_result.city
        result = _commit(current, building_id, "building", old_ids,
                         producer="cityg_building_subtree_planner",
                         metadata={"old_floor_count": old_count, "new_floor_count": floor_count,
                                   "floor_realized": True, "seed": seed})
        return result

    apply = replace


class UrbanSubgraphPlanner:
    """Replace a district/parcel subgraph without touching unrelated districts."""

    def replace(self, city: City, root_id: str, spec: Mapping[str, Any] | None = None,
                *, details: Any = None, seed: int = 0, **options: Any) -> SubtreeTransactionResult:
        spec = {**_details_spec(details), **dict(spec or {}), **options}
        source = _entity(city, root_id)
        if not isinstance(source, (City, District, Parcel)):
            raise ValueError("UrbanSubgraphPlanner root must be city, district, or parcel")
        old_ids = _old_subtree_ids(city, root_id)
        candidate = deepcopy(city)
        target = _entity(candidate, root_id)
        if "function" in spec and hasattr(target, "function"):
            target.function = str(spec["function"])
        if "name" in spec and hasattr(target, "name"):
            target.name = str(spec["name"])
        if "bounds" in spec and hasattr(target, "bounds"):
            target.bounds = _bounds_from(spec["bounds"], target.bounds)
        updates = spec.get("building_updates", {})
        if isinstance(updates, list):
            updates = {item.get("id"): item for item in updates if isinstance(item, Mapping) and item.get("id")}
        for building_id, update in dict(updates).items():
            building = entity_index(candidate).get(str(building_id))
            if not isinstance(building, Building) or str(building_id) not in _descendants(candidate, root_id):
                raise ValueError(f"building update {building_id} is outside urban subtree")
            for key in ("name", "function", "metadata"):
                if key in update:
                    setattr(building, key, deepcopy(update[key]))
            if "footprint" in update:
                building.footprint = _bounds_from(update["footprint"], building.footprint)
        road_updates = spec.get("road_updates", {})
        if isinstance(road_updates, list):
            road_updates = {item.get("id"): item for item in road_updates if isinstance(item, Mapping) and item.get("id")}
        road_ids = {item.id for item in candidate.road_network.segments}
        for road_id, update in dict(road_updates).items():
            if str(road_id) not in road_ids:
                raise ValueError(f"unknown road update: {road_id}")
            road = next(item for item in candidate.road_network.segments if item.id == str(road_id))
            for key in ("road_class", "lane_count", "width_m", "sidewalk_width_m", "speed_limit_kph", "parking_allowed", "bike_lane", "bus_lane"):
                if key in update:
                    setattr(road, key, deepcopy(update[key]))
        return _commit(candidate, root_id, "urban_subgraph", old_ids,
                       producer="cityg_urban_subgraph_planner",
                       metadata={"building_update_count": len(updates), "road_update_count": len(road_updates), "seed": seed})

    apply = replace


def replace_subtree(city: City, root_id: str, kind: str, spec: Mapping[str, Any] | None = None,
                    *, details: Any = None, seed: int = 0) -> SubtreeTransactionResult:
    """Dispatch one typed subtree transaction."""

    from cityg.planning.building_site import BuildingSitePlanner
    planners = {
        "building_site": BuildingSitePlanner(),
        "floor_layout": FloorSubtreePlanner(),
        "building_subtree": BuildingSubtreePlanner(),
        "urban_subgraph": UrbanSubgraphPlanner(),
    }
    if kind not in planners:
        raise ValueError(f"unsupported subtree transaction kind: {kind}")
    return planners[kind].replace(city, root_id, spec, details=details, seed=seed)


__all__ = [
    "SubtreeTransactionResult", "FloorSubtreePlanner", "BuildingSubtreePlanner",
    "UrbanSubgraphPlanner", "replace_subtree",
]
