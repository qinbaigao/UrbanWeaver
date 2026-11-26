"""A small, versioned catalog of composable building archetypes.

The catalog is intentionally metadata-only.  An archetype describes a valid
combination of a massing grammar, facade style and optional ornament kits; it
does not replace the canonical ``Building``/``Floor``/``Room`` hierarchy with
an opaque mesh.  This keeps the catalog usable by OpenUSD, the portable viewer
and the CPU interaction validator alike.

The initial catalog reuses the visual grammars already shipped by CityG.  It is
therefore safe to enable immediately, while leaving room for future polygonal
floor plates and downloaded/generated facade modules.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class BuildingArchetype:
    """A feasible visual/structural building family entry."""

    archetype_id: str
    family: str
    massing_style: str
    massing_signature: str
    compatible_functions: tuple[str, ...]
    facade_style_ids: tuple[str, ...]
    massing_variant: str | None = None
    massing_parameters: tuple[tuple[str, float], ...] = ()
    ornament_kit_ids: tuple[str, ...] = ()
    prototype_ids: tuple[str, ...] = ()
    min_floors: int = 1
    max_floors: int = 80
    min_width_m: float = 8.0
    max_width_m: float = 100.0
    min_depth_m: float = 8.0
    max_depth_m: float = 100.0
    highrise_only: bool = False
    landmark_only: bool = False
    preferred_frontage_roles: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.archetype_id.strip():
            raise ValueError("archetype_id must be non-empty")
        if not self.massing_style.strip() or not self.massing_signature.strip():
            raise ValueError("massing_style and massing_signature must be non-empty")
        if not self.compatible_functions:
            raise ValueError("an archetype must support at least one function")
        if not self.facade_style_ids:
            raise ValueError("an archetype must provide at least one facade style")
        if self.min_floors < 1 or self.max_floors < self.min_floors:
            raise ValueError("invalid archetype floor range")
        for name in ("min_width_m", "max_width_m", "min_depth_m", "max_depth_m"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.max_width_m < self.min_width_m or self.max_depth_m < self.min_depth_m:
            raise ValueError("invalid archetype footprint range")

    @property
    def is_highrise(self) -> bool:
        return self.highrise_only or self.min_floors >= 10

    def supports(self, function: str, floor_count: int, width_m: float, depth_m: float) -> bool:
        """Return whether hard geometric/semantic constraints are satisfied."""

        if function not in self.compatible_functions:
            return False
        if not self.min_floors <= floor_count <= self.max_floors:
            return False
        if not self.min_width_m <= width_m <= self.max_width_m:
            return False
        if not self.min_depth_m <= depth_m <= self.max_depth_m:
            return False
        if self.highrise_only and floor_count < 10:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _a(
    archetype_id: str,
    family: str,
    massing_style: str,
    signature: str,
    functions: Iterable[str],
    facades: Iterable[str],
    *,
    massing_variant: str | None = None,
    massing_parameters: dict[str, float] | None = None,
    ornaments: Iterable[str] = (),
    prototypes: Iterable[str] = (),
    floors: tuple[int, int] = (1, 80),
    width: tuple[float, float] = (8.0, 100.0),
    depth: tuple[float, float] = (8.0, 100.0),
    highrise_only: bool = False,
    landmark_only: bool = False,
    frontage_roles: Iterable[str] = (),
) -> BuildingArchetype:
    return BuildingArchetype(
        archetype_id=archetype_id,
        family=family,
        massing_style=massing_style,
        massing_signature=signature,
        massing_variant=massing_variant,
        massing_parameters=tuple(
            (str(key), float(value))
            for key, value in sorted((massing_parameters or {}).items())
        ),
        compatible_functions=tuple(functions),
        facade_style_ids=tuple(facades),
        ornament_kit_ids=tuple(ornaments),
        prototype_ids=tuple(prototypes),
        min_floors=floors[0],
        max_floors=floors[1],
        min_width_m=width[0],
        max_width_m=width[1],
        min_depth_m=depth[0],
        max_depth_m=depth[1],
        highrise_only=highrise_only,
        landmark_only=landmark_only,
        preferred_frontage_roles=tuple(frontage_roles),
    )


def default_building_catalog() -> tuple[BuildingArchetype, ...]:
    """Return the initial 88-entry catalog.

    These entries deliberately reuse existing massing/facade primitives.  The
    entries are already distinct at the archetype level (massing signature,
    facade family and ornament policy), while future catalog versions can add
    polygonal footprints and downloaded/generated GLB modules without changing
    the selector contract.
    """

    residential = ("residential",)
    commercial = ("commercial",)
    public = ("public_service",)
    industrial = ("industrial",)
    mixed = ("mixed_use",)
    all_urban = ("residential", "commercial", "public_service", "mixed_use")
    entries: list[BuildingArchetype] = []

    # Low/mid-rise families.  The signatures are semantic geometry contracts,
    # not mere floor-count variants.
    lowrise = [
        ("bar", "bar_compact", "frontage_canopy_01"),
        ("bar", "bar_deep_window", "recessed_entry_01"),
        ("l_shape", "l_corner_courtyard", "corner_balcony_01"),
        ("l_shape", "l_frontage_wing", "street_awning_01"),
        ("u_shape", "u_open_to_street", "courtyard_entry_01"),
        ("u_shape", "u_open_to_park", "balcony_stack_01"),
        ("t_shape", "t_transit_frontage", "retail_canopy_01"),
        ("t_shape", "t_civic_axis", "civic_portico_01"),
        ("h_shape", "h_cross_ventilation", "recessed_entry_01"),
        ("courtyard", "courtyard_perimeter", "courtyard_entry_01"),
        ("cross", "cross_landmark_lowrise", "civic_portico_01"),
        ("stepped_bar", "stepped_terrace_lowrise", "terrace_planter_01"),
    ]
    function_specs = [
        (residential, ("residential_brick_v1", "residential_sage_v1", "residential_balcony_v1"), ("residential_slab",)),
        (commercial, ("commercial_teal_curtainwall_v1", "commercial_silver_curtainwall_v1", "commercial_curtainwall_v1"), ("commercial_tower",)),
        (public, ("civic_limestone_v1", "civic_brick_v1", "civic_stone_punched_v1"), ("public_civic",)),
    ]
    # Five footprint/proportion variants per base family.  These variants are
    # not floor-count changes: the compiler applies the recorded parameters to
    # the 2.5-D composition, producing different normalized footprints and
    # offsets while retaining the same safe collision envelope.
    massing_variants = (
        ("compact", {"width_scale": 0.76, "depth_scale": 0.70}),
        ("wide", {"width_scale": 0.94, "depth_scale": 0.48}),
        ("offset_left", {"width_scale": 0.82, "depth_scale": 0.64, "offset_x": -0.08, "offset_y": 0.03}),
        ("offset_right", {"width_scale": 0.82, "depth_scale": 0.64, "offset_x": 0.08, "offset_y": -0.03}),
        ("asymmetric", {"width_scale": 0.88, "depth_scale": 0.72, "offset_x": 0.04, "offset_y": 0.10}),
    )
    for index, (style, signature, ornament) in enumerate(lowrise):
        functions, facades, prototypes = function_specs[index % len(function_specs)]
        for variant_name, parameters in massing_variants:
            entries.append(_a(
                f"{functions[0]}_{signature}_{variant_name}_{index:02d}",
                "low_midrise",
                style,
                f"{signature}_{variant_name}",
                functions,
                facades,
                ornaments=(ornament,),
                prototypes=prototypes,
                massing_parameters=parameters,
                floors=(1, 12),
                width=(6.0, 1000.0),
                depth=(4.0, 1000.0),
            ))

    # Mixed-use and industrial entries use the same grammar but expose a
    # different semantic contract to the selector.
    for index, (style, signature, ornament) in enumerate([
        ("bar", "mixed_bar_retail", "retail_canopy_01"),
        ("l_shape", "mixed_corner_arcade", "corner_balcony_01"),
        ("u_shape", "mixed_u_plaza", "courtyard_entry_01"),
        ("t_shape", "mixed_t_transit", "street_awning_01"),
    ]):
        entries.append(_a(
            f"mixed_use_{signature}_{index:02d}", "mixed_use", style, signature,
            mixed, ("commercial_teal_curtainwall_v1", "civic_limestone_v1", "residential_sage_v1"),
            ornaments=(ornament,), prototypes=("commercial_tower", "public_civic"),
            floors=(1, 16), width=(6.0, 1000.0), depth=(4.0, 1000.0),
            frontage_roles=("frontage", "corner"),
        ))
    for index, (style, signature, ornament) in enumerate([
        ("bar", "industrial_shed_long", "roof_monitor_01"),
        ("l_shape", "industrial_loading_wing", "loading_canopy_01"),
        ("t_shape", "industrial_yard_frontage", "roof_monitor_01"),
        ("stepped_bar", "industrial_sawtooth", "roof_sawtooth_01"),
    ]):
        entries.append(_a(
            f"industrial_{signature}_{index:02d}", "industrial", style, signature,
            industrial, ("industrial_light_ribbon_v1", "industrial_ribbon_v1"),
            ornaments=(ornament,), prototypes=("industrial_hall",),
            floors=(1, 8), width=(6.0, 1000.0), depth=(4.0, 1000.0),
        ))

    # High-rise candidates retain the existing tower-podium floor-plate
    # contract.  They differ in skyline profile and facade/ornament language;
    # highrise geometry variants are applied by HighRisePolicy.
    highrise_specs = [
        ("standard", "tower_podium_standard", False),
        ("setback", "tower_podium_setback", False),
        ("offset", "tower_podium_offset", False),
        ("slender_landmark", "tower_podium_slender_landmark", True),
    ]
    for function, facades, prototype in [
        ("residential", ("residential_balcony_v1", "residential_brick_v1", "residential_sage_v1"), "residential_slab"),
        ("commercial", ("commercial_curtainwall_v1", "commercial_teal_curtainwall_v1", "commercial_silver_curtainwall_v1"), "commercial_tower"),
        ("mixed_use", ("commercial_teal_curtainwall_v1", "civic_limestone_v1", "commercial_silver_curtainwall_v1"), "commercial_tower"),
        ("public_service", ("civic_limestone_v1", "civic_brick_v1", "civic_stone_punched_v1"), "public_civic"),
        ("industrial", ("industrial_light_ribbon_v1", "industrial_ribbon_v1"), "industrial_hall"),
    ]:
        for variant, signature, landmark in highrise_specs:
            entries.append(_a(
                f"{function}_highrise_{variant}", "tower_podium", "tower_podium", signature,
                (function,), facades,
                massing_variant=variant,
                ornaments=("podium_canopy_01", "mechanical_screen_01"),
                prototypes=(prototype,), floors=(10, 80), width=(6.0, 1000.0),
                depth=(6.0, 1000.0), highrise_only=True, landmark_only=landmark,
                frontage_roles=("core", "frontage"),
            ))
    return tuple(entries)


DEFAULT_BUILDING_CATALOG = default_building_catalog()


def catalog_by_id(catalog: Iterable[BuildingArchetype] = DEFAULT_BUILDING_CATALOG) -> dict[str, BuildingArchetype]:
    result: dict[str, BuildingArchetype] = {}
    for item in catalog:
        if item.archetype_id in result:
            raise ValueError(f"duplicate building archetype: {item.archetype_id}")
        result[item.archetype_id] = item
    return result


__all__ = [
    "BuildingArchetype",
    "DEFAULT_BUILDING_CATALOG",
    "catalog_by_id",
    "default_building_catalog",
]
