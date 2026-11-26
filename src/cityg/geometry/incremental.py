"""Disk-backed helpers for safe building-scoped geometry recompilation.

The compiler intentionally keeps the city shell and road network in the IR,
but can expand only a set of buildings.  This module merges that subset with
the last manifest and records the invalidation decision so a later run is
auditable.  A room change invalidates its containing building: the shell,
facade, connectors and floor stack are coupled, so pretending to compile a
single room would risk stale wall and layer data.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

from cityg.geometry.model import (
    ActivationTier,
    GeometryPrimitive,
    GeometryScene,
    InteractionStateMachine,
    LayerDefinition,
    MaterialSpec,
    NavigationEdge,
    NavigationGraph,
    NavigationNode,
    StateTransition,
    Vec3,
)
from cityg.schemas import City
from cityg.serialization import to_primitive


def building_fingerprints(city: City) -> dict[str, str]:
    """Return stable content fingerprints for all buildings in ``city``."""

    result: dict[str, str] = {}
    for building in city.iter_buildings():
        value=to_primitive(building)
        if city.metadata.get("interior_scope") is not None:
            value={"building":value,"compiled_interior_levels":city.metadata["interior_scope"]["building_levels"].get(building.id,[])}
        payload = json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        result[building.id] = hashlib.sha256(payload).hexdigest()
    return result


def entity_building_index(city: City) -> dict[str, str]:
    """Map building, floor, room, object, door and connector IDs to buildings."""

    result: dict[str, str] = {}
    for building in city.iter_buildings():
        result[building.id] = building.id
        for connector in building.vertical_connectors:
            result[connector.id] = building.id
        for floor in building.floors:
            result[floor.id] = building.id
            for room in floor.rooms:
                result[room.id] = building.id
            for door in floor.doors:
                result[door.id] = building.id
            for obj in floor.objects:
                result[obj.id] = building.id
    return result


def affected_buildings(city: City, changed_entity_ids: Iterable[str]) -> set[str]:
    """Resolve room/floor/building IDs to the smallest safe building scope."""

    index = entity_building_index(city)
    changed = {str(item) for item in changed_entity_ids}
    unknown = sorted(item for item in changed if item not in index)
    if unknown:
        raise ValueError(f"incremental compile received unknown entity IDs: {unknown}")
    return {index[item] for item in changed}


def scene_from_manifest(payload: dict[str, Any]) -> GeometryScene:
    """Rehydrate the subset of ``GeometryScene`` persisted by save_json."""

    def vec(data):
        return Vec3(float(data["x"]), float(data["y"]), float(data["z"]))

    materials = [MaterialSpec(**item) for item in payload.get("materials", [])]
    primitives = [
        GeometryPrimitive(
            id=item["id"],
            owner_id=item["owner_id"],
            primitive_type=item["primitive_type"],
            center=vec(item["center"]),
            size=vec(item["size"]),
            rotation_z_deg=float(item["rotation_z_deg"]),
            semantic_class=item["semantic_class"],
            material_id=item["material_id"],
            layer_id=item["layer_id"],
            lod=int(item.get("lod", 0)),
            collision_enabled=bool(item.get("collision_enabled", True)),
            body_type=item.get("body_type", "static"),
            instance_key=item.get("instance_key", "unit_box"),
            metadata=dict(item.get("metadata", {})),
        )
        for item in payload.get("primitives", [])
    ]
    navigation = payload.get("navigation", {})
    nav = NavigationGraph(
        nodes=[NavigationNode(**{**item, "position": vec(item["position"])}) for item in navigation.get("nodes", [])],
        edges=[NavigationEdge(**item) for item in navigation.get("edges", [])],
    )
    state_machines = [
        InteractionStateMachine(
            id=item["id"],
            owner_id=item["owner_id"],
            state_type=item["state_type"],
            initial_state=item["initial_state"],
            states=dict(item.get("states", {})),
            transitions=[StateTransition(**transition) for transition in item.get("transitions", [])],
            persistent=bool(item.get("persistent", True)),
        )
        for item in payload.get("state_machines", [])
    ]
    layers = [LayerDefinition(**item) for item in payload.get("layers", [])]
    tiers = [
        ActivationTier(
            name=item["name"],
            description=item["description"],
            loaded_layer_types=tuple(item.get("loaded_layer_types", [])),
            physics_body_types=tuple(item.get("physics_body_types", [])),
        )
        for item in payload.get("activation_tiers", [])
    ]
    return GeometryScene(
        city_id=payload["city_id"],
        coordinate_system=payload["coordinate_system"],
        materials=materials,
        primitives=primitives,
        navigation=nav,
        state_machines=state_machines,
        layers=layers,
        activation_tiers=tiers,
        building_prototypes=dict(payload.get("building_prototypes", {})),
        metadata=dict(payload.get("metadata", {})),
    )


def merge_building_scene(
    city: City,
    previous: GeometryScene,
    subset: GeometryScene,
    affected: set[str],
    *,
    previous_city: City | None = None,
) -> tuple[GeometryScene, dict[str, int]]:
    """Replace only affected building-owned data in a previous scene."""

    current_index = entity_building_index(city)
    old_index = entity_building_index(previous_city) if previous_city is not None else current_index

    def owner_building(owner_id: str, index: dict[str, str]) -> str | None:
        return index.get(owner_id)

    old_layers = {item.id for item in previous.layers}
    current_layers = {item.id: item for item in subset.layers}
    kept_primitives = [
        item
        for item in previous.primitives
        if item.layer_id in current_layers
        and owner_building(item.owner_id, old_index) not in affected
    ]
    replacement_primitives = [
        item
        for item in subset.primitives
        if owner_building(item.owner_id, current_index) in affected
    ]
    merged_primitives = [*kept_primitives, *replacement_primitives]

    old_nodes = {
        item.id: item for item in previous.navigation.nodes
        if owner_building(item.owner_id, old_index) not in affected
    }
    new_nodes = {
        item.id: item for item in subset.navigation.nodes
        if owner_building(item.owner_id, current_index) in affected
    }
    nodes = list({**old_nodes, **new_nodes}.values())
    node_ids = {item.id for item in nodes}
    edges = [
        item for item in previous.navigation.edges
        # Stable room IDs do not imply stable doors. A floor replacement can
        # keep both endpoint IDs while deleting the old door/state machine.
        # Drop every old edge incident to an invalidated node, then rebuild
        # both interior and entrance boundary edges from the new compilation.
        if item.start_node_id in old_nodes and item.end_node_id in old_nodes
    ]
    edges.extend(
        item for item in subset.navigation.edges
        if item.start_node_id in node_ids
        and item.end_node_id in node_ids
        and item.id not in {edge.id for edge in edges}
    )

    old_machines = {
        item.id: item for item in previous.state_machines
        if owner_building(item.owner_id, old_index) not in affected
    }
    new_machines = {
        item.id: item for item in subset.state_machines
        if owner_building(item.owner_id, current_index) in affected
    }
    prototypes = dict(previous.building_prototypes)
    prototypes.update(subset.building_prototypes)
    # A newly created building may not have existed in the cache.  The
    # compiler already computed its prototype in the subset scene; this
    # fallback keeps the layer writer total for all current buildings.
    prototypes = {
        building.id: prototypes[building.id]
        for building in city.iter_buildings()
        if building.id in prototypes
    }
    from cityg.envelopes import envelope_config
    fresh_navigation = bool(city.rivers or any(len(r.centerline)>2 for r in city.road_network.segments)
                            or any(envelope_config(b) for b in city.iter_buildings())
                            or previous.metadata.get("exterior_only_building_ids"))
    keyed_metadata = {}
    for key in ("facade_buildings", "exterior_envelopes"):
        keyed_metadata[key] = {**{k:v for k,v in previous.metadata.get(key, {}).items()
                                 if k not in affected and k in prototypes},
                               **subset.metadata.get(key, {})}
    for key in ('room_surface_items','room_furnishing_sufficiency','room_finishes','room_decorations'):
        keyed_metadata[key] = {
            **{k: v for k, v in previous.metadata.get(key, {}).items()
               if k in current_index and current_index[k] not in affected},
            **subset.metadata.get(key, {}),
        }
    merged = GeometryScene(
        city_id=subset.city_id,
        coordinate_system=subset.coordinate_system,
        materials=list({**{m.id: m for m in previous.materials}, **{m.id: m for m in subset.materials}}.values()),
        primitives=merged_primitives,
        navigation=(subset.navigation if fresh_navigation
                    else NavigationGraph(nodes=nodes, edges=edges)),
        state_machines=list({**old_machines, **new_machines}.values()),
        layers=subset.layers,
        activation_tiers=subset.activation_tiers,
        building_prototypes=prototypes,
        metadata={
            **previous.metadata,
            **subset.metadata,
            **keyed_metadata,
            "compile_scope": "incremental_building_merge",
            "incremental_affected_buildings": sorted(affected),
            "incremental_reused_building_count": max(
                0, len(list(city.iter_buildings())) - len(affected)
            ),
            "incremental_recompiled_building_count": len(affected),
            "incremental_reused_primitive_count": len(kept_primitives),
            "incremental_recompiled_primitive_count": len(replacement_primitives),
            "incremental_navigation_reused": not fresh_navigation,
        },
    )
    return merged, {
        "reused_primitive_count": len(kept_primitives),
        "recompiled_primitive_count": len(replacement_primitives),
        "reused_building_count": max(0, len(list(city.iter_buildings())) - len(affected)),
        "recompiled_building_count": len(affected),
    }


__all__ = [
    "affected_buildings",
    "building_fingerprints",
    "entity_building_index",
    "merge_building_scene",
    "scene_from_manifest",
]
