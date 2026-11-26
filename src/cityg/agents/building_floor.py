"""Building-specific floor programming after deterministic footprints exist."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from cityg.agents.hierarchy import (
    HierarchyAgentResult,
    _ProgressiveProgramAgent,
)
from cityg.agents.context import ContextSection, ProgressiveContext
from cityg.agents.requirement import AgentGenerationError, _parse_json_object
from cityg.planning.baseline import ROOM_FUNCTIONS
from cityg.planning.highrise import HighRisePolicy
from cityg.planning.programs import (
    DEFAULT_ROOM_MAX_ASPECT_RATIO,
    DEFAULT_ROOM_MAX_DEPTH_M,
    FLOOR_LAYOUTS,
    FLOOR_ROLES,
    VERTICAL_USE_TYPES,
    FloorProfile,
)
from cityg.schemas import Building, City, CitySpec
from cityg.serialization import to_primitive
from cityg.planning.spatial_program import SPATIAL_PROGRAM_GUIDANCE


@dataclass(frozen=True)
class BuildingFloorProgram:
    """A floor profile specialized to one realized building footprint."""

    building_function: str
    profile: FloorProfile
    planning_mode: str = 'legacy_full_program'
    decision_receipt: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BuildingFloorProgram":
        # A few local instruct models add a harmless ``profile`` or named root.
        # The caller unwraps the named root; accepting ``profile`` here keeps the
        # inner contract tolerant without allowing arbitrary fields.
        if set(data) == {"profile"} and isinstance(data["profile"], dict):
            data = data["profile"]
        known = {
            "function",
            "building_function",
            "layout",
            "corridor_ratio",
            "room_function_cycle",
            "space_archetypes",
            "vertical_zones",
        }
        unknown = sorted(set(data) - known)
        if unknown:
            raise ValueError(
                f"Unknown BuildingFloorProgram fields: {', '.join(unknown)}"
            )
        function = str(data.get("building_function", data.get("function", "")))
        profile = FloorProfile.from_dict(
            {
                "function": str(data.get("function", function)),
                "layout": data["layout"],
                "corridor_ratio": data["corridor_ratio"],
                "room_function_cycle": data["room_function_cycle"],
                "space_archetypes": data["space_archetypes"],
                "vertical_zones": data.get("vertical_zones", []),
            }
        )
        return cls(building_function=function, profile=profile)

    def validate(self, building: Building) -> None:
        if self.building_function != building.function:
            raise ValueError(
                f"building-specific plan function {self.building_function} does not "
                f"match {building.function}"
            )
        if self.profile.function != building.function:
            raise ValueError(
                f"floor profile function {self.profile.function} does not match "
                f"{building.function}"
            )
        if self.profile.layout not in FLOOR_LAYOUTS:
            raise ValueError(f"unsupported floor layout: {self.profile.layout}")
        if not 0.12 <= self.profile.corridor_ratio <= 0.30:
            raise ValueError("corridor_ratio must be within [0.12, 0.30]")
        allowed = set(ROOM_FUNCTIONS.get(building.function, ROOM_FUNCTIONS["mixed_use"]))
        if not self.profile.room_function_cycle:
            raise ValueError("room_function_cycle must not be empty")
        unsupported = sorted(set(self.profile.room_function_cycle) - allowed)
        if unsupported:
            raise ValueError(
                f"unsupported room functions for {building.function}: {', '.join(unsupported)}"
            )
        roles = [item.role for item in self.profile.space_archetypes]
        if len(roles) != len(set(roles)) or not {"ground", "typical"}.issubset(roles):
            raise ValueError(
                "building-specific floor plan requires unique ground and typical roles"
            )
        for archetype in self.profile.space_archetypes:
            archetype.validate(building.function)
        zones = self.profile.vertical_zones
        if not zones:
            raise ValueError("building-specific floor plan requires vertical_zones")
        if len(zones) > min(12, len(building.floors)):
            raise ValueError("vertical zone count exceeds the building-specific limit")
        if zones[0].start_level != 0 or zones[0].role != "ground":
            raise ValueError("vertical zoning must begin with a ground zone at level 0")
        if zones[0].end_level != 0:
            raise ValueError("the ground vertical zone must contain only level 0")
        if zones[-1].end_level != len(building.floors) - 1:
            raise ValueError("vertical zoning must cover the building's highest level")
        if len(building.floors) > 1 and zones[-1].role != "top":
            raise ValueError("multi-floor vertical zoning must end with a top zone")
        if len(building.floors) >= 12 and not any(
            zone.role in {"amenity", "refuge", "service", "mechanical"}
            for zone in zones[1:-1]
        ):
            raise ValueError(
                "high-rise vertical zoning requires an interior amenity/refuge/service/mechanical band"
            )
        previous_end = -1
        for zone in zones:
            zone.validate(building.function)
            if zone.start_level != previous_end + 1:
                raise ValueError("vertical zones must be ordered, contiguous, and non-overlapping")
            if zone.end_level >= len(building.floors):
                raise ValueError("vertical zone exceeds the realized building floor count")
            previous_end = zone.end_level


@dataclass(frozen=True)
class BuildingFloorBatchResult:
    overrides: dict[str, FloorProfile]
    signatures: dict[str, str]
    cache_hits: dict[str, bool]
    traces: dict[str, HierarchyAgentResult[BuildingFloorProgram]]
    skipped_buildings: tuple[str, ...] = ()
    failed_buildings: dict[str, str] = field(default_factory=dict)
    failure_attempts: dict[str, tuple[Any, ...]] = field(default_factory=dict)

    @property
    def attempts(self) -> tuple:
        accepted = tuple(
            attempt
            for trace in self.traces.values()
            for attempt in trace.attempts
        )
        rejected = tuple(
            attempt
            for attempts in self.failure_attempts.values()
            for attempt in attempts
        )
        return accepted + rejected

    def program_dict(self) -> dict[str, Any]:
        return {
            "overrides": {
                building_id: to_primitive(profile)
                for building_id, profile in sorted(self.overrides.items())
            },
            "signatures": dict(sorted(self.signatures.items())),
            "cache_hits": dict(sorted(self.cache_hits.items())),
            "planning_modes": {key:self.traces[self.signatures[key]].program.planning_mode
                               for key in sorted(self.overrides)},
            "decision_receipts": {key:self.traces[self.signatures[key]].program.decision_receipt
                                  for key in sorted(self.overrides)},
            "skipped_buildings": list(self.skipped_buildings),
            "failed_buildings": dict(sorted(self.failed_buildings.items())),
        }

    def trace_dict(self) -> dict[str, Any]:
        return {
            "agent": "building_floor",
            "program": self.program_dict(),
            "traces": {
                key: value.trace_dict() for key, value in sorted(self.traces.items())
            },
            "failure_traces": {
                key: [to_primitive(attempt) for attempt in attempts]
                for key, attempts in sorted(self.failure_attempts.items())
            },
            "totals": {
                "model_calls": len(self.attempts),
                "cache_hits": sum(self.cache_hits.values()),
                "planned_buildings": len(self.overrides),
                "skipped_buildings": len(self.skipped_buildings),
                "failed_buildings": len(self.failed_buildings),
            },
        }


class BuildingFloorAgent(_ProgressiveProgramAgent[BuildingFloorProgram]):
    """Personalize a floor program after a concrete building footprint is known."""

    name = "building_floor"

    @staticmethod
    def _room_geometry_defaults(building_function: str) -> tuple[float, float]:
        """Return conservative defaults when a model omits geometry bounds."""

        return {
            "residential": (10.0, 2.6),
            "commercial": (14.0, 2.8),
            "public_service": (12.0, 2.6),
            "industrial": (18.0, 3.5),
            "mixed_use": (14.0, 2.8),
        }.get(
            building_function,
            (DEFAULT_ROOM_MAX_DEPTH_M, DEFAULT_ROOM_MAX_ASPECT_RATIO),
        )

    def plan(
        self,
        building: Building,
        base_profile: FloorProfile,
        spec: CitySpec,
        *, prototype_context: dict | None = None,
    ) -> HierarchyAgentResult[BuildingFloorProgram]:
        from cityg.planning.floor_brief import interior_capability, plan_semantic_brief
        if (building.metadata.get('interior_layout_contract')
                and interior_capability(building)['semantic_brief_supported']):
            return plan_semantic_brief(self, building, base_profile, spec, prototype_context)
        width = building.footprint.width
        depth = building.footprint.depth
        from cityg.planning.programmed import ProgrammedCityPlanner
        base_corridor = ProgrammedCityPlanner._corridor_depth(depth, base_profile.corridor_ratio)
        highrise = building.metadata.get("highrise", {})
        floor_plate_contract = HighRisePolicy.floor_plate_contract(
            building.footprint,
            len(building.floors),
            highrise.get("massing_variant"),
            orientation_deg=float(building.metadata.get("orientation_deg", 0.0)),
        )
        context = ProgressiveContext(
            summary={
                **({'prototype_priors': prototype_context} if prototype_context else {}),
                "building": {
                    "id": building.id,
                    "function": building.function,
                    "footprint_m": {
                        "width": round(width, 3),
                        "depth": round(depth, 3),
                        "area": round(building.footprint.area, 3),
                    },
                    "floor_count": len(building.floors),
                    "floor_levels": [floor.level for floor in building.floors],
                    "highrise": bool(building.metadata.get("highrise", {}).get("enabled")),
                    "prototype_id": building.metadata.get("prototype_id"),
                    "entrance_side": building.metadata.get("entrance_side"),
                    "orientation_deg": building.metadata.get("orientation_deg", 0.0),
                    "floor_plate_contract": floor_plate_contract,
                    "interior_layout_contract": building.metadata.get('interior_layout_contract'),
                    "single_spine_capacity_hint": {
                        "base_corridor_ratio": base_profile.corridor_ratio,
                        "base_corridor_depth_m": base_corridor,
                        "room_band_depth_m": (depth-base_corridor)/2,
                        "usable_area_m2": width*(depth-base_corridor),
                        "note": "Recompute when corridor_ratio changes. All spaces must cover this area; "
                                "global min_room_width_m also constrains depths of small service rooms "
                                "and each anchor/private-child strip. Reference room widths are per-function priors, "
                                "not a minimum width for every space in the floor.",
                    },
                },
                "city_constraints": {
                    "floor_range": [spec.min_floors, spec.max_floors],
                    "room_count_strategy": spec.room_count_strategy,
                    "exact_room_count": (
                        spec.rooms_per_floor
                        if spec.room_count_strategy == "fixed"
                        else None
                    ),
                },
                "supported": {
                    "spatial_program": SPATIAL_PROGRAM_GUIDANCE,
                    "room_functions": list(ROOM_FUNCTIONS.get(building.function, ROOM_FUNCTIONS["mixed_use"])),
                    "spatial_footprint_supported": (
                        building.metadata.get("massing_style", "bar") == "bar"
                        or bool(highrise.get("enabled"))
                    ),
                    "layout": sorted(FLOOR_LAYOUTS),
                    "floor_roles": ["ground", "podium", "typical", "top"],
                    "vertical_zone_roles": [
                        "ground", "podium", "typical", "amenity", "refuge",
                        "service", "mechanical", "top",
                    ],
                    "vertical_use_types": sorted(VERTICAL_USE_TYPES),
                    "room_count_range": [1, 32],
                    "room_geometry_contract": {
                        "max_room_depth_m": [4.0, 30.0],
                        "max_room_aspect_ratio": [1.4, 8.0],
                        "note": "corridors/core/service bands may be deeper; enclosed usable rooms should not be facade-width strips",
                    },
                    "layout_templates": [
                        "auto", "residential_units", "office_core",
                        "commercial_retail", "podium_core", "tower_core",
                        "open_plan",
                    ],
                },
            },
            sections=(
                ContextSection(
                    "base_floor_program",
                    "Accepted global FloorProgram profile to personalize, not discard",
                    self._compact_base_profile(base_profile),
                ),
                ContextSection(
                    "building_geometry_contract",
                    "Concrete geometry and vertical constraints owned by the compiler",
                    {
                        "footprint": to_primitive(building.footprint),
                        "entrance": to_primitive(building.entrance),
                        "realized_floor_plate_contract": floor_plate_contract,
                        "vertical_connectors": [
                            to_primitive(item) for item in building.vertical_connectors
                        ],
                        "floor_levels": [floor.level for floor in building.floors],
                    },
                ),
                ContextSection(
                    "personalization_guidance",
                    "Function-aware building-specific adjustments",
                    {
                        "residential": "Use multiple dwelling units on typical floors; fit more internal rooms when the plate is larger, while keeping each room above its target area and facade bay width.",
                        "commercial": "Use larger ground-floor public/retail spaces and denser typical office/shop/support spaces; open-office zones may be larger than enclosed rooms.",
                        "semantic_topology": (
                            "Choose residential_units for dwelling floors, commercial_retail for "
                            "street-facing retail/podium floors, office_core or open_plan for office "
                            "floors, and tower_core for compact upper tower plates."
                        ),
                        "highrise": "Keep the core and circulation aligned across all floors; vary counts and density without breaking a repeatable typical-floor template. Read the supplied realized_floor_plate_contract: podium levels use the active podium outline, while tower levels use the smaller tower outline.",
                            "vertical_zoning": (
                                "Partition every realized level into ordered, contiguous use bands. "
                                "A tall building may use ground lobby, podium, lower tower, amenity/refuge, "
                                "upper tower, and top/service bands. Give repeated typical bands different "
                                "zone IDs and room programs when their uses differ."
                            ),
                            "highrise_invariant": (
                                "For a building with 12 or more realized floors, include at least one "
                                "interior amenity, refuge, service, or mechanical band between the "
                                "ground/podium and top zones; split the remaining tower into lower and "
                                "upper bands when their uses or density differ."
                            ),
                        "must_preserve": [
                            "all rooms inside the supplied realized floor-plate outline, not merely the parcel footprint",
                            "all room doors connected to corridor",
                            "ground and typical archetypes",
                            "vertical connector continuity",
                        ],
                    },
                ),
            ),
        )
        prompt = self._base_prompt(
            "Building-specific Floor",
            "Return one BuildingFloorProgram with building_function, layout, corridor_ratio, "
            "room_function_cycle, space_archetypes, and vertical_zones. Copy the exact building function. "
            "Adapt preferred/min/max room counts and target areas to the supplied footprint; "
            "for high-rises, adapt every vertical zone to the disclosed realized floor-plate contract and "
            "never budget rooms in the excluded setback area; "
            "do not simply copy the global profile. Provide ground and typical archetypes, "
            "and podium/top only when useful. Keep all counts <= 32 and use only the disclosed "
            "room-function catalog. vertical_zones is required and must cover every integer level "
            "exactly once with ordered inclusive start_level/end_level ranges. Level 0 is a one-level "
            "ground zone; a multi-floor building ends in a top zone. Every vertical zone has zone_id, "
            "start_level, end_level, role, use_type, preferred_room_count, min_room_count, "
            "max_room_count, target_room_area_m2, min_room_width_m, max_room_depth_m, "
            "max_room_aspect_ratio, layout_template, room_function_cycle, and "
            "unit_group_size. max_room_depth_m and max_room_aspect_ratio constrain enclosed usable "
            "rooms; use a multi-corridor/core topology for deep plates rather than making rooms "
            "narrow and excessively deep. For 12 or more floors, at least one interior zone must have role "
            "amenity, refuge, service, or mechanical. Use multiple tower bands when functionally "
            "justified; do not split a small building gratuitously. IMPORTANT: output at most 8 "
            "vertical_zones and express each as an inclusive range; never enumerate one object "
            "per floor. Keep space_archetypes as compact reusable role templates, not per-level "
            "records. Coordinates, wall polygons, doors, and USD remain compiler-owned."
            " When spatial_footprint_supported is true, include spatial_program in each vertical zone: {family, spaces}; "
            "otherwise omit it (irregular low-rise wing connectivity remains on the legacy planner). Follow the disclosed "
            "spatial_program contract. Plan named functional spaces and access relationships first, "
            "then choose area ranges compatible with the actual floor plate. Use unequal target areas "
            "when functions differ. Residential private rooms must access their living/entry anchor, "
            "not public circulation. Choose double_loaded, residential_clusters, or open_office by "
            "use, not for arbitrary variation. Request explicit same-function merges only when useful. "
            "Keep fixed room counts exact after merges. Do not invent atria or unsupported topology."
            " Each spaces entry MUST have key, function, target_area_m2. Use only supported.room_functions "
            "verbatim (shop, not retail; meeting_room, not meeting). access_via is a STRING, "
            "circulation for roots, never null, entrance, or corridor. Do not add implicit circulation "
            "to spaces. Area bounds must cover the usable plate after subtracting the corridor. "
            "Omit optional fields rather than inventing enums."
            " For a building with interior_layout_contract, its physical plate was reserved from "
            "the disclosed room prototype dimensions. Keep several enclosed spaces within the "
            "applicability width/depth/area of same-function room references, rather than a few "
            "oversized rooms. The supported spatial solver has ONE horizontal central corridor; "
            "each room group fills a north/south band. Do not request extra corridors or arbitrarily "
            "tight max_room_depth_m smaller than that band's depth. Give enough independent groups "
            "to achieve the reference frontage widths. Other coarse rooms need not match prototypes."
            " Use single_spine_capacity_hint: total target areas should be near the usable area; "
            "max_area bounds must cover it. A private access group divides its band depth between "
            "anchor and children, so a 6m band cannot contain two strips each requiring min_width=4m. "
            "Do not apply one prototype's width minimum to small service rooms across the whole floor."
        )

        def parse(data: dict[str, Any]) -> BuildingFloorProgram:
            for key in ("BuildingFloorProgram", "building_floor_program"):
                if set(data) == {key} and isinstance(data[key], dict):
                    data = data[key]
                    break
            data = self._coerce_level_archetypes(data, building)
            data = self._coerce_semantic_program(data, building.function)
            data = self._coerce_vertical_zones(data, building)
            program = BuildingFloorProgram.from_dict(data)
            program.validate(building)
            self._check_spatial_feasibility(program.profile, building, spec)
            return program

        if building.metadata.get("massing_style", "bar") != "bar" and not highrise.get("enabled"):
            prompt = (
                "THIS BUILDING HAS AN IRREGULAR LOW-RISE FOOTPRINT. Do NOT output spatial_program "
                "anywhere (including space_archetypes and vertical_zones). Personalize counts, "
                "function cycles, area targets and layout_templates instead. The connected-space "
                "solver is unavailable for this footprint.\n" + prompt)
        return self._run(context, prompt, parse)

    @classmethod
    def _coerce_semantic_program(
        cls, data: dict[str, Any], building_function: str
    ) -> dict[str, Any]:
        """Normalize richer unit/tenant JSON into the bounded compiler contract.

        This is deliberately a narrow adapter, not a second planner.  It handles
        common model expressions such as ``1BR``/``2BR`` and a role-keyed
        ``rooms`` list, while all unsupported values still fail validation.
        """

        result = dict(data)
        result["building_function"] = str(
            result.get("building_function", result.get("function", building_function))
        )
        result["function"] = building_function
        cycle = cls._normalize_cycle(result.get("room_function_cycle", ()), building_function)
        result["room_function_cycle"] = cycle or list(ROOM_FUNCTIONS[building_function])[:4]
        default_depth, default_aspect = cls._room_geometry_defaults(building_function)
        raw_archetypes = result.get("space_archetypes", [])
        if isinstance(raw_archetypes, dict):
            role_items: list[dict[str, Any]] = []
            for role, value in raw_archetypes.items():
                if isinstance(value, dict):
                    role_items.append(dict(value, role=role))
                elif isinstance(value, (list, tuple)):
                    role_items.append({"role": role, "rooms": list(value)})
            raw_archetypes = role_items
        normalized: list[dict[str, Any]] = []
        for raw in raw_archetypes:
            if not isinstance(raw, dict):
                continue
            role_token = re.sub(
                r"[^a-z0-9]+", "_", str(raw.get("role", "typical")).lower()
            ).strip("_")
            role = {
                "lobby": "ground",
                "entrance": "ground",
                "residential_unit": "typical",
                "dwelling_unit": "typical",
                "apartment": "typical",
                "office": "typical",
                "retail": "podium",
                "rooftop": "top",
                "penthouse": "top",
            }.get(role_token, role_token)
            # A model may describe the circulation/service band beside usable
            # rooms as a zero-room archetype. It is useful semantic context but
            # not a compiler room template, so do not let it replace the real
            # typical-floor archetype.
            if role_token in {
                "corridor", "circulation", "corridor_service", "service_core"
            } and max(
                int(raw.get("preferred_room_count", 0) or 0),
                int(raw.get("max_room_count", 0) or 0),
            ) <= 0:
                continue
            entries = raw.get("rooms", raw.get("room_program", []))
            if isinstance(entries, dict):
                entries = [dict(value, function=key) for key, value in entries.items()]
            expanded, weighted_area, group_size = cls._expand_entries(
                entries, building_function
            )
            role_cycle = cls._normalize_cycle(
                raw.get("room_function_cycle", expanded), building_function
            )
            if not expanded:
                expanded = role_cycle or result["room_function_cycle"]
            count = min(32, max(1, int(raw.get("total_rooms", len(expanded)))))
            if entries:
                count = min(32, max(1, len(expanded)))
            preferred = int(raw.get("preferred_room_count", count))
            minimum = int(raw.get("min_room_count", max(1, math.floor(preferred * 0.75))))
            maximum = int(raw.get("max_room_count", math.ceil(preferred * 1.25)))
            preferred = min(32, max(1, preferred))
            minimum = min(preferred, max(1, minimum))
            maximum = min(32, max(preferred, maximum))
            target_area = float(
                raw.get(
                    "target_room_area_m2",
                    weighted_area / max(1, len(expanded)) if weighted_area else 24.0,
                )
            )
            normalized.append(
                {
                    "role": role if role in FLOOR_ROLES else "typical",
                    "preferred_room_count": preferred,
                    "min_room_count": minimum,
                    "max_room_count": maximum,
                    "target_room_area_m2": min(250.0, max(8.0, target_area)),
                    "min_room_width_m": min(
                        12.0, max(2.4, float(raw.get("min_room_width_m", 2.8)))
                    ),
                    "max_room_depth_m": min(
                        30.0,
                        max(4.0, float(raw.get("max_room_depth_m", default_depth))),
                    ),
                    "max_room_aspect_ratio": min(
                        8.0,
                        max(1.4, float(raw.get("max_room_aspect_ratio", default_aspect))),
                    ),
                    "layout_template": cls._layout_template(
                        raw.get("layout_template", "auto"), building_function, role
                    ),
                    "spatial_program": raw.get("spatial_program"),
                    "room_function_cycle": role_cycle or result["room_function_cycle"],
                    "unit_group_size": min(
                        12,
                        max(1, int(raw.get("unit_group_size", group_size or 1))),
                    ),
                }
            )
        # Unit archetype labels (studio/1bed/2bed/unit) describe a room mix,
        # not compiler floor roles. Collapse them into one reusable typical
        # template; vertical zones retain the detailed per-band differences.
        deduplicated: dict[str, dict[str, Any]] = {}
        for item in normalized:
            role = item["role"]
            if (
                role not in deduplicated
                or item["preferred_room_count"]
                > deduplicated[role]["preferred_room_count"]
            ):
                deduplicated[role] = item
        normalized = list(deduplicated.values())
        # Some models use ``space_archetypes`` for dwelling archetypes and put
        # the required ground/typical templates only inside vertical_zones.
        # Preserve those useful templates under the canonical role names.
        existing_roles = {item["role"] for item in normalized}
        for required_role in ("ground", "typical"):
            if required_role in existing_roles:
                continue
            candidates = [
                item for item in result.get("vertical_zones", [])
                if isinstance(item, dict) and item.get("role") == required_role
            ]
            if not candidates:
                continue
            source = dict(candidates[0])
            source["role"] = required_role
            cycle = cls._normalize_cycle(
                source.get("room_function_cycle", result["room_function_cycle"]),
                building_function,
            )
            normalized.append(
                {
                    "role": required_role,
                    "preferred_room_count": int(source.get("preferred_room_count", 4)),
                    "min_room_count": int(source.get("min_room_count", 2)),
                    "max_room_count": int(source.get("max_room_count", 8)),
                    "target_room_area_m2": min(250.0, max(8.0, float(source.get("target_room_area_m2", 24.0)))),
                    "min_room_width_m": min(12.0, max(2.4, float(source.get("min_room_width_m", 2.8)))),
                    "max_room_depth_m": min(30.0, max(4.0, float(source.get("max_room_depth_m", default_depth)))),
                    "max_room_aspect_ratio": min(8.0, max(1.4, float(source.get("max_room_aspect_ratio", default_aspect)))),
                    "layout_template": cls._layout_template(
                        source.get("layout_template", "auto"), building_function, required_role
                    ),
                    "room_function_cycle": cycle or result["room_function_cycle"],
                    "unit_group_size": min(
                        12, max(1, int(source.get("unit_group_size", 1)))
                    ),
                }
            )
        result["space_archetypes"] = normalized
        return result

    @staticmethod
    def _coerce_level_archetypes(
        data: dict[str, Any], building: Building
    ) -> dict[str, Any]:
        """Compact a model's accidental per-level list into contiguous zones."""
        result = dict(data)
        raw = result.get("space_archetypes", [])
        if result.get("vertical_zones") or not isinstance(raw, (list, tuple)):
            return result
        level_items = [item for item in raw if isinstance(item, dict) and "level" in item]
        if not level_items:
            return result
        level_items.sort(key=lambda item: int(item.get("level", 0)))
        zones: list[dict[str, Any]] = []
        templates: dict[str, dict[str, Any]] = {}
        current: dict[str, Any] | None = None
        for item in level_items:
            level = int(item.get("level", 0))
            role = str(item.get("role", "typical"))
            use_type = str(item.get("use_type", role))
            key = f"{role}:{use_type}:{item.get('room_function_cycle', '')}"
            template = dict(item)
            template.pop("level", None)
            templates.setdefault(role, template)
            if current is not None and key == current["_key"] and level == current["end_level"] + 1:
                current["end_level"] = level
                continue
            current = {
                "zone_id": f"zone_{len(zones):02d}",
                "start_level": level,
                "end_level": level,
                "role": role,
                "use_type": use_type,
                "_key": key,
                **template,
            }
            zones.append(current)
        for zone in zones:
            zone.pop("_key", None)
        result["vertical_zones"] = zones
        result["space_archetypes"] = list(templates.values())
        return result

    @classmethod
    def _coerce_vertical_zones(
        cls, data: dict[str, Any], building: Building
    ) -> dict[str, Any]:
        """Normalize common range/role aliases without inventing missing zones."""

        result = dict(data)
        raw_zones = result.get("vertical_zones", [])
        if isinstance(raw_zones, dict):
            raw_zones = [
                dict(value, zone_id=zone_id)
                for zone_id, value in raw_zones.items()
                if isinstance(value, dict)
            ]
        if not isinstance(raw_zones, (list, tuple)):
            raw_zones = []
        archetypes = {
            str(item.get("role")): item
            for item in result.get("space_archetypes", [])
            if isinstance(item, dict)
        }
        role_aliases = {
            "lobby": "ground",
            "entrance": "ground",
            "retail": "podium",
            "tower": "typical",
            "lower_tower": "typical",
            "upper_tower": "typical",
            "residential": "typical",
            "office": "typical",
            "rooftop": "top",
            "penthouse": "top",
        }
        use_aliases = {
            "lobby": "entrance",
            "ground": "entrance",
            "podium": "retail",
            "typical": (
                "residential" if building.function == "residential" else
                "office" if building.function == "commercial" else
                building.function if building.function in VERTICAL_USE_TYPES else "mixed"
            ),
            "top": "amenity",
        }
        default_depth, default_aspect = cls._room_geometry_defaults(building.function)
        normalized: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_zones):
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            levels = item.get("levels", item.get("floor_range"))
            start = item.get("start_level", item.get("start_floor"))
            end = item.get("end_level", item.get("end_floor"))
            if isinstance(levels, (list, tuple)) and len(levels) >= 2:
                start = levels[0] if start is None else start
                end = levels[1] if end is None else end
            if start is None or end is None:
                continue
            role_token = re.sub(
                r"\s+", "_", str(item.get("role", item.get("zone_type", "typical"))).lower()
            )
            role = role_aliases.get(role_token, role_token)
            base = dict(archetypes.get(role, archetypes.get("typical", {})))
            nested = item.get("archetype", item.get("space_program", {}))
            if isinstance(nested, dict):
                base.update(nested)
            base.update(item)
            use_token = re.sub(
                r"\s+", "_", str(base.get("use_type", base.get("purpose", role_token))).lower()
            )
            use_type = use_aliases.get(use_token, use_token)
            if use_type not in VERTICAL_USE_TYPES:
                use_type = use_aliases.get(role, "mixed")
            cycle = cls._normalize_cycle(
                base.get("room_function_cycle", result.get("room_function_cycle", [])),
                building.function,
            )
            preferred = min(32, max(1, int(base.get("preferred_room_count", base.get("preferred_count", 4)))))
            minimum = min(preferred, max(1, int(base.get("min_room_count", base.get("min_count", max(1, preferred - 2))))))
            maximum = min(32, max(preferred, int(base.get("max_room_count", base.get("max_count", preferred + 2)))))
            raw_id = str(base.get("zone_id", base.get("name", f"zone_{index:02d}")))
            zone_id = re.sub(r"[^a-z0-9]+", "_", raw_id.lower()).strip("_") or f"zone_{index:02d}"
            if not re.match(r"^[a-z]", zone_id):
                zone_id = f"zone_{zone_id}"
            normalized.append({
                "zone_id": zone_id[:48],
                "start_level": int(start),
                "end_level": int(end),
                "role": role,
                "use_type": use_type,
                "preferred_room_count": preferred,
                "min_room_count": minimum,
                "max_room_count": maximum,
                "target_room_area_m2": min(250.0, max(8.0, float(base.get("target_room_area_m2", base.get("target_area_m2", 24.0))))),
                "min_room_width_m": min(12.0, max(2.4, float(base.get("min_room_width_m", 2.8)))),
                "max_room_depth_m": min(30.0, max(4.0, float(base.get("max_room_depth_m", default_depth)))),
                "max_room_aspect_ratio": min(8.0, max(1.4, float(base.get("max_room_aspect_ratio", default_aspect)))),
                "layout_template": cls._layout_template(
                    base.get("layout_template", "auto"), building.function, role
                ),
                "spatial_program": base.get("spatial_program"),
                "room_function_cycle": cycle or result["room_function_cycle"],
                "unit_group_size": min(12, max(1, int(base.get("unit_group_size", 1)))),
            })
        # Reconcile a model's nominal range with the already realized building
        # geometry. The last valid band may be extended/clipped, but no new
        # interior layout is invented here.
        if normalized:
            highest = len(building.floors) - 1
            normalized[-1]["start_level"] = min(
                highest, max(0, normalized[-1]["start_level"])
            )
            normalized[-1]["end_level"] = min(
                highest, max(normalized[-1]["start_level"], normalized[-1]["end_level"])
            )
            if normalized[-1]["end_level"] < highest:
                normalized[-1]["end_level"] = highest
            # Clip any preceding nominal bands from the back so an out-of-range
            # model terminal band cannot create overlap or a reversed interval.
            for index in range(len(normalized) - 2, -1, -1):
                normalized[index]["end_level"] = min(
                    normalized[index]["end_level"],
                    normalized[index + 1]["start_level"] - 1,
                )
            normalized = [
                item for item in normalized
                if item["end_level"] >= item["start_level"]
            ]
            if len(building.floors) > 1:
                # The terminal band is semantically the roof/top band even if
                # the model called it amenity, residential, or service.
                normalized[-1]["role"] = "top"
        result["vertical_zones"] = normalized
        return result

    @staticmethod
    def _compact_base_profile(profile: FloorProfile) -> dict:
        """Do not disclose repeated 32-room programs once per role/height band."""
        from collections import Counter
        data = to_primitive(profile)
        for item in [*data.get("space_archetypes", []), *data.get("vertical_zones", [])]:
            spatial = item.pop("spatial_program", None)
            if not spatial:
                continue
            spaces = spatial["spaces"]
            item["spatial_program_summary"] = {
                "family": spatial["family"], "space_count": len(spaces),
                "function_counts": dict(Counter(s["function"] for s in spaces)),
                "target_area_total_m2": sum(s["target_area_m2"] for s in spaces),
                "group_count": len({s["group"] for s in spaces if s.get("group")}),
                "note": "Input summary only. Author a complete spatial_program for the realized building; do not copy this summary into output.",
            }
        return data

    @staticmethod
    def _check_spatial_feasibility(profile: FloorProfile, building: Building, spec: CitySpec,
                                   *, access_constraints=(), _geometry=None) -> None:
        """Return geometric failures to the agent's existing bounded retry loop."""
        from cityg.planning.programmed import ProgrammedCityPlanner
        from cityg.planning.spatial_layout import solve_spatial_floor
        from cityg.schemas import Bounds2D
        from cityg.planning.interior_frame import InteriorFrame, circulation_axis
        frame=InteriorFrame(circulation_axis(building))

        highrise = building.metadata.get("highrise", {})
        plates = [HighRisePolicy.floor_plate_bounds(
            building.footprint, len(building.floors), f.level,
            highrise.get("massing_variant"),
            orientation_deg=float(building.metadata.get("orientation_deg", 0)),
        ) for f in building.floors]
        common = Bounds2D(max(p.min_x for p in plates), max(p.min_y for p in plates),
                          min(p.max_x for p in plates), min(p.max_y for p in plates))
        corridor_depth = min(ProgrammedCityPlanner._corridor_depth(frame.bounds(p).depth, profile.corridor_ratio) for p in plates)
        connectors = (building.vertical_connectors if building.metadata.get("interior_layout_contract")
                      else HighRisePolicy.connectors(building.id, len(building.floors), common, corridor_depth))
        core = ProgrammedCityPlanner._connector_core_bounds(common, connectors, corridor_depth)
        if frame.axis=='y':
            from cityg.planning.floor_brief import geometry_summary
            geometry=_geometry if _geometry is not None else geometry_summary(building,profile)
            core=Bounds2D(**geometry['core'])
        checked = set()
        errors = []
        for floor, plate in zip(building.floors, plates):
            zone = profile.zone_for_level(floor.level)
            archetype = zone.archetype if zone else profile.for_role(floor.metadata.get("program_role", "typical"))
            if archetype is None or archetype.spatial_program is None:
                continue
            if building.metadata.get("massing_style", "bar") != "bar" and not highrise.get("enabled"):
                raise ValueError("spatial_program currently requires a connected rectangular plate; omit it for irregular low-rise massing")
            signature = (repr(archetype), plate, floor.level == 0)
            if signature in checked:
                continue
            checked.add(signature)
            try:
                result = solve_spatial_floor(
                    archetype.spatial_program, floor_id=floor.id, level=floor.level,
                    height=floor.height_m, footprint=plate,
                    corridor_depth=ProgrammedCityPlanner._corridor_depth(frame.bounds(plate).depth, profile.corridor_ratio),
                    circulation_axis=frame.axis,
                    core_bounds=core, entrance=building.entrance,
                    min_width=archetype.min_room_width_m,
                    max_aspect=archetype.max_room_aspect_ratio,
                    max_depth=archetype.max_room_depth_m,
                )
                count = len(result.rooms)-1
                if not archetype.min_room_count <= count <= archetype.max_room_count:
                    raise ValueError("space count after merges outside archetype count range")
                if spec.room_count_strategy == "fixed" and count != spec.rooms_per_floor:
                    raise ValueError("space count after merges must match fixed rooms_per_floor")
                from cityg.planning.floor_access import check_floor_access
                check_floor_access(result,access_constraints)
            except ValueError as exc:
                errors.append(f"spatial_program infeasible at level {floor.level}, plate {plate.width:.1f}x{plate.depth:.1f}m: {exc}")
        if errors:
            raise ValueError("; ".join(errors) + ". Revise space areas, group roots, topology or count; do not change the plate/core.")

    @staticmethod
    def _layout_template(value: Any, building_function: str, role: str) -> str:
        """Normalize a model hint while retaining a function-aware fallback."""

        token = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")
        aliases = {
            "residential": "residential_units",
            "apartments": "residential_units",
            "office": "office_core",
            "retail": "commercial_retail",
            "commercial": "commercial_retail",
            "podium": "podium_core",
            "tower": "tower_core",
            "open_office": "open_plan",
        }
        token = aliases.get(token, token)
        supported = {
            "auto", "residential_units", "office_core", "commercial_retail",
            "podium_core", "tower_core", "open_plan",
        }
        if token in supported and token != "auto":
            return token
        if role == "podium":
            return "podium_core"
        if building_function == "residential":
            return "residential_units"
        if building_function == "commercial":
            return "commercial_retail" if role == "ground" else "office_core"
        if building_function == "mixed_use":
            return "commercial_retail" if role in {"ground", "podium"} else "tower_core"
        return "tower_core" if role in {"typical", "top"} else "auto"

    @staticmethod
    def _normalize_cycle(value: Any, building_function: str) -> list[str]:
        if isinstance(value, str):
            text = value.strip().strip("[]")
            if "," in text:
                tokens = text.split(",")
            elif "-" in text and text.lower() not in {"open-plan", "open_plan"}:
                tokens = text.split("-")
            else:
                tokens = [text]
            value = [item.strip(" '\"") for item in tokens if item.strip()]
        if not isinstance(value, (list, tuple)):
            return []
        aliases = {
            "lobby": "reception",
            "foyer": "reception",
            "mail_room": "storage",
            "mailroom": "storage",
            "utility": "storage",
            "utility_room": "storage",
            "service_room": "storage",
            "service_hall": "reception",
            "bath": "bathroom",
            "bedrooms": "bedroom",
            "living": "living_room",
            "living_unit": "living_room",
            "dwelling_unit": "living_room",
            "apartment": "living_room",
            "retail": "shop",
            "open_plan": "open_office",
            "open-plan": "open_office",
            "amenity": "living_room",
            "service": "storage",
        }
        allowed = set(ROOM_FUNCTIONS.get(building_function, ROOM_FUNCTIONS["mixed_use"]))
        normalized: list[str] = []
        for item in value:
            token = re.sub(r"\s+", "_", str(item).strip().lower())
            match = re.fullmatch(r"(\d+)?br", token)
            if match:
                bedrooms = int(match.group(1) or 1)
                normalized.extend(
                    ["living_room", "kitchen"]
                    + ["bedroom"] * bedrooms
                    + ["bathroom"]
                )
                continue
            if token == "studio":
                normalized.extend(["living_room", "kitchen", "bathroom"])
                continue
            bed_match = re.fullmatch(r"(\d+)?bed", token)
            if bed_match:
                bedrooms = int(bed_match.group(1) or 1)
                normalized.extend(
                    ["living_room", "kitchen"]
                    + ["bedroom"] * bedrooms
                    + ["bathroom"]
                )
                continue
            if token == "reception" and building_function == "public_service":
                token = "waiting_room"
            token = token if token in allowed else aliases.get(token, token)
            if token in allowed:
                normalized.append(token)
        return list(dict.fromkeys(normalized))

    @classmethod
    def _expand_entries(
        cls, entries: Any, building_function: str
    ) -> tuple[list[str], float, int]:
        if not isinstance(entries, (list, tuple)):
            return [], 0.0, 0
        expanded: list[str] = []
        weighted_area = 0.0
        inferred_group_size = 0
        for item in entries:
            if not isinstance(item, dict):
                continue
            function = str(item.get("function", item.get("type", "")))
            count = max(0, int(item.get("count", item.get("preferred_count", 1))))
            area = float(item.get("area_m2", item.get("target_area_m2", 0.0)) or 0.0)
            cycle = cls._normalize_cycle([function], building_function)
            if not cycle:
                continue
            # A 1BR/2BR token expands to a unit-sized sequence. The normalized
            # cycle contains all of that unit's rooms, so count is repeated.
            for _ in range(count):
                expanded.extend(cycle)
                weighted_area += area
            if building_function == "residential" and re.fullmatch(
                r"(\d+)?br", function.strip().lower()
            ):
                inferred_group_size = len(cycle)
        return expanded, weighted_area, inferred_group_size

    @staticmethod
    def signature(building: Building) -> str:
        """Exact metric signature; reuse never assumes a 5m bucket is feasible."""

        fp = building.footprint
        payload = {
            "interior_requirements": building.metadata.get("interior_layout_contract",{}).get("requirements",[]),
            "function": building.function,
            "width_m": round(fp.width, 6),
            "depth_m": round(fp.depth, 6),
            "massing_style": building.metadata.get('massing_style','bar'),
            "orientation_deg": building.metadata.get('orientation_deg',0),
            "reserved_interior": bool(building.metadata.get('interior_layout_contract')),
            "circulation_axis": building.metadata.get('interior_layout_contract',{}).get('circulation_axis','x'),
            "floor_count": len(building.floors),
            "highrise": bool(building.metadata.get("highrise", {}).get("enabled")),
            "massing_variant": building.metadata.get("highrise", {}).get("massing_variant"),
            "prototype_id": building.metadata.get("prototype_id"),
            "entrance_side": building.metadata.get("entrance_side"),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]

    def plan_city(
        self,
        city: City,
        base_profiles: dict[str, FloorProfile],
        spec: CitySpec,
        *,
        max_unique_calls: int = 12,
        prototype_context: dict | None = None,
    ) -> BuildingFloorBatchResult:
        if max_unique_calls < 0:
            raise ValueError("max_unique_calls must be non-negative")
        cache: dict[str, HierarchyAgentResult[BuildingFloorProgram]] = {}
        failed_signatures: dict[str, tuple[Any, ...]] = {}
        overrides: dict[str, FloorProfile] = {}
        signatures: dict[str, str] = {}
        cache_hits: dict[str, bool] = {}
        skipped: list[str] = []
        failed_buildings: dict[str, str] = {}
        for building in city.iter_buildings():
            if city.metadata.get("interior_scope") and building.id not in city.metadata["interior_scope"]["building_levels"]:
                skipped.append(building.id)
                continue
            signature = self.signature(building)
            signatures[building.id] = signature
            if signature not in cache and signature not in failed_signatures:
                if len(cache) + len(failed_signatures) >= max_unique_calls:
                    skipped.append(building.id)
                    cache_hits[building.id] = False
                    continue
                base_profile = base_profiles[building.function]
                try:
                    cache[signature] = self.plan(building, base_profile, spec,
                        **({'prototype_context': prototype_context} if prototype_context else {}))
                except AgentGenerationError as exc:
                    from cityg.progress import progress
                    progress('building_floor', '专属规划失败；保留全局楼层方案，后续仍需校验',
                             building=building.id, attempts=len(exc.attempts))
                    failed_signatures[signature] = exc.attempts
                    failed_buildings[building.id] = str(exc)
                    skipped.append(building.id)
                    cache_hits[building.id] = False
                    continue
                cache_hits[building.id] = False
            elif signature in failed_signatures:
                failed_buildings[building.id] = (
                    "shared building signature previously failed agent validation"
                )
                skipped.append(building.id)
                cache_hits[building.id] = True
                continue
            else:
                cache_hits[building.id] = True
            cache_result = cache[signature]
            # Equal dimensions do not imply equal entrance/core constraints.
            # Recheck cached metric programs against the actual receiving building.
            try:
                cache_result.program.validate(building)
                self._check_spatial_feasibility(cache_result.program.profile, building, spec)
            except ValueError as error:
                failed_buildings[building.id] = f'cached program rejected for actual geometry: {error}'
                skipped.append(building.id)
                continue
            overrides[building.id] = cache_result.program.profile
        return BuildingFloorBatchResult(
            overrides=overrides,
            signatures=signatures,
            cache_hits=cache_hits,
            traces=cache,
            skipped_buildings=tuple(skipped),
            failed_buildings=failed_buildings,
            failure_attempts=failed_signatures,
        )
