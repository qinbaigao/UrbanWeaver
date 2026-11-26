"""Deterministic, topology-preserving facade grammar.

The facade layer is deliberately visual-only.  It decorates the validated
building mass with windows, frames, storefronts and occasional balconies while
leaving the collision envelope, rooms and navigation untouched.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class FacadeStyle:
    id: str
    bay_width_m: float
    window_ratio: float
    window_height_ratio: float
    sill_height_m: float
    frame_width_m: float
    glass_material: str
    frame_material: str
    accent_material: str
    wall_material: str
    storefront: bool = False
    balcony_stride: int = 0
    balcony_side: str = "south"
    vertical_fins: bool = False


@dataclass(frozen=True)
class FacadeProfile:
    """Vertical facade zoning shared by all massing parts of a building."""

    style: FacadeStyle
    floor_count: int
    podium_floors: int
    crown_floors: int
    mechanical_levels: tuple[int, ...] = ()

    def zone_for_ordinal(self, ordinal: int) -> str:
        if ordinal < self.podium_floors:
            return "podium"
        if ordinal in self.mechanical_levels:
            return "mechanical"
        if ordinal >= self.floor_count - self.crown_floors:
            return "crown"
        return "shaft"


RESIDENTIAL_FACADE = FacadeStyle(
    id="residential_balcony_v1",
    bay_width_m=3.2,
    window_ratio=0.66,
    window_height_ratio=0.58,
    sill_height_m=0.78,
    frame_width_m=0.10,
    glass_material="facade_glass_warm",
    frame_material="facade_frame_light",
    accent_material="facade_accent_warm",
    wall_material="residential_facade",
    balcony_stride=3,
    balcony_side="south",
)

COMMERCIAL_FACADE = FacadeStyle(
    id="commercial_curtainwall_v1",
    bay_width_m=2.7,
    window_ratio=0.82,
    window_height_ratio=0.72,
    sill_height_m=0.42,
    frame_width_m=0.075,
    glass_material="facade_glass_blue",
    frame_material="facade_frame_dark",
    accent_material="facade_accent_blue",
    wall_material="commercial_glass",
    storefront=True,
    vertical_fins=True,
)

PUBLIC_FACADE = FacadeStyle(
    id="civic_stone_punched_v1",
    bay_width_m=3.6,
    window_ratio=0.56,
    window_height_ratio=0.60,
    sill_height_m=0.72,
    frame_width_m=0.12,
    glass_material="facade_glass_neutral",
    frame_material="facade_frame_stone",
    accent_material="facade_accent_stone",
    wall_material="civic_stone",
    storefront=True,
    balcony_stride=0,
)

INDUSTRIAL_FACADE = FacadeStyle(
    id="industrial_ribbon_v1",
    bay_width_m=4.4,
    window_ratio=0.78,
    window_height_ratio=0.38,
    sill_height_m=1.42,
    frame_width_m=0.09,
    glass_material="facade_glass_blue",
    frame_material="facade_frame_dark",
    accent_material="facade_accent_metal",
    wall_material="industrial_metal",
    storefront=False,
    vertical_fins=True,
)


RESIDENTIAL_BRICK_FACADE = FacadeStyle(
    **{
        **RESIDENTIAL_FACADE.__dict__,
        "id": "residential_brick_v1",
        "glass_material": "facade_glass_neutral",
        "frame_material": "facade_frame_cream",
        "accent_material": "facade_accent_brick",
        "wall_material": "residential_brick",
        "balcony_stride": 4,
    }
)

RESIDENTIAL_SAGE_FACADE = FacadeStyle(
    **{
        **RESIDENTIAL_FACADE.__dict__,
        "id": "residential_sage_v1",
        "glass_material": "facade_glass_sage",
        "frame_material": "facade_frame_sand",
        "accent_material": "facade_accent_terracotta",
        "wall_material": "residential_sage",
        "bay_width_m": 3.45,
    }
)

COMMERCIAL_TEAL_FACADE = FacadeStyle(
    **{
        **COMMERCIAL_FACADE.__dict__,
        "id": "commercial_teal_curtainwall_v1",
        "glass_material": "facade_glass_teal",
        "frame_material": "facade_frame_graphite",
        "accent_material": "facade_accent_copper",
        "wall_material": "commercial_teal",
        "bay_width_m": 2.9,
    }
)

COMMERCIAL_SILVER_FACADE = FacadeStyle(
    **{
        **COMMERCIAL_FACADE.__dict__,
        "id": "commercial_silver_curtainwall_v1",
        "glass_material": "facade_glass_smoke",
        "frame_material": "facade_frame_silver",
        "accent_material": "facade_accent_navy",
        "wall_material": "commercial_smoke",
        "vertical_fins": False,
    }
)

PUBLIC_LIMESTONE_FACADE = FacadeStyle(
    **{
        **PUBLIC_FACADE.__dict__,
        "id": "civic_limestone_v1",
        "frame_material": "facade_frame_limestone",
        "accent_material": "facade_accent_bronze",
        "wall_material": "civic_limestone",
        "bay_width_m": 3.9,
    }
)

PUBLIC_BRICK_FACADE = FacadeStyle(
    **{
        **PUBLIC_FACADE.__dict__,
        "id": "civic_brick_v1",
        "glass_material": "facade_glass_warm",
        "frame_material": "facade_frame_cream",
        "accent_material": "facade_accent_brick",
        "wall_material": "civic_brick",
        "storefront": False,
    }
)

INDUSTRIAL_LIGHT_FACADE = FacadeStyle(
    **{
        **INDUSTRIAL_FACADE.__dict__,
        "id": "industrial_light_ribbon_v1",
        "glass_material": "facade_glass_smoke",
        "frame_material": "facade_frame_silver",
        "accent_material": "facade_accent_rust",
        "wall_material": "industrial_light",
    }
)

FACADE_FAMILIES = {
    "residential": (
        RESIDENTIAL_FACADE,
        RESIDENTIAL_BRICK_FACADE,
        RESIDENTIAL_SAGE_FACADE,
    ),
    "commercial": (
        COMMERCIAL_FACADE,
        COMMERCIAL_TEAL_FACADE,
        COMMERCIAL_SILVER_FACADE,
    ),
    "public": (
        PUBLIC_FACADE,
        PUBLIC_LIMESTONE_FACADE,
        PUBLIC_BRICK_FACADE,
    ),
    "industrial": (INDUSTRIAL_FACADE, INDUSTRIAL_LIGHT_FACADE),
}


def _stable_variant(key: str, count: int) -> int:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % count


def facade_style_for_function(
    function: str,
    *,
    highrise: bool = False,
    variant_key: str | None = None,
) -> FacadeStyle:
    """Select a deterministic facade family member for one building.

    ``variant_key`` should be a stable building ID. Omitting it keeps the original
    v1 choices for backwards-compatible tests and external callers.
    """
    family_name = "public"
    if function in {"commercial", "mixed_use"}:
        family_name = "commercial"
    elif function == "industrial":
        family_name = "industrial"
    elif function == "residential":
        family_name = "residential"
    family = FACADE_FAMILIES[family_name]
    # Building archetypes may provide an exact catalog style ID.  Preserve the
    # historical stable-hash behavior for unknown keys so old manifests and
    # refinement traces remain backwards compatible.
    exact = next((item for item in family if item.id == variant_key), None)
    style = (
        exact
        if exact is not None
        else family[0]
        if variant_key is None
        else family[_stable_variant(variant_key, len(family))]
    )
    if highrise and function == "residential":
        # Towers retain the selected palette while using a tighter, restrained
        # rhythm that remains structurally plausible for a high-rise envelope.
        return FacadeStyle(
            **{
                **style.__dict__,
                "id": style.id.replace("residential_", "residential_tower_", 1),
                "bay_width_m": min(style.bay_width_m, 2.8),
                "window_ratio": max(style.window_ratio, 0.72),
                "balcony_stride": max(style.balcony_stride, 4),
            }
        )
    return style


def facade_profile_for_building(
    function: str,
    floor_count: int,
    *,
    highrise: bool = False,
    variant_key: str | None = None,
) -> FacadeProfile:
    """Build a restrained podium/shaft/mechanical/crown hierarchy.

    The profile is deterministic, but its proportions are tied to building
    function and height rather than repeating one rule on every floor.
    """
    style = facade_style_for_function(
        function,
        highrise=highrise,
        variant_key=variant_key,
    )
    if floor_count <= 3:
        return FacadeProfile(style, floor_count, 1, 0)
    podium = 2 if function in {"commercial", "mixed_use", "public"} else 1
    if highrise and floor_count >= 18:
        podium += _stable_variant(f"{variant_key}:podium", 2)
    crown = 0
    if highrise and floor_count >= 10:
        crown = 1 + _stable_variant(f"{variant_key}:crown", 2)
    mechanical: list[int] = []
    if highrise and floor_count >= 14:
        first = 8 + _stable_variant(f"{variant_key}:mechanical", 4)
        mechanical = list(range(first, max(first, floor_count - crown), 11))
    return FacadeProfile(
        style=style,
        floor_count=floor_count,
        podium_floors=min(podium, max(1, floor_count - crown)),
        crown_floors=crown,
        mechanical_levels=tuple(mechanical),
    )


__all__ = [
    "FacadeStyle",
    "FacadeProfile",
    "facade_style_for_function",
    "facade_profile_for_building",
    "RESIDENTIAL_FACADE",
    "COMMERCIAL_FACADE",
    "PUBLIC_FACADE",
    "INDUSTRIAL_FACADE",
    "FACADE_FAMILIES",
]
