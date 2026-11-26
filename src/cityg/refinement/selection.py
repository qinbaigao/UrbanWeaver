"""Deterministic budgeted selection of representative high-detail rooms."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from cityg.schemas import City, Room


@dataclass(frozen=True)
class RoomDetailCandidate:
    room_id: str
    score: float
    reason: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "room_id": self.room_id,
            "score": round(self.score, 4),
            "reason": list(self.reason),
        }


@dataclass(frozen=True)
class RoomDetailSelection:
    room_ids: tuple[str, ...]
    candidates: tuple[RoomDetailCandidate, ...]
    budget: int
    strategy: str = "representative_diversity_v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "room_ids": list(self.room_ids),
            "budget": self.budget,
            "strategy": self.strategy,
            "candidates": [item.to_dict() for item in self.candidates],
        }


def _room_context(city: City, room_id: str) -> tuple[Any, Any, Room] | None:
    for building in city.iter_buildings():
        for floor in building.floors:
            for room in floor.rooms:
                if room.id == room_id:
                    return building, floor, room
    return None


def _candidate_score(city: City, building: Any, floor: Any, room: Room) -> RoomDetailCandidate:
    reasons: list[str] = []
    score = 0.0
    if room.function == "corridor":
        return RoomDetailCandidate(room.id, -1000.0, ("corridor_excluded",))

    function_bonus = {
        "living_room": 4.0,
        "bedroom": 3.5,
        "kitchen": 4.5,
        "office": 4.0,
        "open_office": 3.5,
        "meeting_room": 4.0,
        "shop": 4.5,
        "reception": 4.0,
        "restaurant": 4.5,
        "waiting_room": 3.5,
        "workshop": 3.0,
    }
    if room.function in function_bonus:
        score += function_bonus[room.function]
        reasons.append(f"function:{room.function}")
    else:
        score += 1.0

    floor_role = str(floor.metadata.get("role", ""))
    zone_role = str(room.metadata.get("vertical_zone_role", floor_role))
    if floor.level == 0 or zone_role == "ground":
        score += 3.0
        reasons.append("ground_or_entrance")
    if zone_role in {"amenity", "refuge", "service", "mechanical", "top"}:
        score += 2.0
        reasons.append(f"vertical_zone:{zone_role}")
    if building.metadata.get("highrise", {}).get("enabled"):
        score += 2.0
        reasons.append("highrise")
    if room.bounds.area >= 55.0:
        score += 2.0
        reasons.append("large_room")
    elif room.bounds.area >= 30.0:
        score += 1.0
        reasons.append("medium_room")
    if room.metadata.get("space_kind") == "open_plan":
        score += 1.5
        reasons.append("open_plan")

    # Stable, seed-aware tie break prevents the same first rooms from being
    # selected whenever the city contains repeated floor templates.
    digest = hashlib.sha256(f"{city.id}:{room.id}".encode("utf-8")).hexdigest()
    score += int(digest[:6], 16) / 16**6 * 0.25
    return RoomDetailCandidate(room.id, score, tuple(reasons))


def select_hero_rooms(
    city: City,
    *,
    max_rooms: int = 10,
    existing_room_ids: set[str] | None = None,
    eligible_room_ids: set[str] | None = None,
) -> RoomDetailSelection:
    """Choose a diverse, reproducible set of rooms for expensive refinement.

    Selection is greedy over building/function/vertical-zone diversity.  It is
    deliberately deterministic and does not consume an LLM call; the selected
    IDs are then handed to RoomProgramAgent and the local asset/visual stages.
    """
    budget = max(0, int(max_rooms))
    candidates: list[RoomDetailCandidate] = []
    contexts: dict[str, tuple[Any, Any, Room]] = {}
    for building in city.iter_buildings():
        for floor in building.floors:
            for room in floor.rooms:
                if eligible_room_ids is not None and room.id not in eligible_room_ids:
                    continue
                candidate = _candidate_score(city, building, floor, room)
                from cityg.planning.interior_scope import floor_enabled
                if not floor_enabled(city,building,floor):
                    continue
                if candidate.score <= -999:
                    continue
                candidates.append(candidate)
                contexts[room.id] = (building, floor, room)

    candidates.sort(key=lambda item: (-item.score, item.room_id))
    selected: list[str] = []
    covered_buildings: set[str] = set()
    covered_functions: set[str] = set()
    covered_zones: set[str] = set()
    covered_floors: set[str] = set()
    already = set(existing_room_ids or ())

    def diversity_gain(candidate: RoomDetailCandidate) -> float:
        building, floor, room = contexts[candidate.room_id]
        zone = str(room.metadata.get("vertical_zone_role", floor.metadata.get("role", "")))
        if city.metadata.get("interior_scope"):
            return ((8.0 if building.id not in covered_buildings else 0.0)
                    +(10.0 if room.function not in covered_functions else 0.0)
                    +(6.0 if floor.id not in covered_floors else 0.0))
        return (
            (2.0 if building.id not in covered_buildings else 0.0)
            + (1.5 if room.function not in covered_functions else 0.0)
            + (1.0 if zone and zone not in covered_zones else 0.0)
        )

    remaining = [item for item in candidates if item.room_id not in already]
    while remaining and len(selected) < budget:
        remaining.sort(key=lambda item: (-(item.score + diversity_gain(item)), item.room_id))
        candidate = remaining.pop(0)
        selected.append(candidate.room_id)
        building, floor, room = contexts[candidate.room_id]
        covered_buildings.add(building.id)
        covered_floors.add(floor.id)
        covered_functions.add(room.function)
        zone = str(room.metadata.get("vertical_zone_role", floor.metadata.get("role", "")))
        if zone:
            covered_zones.add(zone)

    return RoomDetailSelection(
        room_ids=tuple(selected),
        candidates=tuple(candidates),
        budget=budget,
    )


def mark_room_detail(
    city: City,
    room_ids: set[str] | tuple[str, ...] | list[str],
    *,
    status: str,
    selection: RoomDetailSelection | None = None,
) -> None:
    """Attach a small, portable detail contract to selected room metadata."""
    selected = set(room_ids)
    reasons = {
        item.room_id: list(item.reason)
        for item in (selection.candidates if selection else ())
    }
    for room_id in selected:
        context = _room_context(city, room_id)
        if context is None:
            continue
        _building, _floor, room = context
        room.metadata.update(
            {
                "detail_tier": "hero",
                "refinement_status": status,
                "detail_selection_reasons": reasons.get(room_id, []),
            }
        )


__all__ = [
    "RoomDetailCandidate",
    "RoomDetailSelection",
    "mark_room_detail",
    "select_hero_rooms",
]
