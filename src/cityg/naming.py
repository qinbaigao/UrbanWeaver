"""Compatibility-first identity and naming utilities for CityG entities.

The canonical ``id`` values are intentionally preserved.  This module adds a
machine-oriented UID, a fully qualified hierarchy path and a human-readable
display name in a City-level registry.  The registry is safe to add to old
manifests because it lives in the existing ``City.metadata`` dictionary.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any, Iterable

from cityg.schemas import (
    Building,
    River,
    City,
    District,
    Door,
    Floor,
    InteriorObject,
    Junction,
    Parcel,
    RoadSegment,
    Room,
    VerticalConnector,
)


IDENTITY_SCHEMA_VERSION = "cityg.identity.v1"
REGISTRY_KEY = "identity_registry"


def _uid(city_id: str, entity_type: str, entity_id: str) -> str:
    digest = hashlib.sha256(f"{city_id}|{entity_type}|{entity_id}".encode("utf-8")).hexdigest()[:20]
    return f"cityg:{entity_type}:{digest}"


def _display_name(entity: Any, entity_type: str) -> str:
    if isinstance(entity, (City, District, Building, Room, River)):
        return str(entity.name)
    if isinstance(entity, Floor):
        return f"Floor {entity.level}"
    if isinstance(entity, Parcel):
        return f"Parcel {entity.id}"
    if isinstance(entity, InteriorObject):
        return f"{str(entity.category).replace('_', ' ').title()} {entity.id}"
    if isinstance(entity, VerticalConnector):
        return f"{str(entity.connector_type).title()} {entity.id}"
    if isinstance(entity, RoadSegment):
        return f"{str(entity.road_class).title()} road {entity.id}"
    if isinstance(entity, Junction):
        return f"Junction {entity.id}"
    if isinstance(entity, Door):
        return f"Door {entity.id}"
    return f"{entity_type.replace('_', ' ').title()} {getattr(entity, 'id', '')}"


def _path(parent_path: str | None, entity_type: str, entity_id: str) -> str:
    component = f"{entity_type}/{entity_id}"
    return f"{parent_path}/{component}" if parent_path else component


def annotate_city_identities(city: City, *, overwrite: bool = False) -> dict[str, dict[str, Any]]:
    """Populate and return the deterministic identity registry for ``city``.

    ``uid`` is stable for the lifetime of an entity ID and is not affected by
    display-name/function edits.  Rebuilding a subtree naturally removes
    identities for deleted IDs and creates records for new IDs.
    """

    existing = city.metadata.get(REGISTRY_KEY)
    old_entities = existing.get("entities", {}) if isinstance(existing, dict) else {}
    parent_paths: dict[str, str] = {}
    records: dict[str, dict[str, Any]] = {}
    for entity, entity_type, parent_id in city.iter_entities():
        parent_path = parent_paths.get(parent_id) if parent_id else None
        entity_id = str(entity.id)
        path = _path(parent_path, entity_type, entity_id)
        # Preserve an explicitly curated display name unless a caller asks for
        # a full refresh.  Generated/default names remain derived from the
        # current canonical entity, so renaming a building is reflected.
        previous = old_entities.get(entity_id, {}) if isinstance(old_entities, dict) else {}
        # Named canonical entities are source-of-truth: a user/agent rename is
        # reflected immediately while the machine UID remains unchanged.
        if entity_type in {"city", "district", "building", "room", "river"}:
            display = _display_name(entity, entity_type)
        else:
            display = _display_name(entity, entity_type) if overwrite or not previous.get("display_name") else previous["display_name"]
        record = {
            "legacy_id": entity_id,
            "entity_type": entity_type,
            "uid": _uid(city.id, entity_type, entity_id),
            "path": path,
            "display_name": str(display),
            "parent_id": str(parent_id) if parent_id else None,
            "parent_path": parent_path,
            "naming_version": IDENTITY_SCHEMA_VERSION,
        }
        records[entity_id] = record
        parent_paths[entity_id] = path
    city.metadata = dict(city.metadata)
    city.metadata[REGISTRY_KEY] = {
        "schema_version": IDENTITY_SCHEMA_VERSION,
        "city_id": city.id,
        "entities": records,
    }
    return records


def identity_registry(city: City) -> dict[str, dict[str, Any]]:
    """Return identities, lazily deriving them for legacy in-memory cities."""

    registry = city.metadata.get(REGISTRY_KEY)
    if not isinstance(registry, dict) or not isinstance(registry.get("entities"), dict):
        return annotate_city_identities(city)
    # A loaded manifest may contain a stale registry after a hand edit.  Check
    # the entity set cheaply and refresh only when it no longer matches.
    current_ids = {str(entity.id) for entity, _, _ in city.iter_entities()}
    if set(registry["entities"]) != current_ids:
        return annotate_city_identities(city)
    return registry["entities"]


def identity_for(city: City, entity_id: str) -> dict[str, Any] | None:
    return identity_registry(city).get(str(entity_id))


def alias_index(city: City) -> dict[str, tuple[str, ...]]:
    """Map IDs, UIDs, paths and unique display names to canonical IDs.

    Ambiguous display names deliberately map to multiple IDs; callers must
    request a more specific path/UID instead of guessing.
    """

    records = identity_registry(city)
    aliases: dict[str, list[str]] = defaultdict(list)
    for entity_id, record in records.items():
        for key in (entity_id, record["uid"], record["path"], record["display_name"]):
            aliases[str(key)].append(entity_id)
    return {key: tuple(values) for key, values in aliases.items()}


def resolve_alias(city: City, value: str) -> str | None:
    """Resolve an unambiguous ID/UID/path/display-name alias."""

    matches = alias_index(city).get(str(value), ())
    return matches[0] if len(matches) == 1 else None


__all__ = [
    "IDENTITY_SCHEMA_VERSION",
    "REGISTRY_KEY",
    "alias_index",
    "annotate_city_identities",
    "identity_for",
    "identity_registry",
    "resolve_alias",
]
