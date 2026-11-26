"""Context-aware street programs between city planning and geometry.

The program is deliberately semantic: an LLM may choose street archetypes,
activity levels, frontage treatments, and amenities, while the deterministic
compiler remains solely responsible for metric coordinates and clearance.
When no agent-authored program exists, :class:`StreetProgramPlanner` derives a
stable fallback from the realized road network and each building's nearest
street frontage.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from typing import Any

from cityg.planning.appearance import UrbanAppearanceProgram
from cityg.schemas import Building, City, Point2D, RoadSegment


STREET_ARCHETYPES = frozenset(
    {
        "commercial_main_street",
        "boulevard_arterial",
        "residential_green_street",
        "civic_avenue",
        "industrial_service_street",
        "pedestrian_shared_street",
        "urban_connector",
        "neighborhood_street",
    }
)
STREET_AMENITY_TYPES = frozenset(
    {
        "planter",
        "bench",
        "bicycle_rack",
        "shop_sign",
        "cafe_terrace",
        "bus_stop",
        "fire_hydrant",
        "bollard",
        "small_sign",
        "loading_bay",
    }
)
STREET_ACTIVITY_LEVELS = frozenset({"low", "medium", "high"})
STREET_ACTIVITY_MODES = frozenset(
    {
        "commute_flow",
        "retail_browsing",
        "cafe_dwell",
        "transit_waiting",
        "intersection_waiting",
        "cycle_flow",
        "loading_service",
        "residential_stroll",
    }
)
STREET_FRONTAGE_TREATMENTS = frozenset(
    {"retail", "residential", "civic", "industrial", "mixed"}
)
STREET_PLACEMENT_PATTERNS = frozenset(
    {"formal", "staggered", "clustered", "organic", "sparse"}
)
STREET_LIGHT_FAMILIES = frozenset(
    {"modern_led", "curved", "square", "heritage", "pedestrian_scale"}
)
STREET_TREE_TYPES = frozenset(
    {"deciduous", "broadleaf", "columnar", "ornamental", "evergreen"}
)
_SIDES = {"left", "right"}


@dataclass(frozen=True)
class StreetSegmentProgram:
    """Semantic and cross-section policy for one realized road segment."""

    road_id: str
    archetype: str
    dominant_function: str
    activity_level: str
    frontage_treatment: str
    activity_modes: tuple[str, ...] = ()
    activity_cluster_count: int = 0
    adjacent_building_ids: tuple[str, ...] = ()
    tree_spacing_m: float = 18.0
    street_light_spacing_m: float = 28.0
    vehicle_spacing_m: float = 34.0
    pedestrian_spacing_m: float = 24.0
    parking_sides: tuple[str, ...] = ()
    bicycle_lane_sides: tuple[str, ...] = ()
    amenity_types: tuple[str, ...] = ()
    furnishing_strip_width_m: float = 0.62
    frontage_strip_width_m: float = 0.42
    placement_pattern: str = "organic"
    tree_palette: tuple[str, ...] = ("deciduous", "columnar")
    light_family: str = "modern_led"
    source: str = "deterministic_context"

    def __post_init__(self) -> None:
        if not self.road_id or not self.archetype:
            raise ValueError("road_id and archetype must be non-empty")
        if self.archetype not in STREET_ARCHETYPES:
            raise ValueError("unsupported street archetype")
        if self.activity_level not in STREET_ACTIVITY_LEVELS:
            raise ValueError("unsupported activity_level")
        if not set(self.activity_modes).issubset(STREET_ACTIVITY_MODES):
            raise ValueError("unsupported activity_modes")
        if len(self.activity_modes) != len(set(self.activity_modes)):
            raise ValueError("activity_modes must not contain duplicates")
        if not isinstance(self.activity_cluster_count, int) or not 0 <= self.activity_cluster_count <= 6:
            raise ValueError("activity_cluster_count must be an integer within [0, 6]")
        if self.frontage_treatment not in STREET_FRONTAGE_TREATMENTS:
            raise ValueError("unsupported frontage_treatment")
        if self.placement_pattern not in STREET_PLACEMENT_PATTERNS:
            raise ValueError("unsupported placement_pattern")
        if self.light_family not in STREET_LIGHT_FAMILIES:
            raise ValueError("unsupported light_family")
        if not self.tree_palette or not set(self.tree_palette).issubset(
            STREET_TREE_TYPES
        ):
            raise ValueError("tree_palette must contain supported tree types")
        if len(self.tree_palette) != len(set(self.tree_palette)):
            raise ValueError("tree_palette must not contain duplicates")
        if not set(self.amenity_types).issubset(STREET_AMENITY_TYPES):
            raise ValueError("unsupported amenity_types")
        bounds = {
            "tree_spacing_m": (6.0, 200.0),
            "street_light_spacing_m": (8.0, 200.0),
            "vehicle_spacing_m": (10.0, 300.0),
            "pedestrian_spacing_m": (6.0, 200.0),
            "furnishing_strip_width_m": (0.20, 2.0),
            "frontage_strip_width_m": (0.20, 2.0),
        }
        for name, (minimum, maximum) in bounds.items():
            value = float(getattr(self, name))
            if not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError(f"{name} must be finite and within [{minimum}, {maximum}]")
        if not set(self.parking_sides).issubset(_SIDES):
            raise ValueError("parking_sides must contain left/right only")
        if not set(self.bicycle_lane_sides).issubset(_SIDES):
            raise ValueError("bicycle_lane_sides must contain left/right only")
        if set(self.parking_sides) & set(self.bicycle_lane_sides):
            raise ValueError("parking and bicycle lanes cannot occupy the same side")
        for name in ("parking_sides", "bicycle_lane_sides", "amenity_types"):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must not contain duplicates")

    def to_dict(self) -> dict[str, Any]:
        return {
            "road_id": self.road_id,
            "archetype": self.archetype,
            "dominant_function": self.dominant_function,
            "activity_level": self.activity_level,
            "frontage_treatment": self.frontage_treatment,
            "activity_modes": list(self.activity_modes),
            "activity_cluster_count": self.activity_cluster_count,
            "adjacent_building_ids": list(self.adjacent_building_ids),
            "tree_spacing_m": self.tree_spacing_m,
            "street_light_spacing_m": self.street_light_spacing_m,
            "vehicle_spacing_m": self.vehicle_spacing_m,
            "pedestrian_spacing_m": self.pedestrian_spacing_m,
            "parking_sides": list(self.parking_sides),
            "bicycle_lane_sides": list(self.bicycle_lane_sides),
            "amenity_types": list(self.amenity_types),
            "furnishing_strip_width_m": self.furnishing_strip_width_m,
            "frontage_strip_width_m": self.frontage_strip_width_m,
            "placement_pattern": self.placement_pattern,
            "tree_palette": list(self.tree_palette),
            "light_family": self.light_family,
            "source": self.source,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        fallback: "StreetSegmentProgram | None" = None,
    ) -> "StreetSegmentProgram":
        if fallback is None:
            fallback = cls(
                road_id=str(data.get("road_id", "unknown_road")),
                archetype="neighborhood_street",
                dominant_function="mixed",
                activity_level="medium",
                frontage_treatment="mixed",
            )
        values: dict[str, Any] = {}
        sequence_fields = {
            "adjacent_building_ids",
            "parking_sides",
            "bicycle_lane_sides",
            "amenity_types",
            "tree_palette",
            "activity_modes",
        }
        numeric_fields = {
            "tree_spacing_m",
            "street_light_spacing_m",
            "vehicle_spacing_m",
            "pedestrian_spacing_m",
            "furnishing_strip_width_m",
            "frontage_strip_width_m",
        }
        for name in fallback.__dataclass_fields__:
            if name not in data:
                continue
            value = data[name]
            if name in sequence_fields:
                if isinstance(value, str):
                    value = (value,)
                elif isinstance(value, (list, tuple)):
                    value = tuple(str(item) for item in value)
                else:
                    value = getattr(fallback, name)
            elif name in numeric_fields:
                value = float(value)
            elif name == "activity_cluster_count":
                value = int(value)
            values[name] = value
        values["road_id"] = fallback.road_id
        values["source"] = str(data.get("source", "agent_authored"))
        return replace(fallback, **values)


@dataclass(frozen=True)
class StreetNetworkProgram:
    version: str = "street_network_program.v1"
    segments: tuple[StreetSegmentProgram, ...] = ()

    def for_road(self, road_id: str) -> StreetSegmentProgram:
        for segment in self.segments:
            if segment.road_id == road_id:
                return segment
        raise KeyError(road_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "segments": [segment.to_dict() for segment in self.segments],
        }


class StreetProgramPlanner:
    """Plan street character after actual roads and buildings are available."""

    @staticmethod
    def _seed(*values: str) -> int:
        digest = hashlib.sha256("|".join(values).encode("utf-8")).digest()
        return int.from_bytes(digest[:4], "big")

    @staticmethod
    def _distance_to_segment(point: Point2D, road: RoadSegment) -> float:
        from cityg.ccwp import point_segment_distance
        return point_segment_distance(point, road.centerline)

    @staticmethod
    def _function(value: str) -> str:
        normalized = value.lower().strip()
        if normalized in {"public_service", "public", "education", "healthcare"}:
            return "civic"
        if normalized in {"mixed-use", "mixed_use"}:
            return "mixed_use"
        if normalized in {"office", "retail"}:
            return "commercial"
        return normalized or "mixed"

    def _nearest_street_buildings(
        self, city: City
    ) -> dict[str, list[Building]]:
        assignments: dict[str, list[Building]] = defaultdict(list)
        roads = list(city.road_network.segments)
        for building in city.iter_buildings():
            if not roads:
                break
            ranked = sorted(
                (
                    self._distance_to_segment(building.entrance, road),
                    road.id,
                    road,
                )
                for road in roads
            )
            distance, _road_id, road = ranked[0]
            # Avoid inventing frontage connections across unusually large
            # undeveloped parcels. Such buildings remain visible but unassigned.
            if distance <= road.width_m / 2 + road.sidewalk_width_m + 24.0:
                assignments[road.id].append(building)
        return assignments

    def plan(
        self,
        city: City,
        appearance: UrbanAppearanceProgram,
    ) -> StreetNetworkProgram:
        assignments = self._nearest_street_buildings(city)
        fallback_segments = tuple(
            self._plan_segment(road, assignments.get(road.id, ()), appearance)
            for road in city.road_network.segments
        )
        fallbacks = {segment.road_id: segment for segment in fallback_segments}
        raw = city.metadata.get("street_network_program")
        if not isinstance(raw, dict):
            return StreetNetworkProgram(segments=fallback_segments)
        overrides = {
            str(item.get("road_id")): item
            for item in raw.get("segments", ())
            if isinstance(item, dict) and item.get("road_id") in fallbacks
        }
        merged: list[StreetSegmentProgram] = []
        for road in city.road_network.segments:
            fallback = fallbacks[road.id]
            override = overrides.get(road.id)
            if override is None:
                merged.append(fallback)
                continue
            try:
                merged.append(StreetSegmentProgram.from_dict(override, fallback=fallback))
            except (TypeError, ValueError):
                merged.append(fallback)
        return StreetNetworkProgram(
            version=str(raw.get("version", "street_network_program.v1")),
            segments=tuple(merged),
        )

    def _plan_segment(
        self,
        road: RoadSegment,
        buildings: tuple[Building, ...] | list[Building],
        appearance: UrbanAppearanceProgram,
    ) -> StreetSegmentProgram:
        functions = [self._function(building.function) for building in buildings]
        counts = Counter(functions)
        dominant = (
            sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
            if counts
            else "mixed"
        )
        profile = appearance.profile_for_road(road.road_class)

        if road.road_class == "arterial":
            archetype = "boulevard_arterial"
            dominant = dominant if dominant != "mixed" else "mixed_use"
        elif road.road_class == "shared_space":
            archetype = "pedestrian_shared_street"
            dominant = dominant if dominant != "mixed" else "commercial"
        elif road.road_class == "service" or dominant == "industrial":
            archetype = "industrial_service_street"
        elif dominant in {"commercial", "mixed_use"}:
            archetype = "commercial_main_street"
        elif dominant == "residential":
            archetype = "residential_green_street"
        elif dominant == "civic":
            archetype = "civic_avenue"
        elif road.road_class == "collector":
            archetype = "urban_connector"
        else:
            archetype = "neighborhood_street"

        settings = {
            "boulevard_arterial": (1.45, 0.92, 0.68, 0.88, "medium", "mixed"),
            "commercial_main_street": (0.92, 0.82, 0.84, 0.58, "high", "retail"),
            "residential_green_street": (0.82, 1.02, 1.18, 1.02, "medium", "residential"),
            "civic_avenue": (0.86, 0.82, 0.92, 0.72, "high", "civic"),
            "industrial_service_street": (1.45, 1.10, 0.88, 1.75, "low", "industrial"),
            "pedestrian_shared_street": (0.78, 0.82, 1.65, 0.52, "high", "retail"),
            "urban_connector": (1.10, 0.92, 0.82, 1.20, "medium", "mixed"),
            "neighborhood_street": (1.00, 1.05, 1.20, 1.12, "low", "mixed"),
        }
        tree_factor, light_factor, vehicle_factor, pedestrian_factor, activity, frontage = settings[archetype]

        rhythm = {
            "boulevard_arterial": (
                "staggered", ("columnar", "deciduous", "ornamental"), "modern_led"
            ),
            "commercial_main_street": (
                "clustered", ("deciduous", "ornamental", "columnar"), "modern_led"
            ),
            "residential_green_street": (
                "organic", ("deciduous", "broadleaf", "ornamental"), "curved"
            ),
            "civic_avenue": (
                "staggered", ("columnar", "deciduous"), "square"
            ),
            "industrial_service_street": (
                "sparse", ("columnar", "evergreen"), "modern_led"
            ),
            "pedestrian_shared_street": (
                "clustered", ("ornamental", "deciduous"), "pedestrian_scale"
            ),
            "urban_connector": (
                "staggered", ("deciduous", "columnar"), "modern_led"
            ),
            "neighborhood_street": (
                "organic", ("deciduous", "broadleaf"), "curved"
            ),
        }
        placement_pattern, tree_palette, light_family = rhythm[archetype]
        light_options = {
            "boulevard_arterial": ("modern_led", "square"),
            "commercial_main_street": ("modern_led", "pedestrian_scale"),
            "residential_green_street": ("curved", "heritage"),
            "civic_avenue": ("square", "heritage"),
            "industrial_service_street": ("modern_led",),
            "pedestrian_shared_street": ("pedestrian_scale", "heritage"),
            "urban_connector": ("modern_led", "square"),
            "neighborhood_street": ("curved", "heritage", "pedestrian_scale"),
        }[archetype]
        light_family = light_options[
            self._seed(road.id, archetype, "light_family") % len(light_options)
        ]

        parking: tuple[str, ...] = ()
        bicycle: tuple[str, ...] = ()
        if archetype == "residential_green_street" and road.road_class == "local":
            parking = ("left", "right")
        elif archetype == "commercial_main_street" and road.road_class == "local":
            parking = (
                "left" if self._seed(road.id, "parking") % 2 == 0 else "right",
            )
        elif archetype == "industrial_service_street":
            parking = ("right",)
        elif road.road_class == "arterial" and road.bike_lane:
            bicycle = ("left", "right")
        elif (
            road.road_class == "collector"
            and road.width_m >= 11.0
            and archetype in {"commercial_main_street", "civic_avenue", "urban_connector"}
        ):
            bicycle = ("left", "right")

        amenities = {
            "boulevard_arterial": ("small_sign", "bus_stop", "bicycle_rack", "planter"),
            "commercial_main_street": (
                "planter",
                "bicycle_rack",
                "shop_sign",
                "small_sign",
                "cafe_terrace",
            ),
            "residential_green_street": ("planter", "bench", "fire_hydrant"),
            "civic_avenue": ("planter", "bench", "bicycle_rack", "small_sign", "bus_stop"),
            "industrial_service_street": ("bollard", "loading_bay"),
            "pedestrian_shared_street": ("planter", "bollard", "cafe_terrace"),
            "urban_connector": ("small_sign", "bus_stop"),
            "neighborhood_street": ("bench",),
        }[archetype]
        if road.road_class not in {"collector", "arterial"}:
            amenities = tuple(item for item in amenities if item != "bus_stop")

        activity_modes = {
            "boulevard_arterial": (
                "commute_flow",
                "intersection_waiting",
                "transit_waiting",
                "cycle_flow",
            ),
            "commercial_main_street": (
                "retail_browsing",
                "cafe_dwell",
                "commute_flow",
                "intersection_waiting",
            ),
            "residential_green_street": (
                "residential_stroll",
                "commute_flow",
            ),
            "civic_avenue": (
                "transit_waiting",
                "intersection_waiting",
                "commute_flow",
                "cycle_flow",
            ),
            "industrial_service_street": (
                "loading_service",
                "commute_flow",
            ),
            "pedestrian_shared_street": (
                "retail_browsing",
                "cafe_dwell",
                "residential_stroll",
                "cycle_flow",
            ),
            "urban_connector": (
                "commute_flow",
                "intersection_waiting",
                "cycle_flow",
            ),
            "neighborhood_street": ("residential_stroll",),
        }[archetype]
        if "bus_stop" not in amenities:
            activity_modes = tuple(
                item for item in activity_modes if item != "transit_waiting"
            )
        if not bicycle and road.road_class != "shared_space":
            activity_modes = tuple(
                item for item in activity_modes if item != "cycle_flow"
            )
        if road.road_class == "arterial" and "bus_stop" not in amenities:
            activity_modes = tuple(item for item in activity_modes if item != "transit_waiting")
        if not road.parking_allowed:
            parking = ()
        activity_cluster_count = {
            "low": 1,
            "medium": 2,
            "high": 4,
        }[activity]

        return StreetSegmentProgram(
            road_id=road.id,
            archetype=archetype,
            dominant_function=dominant,
            activity_level=activity,
            frontage_treatment=frontage,
            activity_modes=activity_modes,
            activity_cluster_count=min(activity_cluster_count, len(activity_modes)),
            adjacent_building_ids=tuple(sorted(building.id for building in buildings)),
            tree_spacing_m=max(8.0, profile.tree_spacing_m * tree_factor),
            street_light_spacing_m=max(12.0, profile.street_light_spacing_m * light_factor),
            vehicle_spacing_m=max(16.0, profile.vehicle_spacing_m * vehicle_factor),
            pedestrian_spacing_m=max(8.0, profile.pedestrian_spacing_m * pedestrian_factor),
            parking_sides=parking,
            bicycle_lane_sides=bicycle,
            amenity_types=amenities,
            furnishing_strip_width_m=min(0.78, max(0.42, road.sidewalk_width_m * 0.32)),
            frontage_strip_width_m=min(0.58, max(0.30, road.sidewalk_width_m * 0.22)),
            placement_pattern=placement_pattern,
            tree_palette=tree_palette,
            light_family=light_family,
        )


__all__ = [
    "STREET_ACTIVITY_LEVELS",
    "STREET_ACTIVITY_MODES",
    "STREET_AMENITY_TYPES",
    "STREET_ARCHETYPES",
    "STREET_FRONTAGE_TREATMENTS",
    "STREET_PLACEMENT_PATTERNS",
    "STREET_LIGHT_FAMILIES",
    "STREET_TREE_TYPES",
    "StreetNetworkProgram",
    "StreetProgramPlanner",
    "StreetSegmentProgram",
]
