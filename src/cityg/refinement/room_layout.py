"""Transactional metric commit for Room Agent local furniture edits."""

from __future__ import annotations

import math
import random
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Any

from cityg.assets import AssetResolver, infer_asset_room_types
from cityg.ccwp import build_world_program
from cityg.planning.furnishing_gate import (
    FurnishingNonDegradationPolicy,
    furnishing_non_degradation_check,
)
from cityg.planning.interiors import ASSET_CATALOG, AssetSpec, FloorDetailAgent
from cityg.planning.room_design import group_integrity
from cityg.refinement.room import RoomLayoutRefinementPlan, RoomObjectAdjustment
from cityg.schemas import City, Floor, InteriorObject, Point2D, Room
from cityg.validation import CityValidator, ValidationReport


@dataclass(frozen=True)
class RoomLayoutRefinementResult:
    city: City
    room_id: str
    applied_operations: tuple[dict[str, Any], ...]
    rejected_operations: tuple[dict[str, Any], ...]
    validation: ValidationReport
    gate: dict[str, Any] | None = None
    transaction_report: dict[str, Any] | None = None

    @property
    def changed(self) -> bool:
        return bool(self.applied_operations)

    def trace_dict(self) -> dict[str, Any]:
        return {
            "room_id": self.room_id,
            "changed": self.changed,
            "applied_operations": list(self.applied_operations),
            "rejected_operations": list(self.rejected_operations),
            "validation": self.validation.to_dict(),
            "furnishing_non_degradation_gate": self.gate,
            "transaction": self.transaction_report,
        }


def apply_room_layout_refinement(
    city: City,
    plan: RoomLayoutRefinementPlan,
    *,
    asset_resolver: AssetResolver | None = None,
    seed: int = 17,
    compiled_gate=None,
    memory_store=None,
) -> RoomLayoutRefinementResult:
    from cityg.transactions import MutationProposal, accept_candidate, fingerprint
    proposal = MutationProposal.bind(city, [plan.room_id], source='visual_repair',
        kind='room_layout', proposal_id=f'room_layout__{plan.room_id}__{fingerprint(city)[:16]}')
    result = _apply_room_layout_detached(city, plan, asset_resolver=asset_resolver, seed=seed)
    if not result.changed:
        return result
    accepted = accept_candidate(city, proposal, lambda _: result.city,
                                compiled_gate=compiled_gate, memory_store=memory_store)
    return replace(result, city=accepted.city, transaction_report=accepted.report)


def _apply_room_layout_detached(city, plan, *, asset_resolver=None, seed=17):
    """Apply semantic furniture edits on a copy and commit only a valid room.

    Operations that cannot find a collision-free placement fall back to the
    original object. The canonical city is never partially mutated.
    """

    candidate = deepcopy(city)
    target = _find_room(candidate, plan.room_id)
    if target is None:
        raise ValueError(f"unknown room layout refinement target: {plan.room_id}")
    floor, room = target
    room_objects = [item for item in floor.objects if item.room_id == room.id]
    object_index = {item.id: item for item in room_objects}
    if not room_objects:
        raise ValueError("local room rearrangement requires existing objects")
    if any(item.object_id not in object_index for item in plan.operations):
        raise ValueError("room layout plan references an unknown object")

    detail = FloorDetailAgent(asset_resolver=asset_resolver)
    operation_index = {item.object_id: item for item in plan.operations}
    fixed = [item for item in room_objects if item.id not in operation_index]
    placed = list(fixed)
    occupied = [item.bounds for item in fixed]
    door_zones, front_is_min_y = detail._door_clearance_zones(floor, room)
    usable = room.bounds.inset(detail.wall_clearance_m)
    applied: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    # Removals are independent of metric placement and reduce clutter before
    # moves/replacements are solved.
    for operation in plan.operations:
        if operation.action != "remove":
            continue
        original = object_index[operation.object_id]
        applied.append(
            _operation_trace(operation, original, None, status="removed")
        )

    for operation in plan.operations:
        if operation.action == "remove":
            continue
        original = object_index[operation.object_id]
        replacement = deepcopy(original)
        asset = _asset_for_operation(detail, original, operation, room)
        if asset is None:
            placed.append(original)
            occupied.append(original.bounds)
            rejected.append(
                _operation_trace(
                    operation,
                    original,
                    original,
                    status="rejected",
                    detail="replacement category is incompatible with the room type",
                )
            )
            continue
        if operation.action == "replace":
            replacement.category = asset.category
            replacement.asset_id = asset.id
            replacement.width_m = asset.width_m
            replacement.depth_m = asset.depth_m
            replacement.height_m = asset.height_m
            replacement.metadata = {
                **replacement.metadata,
                "front_axis": asset.front_axis,
                "orientation_confidence": asset.orientation_confidence,
                "room_type": room.function,
            }

        placement = operation.placement
        if placement == "preserve":
            placement = str(original.metadata.get("placement_strategy") or "grid")
        moved = operation.action in {"move", "replace"}
        if moved:
            resolved = None
            realized_placement = placement
            for candidate_placement in _compatible_placement_hints(placement):
                resolved = detail._find_placement(
                    room,
                    usable,
                    asset,
                    candidate_placement,
                    occupied,
                    door_zones,
                    front_is_min_y,
                    random.Random(
                        f"{seed}:{room.id}:{operation.object_id}:{operation.action}:"
                        f"{candidate_placement}"
                    ),
                )
                if resolved is not None:
                    realized_placement = candidate_placement
                    break
            if resolved is None:
                placed.append(original)
                occupied.append(original.bounds)
                rejected.append(
                    _operation_trace(
                        operation,
                        original,
                        original,
                        status="rejected",
                        detail="no collision-free placement satisfied the semantic hint",
                    )
                )
                continue
            position, rotation, _bounds, scale = resolved
            replacement.position = position
            replacement.rotation_deg = rotation
            replacement.width_m = asset.width_m * scale
            replacement.depth_m = asset.depth_m * scale
            replacement.height_m = asset.height_m * scale
            replacement.metadata = {
                **replacement.metadata,
                "placement_strategy": realized_placement,
                "requested_placement_strategy": placement,
                "asset_scale": scale,
            }

        desired_rotation = _desired_rotation(
            replacement,
            operation,
            room,
            floor,
            {**object_index, **{item.id: item for item in placed}},
            asset.front_axis,
        )
        if desired_rotation is not None:
            previous_rotation = replacement.rotation_deg
            replacement.rotation_deg = desired_rotation
            if not detail._relation_position_valid(
                replacement, [*placed, replacement], usable, door_zones
            ):
                replacement.rotation_deg = previous_rotation
                if operation.action == "rotate":
                    placed.append(original)
                    occupied.append(original.bounds)
                    rejected.append(
                        _operation_trace(
                            operation,
                            original,
                            original,
                            status="rejected",
                            detail="requested facing direction violates clearance",
                        )
                    )
                    continue

        if not detail._relation_position_valid(
            replacement, [*placed, replacement], usable, door_zones
        ):
            placed.append(original)
            occupied.append(original.bounds)
            rejected.append(
                _operation_trace(
                    operation,
                    original,
                    original,
                    status="rejected",
                    detail="final object footprint failed containment or clearance checks",
                )
            )
            continue

        replacement.metadata = {
            **replacement.metadata,
            "planner": "RoomLayoutRefinementAgent+FloorDetailAgent",
            "local_refinement": {
                "action": operation.action,
                "reason": operation.reason,
                "plan_confidence": plan.confidence,
            },
        }
        placed.append(replacement)
        occupied.append(replacement.bounds)
        applied.append(
            _operation_trace(operation, original, replacement, status="applied")
        )

    gate = furnishing_non_degradation_check(
        room_objects,
        placed,
        room,
        FurnishingNonDegradationPolicy(),
    )
    groups_ok, group_reason = group_integrity(room_objects, placed)
    if not groups_ok:
        gate = {**gate, "ok": False, "reason": group_reason, "group_integrity": False}
    if not gate["ok"]:
        # Reject the complete transaction.  Returning a copy of the original
        # city (rather than the candidate) prevents downstream stages from
        # accidentally persisting a partially applied removal.
        original_city = deepcopy(city)
        original_validation = CityValidator().validate(original_city)
        rejected.extend(
            {
                "status": "gate_rejected",
                "action": item.get("action"),
                "object_id": item.get("object_id"),
                "reason": item.get("reason", ""),
                "detail": gate["reason"],
            }
            for item in applied
        )
        return RoomLayoutRefinementResult(
            city=original_city,
            room_id=room.id,
            applied_operations=(),
            rejected_operations=tuple([*rejected, {"status": "gate_rejected", **gate}]),
            validation=original_validation,
            gate=gate,
        )

    # Preserve floor ordering outside the room, then insert the locally solved
    # room objects in their previous relative order where possible.
    floor.objects[:] = [item for item in floor.objects if item.room_id != room.id]
    floor.objects.extend(placed)
    room.object_ids[:] = [item.id for item in placed]
    room.metadata["room_layout_refinement"] = {
        "agent": "RoomLayoutRefinementAgent",
        "reason": plan.reason,
        "confidence": plan.confidence,
        "applied_count": len(applied),
        "rejected_count": len(rejected),
    }
    from cityg.transactions import refresh_local_overlay
    refresh_local_overlay(city, candidate, [room.id])
    validation = CityValidator().validate(candidate)
    if not validation.ok:
        codes = ", ".join(sorted({item.code for item in validation.errors}))
        raise ValueError(f"room layout refinement failed canonical validation: {codes}")
    return RoomLayoutRefinementResult(
        city=candidate,
        room_id=room.id,
        applied_operations=tuple(applied),
        rejected_operations=tuple(rejected),
        validation=validation,
        gate=gate,
    )


def _find_room(city: City, room_id: str) -> tuple[Floor, Room] | None:
    for building in city.iter_buildings():
        for floor in building.floors:
            for room in floor.rooms:
                if room.id == room_id:
                    return floor, room
    return None


def _asset_for_operation(
    detail: FloorDetailAgent,
    original: InteriorObject,
    operation: RoomObjectAdjustment,
    room: Room,
) -> AssetSpec | None:
    category = operation.replacement_category or original.category
    compatible_rooms = infer_asset_room_types(category)
    if compatible_rooms and room.function not in compatible_rooms:
        return None
    if operation.action == "replace":
        base = ASSET_CATALOG[category]
        return detail._resolve_asset(base, room_type=room.function) or base
    return AssetSpec(
        id=original.asset_id,
        category=original.category,
        width_m=original.width_m,
        depth_m=original.depth_m,
        height_m=original.height_m,
        semantic_class=ASSET_CATALOG.get(original.category, ASSET_CATALOG["desk"]).semantic_class,
        material_id=ASSET_CATALOG.get(original.category, ASSET_CATALOG["desk"]).material_id,
        proxy_style=ASSET_CATALOG.get(original.category, ASSET_CATALOG["desk"]).proxy_style,
        front_axis=str(original.metadata.get("front_axis", "+Y")),
        orientation_confidence=str(original.metadata.get("orientation_confidence", "inferred")),
    )


def _desired_rotation(
    subject: InteriorObject,
    operation: RoomObjectAdjustment,
    room: Room,
    floor: Floor,
    objects: dict[str, InteriorObject],
    front_axis: str,
) -> float | None:
    if operation.facing == "preserve":
        return None
    target: Point2D | None = None
    if operation.facing in {"room_center", "nearest_wall"}:
        target = room.bounds.center
    elif operation.facing == "door":
        doors = [
            item
            for item in floor.doors
            if room.id in {item.room_a_id, item.room_b_id}
        ]
        if doors:
            target = min(
                doors,
                key=lambda item: math.hypot(
                    item.position.x - subject.position.x,
                    item.position.y - subject.position.y,
                ),
            ).position
    elif operation.facing == "target_object" and operation.target_object_id:
        target_object = objects.get(operation.target_object_id)
        if target_object is not None:
            target = target_object.position
    if target is None:
        return None
    dx = target.x - subject.position.x
    dy = target.y - subject.position.y
    if math.hypot(dx, dy) < 1e-6:
        return None
    target_angle = math.degrees(math.atan2(dy, dx))
    return FloorDetailAgent._rotation_for_front(front_axis, target_angle)


def _compatible_placement_hints(placement: str) -> tuple[str, ...]:
    """Small semantic fallbacks; wall furniture never falls into the center."""

    if placement == "wall_back":
        return ("wall_back", "wall_side")
    if placement == "wall_side":
        return ("wall_side", "wall_back")
    if placement == "center":
        return ("center", "grid")
    return ("grid", "center")


def _operation_trace(
    operation: RoomObjectAdjustment,
    before: InteriorObject,
    after: InteriorObject | None,
    *,
    status: str,
    detail: str = "",
) -> dict[str, Any]:
    return {
        "object_id": operation.object_id,
        "action": operation.action,
        "status": status,
        "reason": operation.reason,
        "detail": detail,
        "before": {
            "category": before.category,
            "asset_id": before.asset_id,
            "position": [before.position.x, before.position.y],
            "rotation_deg": before.rotation_deg,
        },
        "after": None
        if after is None
        else {
            "category": after.category,
            "asset_id": after.asset_id,
            "position": [after.position.x, after.position.y],
            "rotation_deg": after.rotation_deg,
        },
    }


__all__ = ["RoomLayoutRefinementResult", "apply_room_layout_refinement"]
