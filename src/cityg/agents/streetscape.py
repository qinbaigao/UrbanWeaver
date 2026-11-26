"""Post-layout Streetscape Agent with deterministic metric ownership."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from typing import Any

from cityg.agents.context import ContextSection, ProgressiveContext
from cityg.agents.hierarchy import HierarchyAgentResult, _ProgressiveProgramAgent
from cityg.agents.requirement import AgentGenerationError
from cityg.planning.appearance import (
    UrbanAppearanceProgram,
    appearance_program_for_city,
)
from cityg.planning.streetscape import (
    STREET_ACTIVITY_LEVELS,
    STREET_ACTIVITY_MODES,
    STREET_AMENITY_TYPES,
    STREET_ARCHETYPES,
    STREET_FRONTAGE_TREATMENTS,
    STREET_LIGHT_FAMILIES,
    STREET_PLACEMENT_PATTERNS,
    STREET_TREE_TYPES,
    StreetNetworkProgram,
    StreetProgramPlanner,
    StreetSegmentProgram,
)
from cityg.schemas import City


def _changed_roads(candidate, baseline):
    # Provenance alone is not semantic personalization.
    return [a.road_id for a, b in zip(candidate, baseline)
            if {k:v for k,v in a.to_dict().items() if k != 'source'} !=
               {k:v for k,v in b.to_dict().items() if k != 'source'}]


class StreetscapeAgent(_ProgressiveProgramAgent[StreetNetworkProgram]):
    """Personalize realized road segments without emitting metric geometry."""

    name = "streetscape"

    def __init__(self, *args, segment_batch_size=8, **kwargs):
        super().__init__(*args, **kwargs)
        if not 1 <= segment_batch_size <= 32:
            raise ValueError('segment_batch_size must be between 1 and 32')
        self.segment_batch_size = segment_batch_size

    def plan(
        self,
        city: City,
        appearance: UrbanAppearanceProgram | None = None,
    ) -> HierarchyAgentResult[StreetNetworkProgram]:
        appearance = appearance or appearance_program_for_city(city)
        # Derive a clean deterministic baseline rather than recursively reading
        # a program left by a previous generation or refinement pass.
        baseline_city = replace(
            city,
            metadata={
                key: value
                for key, value in city.metadata.items()
                if key != "street_network_program"
            },
        )
        baseline = StreetProgramPlanner().plan(baseline_city, appearance)
        if len(baseline.segments) <= self.segment_batch_size:
            return self._plan_chunk(city, appearance, baseline)
        # All chunks share upstream intent, but only own their exact road IDs.
        # A failed chunk cannot discard previously accepted neighbors.
        segments, attempts, disclosures, batches = [], [], [], []
        for start in range(0, len(baseline.segments), self.segment_batch_size):
            chunk = replace(baseline, segments=baseline.segments[start:start+self.segment_batch_size])
            from cityg.progress import progress
            progress(self.name, '分组规划街景', group=start//self.segment_batch_size+1,
                     roads=len(chunk.segments))
            try:
                result = self._plan_chunk(city, appearance, chunk)
                segments.extend(result.program.segments)
                attempts.extend(result.attempts)
                disclosures.extend(result.disclosures)
                batches.append({'road_ids': [s.road_id for s in chunk.segments],
                                'status': 'accepted', 'diagnostics': result.diagnostics})
            except AgentGenerationError as error:
                segments.extend(chunk.segments)
                attempts.extend(error.attempts)
                batches.append({'road_ids': [s.road_id for s in chunk.segments],
                                'status': 'fallback', 'error': str(error)})
        if all(b['status'] == 'fallback' for b in batches):
            raise AgentGenerationError('All streetscape chunks failed; retain deterministic baseline', attempts)
        return HierarchyAgentResult(self.name, replace(baseline, segments=tuple(segments)),
            self.model_id, tuple(attempts), tuple(disclosures),
            {'batches': batches, 'fallback_road_ids': [rid for b in batches
                if b['status']=='fallback' for rid in b['road_ids']],
             'accepted_road_count': sum(len(b['road_ids']) for b in batches if b['status']=='accepted'),
             'changed_road_ids': _changed_roads(segments, baseline.segments)})

    def _plan_chunk(self, city, appearance, baseline):
        roads = {item.id: item for item in city.road_network.segments}
        buildings = {item.id: item for item in city.iter_buildings()}
        segment_rows: list[dict[str, Any]] = []
        for item in baseline.segments:
            road = roads[item.road_id]
            from cityg.paths import PlanarPath2D
            path = PlanarPath2D(road.centerline)
            adjacent = [buildings[key] for key in item.adjacent_building_ids if key in buildings]
            segment_rows.append(
                {
                    "road_id": item.road_id,
                    "road_class": road.road_class,
                    "length_m": round(path.length, 2),
                    "width_m": road.width_m,
                    "sidewalk_width_m": road.sidewalk_width_m,
                    "lane_count": road.lane_count,
                    "adjacent_buildings": [
                        {"building_id": building.id, "function": building.function}
                        for building in adjacent
                    ],
                    "safe_baseline": item.to_dict(),
                }
            )
        archetypes = Counter(item.archetype for item in baseline.segments)
        context = ProgressiveContext(
            summary={
                "city_id": city.id,
                "road_segment_count": len(baseline.segments),
                "building_count": sum(1 for _ in city.iter_buildings()),
                "baseline_archetype_histogram": dict(sorted(archetypes.items())),
                "realized_segments": segment_rows,
                "city_intent": appearance.to_dict(),
                "supported": {
                    "archetypes": sorted(STREET_ARCHETYPES),
                    "activity_levels": sorted(STREET_ACTIVITY_LEVELS),
                    "activity_modes": sorted(STREET_ACTIVITY_MODES),
                    "frontage_treatments": sorted(STREET_FRONTAGE_TREATMENTS),
                    "amenity_types": sorted(STREET_AMENITY_TYPES),
                    "placement_patterns": sorted(STREET_PLACEMENT_PATTERNS),
                    "tree_types": sorted(STREET_TREE_TYPES),
                    "light_families": sorted(STREET_LIGHT_FAMILIES),
                    "sides": ["left", "right"],
                },
            },
            sections=(
                ContextSection(
                    "realized_segments",
                    "Exact realized road IDs, dimensions, adjacent functions, and complete safe baselines",
                    segment_rows,
                ),
                ContextSection(
                    "city_intent",
                    "Upstream urban appearance intent",
                    appearance.to_dict(),
                ),
                ContextSection(
                    "compiler_contract",
                    "Hard constraints retained by deterministic compilation",
                    {
                        "coordinates": "compiler-owned",
                        "junction_clearance": "compiler-enforced",
                        "road_intrusion": "compiler-rejected",
                        "parking_and_bicycle_same_side": "forbidden",
                        "unknown_road_or_building_ids": "forbidden",
                    },
                ),
            ),
            # Only this batch's roads are exposed. Keep bounded headroom for
            # adjacency, shared intent and compiler contracts, including
            # callers that explicitly choose larger batches (up to 32).
            max_disclosed_chars=76_000,
        )
        prompt = self._base_prompt(
            "Streetscape",
            'Return the program object directly: {"version":"street_network_program.v1","segments":[...]}. '
            'Do NOT wrap it in a StreetNetworkProgram or program property. '
            "segments may contain only "
            "the exact realized road IDs that need personalization; omitted roads retain their "
            "safe baseline. For each returned road, choose semantic archetype, dominant_function, "
            "activity_level, frontage_treatment, activity_modes, activity_cluster_count, "
            "tree_spacing_m, street_light_spacing_m, vehicle_spacing_m, pedestrian_spacing_m, parking_sides, "
            "bicycle_lane_sides, amenity_types, placement_pattern, a compact tree_palette, "
            "light_family, furnishing_strip_width_m and frontage_strip_width_m. "
            "Use exactly these flat field names, not positive_spacings or strip_widths objects. "
            "Use formal/staggered rhythms for civic or "
            "connector streets, clustered rhythms around active commercial frontage, organic "
            "rhythms on residential streets, and sparse rhythms on service streets. Preserve the supplied "
            "adjacent_building_ids exactly. Parking and bicycle lanes may not share a side. "
            "Choose at most six bounded activity clusters per road; these are semantic events, "
            "not raw object counts. Bind retail_browsing/cafe_dwell to active frontage, "
            "transit_waiting to a bus_stop, cycle_flow to a bicycle lane or shared street, "
            "and loading_service to an industrial/service street. Never output coordinates, "
            "meshes, new roads, new buildings, or per-cluster object coordinates.",
        )

        baselines = {item.road_id: item for item in baseline.segments}

        def parse(data: dict[str, Any]) -> StreetNetworkProgram:
            if 'segments' not in data or set(data)-{'version','segments'}:
                raise ValueError('Street program must directly contain segments and optional version; '
                                 'no wrapper/unknown keys. Explicit segments=[] means no change.')
            raw_segments = data['segments']
            if not isinstance(raw_segments, list):
                raise ValueError("segments must be an array")
            seen: set[str] = set()
            overrides: dict[str, StreetSegmentProgram] = {}
            for raw in raw_segments:
                if not isinstance(raw, dict):
                    raise ValueError("each streetscape segment must be an object")
                unknown=set(raw)-set(StreetSegmentProgram.__dataclass_fields__)
                if unknown:
                    raise ValueError(f'Unknown segment fields {sorted(unknown)}; use flat fields '
                        'tree_spacing_m, street_light_spacing_m, vehicle_spacing_m, pedestrian_spacing_m, '
                        'furnishing_strip_width_m, frontage_strip_width_m')
                road_id = str(raw.get("road_id", ""))
                if road_id not in baselines:
                    raise ValueError(f"unknown realized road_id: {road_id}")
                if road_id in seen:
                    raise ValueError(f"duplicate road_id: {road_id}")
                seen.add(road_id)
                fallback = baselines[road_id]
                candidate = StreetSegmentProgram.from_dict(raw, fallback=fallback)
                if candidate.adjacent_building_ids != fallback.adjacent_building_ids:
                    raise ValueError("adjacent_building_ids are immutable")
                overrides[road_id] = candidate
            merged = tuple(overrides.get(item.road_id, item) for item in baseline.segments)
            return StreetNetworkProgram(
                version=str(data.get("version", "street_network_program.v1")),
                segments=merged,
            )

        result = self._run(context, prompt, parse)
        return replace(result, diagnostics={**result.diagnostics,
            'changed_road_ids': _changed_roads(result.program.segments, baseline.segments)})


__all__ = ["StreetscapeAgent"]
