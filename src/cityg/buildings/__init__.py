"""Catalog-grounded building archetypes and deterministic selection."""

from cityg.buildings.catalog import (
    BuildingArchetype,
    DEFAULT_BUILDING_CATALOG,
    default_building_catalog,
)
from cityg.buildings.selector import (
    BuildingSelection,
    BuildingSelectionContext,
    BuildingSelector,
)

__all__ = [
    "BuildingArchetype",
    "BuildingSelection",
    "BuildingSelectionContext",
    "BuildingSelector",
    "DEFAULT_BUILDING_CATALOG",
    "default_building_catalog",
]
