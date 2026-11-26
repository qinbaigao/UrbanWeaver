"""Construction and graph utilities for the CCWP v0.2 registry."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from math import hypot
from typing import Any, Iterable

from cityg.schemas import (
    Artifact,
    Bounds2D,
    Building,
    City,
    Contract,
    Door,
    Floor,
    GeometryBudget,
    InteractionState,
    Intent,
    InteriorObject,
    Point2D,
    ProvenanceRecord,
    Relation,
    RoadSegment,
    Room,
    VerticalConnector,
    WorldNode,
    WorldProgram,
)
from cityg.naming import annotate_city_identities


def entity_index(city: City) -> dict[str, Any]:
    """Return all canonical entities indexed by stable ID."""

    return {entity.id: entity for entity, _, _ in city.iter_entities()}


def expected_hierarchy(city: City) -> dict[str, tuple[str, str | None]]:
    """Map each entity ID to its expected type and parent ID."""

    return {
        entity.id: (entity_type, parent_id)
        for entity, entity_type, parent_id in city.iter_entities()
    }


def build_world_program(city: City, *, producer: str, seed: int | None) -> WorldProgram:
    """Build a deterministic CCWP overlay for an existing canonical city."""

    # Additive identity metadata is refreshed whenever the CCWP is rebuilt.
    # Existing canonical IDs remain unchanged, preserving compatibility with
    # old manifests, patches and exported USD paths.
    identities = annotate_city_identities(city)

    provenance_id = "prov_initial_generation"
    program = WorldProgram(
        provenance=[
            ProvenanceRecord(
                id=provenance_id,
                entity_id=city.id,
                producer=producer,
                operation="generate",
                seed=seed,
                metadata={"schema_version": city.schema_version},
            )
        ]
    )

    entities = list(city.iter_entities())
    by_id = {entity.id: entity for entity, _, _ in entities}
    for entity, entity_type, parent_id in entities:
        identity = identities.get(entity.id, {})
        tags = list(_intent_for(entity, entity_type).tags)
        if identity:
            tags.extend(
                [
                    f"entity_type:{identity['entity_type']}",
                    f"uid:{identity['uid']}",
                    f"path:{identity['path']}",
                ]
            )
        intent = _intent_for(entity, entity_type)
        intent.tags = tags
        program.nodes.append(
            WorldNode(
                entity_id=entity.id,
                entity_type=entity_type,
                parent_id=parent_id,
                intent=intent,
                geometry=_geometry_for(entity, entity_type, by_id, parent_id),
                state=_state_for(entity),
                provenance_ids=[provenance_id],
                status="valid",
            )
        )

    nodes = {node.entity_id: node for node in program.nodes}

    def add_relation(relation: Relation) -> None:
        program.relations.append(relation)
        if relation.source_id in nodes:
            nodes[relation.source_id].relation_ids.append(relation.id)

    def add_contract(contract: Contract) -> None:
        program.contracts.append(contract)
        for entity_id in {contract.scope_id, *contract.subject_ids}:
            if entity_id in nodes and contract.id not in nodes[entity_id].contract_ids:
                nodes[entity_id].contract_ids.append(contract.id)

    from cityg.urban_requirements import matches as urban_matches
    urban_entities = [{'id': b.id, 'zone': d.name, 'function': b.function}
                      for d in city.districts for p in d.parcels for b in p.buildings]
    for rule in city.metadata.get('urban_requirements', []):
        bound = [e['id'] for e in urban_entities if urban_matches(e, rule['subject'])]
        target = rule.get('target')
        if target in ('river', 'road'):
            bound += [e.id for e in (city.rivers if target=='river' else city.road_network.segments)]
        elif target:
            bound += [e['id'] for e in urban_entities if urban_matches(e, target)]
        add_contract(Contract(id='contract_urban__'+rule['id'], kind='urban_spatial',
            scope_id=city.id, subject_ids=sorted(set(bound)), description=rule['source_quote'],
            parameters=dict(rule), severity='error' if rule['strength']=='hard' else 'warning'))

    for entity, _, parent_id in entities:
        if parent_id is not None:
            add_relation(
                Relation(
                    id=f"rel_contains__{parent_id}__{entity.id}",
                    relation_type="contains",
                    source_id=parent_id,
                    target_ids=[entity.id],
                )
            )

    for segment in city.road_network.segments:
        add_relation(
            Relation(
                id=f"rel_road_connects__{segment.id}",
                relation_type="connects",
                source_id=segment.id,
                target_ids=[segment.start_junction_id, segment.end_junction_id],
            )
        )

    for bridge in city.bridges:
        add_relation(Relation(id=f"rel_bridge_supports__{bridge.id}", relation_type="supports_road",
                              source_id=bridge.id, target_ids=[bridge.road_id]))
        add_relation(Relation(id=f"rel_bridge_crosses__{bridge.id}", relation_type="crosses_water",
                              source_id=bridge.id, target_ids=[bridge.river_id],
                              properties={"start_m": bridge.start_m, "end_m": bridge.end_m,
                                          "min_clearance_m": bridge.min_clearance_m}))

    for building in city.iter_buildings():
        nearest_road = min(
            city.road_network.segments,
            key=lambda road: point_segment_distance(building.entrance, road.centerline),
        )
        group_access = building.metadata.get('group_access')
        if group_access:
            nearest_road = next(r for r in city.road_network.segments if r.id == group_access['road_id'])
        access_relation = Relation(
            id=f"rel_building_access__{building.id}",
            relation_type="accessible_from",
            source_id=building.id,
            target_ids=[nearest_road.id],
            properties={
                "mode": "pedestrian",
                "entrance": {"x": building.entrance.x, "y": building.entrance.y},
                "distance_m": round(
                    point_segment_distance(building.entrance, nearest_road.centerline), 6
                ),
            },
        )
        if group_access:
            access_relation.properties.update(mode='parcel_pedestrian_route', distance_m=group_access['length_m'])
        add_relation(access_relation)
        add_contract(
            Contract(
                id=f"contract_entrance_access__{building.id}",
                kind="entrance_access",
                scope_id=building.id,
                subject_ids=[building.id, nearest_road.id],
                description="Building entrance must connect to the pedestrian road network",
                parameters={"relation_id": access_relation.id, "max_distance_m": 25.0,
                    **({'access_mode':'validated_parcel_route', 'route_width_m':group_access['width_m']}
                       if group_access else {})},
            )
        )
        height_contract = building.metadata.get("height_contract")
        if isinstance(height_contract, dict):
            add_contract(
                Contract(
                    id=f"contract_building_height__{building.id}",
                    kind="building_height",
                    scope_id=building.id,
                    subject_ids=[building.id],
                    description=(
                        "Building floor count must remain inside its accepted skyline band"
                    ),
                    parameters={
                        "min_floors": height_contract.get("min_floors"),
                        "max_floors": height_contract.get("max_floors"),
                        "recommended_floors": height_contract.get(
                            "recommended_floors"
                        ),
                        "height_zone": height_contract.get("height_zone"),
                        "height_role": height_contract.get("height_role"),
                        "landmark": bool(height_contract.get("landmark")),
                        "source": height_contract.get("source"),
                    },
                )
            )
        orientation_contract = building.metadata.get("orientation_contract")
        if isinstance(orientation_contract, dict):
            frontage_road_id = orientation_contract.get("frontage_road_id")
            add_contract(
                Contract(
                    id=f"contract_street_alignment__{building.id}",
                    kind="street_alignment",
                    scope_id=building.id,
                    subject_ids=[building.id]
                    + ([str(frontage_road_id)] if frontage_road_id else []),
                    description=(
                        "The building key facade follows its frontage street; "
                        "rotation is limited to eligible edge living areas"
                    ),
                    parameters={
                        "street_axis_deg": orientation_contract.get(
                            "street_axis_deg"
                        ),
                        "local_facade_axis_deg": orientation_contract.get(
                            "local_facade_axis_deg"
                        ),
                        "offset_deg": orientation_contract.get("offset_deg"),
                        "strict_alignment": orientation_contract.get(
                            "strict_alignment"
                        ),
                        "alignment_mode": orientation_contract.get(
                            "alignment_mode"
                        ),
                        "frontage_road_id": frontage_road_id,
                    },
                )
            )
        add_contract(
            Contract(
                id=f"contract_end_to_end_access__{building.id}",
                kind="end_to_end_access",
                scope_id=building.id,
                subject_ids=[building.id]
                + [floor.id for floor in building.floors]
                + [room.id for floor in building.floors for room in floor.rooms],
                description="Every room must be reachable from the outdoor road network",
                parameters={"mode": "pedestrian"},
            )
        )

        if len(building.floors) > 1:
            add_contract(
                Contract(
                    id=f"contract_vertical_circulation__{building.id}",
                    kind="vertical_circulation",
                    scope_id=building.id,
                    subject_ids=[building.id]
                    + [connector.id for connector in building.vertical_connectors],
                    description="All occupied levels require aligned vertical circulation",
                    parameters={"levels": [floor.level for floor in building.floors]},
                )
            )
        highrise = building.metadata.get("highrise", {})
        if isinstance(highrise, dict) and highrise.get("enabled"):
            add_contract(
                Contract(
                    id=f"contract_highrise_core__{building.id}",
                    kind="highrise_core_redundancy",
                    scope_id=building.id,
                    subject_ids=[building.id]
                    + [connector.id for connector in building.vertical_connectors],
                    description=(
                        "Tall buildings require redundant stairs, elevators, and "
                        "explicit typical-floor reuse groups"
                    ),
                    parameters={
                        "required_stair_count": highrise.get(
                            "required_stair_count", 2
                        ),
                        "required_elevator_count": highrise.get(
                            "required_elevator_count", 1
                        ),
                        "podium_floors": highrise.get("podium_floors", 2),
                        "reuse_mode": highrise.get("reuse_mode"),
                        "massing_variant": highrise.get("massing_variant"),
                        "massing_constraint": highrise.get("massing_constraint"),
                    },
                )
            )

        for connector in building.vertical_connectors:
            served = [
                floor.id
                for floor in building.floors
                if connector.from_level <= floor.level <= connector.to_level
            ]
            add_relation(
                Relation(
                    id=f"rel_connector_serves__{connector.id}",
                    relation_type="connects_levels",
                    source_id=connector.id,
                    target_ids=served,
                )
            )

        for floor in building.floors:
            add_contract(
                Contract(
                    id=f"contract_room_connectivity__{floor.id}",
                    kind="room_connectivity",
                    scope_id=floor.id,
                    subject_ids=[floor.id] + [room.id for room in floor.rooms],
                    description="Every room must be reachable through the floor door graph",
                )
            )
            if floor.objects:
                add_contract(
                    Contract(
                        id=f"contract_furnishing_clearance__{floor.id}",
                        kind="furnishing_clearance",
                        scope_id=floor.id,
                        subject_ids=[floor.id]
                        + [obj.id for obj in floor.objects],
                        description=(
                            "Indoor objects must remain inside their rooms without "
                            "overlap or door-clearance obstruction"
                        ),
                        parameters={
                            "object_clearance_m": 0.16,
                            "door_depth_clearance_m": 1.35,
                        },
                    )
                )
            for door in floor.doors:
                targets = [door.room_a_id]
                if door.room_b_id is not None:
                    targets.append(door.room_b_id)
                add_relation(
                    Relation(
                        id=f"rel_door_connects__{door.id}",
                        relation_type=(
                            "connects_exterior" if door.room_b_id is None else "connects_rooms"
                        ),
                        source_id=door.id,
                        target_ids=targets,
                    )
                )

    add_contract(
        Contract(
            id="contract_unique_ids",
            kind="unique_ids",
            scope_id=city.id,
            subject_ids=[city.id],
            description="All canonical entity IDs must be unique",
        )
    )
    add_contract(
        Contract(
            id="contract_connected_roads",
            kind="road_connectivity",
            scope_id=city.id,
            subject_ids=[city.id]
            + [segment.id for segment in city.road_network.segments],
            description="The road graph must form one connected component",
        )
    )

    artifact = Artifact(
        id="artifact_canonical_manifest",
        owner_id=city.id,
        artifact_type="semantic_manifest",
        uri="city.json",
        media_type="application/json",
        status="planned",
    )
    program.artifacts.append(artifact)
    nodes[city.id].artifact_ids.append(artifact.id)
    return program


def _intent_for(entity: Any, entity_type: str) -> Intent:
    function = getattr(entity, "function", entity_type)
    name = getattr(entity, "name", getattr(entity, "id", entity_type))
    tags = [entity_type]
    if isinstance(entity, Door) and entity.interactive:
        tags.append("interactive")
    return Intent(description=str(name), function=str(function), tags=tags)


def _geometry_for(
    entity: Any, entity_type: str, entities: dict[str, Any], parent_id: str | None
) -> GeometryBudget:
    bounds: Bounds2D | None = None
    if isinstance(entity, City):
        bounds = entity.bounds
    elif hasattr(entity, "bounds"):
        bounds = entity.bounds
    elif isinstance(entity, Building):
        bounds = entity.footprint
    elif isinstance(entity, Floor):
        parent = entities.get(parent_id or "")
        bounds = parent.footprint if isinstance(parent, Building) else None

    height = None
    if isinstance(entity, Floor):
        height = entity.height_m
    elif isinstance(entity, Room):
        height = entity.height_m
    elif isinstance(entity, InteriorObject):
        height = entity.height_m
    elif isinstance(entity, Building):
        height = sum(floor.height_m for floor in entity.floors)
    return GeometryBudget(
        max_width_m=bounds.width if bounds else None,
        max_depth_m=bounds.depth if bounds else None,
        max_height_m=height,
        max_area_m2=bounds.area if bounds else None,
    )


def _state_for(entity: Any) -> InteractionState:
    if isinstance(entity, Door):
        return InteractionState(
            mobility="articulated" if entity.interactive else "static",
            state="closed" if entity.interactive else "fixed",
            properties={"interactive": entity.interactive},
        )
    if isinstance(entity, VerticalConnector):
        is_elevator = entity.connector_type == "elevator"
        return InteractionState(
            mobility="kinematic" if is_elevator else "static",
            state=(f"level_{entity.from_level:02d}" if is_elevator else "fixed"),
            properties={
                "connector_type": entity.connector_type,
                "interactive": entity.interactive,
                **entity.metadata,
            },
        )
    if isinstance(entity, InteriorObject):
        return InteractionState(
            mobility="articulated" if entity.interactive else "static",
            state="default",
            properties={
                "interactive": entity.interactive,
                "asset_id": entity.asset_id,
                "category": entity.category,
            },
        )
    return InteractionState()


def closest_point_on_segment(
    point: Point2D, centerline: tuple[Point2D, ...]
) -> Point2D:
    # Historical public name retained for old callers; canonical roads may
    # now contain any number of sampled path points.
    if len(centerline) > 2:
        from cityg.paths import cached_path
        return cached_path(tuple(centerline)).project(point).point
    start, end = centerline
    dx = end.x - start.x
    dy = end.y - start.y
    if dx == 0 and dy == 0:
        return start
    t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return Point2D(start.x + t * dx, start.y + t * dy)


def point_segment_distance(
    point: Point2D, centerline: tuple[Point2D, ...]
) -> float:
    projection = closest_point_on_segment(point, centerline)
    return hypot(point.x - projection.x, point.y - projection.y)


def segment_intersection(
    first: tuple[Point2D, Point2D],
    second: tuple[Point2D, Point2D],
    *,
    epsilon: float = 1e-8,
) -> tuple[float, float, Point2D] | None:
    """Return segment parameters and point for a proper 2-D crossing.

    Collinear overlaps are intentionally ignored; road centerlines in CityG
    are expected to be split at shared junctions, while this helper targets
    the unsplit diagonal-vs-grid crossings that need visual clipping.
    """

    a, b = first
    c, d = second
    rx, ry = b.x - a.x, b.y - a.y
    sx, sy = d.x - c.x, d.y - c.y
    denominator = rx * sy - ry * sx
    if abs(denominator) <= epsilon:
        return None
    qpx, qpy = c.x - a.x, c.y - a.y
    t = (qpx * sy - qpy * sx) / denominator
    u = (qpx * ry - qpy * rx) / denominator
    if not (epsilon < t < 1.0 - epsilon and epsilon < u < 1.0 - epsilon):
        return None
    return t, u, Point2D(a.x + t * rx, a.y + t * ry)


@dataclass(frozen=True)
class DependencyEdge:
    source_id: str
    target_id: str
    kind: str
    reference_id: str


class DependencyGraph:
    """Deterministic hierarchy and cross-reference graph for repair scheduling."""

    def __init__(self, city: City) -> None:
        self.nodes = {node.entity_id: node for node in city.world_program.nodes}
        self.parent = {node.entity_id: node.parent_id for node in self.nodes.values()}
        self.children: dict[str, set[str]] = defaultdict(set)
        self.edges: list[DependencyEdge] = []
        for node in self.nodes.values():
            if node.parent_id is not None:
                self.children[node.parent_id].add(node.entity_id)
                self.edges.append(
                    DependencyEdge(node.parent_id, node.entity_id, "hierarchy", node.entity_id)
                )
        for relation in city.world_program.relations:
            for target in relation.target_ids:
                self.edges.append(
                    DependencyEdge(
                        relation.source_id,
                        target,
                        relation.relation_type,
                        relation.id,
                    )
                )

    def descendants(self, entity_id: str, *, include_self: bool = True) -> set[str]:
        reached = {entity_id} if include_self else set()
        queue = deque([entity_id])
        while queue:
            current = queue.popleft()
            for child in sorted(self.children.get(current, ())):
                if child not in reached:
                    reached.add(child)
                    queue.append(child)
        return reached

    def ancestors(self, entity_id: str, *, include_self: bool = True) -> list[str]:
        result = [entity_id] if include_self else []
        seen = set(result)
        current = self.parent.get(entity_id)
        while current is not None and current not in seen:
            result.append(current)
            seen.add(current)
            current = self.parent.get(current)
        return result

    def hierarchy_path(self, ancestor_id: str, descendant_id: str) -> list[str]:
        reverse = self.ancestors(descendant_id)
        if ancestor_id not in reverse:
            return []
        return list(reversed(reverse[: reverse.index(ancestor_id) + 1]))

    def lowest_common_ancestor(self, entity_ids: Iterable[str]) -> str | None:
        ids = list(entity_ids)
        if not ids:
            return None
        chains = [self.ancestors(entity_id) for entity_id in ids]
        common = set(chains[0]).intersection(*map(set, chains[1:]))
        return next((entity_id for entity_id in chains[0] if entity_id in common), None)

    def is_within_scope(self, entity_id: str, scope_id: str) -> bool:
        return entity_id in self.descendants(scope_id)

    def parent_cycles(self) -> list[list[str]]:
        cycles: list[list[str]] = []
        complete: set[str] = set()
        for start in sorted(self.nodes):
            if start in complete:
                continue
            path: list[str] = []
            positions: dict[str, int] = {}
            current: str | None = start
            while current is not None and current in self.nodes and current not in complete:
                if current in positions:
                    cycles.append(path[positions[current] :] + [current])
                    break
                positions[current] = len(path)
                path.append(current)
                current = self.parent.get(current)
            complete.update(path)
        return cycles
