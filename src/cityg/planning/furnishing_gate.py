"""Shared furnishing completeness gate for deterministic room commits."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from cityg.schemas import InteriorObject, Room


@dataclass(frozen=True)
class FurnishingNonDegradationPolicy:
    minimum_retention_ratio: float = 0.75
    minimum_object_count: int = 2
    protected_categories: tuple[str, ...] = (
        "bed", "sofa", "desk", "table", "dining_table", "office_chair",
        "chair", "counter", "checkout_counter", "display_shelf", "shelf",
        "cabinet", "wardrobe", "storage_rack", "reception_desk",
    )


def furnishing_non_degradation_check(
    before: list[InteriorObject],
    after: list[InteriorObject],
    room: Room,
    policy: FurnishingNonDegradationPolicy | None = None,
) -> dict[str, Any]:
    policy = policy or FurnishingNonDegradationPolicy()
    before_count, after_count = len(before), len(after)
    minimum_count = (
        before_count if before_count <= 1 else max(
            policy.minimum_object_count,
            math.ceil(before_count * policy.minimum_retention_ratio),
        )
    )
    base = {
        "room_id": room.id,
        "room_function": room.function,
        "before_count": before_count,
        "after_count": after_count,
        "minimum_count": minimum_count,
    }
    if after_count < minimum_count:
        return {
            **base,
            "ok": False,
            "code": "furnishing_non_degradation",
            "reason": f"room {room.id} would retain {after_count}/{before_count} objects; minimum is {minimum_count}",
        }

    before_categories = _category_counts(before)
    after_categories = _category_counts(after)
    lost = {
        category: count
        for category, count in before_categories.items()
        if category in policy.protected_categories and after_categories.get(category, 0) < count
    }
    if lost:
        return {
            **base,
            "ok": False,
            "code": "furnishing_anchor_loss",
            "reason": "refinement removed existing semantic furniture anchors: "
            + ", ".join(f"{key}={value}" for key, value in sorted(lost.items())),
            "lost_anchor_categories": lost,
        }
    return {
        **base,
        "ok": True,
        "code": "furnishing_non_degradation",
        "reason": "furnishing completeness retained",
        "lost_anchor_categories": {},
    }


def _category_counts(items: list[InteriorObject]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        category = furnishing_anchor_category(item.category)
        counts[category] = counts.get(category, 0) + 1
    return counts


def furnishing_anchor_category(category: str) -> str:
    value = str(category).lower().replace("-", "_").replace(" ", "_")
    return {
        "armchair": "chair",
        "dining_chair": "chair",
        "workstation": "desk",
        "coffee_table": "table",
        "side_table": "table",
        "bookshelf": "shelf",
        "display_rack": "display_shelf",
        "storage": "storage_rack",
        "rack": "storage_rack",
        "checkout": "checkout_counter",
        "reception": "reception_desk",
    }.get(value, value)


__all__ = [
    "FurnishingNonDegradationPolicy",
    "furnishing_anchor_category",
    "furnishing_non_degradation_check",
]
