"""Small validated programs produced by hierarchical planning agents."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
from typing import Any

from cityg.geometry.prototypes import PROTOTYPES_BY_ID
from cityg.buildings.catalog import DEFAULT_BUILDING_CATALOG
from cityg.planning.baseline import ROOM_FUNCTIONS
from cityg.planning.highrise import (
    DEFAULT_HIGHRISE_MASSING_PALETTE,
    HIGHRISE_MASSING_VARIANTS,
)
from cityg.schemas import CitySpec
from cityg.planning.spatial_program import FloorSpatialProgram


FLOOR_POLICIES = frozenset(
    {"seeded_uniform", "minimum", "midpoint", "maximum", "alternating"}
)
ENTRANCE_SIDES = frozenset({"west", "east", "north", "south"})
BLOCK_TRAVERSALS = frozenset({"row_major", "column_major"})
ROAD_PATTERNS = frozenset({"connected_grid", "organic_hierarchy", "curved_hierarchy", "landscape_adaptive"})
TARGET_ROOM_AREA_RANGE_M2 = (8.0, 250.0)
FLOOR_LAYOUTS = frozenset(
    {
        "double_loaded_corridor",
        "residential_units",
        "office_core",
        "commercial_retail",
        "podium_core",
        "tower_core",
        "open_plan",
    }
)
BUILDING_ARCHETYPE_IDS = frozenset(
    item.archetype_id for item in DEFAULT_BUILDING_CATALOG
)
FLOOR_ROLES = frozenset(
    {"ground", "podium", "typical", "amenity", "refuge", "service", "mechanical", "top"}
)
VERTICAL_USE_TYPES = frozenset(
    {
        "entrance",
        "retail",
        "residential",
        "office",
        "public_service",
        "industrial",
        "amenity",
        "refuge",
        "service",
        "mechanical",
        "mixed",
    }
)
HEIGHT_CENTRALITY_BIASES = frozenset({"core", "distributed", "edge"})
HEIGHT_ROLES = frozenset({"lowrise", "midrise", "highrise", "mixed"})

# Compiler safety defaults for enclosed rooms.  These are deliberately
# conservative geometric bounds rather than building-code claims: the Floor
# Agent may tighten them per use type, while the compiler prevents a large
# plate from becoming a collection of facade-width strips.
DEFAULT_ROOM_MAX_DEPTH_M = 12.0
DEFAULT_ROOM_MAX_ASPECT_RATIO = 2.8


def _reject_unknown(data: dict[str, Any], known: set[str], kind: str) -> None:
    unknown = sorted(set(data) - known)
    if unknown:
        raise ValueError(f"Unknown {kind} fields: {', '.join(unknown)}")


def _normalize_floor_cycle(value: Any, function: str) -> tuple[str, ...]:
    """Normalize common semantic aliases while preserving unknowns for validation."""
    if isinstance(value, str):
        text = value.strip().strip("[]")
        text = text.replace('->', ',').replace('→', ',')
        if "," in text:
            tokens = text.split(",")
        elif "-" in text and text.lower() not in {"open-plan", "open_plan"}:
            tokens = text.split("-")
        else:
            tokens = [text]
        value = [item.strip(" '\"") for item in tokens if item.strip()]
    if not isinstance(value, (list, tuple)):
        raise ValueError(
            "room_function_cycle must be a flat array of room-function strings, "
            "not a role-keyed object; use e.g. ['office', 'meeting_room']. "
            "Ground/typical cycles belong in separate space_archetypes."
        )
    aliases = {
        "lobby": "reception", "foyer": "reception", "mail_room": "storage",
        "mailroom": "storage", "utility": "storage", "utility_room": "storage",
        "service_room": "storage", "service_hall": "reception", "bath": "bathroom",
        "bedrooms": "bedroom", "living": "living_room", "living_unit": "living_room",
        "dwelling_unit": "living_room", "apartment": "living_room", "retail": "shop",
        "open_plan": "open_office", "open-plan": "open_office",
        "amenity": "living_room", "service": "storage",
    }
    allowed = set(ROOM_FUNCTIONS.get(function, ROOM_FUNCTIONS["mixed_use"]))
    result: list[str] = []
    for item in value:
        token = re.sub(r"\s+", "_", str(item).strip().lower())
        match = re.fullmatch(r"(\d+)?br", token)
        if match:
            n = int(match.group(1) or 1)
            result.extend(["living_room", "kitchen"] + ["bedroom"] * n + ["bathroom"])
        elif token == "studio":
            result.extend(["living_room", "kitchen", "bathroom"])
        elif bed_match := re.fullmatch(r"(\d+)?bed", token):
            n = int(bed_match.group(1) or 1)
            result.extend(["living_room", "kitchen"] + ["bedroom"] * n + ["bathroom"])
        else:
            if token == "reception" and function == "public_service":
                token = "waiting_room"
            result.append(token if token in allowed else aliases.get(token, token))
    return tuple(dict.fromkeys(result))


def _normalize_floor_archetypes(raw: Any, function: str) -> list[dict[str, Any]]:
    """Accept canonical archetypes and role-keyed semantic ``rooms`` lists."""
    # Models sometimes put the same keyed role map inside the archetype array.
    if isinstance(raw, (list, tuple)):
        expanded_roles = []
        for entry in raw:
            if isinstance(entry, dict) and entry and set(entry) <= FLOOR_ROLES:
                for role, descriptor in entry.items():
                    if not isinstance(descriptor, dict) or descriptor.get('role', role) != role:
                        raise ValueError(f'Invalid or conflicting floor archetype for {role}')
                    expanded_roles.append(dict(descriptor, role=role))
            else:
                expanded_roles.append(entry)
        raw = expanded_roles
    if isinstance(raw, dict):
        role_items: list[dict[str, Any]] = []
        for role, value in raw.items():
            if isinstance(value, dict):
                role_items.append(dict(value, role=role))
            elif isinstance(value, (list, tuple)):
                role_items.append({"role": role, "rooms": list(value)})
        raw = role_items
    if not isinstance(raw, (list, tuple)):
        return []
    normalized: list[dict[str, Any]] = []
    fallback = _normalize_floor_cycle(ROOM_FUNCTIONS.get(function, ROOM_FUNCTIONS["mixed_use"]), function)
    for item in raw:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "typical"))
        entries = item.get("rooms", item.get("room_program", []))
        if isinstance(entries, dict):
            entries = [dict(value, function=key) for key, value in entries.items()]
        expanded: list[str] = []
        weighted_area = 0.0
        group_size = 0
        if isinstance(entries, (list, tuple)):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                token = str(entry.get("function", entry.get("type", "")))
                count = max(0, int(entry.get("count", entry.get("preferred_count", 1))))
                cycle = _normalize_floor_cycle([token], function)
                area = float(entry.get("area_m2", entry.get("target_area_m2", 0.0)) or 0.0)
                for _ in range(count):
                    expanded.extend(cycle)
                    weighted_area += area
                if function == "residential" and re.fullmatch(r"(\d+)?br", token.strip().lower()):
                    group_size = len(cycle)
        cycle = _normalize_floor_cycle(item.get("room_function_cycle", expanded), function)
        if not cycle:
            cycle = fallback[:4] or ("storage",)
        count = int(item.get("total_rooms", len(expanded) or item.get("preferred_room_count", 1)))
        if entries:
            count = len(expanded) or count
        preferred = min(32, max(1, int(item.get("preferred_room_count", count))))
        minimum = min(preferred, max(1, int(item.get("min_room_count", math.floor(preferred * 0.75)))))
        maximum = min(32, max(preferred, int(item.get("max_room_count", math.ceil(preferred * 1.25)))))
        target = float(item.get("target_room_area_m2", weighted_area / max(1, len(expanded)) if weighted_area and expanded else 24.0))
        normalized.append({
            "role": role,
            "preferred_room_count": preferred,
            "min_room_count": minimum,
            "max_room_count": maximum,
            "target_room_area_m2": min(250.0, max(8.0, target)),
            "min_room_width_m": min(12.0, max(2.4, float(item.get("min_room_width_m", 2.8)))),
            "max_room_depth_m": min(
                30.0,
                max(4.0, float(item.get("max_room_depth_m", DEFAULT_ROOM_MAX_DEPTH_M))),
            ),
        "max_room_aspect_ratio": min(
                8.0,
                max(1.4, float(item.get("max_room_aspect_ratio", DEFAULT_ROOM_MAX_ASPECT_RATIO))),
            ),
            "layout_template": str(item.get("layout_template", "auto")),
            "spatial_program": item.get("spatial_program"),
            "room_function_cycle": cycle,
            "unit_group_size": int(item.get("unit_group_size", group_size or 1)),
        })
    return normalized


@dataclass(frozen=True)
class UrbanProgram:
    district_order: tuple[str, ...]
    road_pattern: str = "connected_grid"
    block_traversal: str = "row_major"
    collector_policy: str = "perimeter"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UrbanProgram":
        _reject_unknown(
            data,
            {"district_order", "road_pattern", "block_traversal", "collector_policy"},
            "UrbanProgram",
        )
        if not isinstance(data.get('district_order'), (list, tuple)):
            raise ValueError('district_order must be an array of exact zone IDs')
        choices = {'road_pattern': sorted(ROAD_PATTERNS),
                   'block_traversal': sorted(BLOCK_TRAVERSALS), 'collector_policy': ['perimeter']}
        for key, allowed in choices.items():
            if key in data and not isinstance(data[key], str):
                raise ValueError(f'{key} must be one scalar string from {allowed}, not '
                                 f'{type(data[key]).__name__}; choose one value, not a list of options')
        return cls(
            district_order=tuple(str(item) for item in data["district_order"]),
            road_pattern=str(data.get("road_pattern", "connected_grid")),
            block_traversal=str(data.get("block_traversal", "row_major")),
            collector_policy=str(data.get("collector_policy", "perimeter")),
        )

    def validate(self, spec: CitySpec) -> None:
        expected = {f"zone_{index:02d}" for index in range(len(spec.zones))}
        if len(self.district_order) != len(expected) or set(self.district_order) != expected:
            raise ValueError("district_order must contain every provided zone ID exactly once")
        if self.road_pattern not in ROAD_PATTERNS:
            raise ValueError("unsupported road_pattern")
        if spec.road_pattern == 'landscape_adaptive' and self.road_pattern != spec.road_pattern:
            raise ValueError('preserve requested landscape_adaptive road pattern')
        if self.block_traversal not in BLOCK_TRAVERSALS:
            raise ValueError('unsupported block_traversal: choose "row_major" or "column_major"')
        if self.collector_policy != "perimeter":
            raise ValueError("current compiler supports only perimeter collectors")


@dataclass(frozen=True)
class BuildingProfile:
    function: str
    floor_policy: str
    entrance_side: str
    prototype_id: str
    highrise_massing_palette: tuple[str, ...] = DEFAULT_HIGHRISE_MASSING_PALETTE
    archetype_palette: tuple[str, ...] = ()
    design_language_palette: tuple[str, ...] = ()
    envelope_preference: dict[str, Any] = field(default_factory=dict)
    roof_profile_palette: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BuildingProfile":
        _reject_unknown(
            data,
            {
                "function",
                "floor_policy",
                "entrance_side",
                "prototype_id",
                "highrise_massing_palette",
                "archetype_palette",
                "design_language_palette",
                "envelope_preference",
                "roof_profile_palette",
            },
            "BuildingProfile",
        )
        return cls(
            function=str(data["function"]),
            floor_policy=str(data["floor_policy"]),
            entrance_side=str(data["entrance_side"]),
            prototype_id=str(data["prototype_id"]),
            highrise_massing_palette=tuple(
                str(item)
                for item in data.get(
                    "highrise_massing_palette",
                    DEFAULT_HIGHRISE_MASSING_PALETTE,
                )
            ),
            archetype_palette=tuple(
                str(item) for item in data.get("archetype_palette", ())
            ),
            design_language_palette=tuple(data.get("design_language_palette", ())),
            envelope_preference=dict(data.get("envelope_preference", {})),
            roof_profile_palette=tuple(data.get("roof_profile_palette", ())),
        )


@dataclass(frozen=True)
class BuildingProgram:
    profiles: tuple[BuildingProfile, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BuildingProgram":
        _reject_unknown(data, {"profiles"}, "BuildingProgram")
        return cls(tuple(BuildingProfile.from_dict(item) for item in data["profiles"]))

    def validate(self, spec: CitySpec) -> None:
        expected = {zone.function for zone in spec.zones}
        actual = [profile.function for profile in self.profiles]
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise ValueError("building profiles must cover each zone function exactly once")
        for profile in self.profiles:
            from cityg.geometry.roof_programs import PROFILES as ROOF_PROFILES
            if any(item not in ROOF_PROFILES for item in profile.roof_profile_palette):
                raise ValueError('unsupported roof profile palette')
            from cityg.architecture import validate_palette
            validate_palette(profile.design_language_palette)
            from cityg.envelopes import validate_envelope
            validate_envelope(profile.envelope_preference)
            if profile.floor_policy not in FLOOR_POLICIES:
                raise ValueError(f"unsupported floor policy: {profile.floor_policy}")
            if profile.entrance_side not in ENTRANCE_SIDES:
                raise ValueError(f"unsupported entrance side: {profile.entrance_side}")
            if profile.prototype_id not in PROTOTYPES_BY_ID:
                raise ValueError(f"unknown prototype: {profile.prototype_id}")
            if not profile.highrise_massing_palette or any(
                item not in HIGHRISE_MASSING_VARIANTS
                for item in profile.highrise_massing_palette
            ):
                raise ValueError("unsupported or empty highrise_massing_palette")
            if any(item not in BUILDING_ARCHETYPE_IDS for item in profile.archetype_palette):
                raise ValueError("unsupported archetype_palette entry")
            if profile.archetype_palette:
                catalog = {
                    item.archetype_id: item for item in DEFAULT_BUILDING_CATALOG
                }
                if any(
                    profile.function not in catalog[item].compatible_functions
                    for item in profile.archetype_palette
                ):
                    raise ValueError(
                        "archetype_palette contains an incompatible function entry"
                    )

    def for_function(self, function: str) -> BuildingProfile:
        return next(item for item in self.profiles if item.function == function)


@dataclass(frozen=True)
class FloorArchetype:
    """Semantic space program for one reusable vertical floor role.

    The LLM predicts a bounded space budget and semantic mix.  Metric room
    coordinates remain the responsibility of the deterministic compiler.
    """

    role: str
    preferred_room_count: int
    min_room_count: int
    max_room_count: int
    target_room_area_m2: float
    min_room_width_m: float
    room_function_cycle: tuple[str, ...]
    unit_group_size: int = 1
    max_room_depth_m: float = DEFAULT_ROOM_MAX_DEPTH_M
    max_room_aspect_ratio: float = DEFAULT_ROOM_MAX_ASPECT_RATIO
    layout_template: str = "auto"
    spatial_program: FloorSpatialProgram | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FloorArchetype":
        _reject_unknown(
            data,
            {
                "role",
                "preferred_room_count",
                "min_room_count",
                "max_room_count",
                "target_room_area_m2",
                "min_room_width_m",
                "max_room_depth_m",
                "max_room_aspect_ratio",
                "layout_template",
                "spatial_program",
                "room_function_cycle",
                "unit_group_size",
            },
            "FloorArchetype",
        )
        return cls(
            role=str(data["role"]),
            preferred_room_count=int(data["preferred_room_count"]),
            min_room_count=int(data["min_room_count"]),
            max_room_count=int(data["max_room_count"]),
            target_room_area_m2=float(data["target_room_area_m2"]),
            min_room_width_m=float(data["min_room_width_m"]),
            room_function_cycle=tuple(
                str(item) for item in data["room_function_cycle"]
            ),
            unit_group_size=int(data.get("unit_group_size", 1)),
            max_room_depth_m=min(
                30.0,
                max(4.0, float(data.get("max_room_depth_m", DEFAULT_ROOM_MAX_DEPTH_M))),
            ),
            max_room_aspect_ratio=min(
                8.0,
                max(1.4, float(data.get("max_room_aspect_ratio", DEFAULT_ROOM_MAX_ASPECT_RATIO))),
            ),
            layout_template=str(data.get("layout_template", "auto")),
            spatial_program=FloorSpatialProgram.from_dict(data.get("spatial_program")),
        )

    def validate(self, function: str) -> None:
        if self.spatial_program is not None:
            self.spatial_program.validate(ROOM_FUNCTIONS.get(function, ROOM_FUNCTIONS["mixed_use"]))
        if self.role not in FLOOR_ROLES:
            raise ValueError(f"unsupported floor role: {self.role}")
        if not (
            1
            <= self.min_room_count
            <= self.preferred_room_count
            <= self.max_room_count
            <= 32
        ):
            raise ValueError(
                "floor archetype room counts must satisfy "
                "1 <= min <= preferred <= max <= 32"
            )
        if not TARGET_ROOM_AREA_RANGE_M2[0] <= self.target_room_area_m2 <= TARGET_ROOM_AREA_RANGE_M2[1]:
            raise ValueError("target_room_area_m2 must be within [8, 250]")
        if not 2.4 <= self.min_room_width_m <= 12.0:
            raise ValueError("min_room_width_m must be within [2.4, 12]")
        if not 4.0 <= self.max_room_depth_m <= 30.0:
            raise ValueError("max_room_depth_m must be within [4, 30]")
        if not 1.4 <= self.max_room_aspect_ratio <= 8.0:
            raise ValueError("max_room_aspect_ratio must be within [1.4, 8]")
        if self.layout_template not in {
            "auto", "residential_units", "office_core", "commercial_retail",
            "podium_core", "tower_core", "open_plan",
        }:
            raise ValueError(f"unsupported layout_template: {self.layout_template}")
        if not 1 <= self.unit_group_size <= 12:
            raise ValueError("unit_group_size must be within [1, 12]")
        if not self.room_function_cycle:
            raise ValueError("room_function_cycle must not be empty")
        allowed = set(ROOM_FUNCTIONS.get(function, ROOM_FUNCTIONS["mixed_use"]))
        unsupported = sorted(set(self.room_function_cycle) - allowed)
        if unsupported:
            raise ValueError(
                f"unsupported room functions for {function}: {', '.join(unsupported)}; "
                f"allowed functions: {', '.join(sorted(allowed))}"
            )


@dataclass(frozen=True)
class VerticalFloorZone:
    """A contiguous, building-specific vertical use band.

    Levels are zero-based and inclusive.  Each zone owns a complete bounded
    room-space archetype, so two ``typical`` tower bands may still have distinct
    densities and semantic mixes.
    """

    zone_id: str
    start_level: int
    end_level: int
    role: str
    use_type: str
    preferred_room_count: int
    min_room_count: int
    max_room_count: int
    target_room_area_m2: float
    min_room_width_m: float
    room_function_cycle: tuple[str, ...]
    unit_group_size: int = 1
    max_room_depth_m: float = DEFAULT_ROOM_MAX_DEPTH_M
    max_room_aspect_ratio: float = DEFAULT_ROOM_MAX_ASPECT_RATIO
    layout_template: str = "auto"
    spatial_program: FloorSpatialProgram | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], function: str) -> "VerticalFloorZone":
        # Accept an optional nested archetype while keeping the serialized
        # contract flat and easy for local instruction models to emit.
        raw = dict(data)
        nested = raw.pop("archetype", None)
        if isinstance(nested, dict):
            for key, value in nested.items():
                raw.setdefault(key, value)
        _reject_unknown(
            raw,
            {
                "zone_id", "start_level", "end_level", "role", "use_type",
                "preferred_room_count", "min_room_count", "max_room_count",
                "target_room_area_m2", "min_room_width_m", "max_room_depth_m",
                "max_room_aspect_ratio", "room_function_cycle",
                "layout_template",
                "spatial_program",
                "unit_group_size",
            },
            "VerticalFloorZone",
        )
        role = str(raw["role"])
        cycle = _normalize_floor_cycle(raw["room_function_cycle"], function)
        return cls(
            zone_id=str(raw["zone_id"]),
            start_level=int(raw["start_level"]),
            end_level=int(raw["end_level"]),
            role=role,
            use_type=str(raw["use_type"]),
            preferred_room_count=int(raw["preferred_room_count"]),
            min_room_count=int(raw["min_room_count"]),
            max_room_count=int(raw["max_room_count"]),
            target_room_area_m2=float(raw["target_room_area_m2"]),
            min_room_width_m=float(raw["min_room_width_m"]),
            room_function_cycle=cycle,
            unit_group_size=int(raw.get("unit_group_size", 1)),
            max_room_depth_m=min(
                30.0,
                max(4.0, float(raw.get("max_room_depth_m", DEFAULT_ROOM_MAX_DEPTH_M))),
            ),
            max_room_aspect_ratio=min(
                8.0,
                max(1.4, float(raw.get("max_room_aspect_ratio", DEFAULT_ROOM_MAX_ASPECT_RATIO))),
            ),
            layout_template=str(raw.get("layout_template", "auto")),
            spatial_program=FloorSpatialProgram.from_dict(raw.get("spatial_program")),
        )

    @property
    def archetype(self) -> FloorArchetype:
        return FloorArchetype(
            role=self.role,
            preferred_room_count=self.preferred_room_count,
            min_room_count=self.min_room_count,
            max_room_count=self.max_room_count,
            target_room_area_m2=self.target_room_area_m2,
            min_room_width_m=self.min_room_width_m,
            room_function_cycle=self.room_function_cycle,
            unit_group_size=self.unit_group_size,
            max_room_depth_m=self.max_room_depth_m,
            max_room_aspect_ratio=self.max_room_aspect_ratio,
            layout_template=self.layout_template,
            spatial_program=self.spatial_program,
        )

    def validate(self, function: str) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", self.zone_id):
            raise ValueError("vertical zone_id must be a lowercase safe identifier")
        if self.start_level < 0 or self.end_level < self.start_level:
            raise ValueError("vertical zone levels must satisfy 0 <= start <= end")
        if self.use_type not in VERTICAL_USE_TYPES:
            raise ValueError(f"unsupported vertical use_type: {self.use_type}")
        self.archetype.validate(function)


@dataclass(frozen=True)
class FloorSpaceProfile:
    function: str
    archetypes: tuple[FloorArchetype, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FloorSpaceProfile":
        _reject_unknown(data, {"function", "archetypes"}, "FloorSpaceProfile")
        function = str(data["function"])
        return cls(
            function=function,
            archetypes=tuple(
                FloorArchetype.from_dict(item)
                for item in _normalize_floor_archetypes(data["archetypes"], function)
            ),
        )

    def validate(self) -> None:
        roles = [item.role for item in self.archetypes]
        if len(roles) != len(set(roles)):
            raise ValueError(
                f"floor roles must be unique for function {self.function}"
            )
        if not {"ground", "typical"}.issubset(roles):
            raise ValueError(
                f"floor space profile for {self.function} requires ground and typical archetypes"
            )
        for archetype in self.archetypes:
            archetype.validate(self.function)

    def for_role(self, role: str) -> FloorArchetype:
        return next(
            (item for item in self.archetypes if item.role == role),
            next(item for item in self.archetypes if item.role == "typical"),
        )


@dataclass(frozen=True)
class FloorSpaceProgram:
    profiles: tuple[FloorSpaceProfile, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FloorSpaceProgram":
        _reject_unknown(data, {"profiles"}, "FloorSpaceProgram")
        return cls(
            tuple(FloorSpaceProfile.from_dict(item) for item in data["profiles"])
        )

    def validate(self, spec: CitySpec) -> None:
        expected = {zone.function for zone in spec.zones}
        actual = [profile.function for profile in self.profiles]
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise ValueError(
                f"floor space profiles must cover each zone function exactly once: required={sorted(expected)}, "
                f"received={actual}, missing={sorted(expected-set(actual))}. Include shell-only zone functions."
            )
        for profile in self.profiles:
            profile.validate()
            if spec.room_count_strategy == "fixed":
                for archetype in profile.archetypes:
                    counts = {
                        archetype.min_room_count,
                        archetype.preferred_room_count,
                        archetype.max_room_count,
                    }
                    if counts != {spec.rooms_per_floor}:
                        raise ValueError(
                            "fixed room_count_strategy requires every archetype count "
                            "to equal rooms_per_floor"
                        )

    def for_function(self, function: str) -> FloorSpaceProfile:
        return next(item for item in self.profiles if item.function == function)


@dataclass(frozen=True)
class FloorProfile:
    function: str
    layout: str
    corridor_ratio: float
    room_function_cycle: tuple[str, ...]
    space_archetypes: tuple[FloorArchetype, ...] = ()
    vertical_zones: tuple[VerticalFloorZone, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FloorProfile":
        _reject_unknown(
            data,
            {
                "function",
                "layout",
                "corridor_ratio",
                "room_function_cycle",
                "space_archetypes",
                "vertical_zones",
            },
            "FloorProfile",
        )
        function = str(data["function"])
        return cls(
            function=function,
            layout=str(data["layout"]),
            corridor_ratio=float(data["corridor_ratio"]),
            room_function_cycle=_normalize_floor_cycle(data["room_function_cycle"], function),
            space_archetypes=tuple(
                FloorArchetype.from_dict(item)
                for item in _normalize_floor_archetypes(data.get("space_archetypes", []), function)
            ),
            vertical_zones=tuple(
                VerticalFloorZone.from_dict(item, function)
                for item in data.get("vertical_zones", [])
            ),
        )

    def for_role(self, role: str) -> FloorArchetype | None:
        if not self.space_archetypes:
            return None
        return next(
            (item for item in self.space_archetypes if item.role == role),
            next(item for item in self.space_archetypes if item.role == "typical"),
        )

    def zone_for_level(self, level: int) -> VerticalFloorZone | None:
        return next(
            (
                zone
                for zone in self.vertical_zones
                if zone.start_level <= level <= zone.end_level
            ),
            None,
        )


@dataclass(frozen=True)
class FloorProgram:
    profiles: tuple[FloorProfile, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FloorProgram":
        _reject_unknown(data, {"profiles"}, "FloorProgram")
        return cls(tuple(FloorProfile.from_dict(item) for item in data["profiles"]))

    def validate(self, spec: CitySpec) -> None:
        expected = {zone.function for zone in spec.zones}
        actual = [profile.function for profile in self.profiles]
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise ValueError("floor profiles must cover each zone function exactly once; "
                f"expected {len(expected)} profiles for unique functions {sorted(expected)}, got {actual}. "
                "Multiple districts with the same function share ONE profile, not one profile per district. "
                "Preserve their room uses via ground/typical semantic cycles; do not duplicate a function.")
        for profile in self.profiles:
            if profile.layout not in FLOOR_LAYOUTS:
                raise ValueError(f"unsupported floor layout: {profile.layout}")
            if not 0.12 <= profile.corridor_ratio <= 0.30:
                raise ValueError("corridor_ratio must be within [0.12, 0.30]")
            if not profile.room_function_cycle:
                raise ValueError("room_function_cycle must not be empty")
            allowed = set(ROOM_FUNCTIONS.get(profile.function, ROOM_FUNCTIONS["mixed_use"]))
            unsupported = sorted(set(profile.room_function_cycle) - allowed)
            if unsupported:
                raise ValueError(
                    f"unsupported room functions for {profile.function}: {', '.join(unsupported)}; "
                    f"allowed functions: {', '.join(sorted(allowed))}"
                )
            roles = [item.role for item in profile.space_archetypes]
            if len(roles) != len(set(roles)):
                raise ValueError(
                    f"floor roles must be unique for function {profile.function}"
                )
            if profile.space_archetypes and not {"ground", "typical"}.issubset(roles):
                raise ValueError(
                    f"floor profile for {profile.function} requires ground and typical archetypes"
                )
            for archetype in profile.space_archetypes:
                archetype.validate(profile.function)
            zone_ids = [zone.zone_id for zone in profile.vertical_zones]
            if len(zone_ids) != len(set(zone_ids)):
                raise ValueError(
                    f"vertical zone IDs must be unique for function {profile.function}"
                )
            previous_end = -1
            for zone in profile.vertical_zones:
                zone.validate(profile.function)
                if zone.start_level != previous_end + 1:
                    raise ValueError(
                        f"vertical zones for {profile.function} must be ordered and contiguous"
                    )
                previous_end = zone.end_level

    def for_function(self, function: str) -> FloorProfile:
        return next(item for item in self.profiles if item.function == function)


@dataclass(frozen=True)
class SkylineProfile:
    function: str
    min_floors: int
    max_floors: int
    centrality_bias: str
    height_role: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkylineProfile":
        _reject_unknown(
            data,
            {
                "function",
                "min_floors",
                "max_floors",
                "centrality_bias",
                "height_role",
            },
            "SkylineProfile",
        )
        return cls(
            function=str(data["function"]),
            min_floors=int(data["min_floors"]),
            max_floors=int(data["max_floors"]),
            centrality_bias=str(data["centrality_bias"]),
            height_role=str(data["height_role"]),
        )


@dataclass(frozen=True)
class SkylineProgram:
    profiles: tuple[SkylineProfile, ...]
    highrise_ratio: float
    landmark_count: int
    landmark_functions: tuple[str, ...]
    skyline_strength: float = 0.75

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkylineProgram":
        _reject_unknown(
            data,
            {
                "profiles",
                "highrise_ratio",
                "landmark_count",
                "landmark_functions",
                "skyline_strength",
            },
            "SkylineProgram",
        )
        return cls(
            profiles=tuple(
                SkylineProfile.from_dict(item) for item in data["profiles"]
            ),
            highrise_ratio=float(data["highrise_ratio"]),
            landmark_count=int(data["landmark_count"]),
            landmark_functions=tuple(
                str(item) for item in data["landmark_functions"]
            ),
            skyline_strength=float(data.get("skyline_strength", 0.75)),
        )

    def validate(self, spec: CitySpec) -> None:
        expected = {zone.function for zone in spec.zones}
        actual = [profile.function for profile in self.profiles]
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise ValueError(
                "skyline profiles must cover each zone function exactly once"
            )
        for profile in self.profiles:
            if not (
                spec.min_floors
                <= profile.min_floors
                <= profile.max_floors
                <= spec.max_floors
            ):
                raise ValueError(
                    f"skyline floor range for {profile.function} exceeds CitySpec"
                )
            if profile.centrality_bias not in HEIGHT_CENTRALITY_BIASES:
                raise ValueError("unsupported skyline centrality_bias")
            if profile.height_role not in HEIGHT_ROLES:
                raise ValueError("unsupported skyline height_role")
        if not 0.0 <= self.highrise_ratio <= 0.5:
            raise ValueError("skyline highrise_ratio must be within [0, 0.5]")
        if not 0 <= self.landmark_count <= min(10, spec.building_count):
            raise ValueError("skyline landmark_count exceeds the city budget")
        if (
            len(self.landmark_functions) != len(set(self.landmark_functions))
            or not set(self.landmark_functions).issubset(expected)
        ):
            raise ValueError("landmark_functions must be unique known functions")
        if self.landmark_count and not self.landmark_functions:
            raise ValueError("landmark_count requires at least one landmark function")
        if (
            (self.highrise_ratio > 0 or self.landmark_count > 0)
            and (
                spec.max_floors < 10
                or spec.max_floors - spec.min_floors < 5
            )
        ):
            raise ValueError(
                "highrise or landmark planning requires a feasible global floor range"
            )
        if not 0.0 <= self.skyline_strength <= 1.0:
            raise ValueError("skyline_strength must be within [0, 1]")

    def for_function(self, function: str) -> SkylineProfile:
        return next(item for item in self.profiles if item.function == function)


@dataclass(frozen=True)
class HierarchicalProgram:
    urban: UrbanProgram
    building: BuildingProgram
    floor: FloorProgram
    skyline: SkylineProgram | None = None

    def validate(self, spec: CitySpec) -> None:
        self.urban.validate(spec)
        self.building.validate(spec)
        self.floor.validate(spec)
        if self.skyline is not None:
            self.skyline.validate(spec)
