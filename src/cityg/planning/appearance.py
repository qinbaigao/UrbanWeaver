"""Structured, deterministic urban appearance programs.

The appearance program is the boundary between an LLM/VLM appearance planner
and the geometry compiler.  It deliberately contains style and density
decisions, not world coordinates.  The compiler remains responsible for
placing every object on a valid road, sidewalk, parcel, or landscape site.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any


@dataclass(frozen=True)
class RoadAppearanceProfile:
    """Visual and snapshot-population policy for one road class."""

    road_class: str
    lane_markings: bool = True
    crosswalks: bool = True
    curbs: bool = True
    tree_spacing_m: float = 18.0
    street_light_spacing_m: float = 28.0
    vehicle_spacing_m: float = 34.0
    pedestrian_spacing_m: float = 24.0
    parking_ratio: float = 0.20
    street_furniture: bool = True

    def __post_init__(self) -> None:
        for name in (
            "tree_spacing_m",
            "street_light_spacing_m",
            "vehicle_spacing_m",
            "pedestrian_spacing_m",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if not 0.0 <= self.parking_ratio <= 1.0:
            raise ValueError("parking_ratio must be within [0, 1]")

    def to_dict(self) -> dict[str, Any]:
        return {
            "road_class": self.road_class,
            "lane_markings": self.lane_markings,
            "crosswalks": self.crosswalks,
            "curbs": self.curbs,
            "tree_spacing_m": self.tree_spacing_m,
            "street_light_spacing_m": self.street_light_spacing_m,
            "vehicle_spacing_m": self.vehicle_spacing_m,
            "pedestrian_spacing_m": self.pedestrian_spacing_m,
            "parking_ratio": self.parking_ratio,
            "street_furniture": self.street_furniture,
        }


@dataclass(frozen=True)
class LandscapeAppearanceProfile:
    """A high-level landscape intent consumed by the deterministic compiler."""

    style: str
    tree_density: float = 0.0008
    shrub_density: float = 0.0015
    seating_count: int = 2
    feature: str | None = None
    density_tier: str = "standard"
    flower_density: float = 0.0
    hedge_density: float = 0.0

    def __post_init__(self) -> None:
        if self.tree_density < 0 or self.shrub_density < 0 or self.flower_density < 0 or self.hedge_density < 0:
            raise ValueError("Landscape densities must be non-negative")
        if self.seating_count < 0:
            raise ValueError("seating_count must be non-negative")
        if self.density_tier not in {"sparse", "standard", "lush"}:
            raise ValueError("density_tier must be sparse, standard, or lush")

    def to_dict(self) -> dict[str, Any]:
        return {
            "style": self.style,
            "tree_density": self.tree_density,
            "shrub_density": self.shrub_density,
            "seating_count": self.seating_count,
            "feature": self.feature,
            "density_tier": self.density_tier,
            "flower_density": self.flower_density,
            "hedge_density": self.hedge_density,
        }


@dataclass(frozen=True)
class UrbanAppearanceProgram:
    """Serializable appearance contract for a whole city."""

    version: str = "urban_appearance.v1"
    time_of_day: str = "day"
    road_profiles: tuple[RoadAppearanceProfile, ...] = ()
    landscape_profiles: tuple[LandscapeAppearanceProfile, ...] = ()
    vehicle_mix: tuple[str, ...] = ("sedan", "suv", "van", "bus")
    pedestrian_mix: tuple[str, ...] = ("walk", "stand", "cycle")

    def profile_for_road(self, road_class: str) -> RoadAppearanceProfile:
        profiles = {item.road_class: item for item in self.road_profiles}
        return profiles.get(road_class, profiles.get("local", _default_road("local")))

    def profile_for_landscape(self, style: str, density_tier: str | None = None) -> LandscapeAppearanceProfile:
        profiles = {item.style: item for item in self.landscape_profiles}
        profile = profiles.get(style, profiles.get("park", _default_landscape("park")))
        if density_tier is None or str(density_tier) == profile.density_tier:
            return profile
        tier = str(density_tier).lower()
        if tier not in {"sparse", "standard", "lush"}:
            return profile
        factors = {
            "sparse": (0.68, 0.60, 0.70, 0.55),
            "standard": (1.0, 1.0, 1.0, 1.0),
            "lush": (1.35, 1.45, 1.35, 1.55),
        }
        current = factors.get(profile.density_tier, (1.0, 1.0, 1.0, 1.0))
        target = factors[tier]
        return replace(
            profile,
            density_tier=tier,
            tree_density=profile.tree_density * target[0] / current[0],
            shrub_density=profile.shrub_density * target[1] / current[1],
            seating_count=max(0, round(profile.seating_count * target[2] / current[2])),
            flower_density=profile.flower_density * target[3] / current[3],
            hedge_density=profile.hedge_density * target[3] / current[3],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "time_of_day": self.time_of_day,
            "road_profiles": [item.to_dict() for item in self.road_profiles],
            "landscape_profiles": [item.to_dict() for item in self.landscape_profiles],
            "vehicle_mix": list(self.vehicle_mix),
            "pedestrian_mix": list(self.pedestrian_mix),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UrbanAppearanceProgram":
        base = default_urban_appearance_program()
        road_defaults = {item.road_class: item for item in base.road_profiles}
        roads: list[RoadAppearanceProfile] = []
        for raw in data.get("road_profiles", []):
            if not isinstance(raw, dict) or not raw.get("road_class"):
                continue
            key = str(raw["road_class"])
            current = road_defaults.get(key, _default_road(key))
            values = {name: raw[name] for name in current.__dataclass_fields__ if name in raw}
            try:
                roads.append(replace(current, **values))
            except (TypeError, ValueError):
                roads.append(current)
        if not roads:
            roads = list(base.road_profiles)
        landscape_defaults = {item.style: item for item in base.landscape_profiles}
        landscapes: list[LandscapeAppearanceProfile] = []
        for raw in data.get("landscape_profiles", []):
            if not isinstance(raw, dict) or not raw.get("style"):
                continue
            key = str(raw["style"])
            current = landscape_defaults.get(key, _default_landscape(key))
            values = {name: raw[name] for name in current.__dataclass_fields__ if name in raw}
            try:
                landscapes.append(replace(current, **values))
            except (TypeError, ValueError):
                landscapes.append(current)
        if not landscapes:
            landscapes = list(base.landscape_profiles)
        return cls(
            version=str(data.get("version", base.version)),
            time_of_day=str(data.get("time_of_day", base.time_of_day)),
            road_profiles=tuple(roads),
            landscape_profiles=tuple(landscapes),
            vehicle_mix=tuple(str(item) for item in data.get("vehicle_mix", base.vehicle_mix)),
            pedestrian_mix=tuple(str(item) for item in data.get("pedestrian_mix", base.pedestrian_mix)),
        )


def _default_road(road_class: str) -> RoadAppearanceProfile:
    values = {
        "arterial": dict(tree_spacing_m=24.0, street_light_spacing_m=30.0, vehicle_spacing_m=24.0, pedestrian_spacing_m=24.0, parking_ratio=0.0),
        "collector": dict(tree_spacing_m=15.0, street_light_spacing_m=24.0, vehicle_spacing_m=28.0, pedestrian_spacing_m=18.0, parking_ratio=0.12),
        "local": dict(tree_spacing_m=18.0, street_light_spacing_m=30.0, vehicle_spacing_m=38.0, pedestrian_spacing_m=28.0, parking_ratio=0.28),
        "service": dict(tree_spacing_m=22.0, street_light_spacing_m=36.0, vehicle_spacing_m=48.0, pedestrian_spacing_m=36.0, parking_ratio=0.18, crosswalks=False),
        "shared_space": dict(tree_spacing_m=14.0, street_light_spacing_m=22.0, vehicle_spacing_m=44.0, pedestrian_spacing_m=12.0, parking_ratio=0.10),
    }
    return RoadAppearanceProfile(road_class=road_class, **values.get(road_class, {}))


def _default_landscape(style: str) -> LandscapeAppearanceProfile:
    values = {
        # Public-space defaults are intentionally fuller than the original
        # sparse prototype.  They still use hard caps in the compiler so a
        # large site cannot become an impenetrable forest.
        "park": dict(tree_density=0.00135, shrub_density=0.0034, seating_count=6, feature="playground", density_tier="lush", flower_density=0.0010, hedge_density=0.0008),
        "garden": dict(tree_density=0.0018, shrub_density=0.0042, seating_count=4, feature="flower_bed", density_tier="lush", flower_density=0.0018, hedge_density=0.0012),
        "plaza": dict(tree_density=0.00035, shrub_density=0.0010, seating_count=8, feature="fountain", density_tier="standard", flower_density=0.0007, hedge_density=0.00045),
    }
    return LandscapeAppearanceProfile(style=style, **values.get(style, {}))


def default_urban_appearance_program() -> UrbanAppearanceProgram:
    return UrbanAppearanceProgram(
        road_profiles=tuple(_default_road(item) for item in ("collector", "local", "service", "shared_space")),
        landscape_profiles=tuple(_default_landscape(item) for item in ("park", "garden", "plaza")),
    )


def appearance_program_for_city(city: Any) -> UrbanAppearanceProgram:
    """Read an optional agent-authored program with a safe deterministic fallback."""

    raw = getattr(city, "metadata", {}).get("urban_appearance_program")
    if isinstance(raw, dict):
        return UrbanAppearanceProgram.from_dict(raw)
    return default_urban_appearance_program()


__all__ = [
    "LandscapeAppearanceProfile",
    "RoadAppearanceProfile",
    "UrbanAppearanceProgram",
    "appearance_program_for_city",
    "default_urban_appearance_program",
]
