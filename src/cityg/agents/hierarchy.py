"""Urban, building and floor agents with structured progressive disclosure."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, replace, field
from typing import Any, Callable, Generic, TypeVar

from cityg.agents.context import ContextSection, DisclosureEvent, ProgressiveContext
from cityg.agents.protocol import normalize_program, rejection_feedback
from cityg.agents.requirement import AgentAttempt, AgentGenerationError, _parse_json_object
from cityg.buildings.catalog import DEFAULT_BUILDING_CATALOG
from cityg.geometry.prototypes import PROTOTYPES_BY_ID
from cityg.planning.baseline import BaselineCityPlanner, ROOM_FUNCTIONS
from cityg.planning.appearance import (
    UrbanAppearanceProgram,
    default_urban_appearance_program,
)
from cityg.planning.programs import (
    BLOCK_TRAVERSALS,
    ROAD_PATTERNS,
    ENTRANCE_SIDES,
    FLOOR_LAYOUTS,
    FLOOR_ROLES,
    FLOOR_POLICIES,
    HEIGHT_CENTRALITY_BIASES,
    HEIGHT_ROLES,
    HIGHRISE_MASSING_VARIANTS,
    BuildingProgram,
    FloorProgram,
    FloorSpaceProgram,
    HierarchicalProgram,
    SkylineProgram,
    UrbanProgram,
)
from cityg.schemas import CitySpec
from cityg.planning.spatial_program import SPATIAL_PROGRAM_GUIDANCE
from cityg.serialization import to_primitive
from cityg.services.interfaces import ChatMessage, TextReasoningService


PROGRAM_ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "action": {"type": "string", "enum": ["request_details", "final"]},
        "detail_keys": {"type": "array", "items": {"type": "string"}},
        "program_json": {"type": "string"},
    },
    "required": ["action", "detail_keys", "program_json"],
}

ProgramT = TypeVar("ProgramT")

_BUILDING_ARCHETYPES_BY_ID = {
    item.archetype_id: item for item in DEFAULT_BUILDING_CATALOG
}


def _normalize_building_prototype_ids(data: dict[str, Any]) -> dict[str, Any]:
    """Repair the one unambiguous prototype/archetype namespace mix-up.

    Building archetypes explicitly declare their compatible structural
    prototypes. If a model places a known archetype ID in ``prototype_id``,
    mapping to the first declared compatible prototype preserves the authored
    archetype palette without guessing geometry. Unknown IDs remain untouched
    so normal validation rejects them.
    """
    normalized = dict(data)
    profiles: list[object] = []
    for raw_profile in data.get("profiles", []):
        if not isinstance(raw_profile, dict):
            profiles.append(raw_profile)
            continue
        profile = dict(raw_profile)
        prototype_id = str(profile.get("prototype_id", ""))
        archetype = _BUILDING_ARCHETYPES_BY_ID.get(prototype_id)
        compatible = tuple(
            item for item in (archetype.prototype_ids if archetype else ())
            if item in PROTOTYPES_BY_ID
        )
        if prototype_id not in PROTOTYPES_BY_ID and compatible:
            profile["prototype_id"] = compatible[0]
            palette = [str(item) for item in profile.get("archetype_palette", ())]
            if prototype_id not in palette:
                profile["archetype_palette"] = [prototype_id, *palette]
        profiles.append(profile)
    normalized["profiles"] = profiles
    return normalized


@dataclass(frozen=True)
class HierarchyAgentResult(Generic[ProgramT]):
    agent: str
    program: ProgramT
    model_id: str
    attempts: tuple[AgentAttempt, ...]
    disclosures: tuple[DisclosureEvent, ...]
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def trace_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "model_id": self.model_id,
            "program": to_primitive(self.program),
            "attempts": [asdict(item) for item in self.attempts],
            "disclosures": [asdict(item) for item in self.disclosures],
            "diagnostics": self.diagnostics,
            "totals": {
                "model_calls": len(self.attempts),
                "disclosure_rounds": len(self.disclosures),
                "disclosed_chars": sum(item.serialized_chars for item in self.disclosures),
                "prompt_tokens": sum(
                    int(item.usage.get("prompt_tokens", 0)) for item in self.attempts
                ),
                "completion_tokens": sum(
                    int(item.usage.get("completion_tokens", 0)) for item in self.attempts
                ),
                "elapsed_s": round(sum(item.elapsed_s for item in self.attempts), 6),
            },
        }


@dataclass(frozen=True)
class HierarchicalPlanningResult:
    program: HierarchicalProgram
    urban: HierarchyAgentResult[UrbanProgram]
    skyline: HierarchyAgentResult[SkylineProgram]
    building: HierarchyAgentResult[BuildingProgram]
    floor: HierarchyAgentResult[FloorProgram]
    appearance: HierarchyAgentResult[UrbanAppearanceProgram] | None = None

    def trace_dict(self) -> dict[str, Any]:
        stages = [self.urban, self.skyline, self.building, self.floor]
        if self.appearance is not None:
            stages.append(self.appearance)
        return {
            "program": to_primitive(self.program),
            "stages": [item.trace_dict() for item in stages],
            "totals": {
                "model_calls": sum(len(item.attempts) for item in stages),
                "disclosure_rounds": sum(len(item.disclosures) for item in stages),
                "disclosed_chars": sum(
                    event.serialized_chars
                    for item in stages
                    for event in item.disclosures
                ),
                "prompt_tokens": sum(
                    int(attempt.usage.get("prompt_tokens", 0))
                    for item in stages
                    for attempt in item.attempts
                ),
                "completion_tokens": sum(
                    int(attempt.usage.get("completion_tokens", 0))
                    for item in stages
                    for attempt in item.attempts
                ),
                "elapsed_s": round(
                    sum(
                        attempt.elapsed_s
                        for item in stages
                        for attempt in item.attempts
                    ),
                    6,
                ),
            },
        }


class _ProgressiveProgramAgent(Generic[ProgramT]):
    name = "hierarchy"

    def __init__(
        self,
        service: TextReasoningService,
        *,
        model_id: str = "unknown",
        max_calls: int = 4,
    ) -> None:
        if max_calls < 1:
            raise ValueError("max_calls must be at least 1")
        self.service = service
        self.model_id = model_id
        self.max_calls = max_calls

    def _run(
        self,
        context: ProgressiveContext,
        system_prompt: str,
        parse_and_validate: Callable[[dict[str, Any]], ProgramT],
    ) -> HierarchyAgentResult[ProgramT]:
        from cityg.design_goals import goal_context
        payload=context.initial_payload()
        goals=goal_context(getattr(self,'design_goals',[]),self.name)
        if goals:
            payload={**payload,'shared_design_goals':goals,
                     'goal_authority':'Soft interpretations only; explicit user constraints and scope take precedence.'}
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(
                role="user",
                content=json.dumps(
                    payload, ensure_ascii=False, sort_keys=True
                ),
            ),
        ]
        attempts: list[AgentAttempt] = []
        previous_error: str | None = None
        repeated_errors = 0
        proposal_attempts = 0
        normalizations = []
        # Successful disclosures have their own bounded budget. Invalid requests
        # still consume proposal attempts, so alternating errors cannot loop.
        total_limit = self.max_calls + max(0, context.max_rounds-len(context.events))
        for index in range(1, total_limit + 1):
            from cityg.progress import progress
            progress(self.name, '请求模型（上下文读取与方案尝试分别计数）', call=f'{index}/{total_limit}', proposal_attempts=proposal_attempts)
            started = time.monotonic()
            raw = ""
            finish_reason = None
            usage: dict[str, Any] = {}
            error: str | None = None
            program = None
            disclosure = None
            try:
                method = getattr(self.service, "complete_with_metadata", None)
                if callable(method):
                    completion = method(messages, PROGRAM_ACTION_SCHEMA)
                    raw = completion.content
                    finish_reason = completion.finish_reason
                    usage = completion.usage
                else:
                    raw = self.service.complete(messages, PROGRAM_ACTION_SCHEMA)
                if finish_reason == "length":
                    raise ValueError("model output reached max_tokens")
                response = _parse_json_object(raw)
                action = response.get("action")
                if action == "request_details":
                    keys = response.get("detail_keys")
                    if not isinstance(keys, list):
                        raise ValueError("detail_keys must be an array")
                    disclosure = context.disclose([str(key) for key in keys])
                elif action == "final":
                    if response.get("detail_keys"):
                        raise ValueError("final action must use an empty detail_keys array")
                    encoded = response.get("program_json")
                    if not isinstance(encoded, str):
                        raise ValueError("program_json must be a JSON-encoded string")
                    data, changes = normalize_program(_parse_json_object(encoded))
                    normalizations.extend({'call': index, **item} for item in changes)
                    program = parse_and_validate(data)
                else:
                    raise ValueError("action must be request_details or final")
            except (TypeError, ValueError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
                error = f"{type(exc).__name__}: {exc}"
            if disclosure is None or error is not None:
                proposal_attempts += 1
            elapsed = time.monotonic() - started
            serialized_messages = tuple(
                {"role": item.role, "content": item.content} for item in messages
            )
            prompt_hash = hashlib.sha256(
                json.dumps(
                    serialized_messages, sort_keys=True, ensure_ascii=False
                ).encode("utf-8")
            ).hexdigest()
            attempts.append(
                AgentAttempt(
                    index=index,
                    prompt_hash=prompt_hash,
                    messages=serialized_messages,
                    raw_output=raw,
                    elapsed_s=round(elapsed, 6),
                    error=error,
                    finish_reason=finish_reason,
                    usage=usage,
                )
            )
            if program is not None and error is None:
                return HierarchyAgentResult(
                    self.name,
                    program,
                    self.model_id,
                    tuple(attempts),
                    tuple(context.events),
                    {'proposal_attempts': proposal_attempts,
                     'successful_disclosures': len(context.events),
                     'normalizations': normalizations},
                )
            # Scope this guard to one planning action, not to unrelated buildings.
            # Different errors remain bounded by max_calls; successful disclosure
            # is progress and resets the consecutive-failure counter.
            if error is None:
                repeated_errors = 0
            elif error == previous_error:
                repeated_errors += 1
            else:
                repeated_errors = 1
            previous_error = error
            if error:
                stalled = repeated_errors >= 3
                exhausted = proposal_attempts >= self.max_calls
                progress(
                    self.name,
                    '停止本次规划：连续三次相同校验失败' if stalled else (
                        '停止本次规划：调用次数已用尽' if exhausted else '校验失败；携带反馈重试'),
                    call=f'{index}/{total_limit}', consecutive_failures=repeated_errors,
                )
                if stalled:
                    raise AgentGenerationError(
                        f"{self.name} agent stopped after {index} model calls: "
                        f"same validation error repeated 3 times: {error}", attempts
                    )
            if proposal_attempts >= self.max_calls:
                break
            if index < total_limit:
                messages.append(ChatMessage(role="assistant", content=raw[:10000]))
                if disclosure is not None and error is None:
                    messages.append(
                        ChatMessage(
                            role="user",
                            content=json.dumps(
                                disclosure, ensure_ascii=False, sort_keys=True
                            ),
                        )
                    )
                else:
                    messages.append(
                        ChatMessage(
                            role="user",
                            content=json.dumps(rejection_feedback(
                                error, context, self.max_calls-proposal_attempts), ensure_ascii=False),
                        )
                    )
        raise AgentGenerationError(
            f"{self.name} agent failed after {len(attempts)} model calls "
            f"({proposal_attempts} proposal/invalid-action attempts)", attempts
        )

    @staticmethod
    def _base_prompt(role: str, program_contract: str) -> str:
        return (
            f"You are CityG's {role} Agent. You receive a compact summary and a catalog of "
            "optional detail sections. Respond with exactly one structured action. If essential "
            "facts are absent, set action=request_details, list only required keys, and set "
            "program_json='{}'. Otherwise set action=final, detail_keys=[], and encode the "
            f"complete program as a compact JSON string. {program_contract} Never invent IDs or "
            "unsupported enum values. The deterministic compiler and validators are final."
        )


class UrbanAgent(_ProgressiveProgramAgent[UrbanProgram]):
    name = "urban"

    def plan(self, spec: CitySpec) -> HierarchyAgentResult[UrbanProgram]:
        zones = [
            {
                "zone_id": f"zone_{index:02d}",
                "name": zone.name,
                "function": zone.function,
                "weight": zone.weight,
            }
            for index, zone in enumerate(spec.zones)
        ]
        context = ProgressiveContext(
            summary={
                "interior_requirements": spec.interior_requirements,
                "urban_requirements": spec.urban_requirements,
                "city_name": spec.name,
                "extent_m": [spec.width_m, spec.depth_m],
                "building_count": spec.building_count,
                "zone_count": len(spec.zones),
                "layout_style": spec.layout_style,
                "supported": {
                    "road_pattern": sorted(ROAD_PATTERNS),
                    "block_traversal": sorted(BLOCK_TRAVERSALS),
                    "collector_policy": ["perimeter"],
                },
            },
            sections=(
                ContextSection(
                    "zones", "Exact zone IDs, functions and allocation weights", zones
                ),
                ContextSection(
                    "site_constraints",
                    "Road, sidewalk, setback and vertical density limits",
                    {
                        "road_width_m": spec.road_width_m,
                        "sidewalk_width_m": spec.sidewalk_width_m,
                        "parcel_setback_m": spec.parcel_setback_m,
                        "open_space_ratio": spec.open_space_ratio,
                        "layout_irregularity": spec.layout_irregularity,
                        "buildings_per_block": spec.buildings_per_block,
                        "branch_road_ratio": spec.branch_road_ratio,
                        "requested_road_pattern": spec.road_pattern,
                        "morphology": spec.morphology,
                        "floor_range": [spec.min_floors, spec.max_floors],
                    },
                ),
            ),
        )
        prompt = self._base_prompt(
            "Urban",
            "UrbanProgram fields are district_order, road_pattern, block_traversal, and "
            "collector_policy. district_order must contain every exact zone_id once. "
            "Only district_order is an array. road_pattern, block_traversal and collector_policy "
            "are scalar strings: choose ONE value from each supported list, never copy the list. "
            'For example block_traversal="row_major" (not ["row_major"]). '
            "Preserve the requested landscape_adaptive road pattern; its morphology is a hard contract."
        )

        def parse(data: dict[str, Any]) -> UrbanProgram:
            program = UrbanProgram.from_dict(data)
            program.validate(spec)
            return program

        return self._run(context, prompt, parse)


class BuildingAgent(_ProgressiveProgramAgent[BuildingProgram]):
    name = "building"

    def plan(
        self,
        spec: CitySpec,
        urban: UrbanProgram,
        skyline: SkylineProgram | None = None,
        *, prototype_context: dict | None = None,
    ) -> HierarchyAgentResult[BuildingProgram]:
        from cityg.architecture import DESIGN_LANGUAGES
        from cityg.envelopes import ENVELOPE_SCHEMA
        functions = sorted({zone.function for zone in spec.zones})
        zone_map = {
            f"zone_{index:02d}": zone for index, zone in enumerate(spec.zones)
        }
        ordered_zones = [zone_map[key] for key in urban.district_order]
        allocations = BaselineCityPlanner._allocate_zones(
            tuple(ordered_zones), spec.building_count
        )
        context = ProgressiveContext(
            summary={
                "interior_requirements": spec.interior_requirements,
                "building_count": spec.building_count,
                **({'prototype_interior_capabilities': prototype_context} if prototype_context else {}),
                "functions": functions,
                "floor_range": [spec.min_floors, spec.max_floors],
                "architectural_context": spec.architecture,
                "district_architecture": {zone.name: zone.architecture for zone in spec.zones},
                "design_language_catalog": DESIGN_LANGUAGES,
                "exterior_envelope_schema": ENVELOPE_SCHEMA,
                "supported": {
                    "floor_policy": sorted(FLOOR_POLICIES),
                    "entrance_side": sorted(ENTRANCE_SIDES),
                    "prototype_id": sorted(PROTOTYPES_BY_ID),
                    "highrise_massing_palette": sorted(
                        HIGHRISE_MASSING_VARIANTS
                    ),
                    "building_archetype_count": len(DEFAULT_BUILDING_CATALOG),
                    "building_archetype_ids": [
                        item.archetype_id for item in DEFAULT_BUILDING_CATALOG
                    ],
                },
            },
            sections=(
                ContextSection(
                    "urban_program", "Accepted upstream UrbanProgram", to_primitive(urban)
                ),
                ContextSection(
                    "skyline_program",
                    "Accepted upstream height zoning and landmark contract",
                    to_primitive(skyline) if skyline is not None else None,
                ),
                ContextSection(
                    "zone_allocations",
                    "Deterministic building counts per ordered district",
                    [
                        {
                            "name": zone.name,
                            "function": zone.function,
                            "building_count": count,
                        }
                        for zone, count in allocations
                    ],
                ),
                ContextSection(
                    "prototype_catalog",
                    "Physical and visual properties of every prototype",
                    {key: asdict(value) for key, value in PROTOTYPES_BY_ID.items()},
                ),
                ContextSection(
                    "building_archetype_catalog",
                    "Catalog-grounded visual/structural candidates. The final selector still enforces footprint, height, function and prototype constraints.",
                    [
                        {
                            "archetype_id": item.archetype_id,
                            "family": item.family,
                            "massing_style": item.massing_style,
                            "massing_signature": item.massing_signature,
                            "compatible_functions": list(item.compatible_functions),
                            "facade_style_ids": list(item.facade_style_ids),
                            "highrise_only": item.highrise_only,
                            "landmark_only": item.landmark_only,
                        }
                        for item in DEFAULT_BUILDING_CATALOG
                    ],
                ),
            ),
        )
        prompt = self._base_prompt(
            "Building",
            "BuildingProgram has profiles. Each profile has function, floor_policy, "
            "entrance_side, prototype_id, optional highrise_massing_palette, and an "
            "optional archetype_palette of compatible catalog IDs, and optional "
            "design_language_palette of 2-4 IDs from design_language_catalog. Choose a coherent "
            "set using architectural_context (region, era, climate) without country stereotypes. "
            "District-specific explicit design languages override this shared function preference. "
            "Optionally provide roof_profile_palette using quiet, mechanical, solar, garden, mixed. "
            "Choose 2-3 roof uses compatible with function and climate, keeping some roofs restrained; "
            "mixed permits service equipment on upper roofs and planted lower terraces. "
            "This is a semantic brief: the compiler checks actual exposed horizontal roof polygons, "
            "equipment clearance and support height; it does not promise accessible rooftop interiors. "
            "An optional envelope_preference follows exterior_envelope_schema; leave it empty unless "
            "architecture requests exterior-only forms via expressive_ratio, explicit shapes or curtain-wall "
            "buildings. Explicit district envelopes override this shared preference. These shapes "
            "are budgeted per building when expressive_ratio is present (normally 0.2), not copied "
            "onto every building of a function. Prefer a restrained compatible candidate; "
            "replace the legacy visual massing, not its planned room layout; interior compilation is unsupported. "
            "Do not reduce appearance differences to colors; languages change opening rhythm, "
            "solid/glass proportions and shading. The archetype palette is a "
            "semantic preference only; the deterministic selector later checks each "
            "building's realized footprint, floor count, frontage and landmark role. "
            "The palette is a non-empty list drawn from the supported values and should "
            "usually keep standard while permitting restrained setback/offset diversity; "
            "slender_landmark should be rare. Cover every unique function once: if multiple "
            "zones or allocations share a function (for example two commercial districts), "
            "they still use one shared function profile rather than duplicate profiles. Choose "
            "semantically compatible prototypes. CRITICAL: prototype_id and archetype IDs "
            "belong to different namespaces. prototype_id must be exactly one value from "
            f"{sorted(PROTOTYPES_BY_ID)}; IDs from building_archetype_ids may appear only "
            "inside archetype_palette. floor_policy selects a value inside the "
            "accepted per-site SkylineProgram contract; it expresses only a bounded bias "
            "around SkylineAgent's recommended floors and cannot flatten a function to one height."
        )

        def parse(data: dict[str, Any]) -> BuildingProgram:
            program = BuildingProgram.from_dict(
                _normalize_building_prototype_ids(data)
            )
            program.validate(spec)
            return program

        return self._run(context, prompt, parse)


class SkylineAgent(_ProgressiveProgramAgent[SkylineProgram]):
    name = "skyline"

    def plan(
        self, spec: CitySpec, urban: UrbanProgram
    ) -> HierarchyAgentResult[SkylineProgram]:
        functions = sorted({zone.function for zone in spec.zones})
        # High-rise/landmark planning has a stricter global feasibility
        # contract than ordinary floor ranges. Expose that contract directly
        # to the LLM so it does not repeatedly propose an invalid skyline for
        # a compact low-rise test scene (for example, a 3-8 floor city).
        skyline_features_feasible = (
            spec.max_floors >= 10 and spec.max_floors - spec.min_floors >= 5
        )
        allocations = BaselineCityPlanner._allocate_zones(
            spec.zones, spec.building_count
        )
        context = ProgressiveContext(
            summary={
                "interior_requirements": spec.interior_requirements,
                "building_count": spec.building_count,
                "functions": functions,
                "global_floor_range": [spec.min_floors, spec.max_floors],
                    "supported": {
                        "centrality_bias": sorted(HEIGHT_CENTRALITY_BIASES),
                        "height_role": sorted(HEIGHT_ROLES),
                        "highrise_ratio_range": (
                            [0.0, 0.5] if skyline_features_feasible else [0.0, 0.0]
                        ),
                        "landmark_count_range": (
                            [0, min(10, spec.building_count)]
                            if skyline_features_feasible
                            else [0, 0]
                        ),
                        "highrise_landmark_feasibility": skyline_features_feasible,
                    },
            },
            sections=(
                ContextSection(
                    "urban_program",
                    "Accepted road and district ordering program",
                    to_primitive(urban),
                ),
                ContextSection(
                    "zone_allocations",
                    "Functions and deterministic building counts",
                    [
                        {
                            "name": zone.name,
                            "function": zone.function,
                            "building_count": count,
                        }
                        for zone, count in allocations
                    ],
                ),
                ContextSection(
                    "planning_guidance",
                    "Non-binding urban-design considerations for a plausible skyline",
                    {
                        "commercial": "usually tallest and core-oriented",
                        "mixed_use": "mid/high transition around activity centers",
                        "residential": "varied mid-rise with selective towers",
                        "public_service": "usually low/mid-rise; landmark only when justified",
                        "industrial": "normally low-rise and distributed/edge-oriented",
                        "avoid": [
                            "every building at the maximum",
                            "industrial towers without an explicit user reason",
                            "more landmarks than the allocated function can support",
                        ],
                        "small_scene_constraint": (
                            "Set highrise_ratio=0 and landmark_count=0 because the "
                            "global floor range cannot support high-rise or landmark "
                            "planning."
                            if not skyline_features_feasible
                            else "High-rise and landmark choices are allowed only "
                            "within the advertised global floor range."
                        ),
                    },
                ),
            ),
        )
        prompt = self._base_prompt(
            "Skyline",
            "SkylineProgram fields are profiles, highrise_ratio, landmark_count, "
            "landmark_functions, and skyline_strength. Each profile has exact function, "
            "min_floors, max_floors, centrality_bias, and height_role. Cover every function "
            "once and stay inside global_floor_range. Use the user intent and urban program "
            "to create functional height zoning and a readable but non-uniform skyline."
        )

        def parse(data: dict[str, Any]) -> SkylineProgram:
            program = SkylineProgram.from_dict(data)
            program.validate(spec)
            return program

        return self._run(context, prompt, parse)


class FloorAgent(_ProgressiveProgramAgent[FloorProgram]):
    name = "floor"

    def rank_access_repair(self, feedback, choices, *, on_attempts=None):
        """Prioritize one realized-floor edit. Geometry decides whether to commit."""
        ids = list(range(len(choices)))
        schema = {"type": "object", "additionalProperties": False,
                  "properties": {"candidate": {"type": "integer", "enum": ids},
                                 "reason": {"type": "string"}}, "required": ["candidate", "reason"]}
        messages = [ChatMessage("system",
            "You are the Floor Agent revising a compiled ground floor. Select the first candidate to test. "
            "Reconnect a split corridor on supported slab; for an isolated blocked doorway, prefer a local move. "
            "Preserve the exterior entrance, vertical core, room functions and furniture. "
            "Use the typed JSON response, with a one-sentence reason."),
            ChatMessage("user", json.dumps({
                "breakpoint": feedback["breakpoint"], "geometry": feedback["geometry"],
                "floor_goals": getattr(self, "design_goals", []),
                "candidates": [{"index": i, **choice} for i, choice in enumerate(choices)]
            }, ensure_ascii=False))]
        start = time.monotonic()
        raw, usage, finish, error = "", {}, None, None
        try:
            method = getattr(self.service, "complete_with_metadata", None)
            if callable(method):
                completion = method(messages, schema)
                raw, usage, finish = completion.content, completion.usage, completion.finish_reason
            else:
                raw = self.service.complete(messages, schema)
            chosen = _parse_json_object(raw)
            if (finish == "length" or type(chosen.get("candidate")) is not int or chosen["candidate"] not in ids
                    or not isinstance(chosen.get("reason"), str) or not chosen["reason"].strip()):
                raise ValueError("Incomplete or invalid floor access selection")
            feedback["selection"] = {"source": "floor_agent", **chosen}
        except (ValueError, TypeError, RuntimeError, OSError) as exc:
            error = str(exc)
            feedback["selection"] = {"source": "geometry_fallback", "reason": error}
        if on_attempts:
            serialized = tuple({"role": m.role, "content": m.content} for m in messages)
            digest = hashlib.sha256(json.dumps(serialized).encode()).hexdigest()
            on_attempts([AgentAttempt(1, digest, serialized, raw, time.monotonic()-start, error, finish, usage)])
        return None if error is not None else chosen["candidate"]

    def plan(
        self, spec: CitySpec, building: BuildingProgram, *, prototype_context: dict | None = None
    ) -> HierarchyAgentResult[FloorProgram]:
        functions = sorted({zone.function for zone in spec.zones})
        site_area_per_building = spec.width_m * spec.depth_m / spec.building_count
        estimated_floor_plate_range = [
            round(max(80.0, site_area_per_building * 0.05), 1),
            round(min(3000.0, max(160.0, site_area_per_building * 0.22)), 1),
        ]
        room_count_contract = (
            {
                "mode": "fixed",
                "exact_room_count": spec.rooms_per_floor,
            }
            if spec.room_count_strategy == "fixed"
            else {
                "mode": "adaptive",
                "exact_room_count": None,
                "instruction": (
                    "Infer count ranges from floor role, function, target room area, "
                    "and estimated floor-plate area. No legacy count should anchor the result."
                ),
            }
        )
        space_context = ProgressiveContext(
            summary={
                "interior_requirements": spec.interior_requirements,
                **({'prototype_priors': prototype_context} if prototype_context else {}),
                "functions": functions,
                "profile_cardinality_contract": {"exact_function_ids": functions, "exact_count": len(functions)},
                "floor_range": [spec.min_floors, spec.max_floors],
                "room_count_contract": room_count_contract,
                "estimated_floor_plate_area_range_m2": estimated_floor_plate_range,
                "supported": {
                    "floor_roles": sorted(FLOOR_ROLES),
                    "room_functions_by_building_function": {key:list(ROOM_FUNCTIONS[key]) for key in functions},
                    "spatial_program": SPATIAL_PROGRAM_GUIDANCE,
                    "room_count_range": [1, 32],
                    "target_room_area_m2_range": [8, 250],
                    "min_room_width_m_range": [2.4, 12],
                    "max_room_depth_m_range": [4, 30],
                    "max_room_aspect_ratio_range": [1.4, 8],
                    "unit_group_size_range": [1, 12],
                    "layout_templates": [
                        "auto", "residential_units", "office_core",
                        "commercial_retail", "podium_core", "tower_core",
                        "open_plan",
                    ],
                },
            },
            sections=(
                ContextSection(
                    "building_program",
                    "Accepted upstream BuildingProgram",
                    to_primitive(building),
                ),
                ContextSection(
                    "room_function_catalog",
                    "Allowed room functions for every building function",
                    {key: list(value) for key, value in ROOM_FUNCTIONS.items()},
                ),
                ContextSection(
                    "space_program_guidance",
                    "How reusable floor roles should become bounded semantic space programs",
                    {
                        "required_roles": ["ground", "typical"],
                        "optional_roles": ["podium", "top"],
                        "ground": "public-facing, entrance, lobby, retail or service spaces; often fewer and larger",
                        "podium": "larger shared, commercial, amenity or service spaces",
                        "typical": "repeatable primary-use floor; may contain many residential rooms, offices, or shops",
                        "top": "executive, amenity, mechanical-support or premium spaces",
                        "residential": (
                            "Use unit_group_size to group consecutive rooms into dwelling units; "
                            "count rooms inside units rather than treating an entire apartment as one room. "
                            "A typical multi-unit floor commonly needs materially more rooms than units."
                        ),
                        "commercial": (
                            "Distinguish office/meeting/support spaces or shop/service spaces; "
                            "do not force every commercial floor to have the same density. Large open-plan "
                            "zones may have larger target areas than enclosed offices or shops."
                        ),
                        "count_rule": (
                            "Predict min/preferred/max counts from function and role. "
                            "The compiler will adapt preferred count to the realized floor plate area."
                        ),
                    },
                ),
            ),
        )
        space_prompt = self._base_prompt(
            "Floor Space Programming",
            "FloorSpaceProgram has profiles. Include every zone function in profile_cardinality_contract exactly once, "
            "including shell-only functions without selected interiors. Each profile has an exact function and "
            "archetypes. Every archetype has role, preferred_room_count, min_room_count, "
            "max_room_count, target_room_area_m2, min_room_width_m, max_room_depth_m, "
            "max_room_aspect_ratio, layout_template, room_function_cycle, "
            "and unit_group_size. Provide ground and typical once for every function; "
            "podium and top are optional. Counts must satisfy min <= preferred <= max. "
            "When room_count_contract.mode is adaptive, derive counts from function, role, "
            "target area, and the estimated floor-plate range without anchoring to a global "
            "default. When it is fixed, every archetype must set min, preferred, and max "
            "to exact_room_count. Every room function must come from the "
            "disclosed function catalog."
            " At this city-profile stage output only compact ground and typical archetypes. "
            "Omit optional spatial_program, podium and top until actual floor geometry exists: "
            "the Building-specific Floor Agent will generate their individualized spatial programs. "
            "Do not expand repeated apartments or every room instance into this shared profile. "
            "Preserve functional counts/cycles and geometry constraints rather than equal-area room lists."
        )

        def parse_space(data: dict[str, Any]) -> FloorSpaceProgram:
            data = self._unwrap_floor_program(
                data, "FloorSpaceProgram", "floor_space_program"
            )
            program = FloorSpaceProgram.from_dict(data)
            program.validate(spec)
            return program

        space_result = self._run(space_context, space_prompt, parse_space)

        layout_context = ProgressiveContext(
            summary={
                "interior_requirements": spec.interior_requirements,
                **({'prototype_priors': prototype_context} if prototype_context else {}),
                "functions": functions,
                "profile_cardinality_contract":{
                    "exact_count":len(functions),"exact_function_ids":functions,
                    "key":"unique zone FUNCTION, not district name or floor role",
                    "per_building_personalization":"later Building-specific Floor Agent"},
                "supported": {
                    "layout": sorted(FLOOR_LAYOUTS),
                    "corridor_ratio_range": [0.12, 0.30],
                },
            },
            sections=(
                ContextSection(
                    "building_program",
                    "Accepted upstream BuildingProgram",
                    to_primitive(building),
                ),
                ContextSection(
                    "space_program",
                    "Accepted FloorSpaceProgram whose counts and semantic cycles must be preserved",
                    to_primitive(space_result.program),
                ),
                ContextSection(
                    "layout_constraints",
                    "Deterministic geometry rules for the supported layout",
                    {
                        "double_loaded_corridor": {
                            "corridor_axis": "east_west",
                            "rooms": "split across north and south sides",
                            "all_room_doors_connect_to_corridor": True,
                            "vertical_connector_inside_corridor": True,
                        },
                        "semantic_templates": {
                            "residential_units": "dwelling-unit groups around an aligned core",
                            "office_core": "open and enclosed office zones around a service core",
                            "commercial_retail": "street-facing retail bays with rear support spaces",
                            "podium_core": "larger public floor plate around a shared service core",
                            "tower_core": "compact repeatable upper-floor plate around a vertical core",
                            "open_plan": "preserved large open zone plus enclosed support spaces",
                        },
                    },
                ),
            ),
        )
        layout_prompt = self._base_prompt(
            "Floor Layout",
            "FloorProgram has profiles. Each profile has function, layout, corridor_ratio, "
            "and room_function_cycle (a flat JSON array of strings, NEVER a dictionary "
            "keyed by ground/typical; e.g. [\"office\",\"meeting_room\"]). "
            "Cover every exact function once. Choose a safe layout and circulation ratio. "
            "Read profile_cardinality_contract: districts sharing commercial still need ONE "
            "commercial profile, with retail/office differences in ground/typical cycles and "
            "later building-specific plans. Never duplicate function profiles by district. "
            "room_function_cycle is a legacy fallback: use the accepted typical archetype's "
            "flat cycle from space_program. Do not repeat space_archetypes; "
            "the coordinator attaches the accepted space program after validation."
        )

        def parse_layout(data: dict[str, Any]) -> FloorProgram:
            data = self._unwrap_floor_program(data, "FloorProgram", "floor_program")
            program = FloorProgram.from_dict(data)
            program.validate(spec)
            return program

        layout_result = self._run(layout_context, layout_prompt, parse_layout)
        profiles = tuple(
            replace(
                profile,
                space_archetypes=space_result.program.for_function(
                    profile.function
                ).archetypes,
            )
            for profile in layout_result.program.profiles
        )
        program = FloorProgram(profiles)
        program.validate(spec)
        return HierarchyAgentResult(
            self.name,
            program,
            self.model_id,
            space_result.attempts + layout_result.attempts,
            space_result.disclosures + layout_result.disclosures,
        )

    @staticmethod
    def _unwrap_floor_program(
        data: dict[str, Any], *wrapper_keys: str
    ) -> dict[str, Any]:
        """Accept a harmless named root emitted by otherwise valid local models."""

        if len(data) != 1:
            return data
        key = next(iter(data))
        nested = data[key]
        if key in wrapper_keys and isinstance(nested, dict):
            return nested
        return data


class AppearanceAgent(_ProgressiveProgramAgent[UrbanAppearanceProgram]):
    """Choose bounded city appearance profiles, never object coordinates."""

    name = "appearance"

    def plan(
        self,
        spec: CitySpec,
        urban: UrbanProgram,
        building: BuildingProgram,
    ) -> HierarchyAgentResult[UrbanAppearanceProgram]:
        defaults = default_urban_appearance_program()
        context = ProgressiveContext(
            summary={
                "interior_requirements": spec.interior_requirements,
                "city_name": spec.name,
                "extent_m": [spec.width_m, spec.depth_m],
                "building_count": spec.building_count,
                "functions": sorted({zone.function for zone in spec.zones}),
                "road_pattern": urban.road_pattern,
                "open_space_ratio": spec.open_space_ratio,
                "supported": {
                    "road_classes": ["collector", "local", "service", "shared_space"],
                    "landscape_styles": ["park", "garden", "plaza"],
                    "time_of_day": ["day", "evening", "overcast"],
                    "vehicle_types": ["sedan", "suv", "van", "bus"],
                    "pedestrian_states": ["walk", "stand", "cycle"],
                },
            },
            sections=(
                ContextSection(
                    "upstream_programs",
                    "Accepted urban and building profiles",
                    {"urban": to_primitive(urban), "building": to_primitive(building)},
                ),
                ContextSection(
                    "safe_defaults",
                    "Complete conservative appearance program that may be adapted",
                    defaults.to_dict(),
                ),
                ContextSection(
                    "placement_contract",
                    "Hard constraints enforced after this style decision",
                    {
                        "vehicles": "lane-bound and junction-clear",
                        "pedestrians": "sidewalk/path-bound",
                        "trees": "sidewalk furniture strip and entrance-clear",
                        "coordinates": "owned exclusively by deterministic compiler",
                    },
                ),
            ),
        )
        prompt = self._base_prompt(
            "Urban Appearance",
            "UrbanAppearanceProgram fields are version, time_of_day, road_profiles, "
            "landscape_profiles, vehicle_mix, and pedestrian_mix. Return profiles for "
            "collector, local, service, shared_space and park, garden, plaza. Adapt "
            "density and style to function and scale, but never emit coordinates, IDs, "
            "meshes, or unconstrained object counts. All spacings must be positive and "
            "parking_ratio must remain within [0,1].",
        )

        def parse(data: dict[str, Any]) -> UrbanAppearanceProgram:
            program = UrbanAppearanceProgram.from_dict(data)
            if program.time_of_day not in {"day", "evening", "overcast"}:
                raise ValueError("unsupported appearance time_of_day")
            if not program.vehicle_mix or not program.pedestrian_mix:
                raise ValueError("appearance population mixes must not be empty")
            return program

        return self._run(context, prompt, parse)


class HierarchicalPlanningAgent:
    """Run four bounded agents and return one validated hierarchy program."""

    def __init__(
        self,
        service: TextReasoningService,
        *,
        model_id: str = "unknown",
        max_calls_per_agent: int = 4,
        enable_appearance_agent: bool = False,
    ) -> None:
        kwargs = {
            "model_id": model_id,
            "max_calls": max_calls_per_agent,
        }
        self.urban_agent = UrbanAgent(service, **kwargs)
        self.skyline_agent = SkylineAgent(service, **kwargs)
        self.building_agent = BuildingAgent(service, **kwargs)
        self.floor_agent = FloorAgent(service, **kwargs)
        self.appearance_agent = AppearanceAgent(service, **kwargs)
        self.enable_appearance_agent = enable_appearance_agent

    def plan(self, spec: CitySpec) -> HierarchicalPlanningResult:
        urban = self.urban_agent.plan(spec)
        skyline = self.skyline_agent.plan(spec, urban.program)
        building = self.building_agent.plan(
            spec, urban.program, skyline.program
        )
        floor = self.floor_agent.plan(spec, building.program)
        appearance = (
            self.appearance_agent.plan(spec, urban.program, building.program)
            if self.enable_appearance_agent
            else None
        )
        program = HierarchicalProgram(
            urban.program, building.program, floor.program, skyline.program
        )
        program.validate(spec)
        return HierarchicalPlanningResult(program, urban, skyline, building, floor, appearance)
