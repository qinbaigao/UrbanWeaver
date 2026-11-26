"""Deterministic building prototype policies."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BuildingPrototype:
    id: str
    wall_thickness_m: float
    slab_thickness_m: float
    facade_material: str
    roof_style: str
    entrance_canopy: bool = False
    roof_monitor: bool = False


RESIDENTIAL_SLAB = BuildingPrototype(
    id="residential_slab",
    wall_thickness_m=0.20,
    slab_thickness_m=0.18,
    facade_material="residential_facade",
    roof_style="parapet",
)

COMMERCIAL_TOWER = BuildingPrototype(
    id="commercial_tower",
    wall_thickness_m=0.24,
    slab_thickness_m=0.22,
    facade_material="commercial_glass",
    roof_style="flat_mechanical",
    entrance_canopy=True,
)

INDUSTRIAL_HALL = BuildingPrototype(
    id="industrial_hall",
    wall_thickness_m=0.28,
    slab_thickness_m=0.25,
    facade_material="industrial_metal",
    roof_style="monitor",
    roof_monitor=True,
)

PUBLIC_CIVIC = BuildingPrototype(
    id="public_civic",
    wall_thickness_m=0.24,
    slab_thickness_m=0.20,
    facade_material="civic_stone",
    roof_style="flat",
    entrance_canopy=True,
)

PROTOTYPES_BY_ID = {
    prototype.id: prototype
    for prototype in (
        RESIDENTIAL_SLAB,
        COMMERCIAL_TOWER,
        INDUSTRIAL_HALL,
        PUBLIC_CIVIC,
    )
}


def prototype_by_id(prototype_id: str) -> BuildingPrototype:
    try:
        return PROTOTYPES_BY_ID[prototype_id]
    except KeyError as error:
        raise ValueError(f"Unknown building prototype: {prototype_id}") from error


def prototype_for_function(function: str) -> BuildingPrototype:
    if function == "residential":
        return RESIDENTIAL_SLAB
    if function in {"commercial", "mixed_use"}:
        return COMMERCIAL_TOWER
    if function == "industrial":
        return INDUSTRIAL_HALL
    return PUBLIC_CIVIC
