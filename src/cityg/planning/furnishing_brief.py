"""Capacity-aware furnishing contracts, distinct from geometric occupancy.

Area suggestions are advisory, not building-code occupancy limits. The Room
Agent chooses capacity and inventory; the solver must realize the essential
counts or reject the proposal without deleting the previous room.
"""
from collections import Counter
import math


BRIEF_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "occupants": {"type": "integer", "minimum": 1, "maximum": 64},
        "capacity_reason": {"type": "string", "minLength": 1, "maxLength": 600},
        "items": {"type": "array", "minItems": 1, "maxItems": 16, "items": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "category": {"type": "string"},
                "minimum": {"type": "integer", "minimum": 0, "maximum": 32},
                "target": {"type": "integer", "minimum": 1, "maximum": 32},
                "purpose": {"type": "string", "minLength": 1, "maxLength": 240},
            }, "required": ["category", "minimum", "target", "purpose"]}},
        "tradeoffs": {"type": "string", "maxLength": 800},
    }, "required": ["occupants", "capacity_reason", "items", "tradeoffs"],
}


def capacity_context(room):
    area = room.bounds.area
    requirement = room.metadata.get("spatial_requirement") or {}
    suggestion = None
    if room.function in {"office", "open_office", "study"}:
        # One seat needs furniture AND circulation. These are starting points;
        # the model must account for narrow rooms, storage and private offices.
        lower, upper = (1, 2) if room.function == "study" else (
            max(1, min(12, math.floor(area / 14))), max(1, min(12, math.floor(area / 8))))
        suggestion = [lower, upper]
    elif room.function == "bedroom":
        suggestion = [1, 2]
    elif room.function in {"meeting_room", "dining_room"}:
        suggestion = [max(2, min(8, int(area / 8))), max(2, min(8, int(area / 5)))]
    return {
        "area_m2": round(area, 2),
        "short_side_m": round(min(room.bounds.width, room.bounds.depth), 2),
        "requested_capacity": requirement.get("capacity"),
        "advisory_occupants_range": suggestion,
        "major_furniture_budget": 32, "group_budget": 16,
        "surface_object_budget": 48,
        "policy": "Use requested capacity and actual room purpose first. Explain any reduction. "
                  "Ranges are soft area-based hints, not occupancy certification or mandatory density. "
                  "Do not turn a large private office into an open office merely to fill space.",
    }


def validate_brief(brief, catalog, groups):
    if brief is None:  # Legacy saved designs remain readable.
        return
    if not isinstance(brief, dict) or set(brief) != set(BRIEF_SCHEMA["properties"]):
        raise ValueError("furnishing_brief needs occupants, capacity_reason, items and tradeoffs")
    if type(brief["occupants"]) is not int or not 1 <= brief["occupants"] <= 64:
        raise ValueError("invalid furnishing occupants")
    for key, limit, minimum in (("capacity_reason", 600, 1), ("tradeoffs", 800, 0)):
        if not isinstance(brief[key], str) or not minimum <= len(brief[key].strip()) <= limit:
            raise ValueError(f"invalid furnishing {key}")
    if not isinstance(brief["items"], (list, tuple)) or not 1 <= len(brief["items"]) <= 16:
        raise ValueError("furnishing inventory needs 1..16 categories")
    counts = Counter(i["category"] for g in groups for i in [g["anchor"], *g["members"]])
    seen = set()
    for item in brief["items"]:
        if not isinstance(item, dict) or set(item) != {"category", "minimum", "target", "purpose"}:
            raise ValueError("invalid furnishing inventory item")
        category = item["category"]
        if not isinstance(category, str) or category not in catalog or category in seen:
            raise ValueError("unknown or duplicate furnishing inventory category")
        seen.add(category)
        low, target = item["minimum"], item["target"]
        if type(low) is not int or type(target) is not int or not 0 <= low <= target <= 32 or target < 1:
            raise ValueError("invalid furnishing count range")
        if not isinstance(item["purpose"], str) or not 1 <= len(item["purpose"].strip()) <= 240:
            raise ValueError("furnishing items need a functional purpose")
        if counts[category] < low:
            raise ValueError(f"essential furnishing shortfall: {category} needs {low}, design has {counts[category]}")
        if counts[category] < target and not brief["tradeoffs"].strip():
            raise ValueError(f"explain target shortfall for {category} in tradeoffs")
    if set(counts) - seen:
        raise ValueError("every major furniture category must be listed in furnishing_brief")
    if sum(i["minimum"] for i in brief["items"]) > 32:
        raise ValueError("essential inventory exceeds furniture budget")


def check_capacity(room, brief, groups):
    """Check selected capacity against the final design, never auto-shrink it."""
    if brief is None:
        return
    counts = Counter(i["category"] for g in groups for i in [g["anchor"], *g["members"]])
    needs = {"office": ("desk", "office_chair"), "open_office": ("desk", "office_chair"),
             "study": ("desk", "office_chair"), "meeting_room": ("meeting_chair",)}
    for category in needs.get(room.function, ()):
        if counts[category] < brief["occupants"]:
            raise ValueError(f"capacity {brief['occupants']} requires at least that many {category} instances")
    requested = (room.metadata.get("spatial_requirement") or {}).get("capacity")
    if isinstance(requested, (int, float)) and requested > brief["occupants"] and not brief["tradeoffs"].strip():
        raise ValueError("explain the reduction from requested capacity in tradeoffs")
