"""Deterministic functional height zoning and skyline contracts."""

from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass

from cityg.schemas import CitySpec, Point2D


FUNCTION_HEIGHT_BANDS: dict[str, tuple[float, float]] = {
    "industrial": (0.00, 0.22),
    "public_service": (0.00, 0.34),
    "residential": (0.16, 0.62),
    "mixed_use": (0.30, 0.82),
    "commercial": (0.44, 1.00),
}

FUNCTION_SKYLINE_PRIORITY = {
    "industrial": 0.10,
    "public_service": 0.55,
    "residential": 0.72,
    "mixed_use": 0.92,
    "commercial": 1.00,
}


@dataclass(frozen=True)
class HeightCandidate:
    building_index: int
    function: str
    position: Point2D


@dataclass(frozen=True)
class HeightDecision:
    building_index: int
    function: str
    height_zone: str
    height_role: str
    min_floors: int
    max_floors: int
    recommended_floors: int
    centrality: float
    source: str = "deterministic_fallback"
    highrise: bool = False
    landmark: bool = False

    def to_metadata(self) -> dict:
        return {
            "planner": "zoned_skyline_v1",
            "source": self.source,
            "height_zone": self.height_zone,
            "height_role": self.height_role,
            "min_floors": self.min_floors,
            "max_floors": self.max_floors,
            "recommended_floors": self.recommended_floors,
            "centrality": round(self.centrality, 6),
            "highrise": self.highrise,
            "landmark": self.landmark,
        }


class SkylinePlanner:
    """Assign a bounded height contract before individual buildings are built."""

    def plan(
        self, spec: CitySpec, candidates: list[HeightCandidate], program=None
    ) -> list[HeightDecision]:
        if program is not None:
            program.validate(spec)
        if spec.height_strategy == "uniform_random":
            return self._uniform(spec, candidates)
        if not candidates:
            return []

        scored = {
            item.building_index: self._centrality(spec, item.position)
            for item in candidates
        }
        def planning_score(item: HeightCandidate) -> float:
            centrality = scored[item.building_index]
            if program is None:
                spatial = centrality
                function_priority = FUNCTION_SKYLINE_PRIORITY.get(
                    item.function, 0.6
                )
            else:
                profile = program.for_function(item.function)
                spatial = self._biased_centrality(
                    centrality, profile.centrality_bias
                )
                function_priority = {
                    "lowrise": 0.25,
                    "midrise": 0.58,
                    "highrise": 1.0,
                    "mixed": 0.78,
                }[profile.height_role]
            return (
                function_priority
                + 1.35 * spatial
                + random.Random(
                    f"{spec.seed}:skyline-rank:{item.building_index}"
                ).uniform(-0.08, 0.08)
            )

        priority = sorted(
            candidates,
            key=lambda item: (
                -planning_score(item),
                item.building_index,
            ),
        )
        highrise_ratio = (
            program.highrise_ratio if program is not None else spec.highrise_ratio
        )
        requested_landmarks = (
            program.landmark_count if program is not None else spec.landmark_count
        )
        landmark_functions = (
            set(program.landmark_functions)
            if program is not None
            else {"commercial", "mixed_use", "residential"}
        )
        highrise_feasible = spec.max_floors >= 10 and spec.max_floors - spec.min_floors >= 5
        eligible = []
        for item in priority:
            if program is None:
                accepted = item.function in {
                    "commercial",
                    "mixed_use",
                    "residential",
                }
            else:
                profile = program.for_function(item.function)
                accepted = (
                    item.function in landmark_functions
                    or profile.height_role in {"highrise", "mixed"}
                )
            if accepted:
                eligible.append(item)
        landmark_eligible = [
            item for item in priority if item.function in landmark_functions
        ]
        landmark_count = (
            min(requested_landmarks, len(landmark_eligible))
            if highrise_feasible
            else 0
        )
        highrise_count = (
            min(
                len(eligible),
                max(landmark_count, round(len(candidates) * highrise_ratio)),
            )
            if highrise_feasible
            else 0
        )
        landmark_ids = {
            item.building_index for item in landmark_eligible[:landmark_count]
        }
        remaining_highrise = [
            item for item in eligible if item.building_index not in landmark_ids
        ]
        highrise_ids = landmark_ids | {
            item.building_index
            for item in remaining_highrise[
                : max(0, highrise_count - len(landmark_ids))
            ]
        }

        decisions = []
        for item in candidates:
            centrality = scored[item.building_index]
            landmark = item.building_index in landmark_ids
            highrise = item.building_index in highrise_ids
            if program is None:
                low_ratio, high_ratio = FUNCTION_HEIGHT_BANDS.get(
                    item.function, (0.12, 0.66)
                )
                strength = spec.skyline_strength
                low_ratio *= strength
                high_ratio = 1.0 - strength * (1.0 - high_ratio)
                if highrise:
                    low_ratio = max(low_ratio, 0.66)
                    high_ratio = max(high_ratio, 0.88)
                minimum = self._floor_at(spec, low_ratio)
                maximum = max(minimum, self._floor_at(spec, high_ratio))
                spatial_preference = centrality
            else:
                profile = program.for_function(item.function)
                minimum = profile.min_floors
                maximum = profile.max_floors
                spatial_preference = self._biased_centrality(
                    centrality, profile.centrality_bias
                )
                if highrise:
                    minimum = max(
                        minimum, round(minimum + 0.62 * (maximum - minimum))
                    )

            rng = random.Random(
                f"{spec.seed}:skyline-height:{item.building_index}:{item.function}"
            )
            within_band = min(
                1.0,
                max(
                    0.0,
                    0.18
                    + 0.72 * spatial_preference
                    + rng.uniform(-0.10, 0.10),
                ),
            )
            recommended = round(minimum + within_band * (maximum - minimum))
            if highrise:
                highrise_floor = round(
                    minimum
                    + min(
                        1.0,
                        0.72
                        + 0.22 * spatial_preference
                        + rng.uniform(-0.03, 0.03),
                    )
                    * (maximum - minimum)
                )
                recommended = max(recommended, highrise_floor)
            if landmark:
                minimum = max(minimum, maximum - 2)
                recommended = maximum
            recommended = min(maximum, max(minimum, recommended))
            decisions.append(
                HeightDecision(
                    building_index=item.building_index,
                    function=item.function,
                    height_zone=self._height_zone(centrality),
                    height_role=self._height_role(recommended, landmark),
                    min_floors=minimum,
                    max_floors=maximum,
                    recommended_floors=recommended,
                    centrality=centrality,
                    source=(
                        "llm_skyline_program"
                        if program is not None
                        else "deterministic_fallback"
                    ),
                    highrise=highrise,
                    landmark=landmark,
                )
            )
        return decisions

    @staticmethod
    def _uniform(
        spec: CitySpec, candidates: list[HeightCandidate]
    ) -> list[HeightDecision]:
        decisions = []
        for item in candidates:
            centrality = SkylinePlanner._centrality(spec, item.position)
            floors = random.Random(
                f"{spec.seed}:uniform-height:{item.building_index}"
            ).randint(spec.min_floors, spec.max_floors)
            decisions.append(
                HeightDecision(
                    building_index=item.building_index,
                    function=item.function,
                    height_zone="unconstrained",
                    height_role=SkylinePlanner._height_role(floors, False),
                    min_floors=spec.min_floors,
                    max_floors=spec.max_floors,
                    recommended_floors=floors,
                    centrality=centrality,
                    source="uniform_random_ablation",
                )
            )
        return decisions

    @staticmethod
    def summarize(
        spec: CitySpec,
        decisions: list[HeightDecision],
        realized: dict[int, int],
        program=None,
    ) -> dict:
        by_function: dict[str, list[int]] = defaultdict(list)
        roles = Counter()
        zones = Counter()
        landmark_ids = []
        highrise_ids = []
        for item in decisions:
            floors = realized[item.building_index]
            by_function[item.function].append(floors)
            roles[item.height_role] += 1
            zones[item.height_zone] += 1
            building_id = f"building_{item.building_index:03d}"
            if item.landmark:
                landmark_ids.append(building_id)
            if item.highrise:
                highrise_ids.append(building_id)
        values = list(realized.values())
        floor_histogram = Counter(values)
        sources = Counter(item.source for item in decisions)
        return {
            "planner": (
                "llm_skyline_program_v1"
                if program is not None
                else (
                    "zoned_skyline_v1"
                    if spec.height_strategy == "zoned_skyline"
                    else "uniform_random_v1"
                )
            ),
            "strategy": (
                "agent_authored_zoning"
                if program is not None
                else spec.height_strategy
            ),
            "decision_sources": dict(sorted(sources.items())),
            "skyline_strength": spec.skyline_strength,
            "requested_highrise_ratio": (
                program.highrise_ratio if program is not None else spec.highrise_ratio
            ),
            "requested_landmark_count": (
                program.landmark_count if program is not None else spec.landmark_count
            ),
            "realized_min_floors": min(values) if values else 0,
            "realized_max_floors": max(values) if values else 0,
            "realized_mean_floors": round(sum(values) / len(values), 6)
            if values
            else 0.0,
            "unique_realized_floor_count": len(floor_histogram),
            "dominant_realized_floor_share": round(
                max(floor_histogram.values(), default=0) / max(1, len(values)), 6
            ),
            "realized_floor_histogram": {
                str(floors): count
                for floors, count in sorted(floor_histogram.items())
            },
            "height_role_histogram": dict(sorted(roles.items())),
            "height_zone_histogram": dict(sorted(zones.items())),
            "landmark_building_ids": landmark_ids,
            "highrise_building_ids": highrise_ids,
            "function_floor_statistics": {
                function: {
                    "count": len(floors),
                    "min": min(floors),
                    "max": max(floors),
                    "mean": round(sum(floors) / len(floors), 6),
                    "unique_floor_count": len(set(floors)),
                }
                for function, floors in sorted(by_function.items())
            },
        }

    @staticmethod
    def _centrality(spec: CitySpec, position: Point2D) -> float:
        dx = abs(position.x - spec.width_m / 2) / max(spec.width_m / 2, 1e-6)
        dy = abs(position.y - spec.depth_m / 2) / max(spec.depth_m / 2, 1e-6)
        radial = math.hypot(dx, dy) / math.sqrt(2.0)
        return min(1.0, max(0.0, 1.0 - radial))

    @staticmethod
    def _floor_at(spec: CitySpec, ratio: float) -> int:
        ratio = min(1.0, max(0.0, ratio))
        return round(spec.min_floors + ratio * (spec.max_floors - spec.min_floors))

    @staticmethod
    def _height_zone(centrality: float) -> str:
        if centrality >= 0.64:
            return "urban_core"
        if centrality >= 0.36:
            return "transition_belt"
        return "urban_edge"

    @staticmethod
    def _height_role(floors: int, landmark: bool) -> str:
        if landmark:
            return "landmark"
        if floors >= 12:
            return "highrise"
        if floors >= 6:
            return "midrise"
        return "lowrise"

    @staticmethod
    def _biased_centrality(centrality: float, bias: str) -> float:
        if bias == "edge":
            return 1.0 - centrality
        if bias == "distributed":
            return 0.5 + 0.25 * (centrality - 0.5)
        return centrality
