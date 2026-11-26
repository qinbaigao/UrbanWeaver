"""Explicit manifest version compatibility and migration rules."""

from __future__ import annotations

from cityg.ccwp import build_world_program
from cityg.schemas import CCWP_SCHEMA_VERSION, City


LEGACY_SCHEMA_VERSION = "0.1.0"
SUPPORTED_SCHEMA_VERSIONS = frozenset({LEGACY_SCHEMA_VERSION, CCWP_SCHEMA_VERSION})


def require_supported_version(version: str) -> None:
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        supported = ", ".join(sorted(SUPPORTED_SCHEMA_VERSIONS))
        raise ValueError(
            f"Unsupported CityG schema version {version!r}; supported versions: {supported}"
        )


def migrate_legacy_city(city: City, source_version: str) -> City:
    """Upgrade a parsed legacy city to the current in-memory CCWP representation."""

    require_supported_version(source_version)
    if source_version == CCWP_SCHEMA_VERSION:
        return city
    city.schema_version = CCWP_SCHEMA_VERSION
    city.metadata = dict(city.metadata)
    city.metadata["migrated_from_schema_version"] = source_version
    city.world_program = build_world_program(
        city,
        producer="cityg.migration",
        seed=city.metadata.get("seed"),
    )
    return city
