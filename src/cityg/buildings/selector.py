"""Deterministic candidate filtering and diversity-aware archetype selection."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from typing import Iterable

from cityg.buildings.catalog import (
    DEFAULT_BUILDING_CATALOG,
    BuildingArchetype,
    catalog_by_id,
)
from cityg.schemas import Building


@dataclass(frozen=True)
class BuildingSelectionContext:
    building_id: str
    function: str
    floor_count: int
    width_m: float
    depth_m: float
    highrise: bool = False
    landmark: bool = False
    parcel_role: str = "interior"
    prototype_id: str | None = None

    @classmethod
    def from_building(cls, building: Building) -> "BuildingSelectionContext":
        height_contract = building.metadata.get("height_contract", {})
        return cls(
            building_id=building.id,
            function=building.function,
            floor_count=len(building.floors),
            width_m=building.footprint.width,
            depth_m=building.footprint.depth,
            highrise=bool(building.metadata.get("highrise", {}).get("enabled")),
            landmark=bool(height_contract.get("landmark")),
            parcel_role=str(building.metadata.get("parcel_role", "interior")),
            prototype_id=(
                str(building.metadata["prototype_id"])
                if building.metadata.get("prototype_id") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class BuildingSelection:
    archetype: BuildingArchetype
    facade_style_id: str
    score: float
    candidate_count: int
    rejected_reasons: tuple[str, ...] = ()
    source: str = "deterministic_catalog_v1"

    def to_metadata(self) -> dict:
        return {
            "archetype_id": self.archetype.archetype_id,
            "massing_signature": self.archetype.massing_signature,
            "massing_variant": self.archetype.massing_variant,
            "massing_style": self.archetype.massing_style,
            "massing_parameters": {
                key: value for key, value in self.archetype.massing_parameters
            },
            "massing_family": self.archetype.family,
            "facade_style_override": self.facade_style_id,
            "ornament_kit_ids": list(self.archetype.ornament_kit_ids),
            "archetype_selection": {
                "source": self.source,
                "score": round(self.score, 5),
                "candidate_count": self.candidate_count,
                "rejected_reasons": list(self.rejected_reasons),
            },
        }


class BuildingSelector:
    """Select a valid catalog entry without changing canonical geometry.

    The selector is intentionally deterministic.  A future LLM/VLM ranker can
    provide a preferred candidate ordering, while this class remains the hard
    constraint gate and deterministic tie breaker.
    """

    def __init__(self, catalog: Iterable[BuildingArchetype] = DEFAULT_BUILDING_CATALOG) -> None:
        self.catalog = tuple(catalog)
        self._by_id = catalog_by_id(self.catalog)

    def candidates(
        self,
        context: BuildingSelectionContext,
        *,
        preferred_ids: Iterable[str] = (),
    ) -> list[BuildingArchetype]:
        preferred = set(preferred_ids)
        result: list[BuildingArchetype] = []
        for item in self.catalog:
            if not item.supports(
                context.function,
                context.floor_count,
                context.width_m,
                context.depth_m,
            ):
                continue
            if item.landmark_only and not context.landmark:
                continue
            if context.prototype_id and item.prototype_ids and context.prototype_id not in item.prototype_ids:
                continue
            if preferred and item.archetype_id not in preferred:
                continue
            result.append(item)
        return result

    @staticmethod
    def _stable_index(key: str, count: int) -> int:
        if count <= 0:
            return 0
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        return int.from_bytes(digest[:4], "big") % count

    def select(
        self,
        context: BuildingSelectionContext,
        *,
        used_archetype_ids: Iterable[str] = (),
        used_massing_signatures: Iterable[str] = (),
        preferred_ids: Iterable[str] = (),
    ) -> BuildingSelection:
        candidates = self.candidates(context, preferred_ids=preferred_ids)
        if not candidates and preferred_ids:
            candidates = self.candidates(context)
        if not candidates and context.prototype_id is not None:
            # A legacy/manual BuildingProfile may intentionally pair a
            # function with a different visual prototype.  Keep that explicit
            # override while relaxing only the catalog's prototype preference;
            # footprint, height and function constraints remain hard.
            relaxed = replace(context, prototype_id=None)
            candidates = self.candidates(relaxed, preferred_ids=preferred_ids)
            if not candidates and preferred_ids:
                candidates = self.candidates(relaxed)
        if not candidates:
            raise ValueError(
                f"no building archetype satisfies {context.function=} {context.floor_count=} "
                f"{context.width_m=:.2f} {context.depth_m=:.2f}"
            )
        used = set(used_archetype_ids)
        used_signatures = set(used_massing_signatures)
        scored: list[tuple[float, str, BuildingArchetype]] = []
        for item in candidates:
            score = 0.0
            # Prefer a genuinely new massing signature, but do not prohibit
            # repetition: repeated buildings are expected in real cities.
            if item.archetype_id not in used:
                score += 2.0
            if item.massing_signature not in used_signatures:
                score += 1.0
            if context.parcel_role in item.preferred_frontage_roles:
                score += 0.65
            if context.highrise == item.is_highrise:
                score += 0.35
            # Stable, seed-free ordering makes the same canonical input
            # reproducible across machines and process runs.
            tie = self._stable_index(f"{context.building_id}:{item.archetype_id}", 10_000)
            scored.append((score, f"{tie:05d}:{item.archetype_id}", item))
        _, _, archetype = max(scored, key=lambda item: (item[0], item[1]))
        facade_index = self._stable_index(
            f"{context.building_id}:facade:{archetype.archetype_id}",
            len(archetype.facade_style_ids),
        )
        facade_style = archetype.facade_style_ids[facade_index]
        return BuildingSelection(
            archetype=archetype,
            facade_style_id=facade_style,
            score=max(score for score, _, item in scored if item is archetype),
            candidate_count=len(candidates),
        )

    def describe(self) -> list[dict]:
        """Return compact candidate data suitable for an LLM progressive context."""
        return [
            {
                "archetype_id": item.archetype_id,
                "family": item.family,
                "massing_style": item.massing_style,
                "massing_signature": item.massing_signature,
                "massing_variant": item.massing_variant,
                "massing_parameters": {
                    key: value for key, value in item.massing_parameters
                },
                "compatible_functions": list(item.compatible_functions),
                "facade_style_ids": list(item.facade_style_ids),
                "ornament_kit_ids": list(item.ornament_kit_ids),
                "floor_range": [item.min_floors, item.max_floors],
                "highrise_only": item.highrise_only,
                "landmark_only": item.landmark_only,
            }
            for item in self.catalog
        ]


__all__ = [
    "BuildingSelection",
    "BuildingSelectionContext",
    "BuildingSelector",
]
