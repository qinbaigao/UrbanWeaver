"""Bounded VLM-to-streetscape semantic repairs.

The VLM never supplies coordinates.  It binds an observable issue to an exact
road ID and this module adjusts only the validated semantic street program;
the topology-aware compiler remains responsible for every placement.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace, field
from typing import Any, Iterable

from cityg.planning.appearance import appearance_program_for_city
from cityg.planning.streetscape import (
    STREET_AMENITY_TYPES,
    StreetNetworkProgram,
    StreetProgramPlanner,
    StreetSegmentProgram,
)
from cityg.schemas import City


STREET_VISUAL_ISSUE_CODES = frozenset(
    {
        "street_underfurnished",
        "street_overcrowded",
        "frontage_disconnect",
        "cross_section_conflict",
        "street_asset_repetition",
        "vegetation_overdensity",
        "traffic_implausible",
        "road_intrusion",
    }
)


@dataclass(frozen=True)
class StreetscapeRefinementResult:
    city: City
    changed_road_ids: tuple[str, ...]
    applied_issues: tuple[dict[str, Any], ...]
    skipped_issues: tuple[dict[str, Any], ...]
    transaction_report: dict = field(default_factory=dict)

    @property
    def changed(self) -> bool:
        return bool(self.changed_road_ids)

    def trace_dict(self) -> dict[str, Any]:
        return {
            "changed": self.changed,
            "changed_road_ids": list(self.changed_road_ids),
            "applied_issues": [dict(item) for item in self.applied_issues],
            "skipped_issues": [dict(item) for item in self.skipped_issues],
            "commit_policy": "semantic_program_only_then_deterministic_recompile_v1",
            "transaction": self.transaction_report,
        }


def _infer_issue_code(issue: dict[str, Any]) -> str | None:
    explicit = str(issue.get("issue_code", ""))
    if explicit in STREET_VISUAL_ISSUE_CODES:
        return explicit
    text = " ".join(
        str(issue.get(key, "")).lower()
        for key in ("description", "suggested_action")
    )
    rules = (
        ("road_intrusion", ("intrud", "on the road", "in the lane", "道路内", "侵入")),
        ("cross_section_conflict", ("cross-section", "bike lane", "parking conflict", "横断面", "冲突")),
        ("frontage_disconnect", ("frontage", "entrance", "disconnect", "沿街界面", "入口断开")),
        ("vegetation_overdensity", ("too many tree", "vegetation dense", "树木过密", "遮挡入口")),
        ("traffic_implausible", ("traffic", "vehicle", "wrong lane", "车辆", "交通")),
        ("street_asset_repetition", ("repet", "identical asset", "重复", "单调")),
        ("street_overcrowded", ("overcrowd", "clutter", "too dense", "拥挤", "杂乱")),
        ("street_underfurnished", ("empty", "sparse", "underfurnished", "空旷", "稀疏")),
    )
    for code, tokens in rules:
        if any(token in text for token in tokens):
            return code
    return None


def _add_amenities(
    program: StreetSegmentProgram, values: Iterable[str]
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            [*program.amenity_types, *(item for item in values if item in STREET_AMENITY_TYPES)]
        )
    )


def _apply_issue(
    program: StreetSegmentProgram, code: str
) -> StreetSegmentProgram:
    if code == "street_underfurnished":
        additions = {
            "commercial_main_street": ("planter", "bicycle_rack", "cafe_terrace"),
            "residential_green_street": ("planter", "bench"),
            "civic_avenue": ("planter", "bench", "bicycle_rack"),
            "industrial_service_street": ("bollard", "loading_bay"),
        }.get(program.archetype, ("bench", "planter"))
        return replace(
            program,
            tree_spacing_m=max(8.0, program.tree_spacing_m * 0.88),
            street_light_spacing_m=max(12.0, program.street_light_spacing_m * 0.88),
            pedestrian_spacing_m=max(8.0, program.pedestrian_spacing_m * 0.82),
            activity_cluster_count=min(6, max(1, program.activity_cluster_count + 1)),
            amenity_types=_add_amenities(program, additions),
            source="vlm_refined",
        )
    if code == "street_overcrowded":
        return replace(
            program,
            tree_spacing_m=program.tree_spacing_m * 1.28,
            pedestrian_spacing_m=program.pedestrian_spacing_m * 1.40,
            vehicle_spacing_m=program.vehicle_spacing_m * 1.22,
            activity_cluster_count=max(0, program.activity_cluster_count - 1),
            amenity_types=program.amenity_types[: max(1, len(program.amenity_types) // 2)],
            source="vlm_refined",
        )
    if code == "frontage_disconnect":
        return replace(
            program,
            frontage_strip_width_m=min(0.78, program.frontage_strip_width_m * 1.25),
            amenity_types=_add_amenities(program, ("planter",)),
            source="vlm_refined",
        )
    if code in {"cross_section_conflict", "road_intrusion"}:
        return replace(
            program,
            parking_sides=(),
            bicycle_lane_sides=(),
            furnishing_strip_width_m=max(0.42, program.furnishing_strip_width_m * 0.86),
            source="vlm_refined",
        )
    if code == "street_asset_repetition":
        additions = ("bench", "planter", "bicycle_rack")
        return replace(
            program,
            tree_spacing_m=program.tree_spacing_m * 1.12,
            street_light_spacing_m=program.street_light_spacing_m * 1.10,
            amenity_types=_add_amenities(program, additions),
            source="vlm_refined",
        )
    if code == "vegetation_overdensity":
        return replace(
            program,
            tree_spacing_m=program.tree_spacing_m * 1.50,
            amenity_types=tuple(item for item in program.amenity_types if item != "planter"),
            source="vlm_refined",
        )
    if code == "traffic_implausible":
        return replace(
            program,
            vehicle_spacing_m=program.vehicle_spacing_m * 1.45,
            parking_sides=(),
            source="vlm_refined",
        )
    return program


def apply_streetscape_visual_refinement(
    city: City,
    issues: Iterable[dict[str, Any]],
    *,
    max_roads: int = 2,
    memory_store=None,
) -> StreetscapeRefinementResult:
    """Apply high-confidence road-bound issues as one transactional program edit."""
    current = StreetProgramPlanner().plan(city, appearance_program_for_city(city))
    programs = {item.road_id: item for item in current.segments}
    known_roads = set(programs)
    touched: list[str] = []
    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for raw in issues:
        issue = dict(raw)
        road_id = str(issue.get("entity_id", ""))
        confidence = float(issue.get("binding_confidence", 0.0))
        code = _infer_issue_code(issue)
        if road_id not in known_roads:
            issue["skip_reason"] = "unknown_road"
            skipped.append(issue)
            continue
        if confidence < 0.72:
            issue["skip_reason"] = "low_binding_confidence"
            skipped.append(issue)
            continue
        if code is None:
            issue["skip_reason"] = "unsupported_issue_code"
            skipped.append(issue)
            continue
        if road_id not in touched and len(touched) >= max(0, max_roads):
            issue["skip_reason"] = "road_budget_exhausted"
            skipped.append(issue)
            continue
        before = programs[road_id]
        after = _apply_issue(before, code)
        if after == before:
            issue["skip_reason"] = "no_semantic_change"
            skipped.append(issue)
            continue
        programs[road_id] = after
        if road_id not in touched:
            touched.append(road_id)
        applied.append(
            {
                "issue_id": issue.get("issue_id"),
                "road_id": road_id,
                "issue_code": code,
                "binding_confidence": confidence,
            }
        )
    refined = copy.deepcopy(city)
    if touched:
        existing = {s['road_id']: s for s in city.metadata.get('street_network_program', {}).get('segments', [])}
        existing.update({key: programs[key].to_dict() for key in touched})
        program = {
            **copy.deepcopy(city.metadata.get('street_network_program') or {'version': 'street_network_program.v1'}),
            'segments': list(existing.values())}
        refined.metadata['street_network_program'] = program
        from cityg.transactions import MutationProposal, accept_candidate, fingerprint
        proposal = MutationProposal.bind(city, touched, source='visual_repair', kind='streetscape',
            proposal_id='street_review_'+fingerprint(city)[:20])
        committed = accept_candidate(city, proposal, lambda _: refined, memory_store=memory_store)
        refined = committed.city
    return StreetscapeRefinementResult(
        city=refined,
        changed_road_ids=tuple(touched),
        applied_issues=tuple(applied),
        skipped_issues=tuple(skipped),
        transaction_report=committed.report if touched else {},
    )


__all__ = [
    "STREET_VISUAL_ISSUE_CODES",
    "StreetscapeRefinementResult",
    "apply_streetscape_visual_refinement",
]
