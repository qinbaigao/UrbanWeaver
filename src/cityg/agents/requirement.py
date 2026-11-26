"""Natural-language requirement to validated CitySpec conversion."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Sequence

from cityg.schemas import CitySpec
from cityg.architecture import ARCHITECTURE_SCHEMA, DESIGN_LANGUAGES
from cityg.morphology import MORPHOLOGY_SCHEMA
from cityg.urban_requirements import response_schema as urban_schema
from cityg.agents.requirement_contracts import explicit_contract, check_explicit_contract, constrained_response_schema
from cityg.serialization import to_primitive
from cityg.services.interfaces import ChatMessage, TextReasoningService


SUPPORTED_FUNCTIONS = (
    "residential",
    "commercial",
    "public_service",
    "industrial",
    "mixed_use",
)


CITY_SPEC_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string"},
        "width_m": {"type": "number"},
        "depth_m": {"type": "number"},
        "building_count": {"type": "integer"},
        "min_floors": {"type": "integer"},
        "max_floors": {"type": "integer"},
        "rooms_per_floor": {"type": "integer"},
        "room_count_strategy": {
            "type": "string",
            "enum": ["adaptive", "fixed"],
        },
        "road_width_m": {"type": "number"},
        "sidewalk_width_m": {"type": "number"},
        "parcel_setback_m": {"type": "number"},
        "layout_style": {
            "type": "string",
            "enum": ["regular_grid", "organic_grid"],
        },
        "open_space_ratio": {"type": "number"},
        "layout_irregularity": {"type": "number"},
        "road_pattern": {
            "type": "string",
            "enum": ["connected_grid", "organic_hierarchy", "curved_hierarchy", "landscape_adaptive"],
        },
        "buildings_per_block": {"type": "integer"},
        "branch_road_ratio": {"type": "number"},
        "parcel_layout": {"type": "string", "enum": ["rectangular", "polygonal"]},
        "river_mode": {"type": "string", "enum": ["none", "meandering"]},
        "river_width_m": {"type": "number", "minimum": 4},
        "river_bank_width_m": {"type": "number", "minimum": 2},
        "river_setback_m": {"type": "number", "minimum": 3},
        "morphology": MORPHOLOGY_SCHEMA,
        "urban_requirements": urban_schema(),
        "height_strategy": {
            "type": "string",
            "enum": ["uniform_random", "zoned_skyline"],
        },
        "highrise_ratio": {"type": "number"},
        "landmark_count": {"type": "integer"},
        "skyline_strength": {"type": "number"},
        "seed": {"type": "integer"},
        "architecture": ARCHITECTURE_SCHEMA,
        "zones": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "function": {"type": "string", "enum": list(SUPPORTED_FUNCTIONS)},
                    "weight": {"type": "number"},
                    "architecture": ARCHITECTURE_SCHEMA,
                },
                "required": ["name", "function", "weight"],
            },
        },
    },
    "required": [
        "name",
        "width_m",
        "depth_m",
        "building_count",
        "min_floors",
        "max_floors",
        "rooms_per_floor",
        "road_width_m",
        "sidewalk_width_m",
        "parcel_setback_m",
        "seed",
        "zones",
        "urban_requirements",
        "road_pattern",
        "layout_style",
    ],
}


@dataclass(frozen=True)
class RequirementPolicy:
    """Conservative Phase 3 bounds for city-scale experiments."""

    min_extent_m: float = 100.0
    max_extent_m: float = 2000.0
    min_buildings: int = 1
    max_buildings: int = 200
    max_floors: int = 30
    max_rooms_per_floor: int = 20
    max_zones: int = 6

    def validate(self, spec: CitySpec) -> None:
        if not self.min_extent_m <= spec.width_m <= self.max_extent_m:
            raise ValueError(
                f"width_m must be within [{self.min_extent_m}, {self.max_extent_m}]"
            )
        if not self.min_extent_m <= spec.depth_m <= self.max_extent_m:
            raise ValueError(
                f"depth_m must be within [{self.min_extent_m}, {self.max_extent_m}]"
            )
        if not self.min_buildings <= spec.building_count <= self.max_buildings:
            raise ValueError(
                f"building_count must be within [{self.min_buildings}, {self.max_buildings}]"
            )
        if spec.max_floors > self.max_floors:
            raise ValueError(f"max_floors must not exceed {self.max_floors}")
        if spec.rooms_per_floor > self.max_rooms_per_floor:
            raise ValueError(
                f"rooms_per_floor must not exceed {self.max_rooms_per_floor}"
            )
        if len(spec.zones) > self.max_zones:
            raise ValueError(f"zone count must not exceed {self.max_zones}")
        unsupported = sorted(
            {zone.function for zone in spec.zones} - set(SUPPORTED_FUNCTIONS)
        )
        if unsupported:
            raise ValueError(f"unsupported zone functions: {', '.join(unsupported)}")


@dataclass(frozen=True)
class AgentAttempt:
    index: int
    prompt_hash: str
    messages: tuple[dict[str, str], ...]
    raw_output: str
    elapsed_s: float
    error: str | None = None
    finish_reason: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RequirementResult:
    spec: CitySpec
    model_id: str
    attempts: tuple[AgentAttempt, ...]

    def trace_dict(self) -> dict[str, Any]:
        return {
            "agent": "requirement",
            "model_id": self.model_id,
            "accepted_attempt": len(self.attempts),
            "spec": to_primitive(self.spec),
            "attempts": [asdict(attempt) for attempt in self.attempts],
        }


class AgentGenerationError(RuntimeError):
    def __init__(self, message: str, attempts: Sequence[AgentAttempt]) -> None:
        super().__init__(message)
        self.attempts = tuple(attempts)


class RequirementAgent:
    """Parse requirements with bounded retries; deterministic code accepts output."""

    def __init__(
        self,
        service: TextReasoningService,
        *,
        model_id: str = "unknown",
        policy: RequirementPolicy | None = None,
        max_attempts: int = 3,
        exterior_only: bool = False,
        separate_interiors: bool = False,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.service = service
        self.model_id = model_id
        self.policy = policy or RequirementPolicy()
        self.max_attempts = max_attempts
        self.exterior_only = exterior_only
        self.separate_interiors = separate_interiors

    def parse(self, requirement: str, *, reference_context: dict | None = None) -> RequirementResult:
        if not requirement.strip():
            raise ValueError("Requirement text must not be empty")
        contract = explicit_contract(requirement)
        interior_rows = None
        interior_attempts = ()
        if self.separate_interiors and not self.exterior_only:
            from cityg.agents.interior_requirement import InteriorRequirementAgent
            interior_rows, interior_attempts = InteriorRequirementAgent(
                self.service, self.max_attempts).extract(requirement)
        from copy import deepcopy
        from cityg.interior_requirements import response_schema as interior_schema
        base_schema = deepcopy(CITY_SPEC_RESPONSE_SCHEMA)
        if interior_rows is None:
            base_schema["properties"]["interior_requirements"] = interior_schema()
            base_schema["required"].append("interior_requirements")
        response_schema = constrained_response_schema(base_schema, contract)
        from cityg.inventory_provenance import ground_extraction_schema, deduplicate_identical_inventory
        if interior_rows is None:
            response_schema=ground_extraction_schema(response_schema,requirement)
        urban_clauses = None
        if interior_rows:
            from cityg.agents.urban_scope import urban_scope
            urban_clauses, scope_trace = urban_scope(requirement, self.service)
            interior_attempts = (*interior_attempts, scope_trace)
            if urban_clauses == []:
                response_schema['properties'].pop('urban_requirements')
                response_schema['required'].remove('urban_requirements')
        system_prompt=self._system_prompt()
        if interior_rows is not None:
            urban_prompt = system_prompt[system_prompt.index('Preserve urban spatial demands'):
                                         system_prompt.index('Use an exact source_quote')]
            start=system_prompt.index('Preserve explicit building-specific interior area')
            end=system_prompt.index('road_width_m should normally')
            system_prompt=system_prompt[:start]+(
                'Interior requirements have been extracted and reviewed separately. Do not output interior_requirements '
                'or furniture. Include carrier zones for these required building functions: '+
                json.dumps(sorted({r['building_function'] for r in interior_rows}))+'. '
                'Omit irrelevant optional fields; do not fill unused river parameters with zero, or include morphology '
                'unless road_pattern is landscape_adaptive. ')+urban_prompt+system_prompt[end:]
        if urban_clauses is not None:
            system_prompt += (' Spatial relation evidence selected from the original brief: '+
                              json.dumps(urban_clauses,ensure_ascii=False)+
                              '. Use [] when empty. Interior building A/B labels, floor areas, park presence and '
                              'generic access do not imply geographic thresholds or half-plane assignments.')
        if urban_clauses == []:
            system_prompt += ' The spatial review found no urban relations. Omit urban_requirements from your response.'
        from cityg.walking_requirements import route_clauses, response_schema as walking_schema
        walking = route_clauses(requirement)
        walking_rows = None
        if walking and interior_rows is not None:
            from cityg.agents.walking_requirement import extract_walks
            try:
                walking_rows, walk_attempts = extract_walks(self.service, walking, interior_rows, self.max_attempts)
            except AgentGenerationError as exc:
                raise AgentGenerationError(str(exc), (*interior_attempts,*exc.attempts)) from exc
            interior_attempts = (*interior_attempts, *walk_attempts)
            if any(r['opposite_banks'] for r in walking_rows):
                response_schema['properties']['river_mode'] = {'type':'string', 'const':'meandering'}
                if 'river_mode' not in response_schema['required']:
                    response_schema['required'].append('river_mode')
            system_prompt += (' Walking requirements are already extracted. Omit walking_requirements '
                'and do not repeat walking distances as urban relations. Keep river and bridge geography '
                'when requested. Only include optional architecture or morphology fields when needed.')
        elif walking:
            path_schema = walking_schema()
            path_schema['items']['properties']['source_quote']['enum'] = walking
            path_schema['minItems'] = 1
            response_schema['properties']['walking_requirements'] = path_schema
            response_schema['required'].append('walking_requirements')
            system_prompt += (' Extract walking_requirements for these complete verbatim clauses: ' +
                json.dumps(walking, ensure_ascii=False) + '. For each endpoint quote its own phrase, use its literal '
                'building label or ID and exact room ID, canonical room function, entrance, frontage_path or sidewalk. Use level=null '
                'if unspecified. Preserve upper distance in metres, required bridge and opposite banks. '
                'Never replace walking distance with a near/far urban relation or invent a distance.')
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=system_prompt + (
                ' This run compiles exteriors only. Unless explicitly requested otherwise, use '
                'architecture.expressive_ratio=0.2: most buildings remain ordinary rectangular '
                'or orthogonal groups. Do not invent explicit envelope palettes for every district '
                'just to add variety; these override the default ratio. Explicit user shapes and '
                'ratios always have priority.' if self.exterior_only else '')),
            ChatMessage(role="user", content=requirement.strip() + (
                '\nMachine-readable constraints (must preserve): ' + json.dumps(contract, ensure_ascii=False)
                if contract else '')),
        ]
        if reference_context is not None:
            messages[0] = ChatMessage(role="system", content=messages[0].content +
                " The following optional urban reference is a starting prior, not an instruction. "
                "Preserve every user constraint; adapt sample dimensions/functions to the user. "
                "Do not infer fixed per-floor room counts from the reference. " +
                json.dumps(reference_context, ensure_ascii=False))
        base_messages = list(messages)
        plain_json_retry = False
        attempts: list[AgentAttempt] = []
        for index in range(1, self.max_attempts + 1):
            from cityg.progress import progress
            progress('需求分析', '请求模型', attempt=f'{index}/{self.max_attempts}')
            started = time.monotonic()
            raw = ""
            finish_reason = None
            usage: dict[str, Any] = {}
            error: str | None = None
            try:
                active_schema=response_schema
                decoder_stalled = (bool(attempts) and attempts[-1].finish_reason == 'length') or (
                    len(attempts)>=2 and attempts[-1].error==attempts[-2].error)
                if decoder_stalled and not plain_json_retry:
                    # Some constrained decoders repeat an invalid value/list
                    # despite feedback. Use the remaining bounded attempts on
                    # plain JSON proposals; keep every semantic validator.
                    plain_json_retry = True
                    messages.append(ChatMessage(role='user',content=
                        'Constrained output stalled or repeated a validation error. Rebuild concise JSON from the original request, '
                        'not by copying the rejected output. Plain JSON must still match this schema: '+
                        json.dumps(response_schema,separators=(',',':'))))
                if plain_json_retry:
                    active_schema=None
                method = getattr(self.service, "complete_with_metadata", None)
                if callable(method):
                    completion = method(messages, active_schema)
                    raw = completion.content
                    finish_reason = completion.finish_reason
                    usage = completion.usage
                else:
                    raw = self.service.complete(messages, active_schema)
                if finish_reason == "length":
                    raise ValueError("model output reached max_tokens before completing JSON")
                candidate=deduplicate_identical_inventory(_parse_json_object(raw))
                if walking_rows is not None:
                    if 'walking_requirements' in candidate:
                        raise ValueError('Walking requirements already extracted. Omit that field.')
                    candidate['walking_requirements'] = walking_rows
                if interior_rows is not None:
                    if 'interior_requirements' in candidate:
                        raise ValueError('City stage must omit interior_requirements; it cannot overwrite the reviewed ledger')
                    candidate['interior_requirements']=interior_rows
                if urban_clauses == []:
                    # A separate stage owns this empty ledger, including during plain JSON retries.
                    candidate['urban_requirements'] = []
                elif urban_clauses is not None:
                    for row in candidate.get('urban_requirements', []):
                        quote = row.get('source_quote') if isinstance(row,dict) else None
                        if not quote or not any(quote in s for s in urban_clauses):
                            raise ValueError('Urban relation must cite a selected spatial clause; use [] if empty')
                if interior_rows is None and isinstance(candidate.get('interior_requirements'), list):
                    from cityg.agents.building_uses import ground_named_uses
                    ground_named_uses(candidate['interior_requirements'], requirement)
                spec = CitySpec.from_dict(candidate)
                from cityg.walking_requirements import validate as validate_walks
                validate_walks(spec.walking_requirements, requirement)
                for walk in spec.walking_requirements:
                    if any(rel['relation'] in ('near','far','served_by')
                           and rel['source_quote'] in walk['source_quote']
                           and rel['threshold'] == walk['max_distance_m']
                           and not any(word in rel['source_quote'].lower() for word in ('直线','straight-line','euclidean'))
                           for rel in spec.urban_requirements):
                        raise ValueError('Use walking_requirements for route distances; omit duplicate planar distance rows')
                self.policy.validate(spec)
                from cityg.interior_requirements import validate_requirements
                validate_requirements(spec.interior_requirements, instruction=requirement)
                from cityg.urban_requirements import validate as validate_urban
                validate_urban(spec.urban_requirements, spec=spec, instruction=requirement)
                missing_types = {r['building_function'] for r in spec.interior_requirements} - {z.function for z in spec.zones}
                if missing_types:
                    raise ValueError(f'Interior requirements lack carrier building types in zones: {sorted(missing_types)}. '
                                     'Include zones with these exact functions; mixed_use does not automatically create commercial buildings.')
                check_explicit_contract(to_primitive(spec), contract)
                if self.exterior_only and 'expressive_ratio' not in spec.architecture:
                    spec = replace(spec, architecture={**spec.architecture, 'expressive_ratio': .2})
            except (TypeError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
                error = f"{type(exc).__name__}: {exc}"
                progress('需求分析', '输出未通过校验；预算内重试，否则失败', error_type=type(exc).__name__)
            elapsed = time.monotonic() - started
            serialized_messages = tuple(
                {"role": item.role, "content": item.content} for item in messages
            )
            prompt_bytes = json.dumps(
                serialized_messages, sort_keys=True, ensure_ascii=False
            ).encode("utf-8")
            attempts.append(
                AgentAttempt(
                    index=index,
                    prompt_hash=hashlib.sha256(prompt_bytes).hexdigest(),
                    messages=serialized_messages,
                    raw_output=raw,
                    elapsed_s=round(elapsed, 6),
                    error=error,
                    finish_reason=finish_reason,
                    usage=usage,
                )
            )
            if error is None:
                combined=tuple(replace(a,index=i+1) for i,a in enumerate([*interior_attempts,*attempts]))
                return RequirementResult(spec, self.model_id, combined)
            if index < self.max_attempts:
                if finish_reason == 'length':
                    # Preserve the full rejected output in the trace, but do
                    # not prime the next response with a long repetitive list.
                    messages=list(base_messages)
                    plain_json_retry=False
                    messages.append(ChatMessage(role='user',content=
                        f'The previous candidate was rejected: {error}. Output one concise complete object; '
                        'do not repeat inventory rows. Keep every distinct requested function and item.'))
                    continue
                messages.extend(
                    [
                        ChatMessage(role="assistant", content=raw),
                        ChatMessage(
                            role="user",
                            content=(
                                "The candidate was rejected by deterministic validation: "
                                f"{error}. Return a corrected complete JSON object."
                            ),
                        ),
                    ]
                )
        raise AgentGenerationError(
            f"Requirement agent failed after {self.max_attempts} city attempts",
            tuple(replace(a,index=i+1) for i,a in enumerate([*interior_attempts,*attempts]))
        )

    def _system_prompt(self) -> str:
        from cityg.planning.baseline import ROOM_FUNCTIONS
        return (
            "You are CityG's requirement agent. Convert the user's request into one "
            "finite CitySpec JSON object. Never write prose. Use meters. Required bounds: "
            f"width/depth {self.policy.min_extent_m}-{self.policy.max_extent_m}; "
            f"buildings {self.policy.min_buildings}-{self.policy.max_buildings}; "
            f"floors 1-{self.policy.max_floors}; rooms_per_floor 1-"
            f"{self.policy.max_rooms_per_floor}; at most {self.policy.max_zones} zones. "
            "If the user explicitly specifies a building, floor, or zone count, preserve "
            "that number exactly. Set room_count_strategy=fixed only when the user explicitly "
            "requires an exact per-floor room count; otherwise set it to adaptive and treat "
            "rooms_per_floor as a conservative fallback hint for the downstream Floor Agent. "
            "Preserve explicit building-specific interior area, functions and inventory in interior_requirements. "
            "Preserve urban spatial demands in urban_requirements: north_half, south_half, east_half, west_half, near, far, "
            "served_by (EVERY subject has some target within threshold), min_footprint_area. "
            "Each row has EXACTLY id, source_quote, subject, relation, target, threshold, strength, reason. "
            "There is no half_plane relation and no direction field. For north use relation=north_half. "
            "Selectors are zone:<exact zone name>, function:<function>, building:<supplied existing ID>; "
            "A subject MUST select buildings, never river or road. River shape/width/bank/setback belong only "
            "in CitySpec river fields, not in urban_requirements. For a zone named Shops with function commercial, "
            "use zone:Shops or function:commercial, NEVER function:shops. "
            "distance targets also allow river (water edge) and road (road/sidewalk edge). "
            "All distances use building centres in metres, not walking distance; area is m2. "
            "min_footprint_area measures the canonical building footprint rectangle (planning envelope), "
            "not usable/net floor area or the exact occupied polygon of an irregular shell. "
            "Half-plane and area rules have null target; half-plane rules have null threshold. "
            "Use separate named zones for school, hospital or service facilities sharing public_service. "
            "Quote the user's exact words in source_quote and explain interpretation in reason. "
            "Unnumbered 'near/away' targets must be soft: choose and explain a design distance, never "
            "invent a hard user threshold. Explicit numerical limits and directions may be hard. "
            "Example: shops preferably near water -> subject=zone:Shops, relation=near, target=river, "
            "threshold=60, strength=soft; quote the user's preference and explain the design distance. "
            "Never resolve an ambiguous demonstrative to an invented building ID. Always return urban_requirements; "
            "use [] ONLY if there are no supported spatial/footprint requirements. Check each user sentence for "
            "directions, service distances and footprint minima before returning. Building footprint area is "
            "min_footprint_area, NOT an interior floor area: do not invent interior functions from a footprint request. "
            "Preserve explicitly named road_pattern and layout_style values instead of substituting defaults. "
            "Omit morphology unless road_pattern=landscape_adaptive. When river_mode=none, omit unused river "
            "dimensions instead of assigning zero. Return only the instance, never its JSON schema or reasoning. "
            "Use an exact source_quote, the user building label (A/B/name), building_id=null unless supplied, "
            "and zero-based levels (ground/first floor=0). Repeated requirements for one building use the SAME label. "
            "Use ONE combined requirement per building and set of levels, not one row per furniture item/activity. "
            "Its source_quote includes the FULL exact passage about that building, including area and furnishings. "
            "Each room_function/category pair occurs ONCE in its inventory; never repeat rows to represent quantities. "
            "Include only explicitly requested functions and furniture minimum counts, never invented inventory. "
            "Counts apply across rooms of that function on EACH specified floor, not to every room. "
            "An unnumbered requested item has minimum 1; repeated seating requires explicit count. "
            "Use the enclosing building-specific source_quote as inventory evidence. Use count_basis=presence and min_count=1 "
            "for unnumbered plurals too; desired capacity is planned later, not fabricated as a user minimum. "
            "Use explicit_number only for that furniture's number actually stated in the building quote (e.g. seating for six). "
            "Capture ALL explicitly requested furniture roles, including service/checkout surfaces and storage. "
            "A cafe service counter maps to checkout_counter; preparation surface maps to kitchen_counter; "
            "meeting seating maps to meeting_chair, office desk seating to office_chair. "
            "Map supported functions semantically: office buildings use commercial, apartments use residential. "
            "In a commercial cafe use break_room for customer dining and service/preparation, reception for waiting, "
            "storage for a separately requested storage room. Dining in a dwelling may share kitchen or living_room. "
            "Do not invent separate rooms for every furniture item or every activity; open functional areas may share a room. "
            "area_m2=null if not specified. area_basis=floor_gross for floor area, rooms_net only for explicit "
            "net room area, building_gross only for the whole building. Never convert these meanings. "
            "An approximately N square meter ground floor means floor_gross, NOT rooms_net. "
            "Keep all target building functions represented in zones. No specific interior requirements: []. "
            f"Supported room functions by building function: {json.dumps(ROOM_FUNCTIONS)}. "
            "road_width_m should normally be 8-20, sidewalk_width_m 1.5-5, and "
            "parcel_setback_m 2-10. Zone weights must be positive and functions must "
            f"come from: {', '.join(SUPPORTED_FUNCTIONS)}. If unspecified, choose "
            "conservative realistic values. Optional layout controls are layout_style "
            "(regular_grid or organic_grid), open_space_ratio 0-0.35, and "
            "layout_irregularity 0-1. Optional urban controls are road_pattern "
            "(connected_grid, organic_hierarchy, curved_hierarchy or landscape_adaptive), buildings_per_block 1-4, and "
            "curved_hierarchy adds gentle curved secondary streets only in reserved unbuilt blocks; "
            "For independent meandering rivers and mostly straight streets choose landscape_adaptive: "
            "only bank collectors curve; staggered straight local streets form T junctions and oblique plots. "
            "It never warps the whole city along the river. morphology optionally sets river_amplitude_ratio "
            ".03-.14 (default .10 of city width), river_cycles .5-1.5 (default 1), "
            "road_warp_ratio .01-.06 (default .035, legacy key now controlling straight local street skew, "
            "not global deformation). It is a bounded street grammar, not free-topology urban design. "
            "Prefer branch_road_ratio=0 in this mode until a feasible primary river crossing layout is established. "
            "For riverfront cities choose river_mode=meandering and parcel_layout=polygonal; "
            "river_width_m, river_bank_width_m and river_setback_m control water, banks and land reservation. "
            "The geometry planner determines exact curves, parcel boundaries and bridge spans. "
            "branch_road_ratio 0-1. Prefer organic_grid and organic_hierarchy for "
            "realistic scenes. Optional skyline controls are height_strategy "
            "(zoned_skyline or uniform_random), highrise_ratio 0-0.5, "
            "landmark_count 0-10, and skyline_strength 0-1. Prefer zoned_skyline "
            "unless the user requests an ablation. The downstream Skyline Agent will "
            "personalize functional height bands inside min_floors/max_floors. "
            "Architecture is an optional object: region, era, climate, district_character, "
            "design_languages, material_palette (brick, plaster, stone, metal, glass). "
            "Preserve explicit material requests such as brick walls in material_palette, "
            "not just a district name. Leave unspecified geographic identifiers empty; do not "
            "invent a country/city when only climate is specified. "
            "Preserve user-specified geographic/period intent; do not assign "
            "a stereotyped national style or claim historical authenticity. A zone may override "
            "architecture for old districts vs new development, even with the same function. "
            "Choose 2-4 compatible design_languages when diversity is requested, or one for an "
            "explicitly uniform ensemble. The supported facade grammars are "
            f"{DESIGN_LANGUAGES}. These control openings/articulation, not historical roofs. "
            "Optional architecture.envelope enables EXTERIOR-ONLY loft geometry: shape rectangle, "
            "chamfered, trapezoid, hexagon, ellipse; profile straight, taper or lean; "
            "facade_system punched or curtain_wall. top_scale .55-1 is only for taper; "
            "lean_x/lean_y are footprint fractions in -0.18..0.18 only for lean. "
            "Use it only for explicit exterior-only requests, with district overrides for variety. "
            "For multiple shapes WITHIN one district use architecture.envelope_palette, a list of "
            "1-8 complete envelope configurations distributed evenly; repeated entries express higher "
            "frequency. Do not combine envelope and envelope_palette in the same architecture object. "
            "Retain ordinary rectangular forms as appropriate; use nonrectangular forms in selected "
            "locations. For exterior-only scenes architecture.expressive_ratio (0..1) budgets "
            "nonrectangular/sloping envelopes, default 0.2 unless otherwise requested. Explicit "
            "envelope/envelope_palette overrides this ratio. Orthogonal L/U/courtyard groups remain ordinary. "
            "Use nonrectangular forms in selected "
            "waterfront/civic/gateway districts. Preserve explicit JSON shape contracts exactly. "
            "Do not imply support for interiors, twist, ornate/pitched roofs or arbitrary freeform surfaces. "
            "Keep every number short and finite."
        )


def _parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        start = stripped.find("{")
        if start < 0:
            raise ValueError("model output contains no JSON object")
        value, _ = decoder.raw_decode(stripped[start:])
    if not isinstance(value, dict):
        raise ValueError("model output must be a JSON object")
    return value
