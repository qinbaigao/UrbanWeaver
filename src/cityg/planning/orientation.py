"""Street-aware orientation contracts for CityG building masses."""

from __future__ import annotations

import random
from dataclasses import dataclass


LIVING_FUNCTIONS = {"residential", "mixed_use", "public_service"}


@dataclass(frozen=True)
class OrientationDecision:
    orientation_deg: float
    street_axis_deg: float
    local_facade_axis_deg: float
    base_alignment_deg: float
    offset_deg: float
    urban_context: str
    alignment_mode: str
    strict_alignment: bool
    variation_eligible: bool
    reason: str
    frontage_road_id: str | None = None

    def to_metadata(self) -> dict:
        return {
            "planner": "street_alignment_v1",
            "key_facade_relation": "parallel_to_frontage_street",
            "street_axis_deg": round(self.street_axis_deg, 6),
            "local_facade_axis_deg": round(self.local_facade_axis_deg, 6),
            "base_alignment_deg": round(self.base_alignment_deg, 6),
            "offset_deg": round(self.offset_deg, 6),
            "orientation_deg": round(self.orientation_deg, 6),
            "urban_context": self.urban_context,
            "alignment_mode": self.alignment_mode,
            "strict_alignment": self.strict_alignment,
            "variation_eligible": self.variation_eligible,
            "reason": self.reason,
            "frontage_road_id": self.frontage_road_id,
        }


class StreetAlignmentPlanner:
    """Keep urban street walls coherent and bound contextual edge rotation."""

    core_threshold = 0.64
    edge_threshold = 0.36
    max_contextual_offset_deg = 14.0

    @classmethod
    def plan(
        cls,
        *,
        entrance_side: str,
        function: str,
        centrality: float,
        cluster_size: int,
        highrise: bool,
        landmark: bool,
        layout_style: str,
        building_index: int,
        seed: int,
        street_axis_deg: float | None = None,
        frontage_road_id: str | None = None,
    ) -> OrientationDecision:
        centrality = min(1.0, max(0.0, float(centrality)))
        context = (
            "urban_core"
            if centrality >= cls.core_threshold
            else (
                "transition_belt"
                if centrality >= cls.edge_threshold
                else "urban_edge"
            )
        )
        # Facade axes and facade normals are different. West/east facades run
        # north-south locally; north/south facades run east-west.
        local_facade_axis = 90.0 if entrance_side in {"west", "east"} else 0.0
        if street_axis_deg is None:
            street_axis_deg = local_facade_axis
        street_axis_deg = float(street_axis_deg) % 180.0
        base = cls._normalize_axis_rotation(street_axis_deg - local_facade_axis)

        fragmented_living_cluster = (
            function in LIVING_FUNCTIONS
            and cluster_size == 1
            and centrality < 0.52
        )
        edge_living_area = (
            function in LIVING_FUNCTIONS and context == "urban_edge"
        )
        strict = (
            layout_style == "regular_grid"
            or context == "urban_core"
            or highrise
            or landmark
            or function in {"commercial", "industrial"}
        )
        eligible = not strict and (
            edge_living_area or fragmented_living_cluster
        )

        offset = 0.0
        if eligible:
            rng = random.Random(
                f"{seed}:street-orientation:{building_index}:{function}"
            )
            # Zero appears twice: contextual variation is possible, not mandatory.
            candidate = rng.choice(
                (-14.0, -10.0, -7.0, 0.0, 0.0, 6.0, 9.0, 13.0)
            )
            if context == "transition_belt":
                candidate *= 0.55
            if function == "public_service":
                candidate = max(-8.0, min(8.0, candidate))
            offset = round(candidate, 3)

        orientation = cls._normalize_orientation(base + offset)
        if strict:
            mode = "strict_street_alignment"
            reason = (
                "core/highrise/institutional street wall"
                if layout_style != "regular_grid"
                else "regular-grid ablation"
            )
        elif eligible and abs(offset) > 1e-9:
            mode = "contextual_edge_rotation"
            reason = "peripheral or fragmented living-area composition"
        elif eligible:
            mode = "contextual_edge_aligned"
            reason = "eligible edge site retained street alignment"
        else:
            mode = "street_aligned"
            reason = "continuous urban frontage"
        return OrientationDecision(
            orientation_deg=orientation,
            street_axis_deg=float(street_axis_deg),
            local_facade_axis_deg=local_facade_axis,
            base_alignment_deg=base,
            offset_deg=offset,
            urban_context=context,
            alignment_mode=mode,
            strict_alignment=strict,
            variation_eligible=eligible,
            reason=reason,
            frontage_road_id=frontage_road_id,
        )

    @staticmethod
    def _normalize_axis_rotation(value: float) -> float:
        """Return the smallest rotation because facade axes are undirected."""

        return (float(value) + 90.0) % 180.0 - 90.0

    @staticmethod
    def _normalize_orientation(value: float) -> float:
        return round((float(value) + 180.0) % 360.0 - 180.0, 6)
