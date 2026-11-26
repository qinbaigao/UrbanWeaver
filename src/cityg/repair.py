"""Versioned, scope-limited and atomic repair patches for CCWP cities."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any

from cityg.ccwp import DependencyGraph, entity_index
from cityg.schemas import (
    Bounds2D,
    Building,
    Bridge,
    River,
    City,
    District,
    Door,
    Floor,
    InteriorObject,
    Junction,
    Parcel,
    Point2D,
    ProvenanceRecord,
    Relation,
    RoadSegment,
    Room,
    VerticalConnector,
)
from cityg.validation import CityValidator, ValidationReport


ENTITY_PATCH_FIELDS: dict[type, frozenset[str]] = {
    City: frozenset({"name", "bounds", "coordinate_system", "metadata"}),
    Junction: frozenset({"position"}),
    RoadSegment: frozenset(
        {
            "start_junction_id",
            "end_junction_id",
            "centerline",
            "road_class",
            "lane_count",
            "width_m",
            "sidewalk_width_m",
            "speed_limit_kph",
        }
    ),
    District: frozenset({"name", "function", "bounds"}),
    Parcel: frozenset({"bounds", "boundary", "holes"}),
    River: frozenset({"name", "centerline", "width_m", "bank_width_m", "setback_m", "water_elevation_m", "bed_elevation_m"}),
    Bridge: frozenset({"start_m", "end_m", "deck_elevation_m", "structural_depth_m", "min_clearance_m"}),
    Building: frozenset({"name", "function", "footprint", "entrance", "metadata"}),
    VerticalConnector: frozenset(
        {
            "connector_type",
            "bounds",
            "from_level",
            "to_level",
            "interactive",
            "metadata",
        }
    ),
    Floor: frozenset({"elevation_m", "height_m", "metadata"}),
    InteriorObject: frozenset(
        {
            "room_id",
            "category",
            "asset_id",
            "position",
            "width_m",
            "depth_m",
            "height_m",
            "rotation_deg",
            "interactive",
            "metadata",
        }
    ),
    Room: frozenset({"name", "function", "bounds", "height_m", "object_ids"}),
    Door: frozenset(
        {"room_a_id", "room_b_id", "position", "width_m", "door_type", "interactive"}
    ),
}

NODE_PATCH_PATHS = frozenset(
    {
        "intent.description",
        "intent.function",
        "intent.tags",
        "geometry",
        "state.mobility",
        "state.state",
        "state.properties",
        "status",
    }
)


@dataclass(frozen=True)
class PatchOperation:
    """One typed operation in a repair patch.

    Supported operations are ``replace_entity``, ``replace_node``,
    ``add_relation``, ``replace_relation`` and ``remove_relation``.
    """

    op: str
    target_id: str
    path: str = ""
    value: Any = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PatchOperation":
        known = {"op", "target_id", "path", "value"}
        unknown = sorted(set(data) - known)
        if unknown:
            raise ValueError(f"Unknown PatchOperation fields: {', '.join(unknown)}")
        return cls(
            op=str(data["op"]),
            target_id=str(data["target_id"]),
            path=str(data.get("path", "")),
            value=data.get("value"),
        )


@dataclass(frozen=True)
class WorldPatch:
    id: str
    scope_entity_id: str
    operations: tuple[PatchOperation, ...]
    expected_versions: dict[str, int]
    author: str = "repair_agent"
    reason: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorldPatch":
        known = {
            "id",
            "scope_entity_id",
            "operations",
            "expected_versions",
            "author",
            "reason",
        }
        unknown = sorted(set(data) - known)
        if unknown:
            raise ValueError(f"Unknown WorldPatch fields: {', '.join(unknown)}")
        return cls(
            id=str(data["id"]),
            scope_entity_id=str(data["scope_entity_id"]),
            operations=tuple(
                PatchOperation.from_dict(item) for item in data.get("operations", [])
            ),
            expected_versions={
                str(key): int(value)
                for key, value in data.get("expected_versions", {}).items()
            },
            author=str(data.get("author", "repair_agent")),
            reason=str(data.get("reason", "")),
        )


@dataclass
class PatchResult:
    city: City
    touched_entity_ids: tuple[str, ...]
    validation: ValidationReport
    provenance_ids: tuple[str, ...] = ()
    transaction_report: dict | None = None


class PatchRejected(ValueError):
    def __init__(
        self, code: str, message: str, validation: ValidationReport | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.validation = validation


class PatchEngine:
    """Apply patches to a copy and commit only a fully valid result."""

    def __init__(self, validator: CityValidator | None = None) -> None:
        self.validator = validator or CityValidator()

    def apply(self, city: City, patch: WorldPatch, *, source: str = 'validation_repair',
              memory_store=None, compiled_gate=None) -> PatchResult:
        from cityg.transactions import MutationProposal, accept_candidate
        # Keep legacy per-operation version validation/error codes, then use
        # the same actual-diff/ancestor-lock gate as candidate replanners.
        proposal = MutationProposal.bind(city, [patch.scope_entity_id], source=source,
            kind='patch', proposal_id=patch.id)
        result = self._apply_detached(city, patch)
        accepted = accept_candidate(city, proposal, lambda _: result.city,
                                    memory_store=memory_store, compiled_gate=compiled_gate)
        result.city = accepted.city
        result.transaction_report = accepted.report
        return result

    def _apply_detached(self, city: City, patch: WorldPatch) -> PatchResult:
        if not patch.id.strip():
            raise PatchRejected("invalid_patch", "Patch ID must not be empty")
        if not patch.operations:
            raise PatchRejected("invalid_patch", "Patch must contain at least one operation")

        candidate = deepcopy(city)
        graph = DependencyGraph(candidate)
        if patch.scope_entity_id not in graph.nodes:
            raise PatchRejected("invalid_scope", "Patch scope is not a CCWP node")

        entities = entity_index(candidate)
        nodes = {node.entity_id: node for node in candidate.world_program.nodes}
        relations = {relation.id: relation for relation in candidate.world_program.relations}
        touched: set[str] = set()

        for operation in patch.operations:
            owner_id = self._operation_owner(operation, relations)
            if owner_id is None or owner_id not in nodes:
                raise PatchRejected(
                    "unknown_target", f"Patch target has no owning CCWP node: {operation.target_id}"
                )
            if not graph.is_within_scope(owner_id, patch.scope_entity_id):
                raise PatchRejected(
                    "scope_violation",
                    f"Entity {owner_id} is outside patch scope {patch.scope_entity_id}",
                )
            if nodes[owner_id].locked:
                raise PatchRejected("locked_node", f"Entity {owner_id} is locked")
            expected = patch.expected_versions.get(owner_id)
            if expected is None:
                raise PatchRejected(
                    "missing_expected_version",
                    f"Patch does not declare expected version for {owner_id}",
                )
            if nodes[owner_id].version != expected:
                raise PatchRejected(
                    "version_conflict",
                    f"Entity {owner_id} is version {nodes[owner_id].version}, expected {expected}",
                )

            self._apply_operation(candidate, operation, entities, nodes, relations)
            relations = {relation.id: relation for relation in candidate.world_program.relations}
            touched.add(owner_id)

        provenance_ids: list[str] = []
        existing_provenance = {record.id for record in candidate.world_program.provenance}
        for entity_id in sorted(touched):
            node = nodes[entity_id]
            node.version += 1
            provenance_id = f"prov_patch__{patch.id}__{entity_id}"
            if provenance_id in existing_provenance:
                raise PatchRejected(
                    "duplicate_patch_provenance",
                    f"Patch provenance already exists: {provenance_id}",
                )
            record = ProvenanceRecord(
                id=provenance_id,
                entity_id=entity_id,
                producer=patch.author,
                operation="repair_patch",
                parent_record_ids=list(node.provenance_ids),
                metadata={"patch_id": patch.id, "reason": patch.reason},
            )
            candidate.world_program.provenance.append(record)
            node.provenance_ids.append(provenance_id)
            provenance_ids.append(provenance_id)

        validation = self.validator.validate(candidate)
        if not validation.ok:
            raise PatchRejected(
                "post_validation_failed",
                f"Patch result has {len(validation.errors)} validation error(s)",
                validation,
            )
        return PatchResult(
            city=candidate,
            touched_entity_ids=tuple(sorted(touched)),
            validation=validation,
            provenance_ids=tuple(provenance_ids),
        )

    @staticmethod
    def _operation_owner(
        operation: PatchOperation, relations: dict[str, Relation]
    ) -> str | None:
        if operation.op in {"replace_entity", "replace_node", "add_relation"}:
            return operation.target_id
        if operation.op in {"replace_relation", "remove_relation"}:
            relation = relations.get(operation.target_id)
            return relation.source_id if relation else None
        return None

    def _apply_operation(self, city, operation, entities, nodes, relations) -> None:
        if operation.op == "replace_entity":
            entity = entities.get(operation.target_id)
            if entity is None:
                raise PatchRejected("unknown_target", f"Unknown entity {operation.target_id}")
            allowed = next(
                (paths for cls, paths in ENTITY_PATCH_FIELDS.items() if isinstance(entity, cls)),
                frozenset(),
            )
            top_level = operation.path.split(".", 1)[0]
            if top_level not in allowed or "." in operation.path:
                raise PatchRejected(
                    "forbidden_field",
                    f"Field {operation.path!r} is not patchable for {type(entity).__name__}",
                )
            current = getattr(entity, operation.path)
            setattr(entity, operation.path, _coerce_like(current, operation.value))
            return

        if operation.op == "replace_node":
            if operation.path not in NODE_PATCH_PATHS:
                raise PatchRejected(
                    "forbidden_field", f"CCWP node path is not patchable: {operation.path}"
                )
            _replace_path(nodes[operation.target_id], operation.path, operation.value)
            return

        if operation.op == "add_relation":
            relation = _relation_from_value(operation.value)
            if relation.source_id != operation.target_id:
                raise PatchRejected(
                    "invalid_relation", "Added relation source must equal operation target_id"
                )
            if relation.id in relations:
                raise PatchRejected("duplicate_relation", f"Relation exists: {relation.id}")
            if relation.source_id not in nodes or any(
                target not in nodes for target in relation.target_ids
            ):
                raise PatchRejected("invalid_relation", "Relation endpoints must exist")
            city.world_program.relations.append(relation)
            nodes[relation.source_id].relation_ids.append(relation.id)
            return

        if operation.op == "replace_relation":
            old = relations.get(operation.target_id)
            if old is None:
                raise PatchRejected("unknown_target", f"Unknown relation {operation.target_id}")
            replacement = _relation_from_value(operation.value)
            if replacement.id != old.id or replacement.source_id != old.source_id:
                raise PatchRejected(
                    "invalid_relation", "Replacement must preserve relation ID and source"
                )
            if any(target not in nodes for target in replacement.target_ids):
                raise PatchRejected("invalid_relation", "Relation endpoints must exist")
            index = city.world_program.relations.index(old)
            city.world_program.relations[index] = replacement
            if old.id in nodes[old.source_id].relation_ids:
                nodes[old.source_id].relation_ids.remove(old.id)
            nodes[replacement.source_id].relation_ids.append(replacement.id)
            return

        if operation.op == "remove_relation":
            relation = relations.get(operation.target_id)
            if relation is None:
                raise PatchRejected("unknown_target", f"Unknown relation {operation.target_id}")
            city.world_program.relations.remove(relation)
            if relation.id in nodes[relation.source_id].relation_ids:
                nodes[relation.source_id].relation_ids.remove(relation.id)
            return

        raise PatchRejected("unsupported_operation", f"Unsupported patch op: {operation.op}")


def set_subtree_lock(city: City, root_entity_id: str, locked: bool = True) -> tuple[str, ...]:
    """Lock or unlock a hierarchy subtree and return affected stable IDs."""

    graph = DependencyGraph(city)
    if root_entity_id not in graph.nodes:
        raise ValueError(f"Unknown CCWP node: {root_entity_id}")
    affected = graph.descendants(root_entity_id)
    for node in city.world_program.nodes:
        if node.entity_id in affected:
            node.locked = locked
    return tuple(sorted(affected))


def lock_outside_scope(city: City, scope_entity_id: str) -> tuple[str, ...]:
    """Lock unrelated subtrees without unlocking existing user protection.

    Ancestors are frozen by the proposal's exact scope, not subtree locks:
    locking the city root would also prohibit the intended local repair.
    """

    graph = DependencyGraph(city)
    if scope_entity_id not in graph.nodes:
        raise ValueError(f"Unknown CCWP node: {scope_entity_id}")
    allowed = graph.descendants(scope_entity_id)
    ancestors = set(graph.ancestors(scope_entity_id, include_self=False))
    locked = []
    for node in city.world_program.nodes:
        if node.entity_id not in allowed and node.entity_id not in ancestors:
            node.locked = True
        if node.locked:
            locked.append(node.entity_id)
    return tuple(sorted(locked))


def _replace_path(root: Any, path: str, value: Any) -> None:
    parts = path.split(".")
    target = root
    for part in parts[:-1]:
        target = getattr(target, part)
    current = getattr(target, parts[-1])
    setattr(target, parts[-1], _coerce_like(current, value))


def _coerce_like(current: Any, value: Any) -> Any:
    if isinstance(current, Point2D) and isinstance(value, dict):
        return Point2D(float(value["x"]), float(value["y"]))
    if isinstance(current, Bounds2D) and isinstance(value, dict):
        return Bounds2D(
            float(value["min_x"]),
            float(value["min_y"]),
            float(value["max_x"]),
            float(value["max_y"]),
        )
    if isinstance(current, tuple) and isinstance(value, (tuple, list)):
        if current and isinstance(current[0], Point2D):
            return tuple(_coerce_like(current[0], item) for item in value)
        if value and isinstance(value[0], dict) and set(value[0]) == {"x", "y"}:
            return tuple(Point2D(float(item["x"]), float(item["y"])) for item in value)
        if value and isinstance(value[0], (list, tuple)):
            return tuple(_coerce_like((), item) for item in value)
        return tuple(value)
    if is_dataclass(current) and isinstance(value, dict):
        values = {
            item.name: _coerce_like(getattr(current, item.name), value[item.name])
            if item.name in value
            else getattr(current, item.name)
            for item in fields(current)
        }
        return type(current)(**values)
    if isinstance(current, bool):
        return bool(value)
    if isinstance(current, int):
        return int(value)
    if isinstance(current, float):
        return float(value)
    if isinstance(current, list):
        return list(value)
    if isinstance(current, dict):
        return dict(value)
    return value


def _relation_from_value(value: Any) -> Relation:
    if isinstance(value, Relation):
        return deepcopy(value)
    if not isinstance(value, dict):
        raise PatchRejected("invalid_relation", "Relation value must be a mapping")
    try:
        return Relation(
            id=str(value["id"]),
            relation_type=str(value["relation_type"]),
            source_id=str(value["source_id"]),
            target_ids=[str(item) for item in value["target_ids"]],
            properties=dict(value.get("properties", {})),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise PatchRejected("invalid_relation", f"Invalid relation value: {error}") from error
