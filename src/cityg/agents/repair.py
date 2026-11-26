"""Validator-guided, scope-limited CCWP repair agent."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Any

from cityg.agents.requirement import AgentAttempt, AgentGenerationError, _parse_json_object
from cityg.ccwp import DependencyGraph, entity_index, point_segment_distance
from cityg.repair import PatchEngine, PatchOperation, PatchRejected, WorldPatch
from cityg.schemas import Building, City, Door, Floor, Room, VerticalConnector
from cityg.serialization import to_primitive
from cityg.services.interfaces import ChatMessage, TextReasoningService
from cityg.validation import CityValidator, ValidationReport


REPAIR_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reason": {"type": "string"},
        "operations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "op": {
                        "type": "string",
                        "enum": [
                            "replace_entity",
                            "replace_node",
                            "add_relation",
                            "replace_relation",
                            "remove_relation",
                        ],
                    },
                    "target_id": {"type": "string"},
                    "path": {"type": "string"},
                    "value_json": {"type": "string"},
                },
                "required": ["op", "target_id", "path", "value_json"],
            },
        },
    },
    "required": ["reason", "operations"],
}


@dataclass(frozen=True)
class RepairResult:
    city: City
    validation: ValidationReport
    patch: WorldPatch
    touched_entity_ids: tuple[str, ...]
    model_id: str
    attempts: tuple[AgentAttempt, ...]

    def trace_dict(self) -> dict[str, Any]:
        return {
            "agent": "repair",
            "model_id": self.model_id,
            "accepted_attempt": len(self.attempts),
            "patch": to_primitive(self.patch),
            "touched_entity_ids": list(self.touched_entity_ids),
            "post_validation": self.validation.to_dict(),
            "attempts": [asdict(attempt) for attempt in self.attempts],
        }


class RepairAgent:
    """Propose patches, while PatchEngine retains scope and commit authority."""

    def __init__(
        self,
        service: TextReasoningService,
        *,
        model_id: str = "unknown",
        validator: CityValidator | None = None,
        max_attempts: int = 3,
        max_operations: int = 12,
    ) -> None:
        if max_attempts < 1 or max_operations < 1:
            raise ValueError("repair budgets must be positive")
        self.service = service
        self.model_id = model_id
        self.validator = validator or CityValidator()
        self.max_attempts = max_attempts
        self.max_operations = max_operations

    def repair(
        self, city: City, report: ValidationReport | None = None
    ) -> RepairResult:
        report = report or self.validator.validate(city)
        if report.ok:
            raise ValueError("Cannot repair a city that already passes validation")
        scopes = {issue.allowed_patch_scope for issue in report.errors}
        graph = DependencyGraph(city)
        if None in scopes or not scopes or not scopes <= set(graph.nodes):
            raise ValueError('Repair requires known, explicit allowed patch scopes')
        # Nested reports often describe the same fault at room/floor/building
        # levels. Use their INTERSECTION, never an implicitly broader ancestor.
        common = [scope for scope in scopes
                  if all(graph.is_within_scope(scope, other) for other in scopes)]
        if len(common) != 1:
            raise ValueError('Disjoint repair scopes require separately authorized coordination; '
                             'will not widen to a common ancestor')
        scope_id = common[0]
        context = self._context(city, report, scope_id)
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=self._system_prompt(scope_id)),
            ChatMessage(
                role="user",
                content=json.dumps(context, ensure_ascii=False, sort_keys=True),
            ),
        ]
        attempts: list[AgentAttempt] = []
        for index in range(1, self.max_attempts + 1):
            started = time.monotonic()
            raw = ""
            finish_reason = None
            usage: dict[str, Any] = {}
            error: str | None = None
            result = None
            patch = None
            try:
                method = getattr(self.service, "complete_with_metadata", None)
                if callable(method):
                    completion = method(messages, REPAIR_RESPONSE_SCHEMA)
                    raw = completion.content
                    finish_reason = completion.finish_reason
                    usage = completion.usage
                else:
                    raw = self.service.complete(messages, REPAIR_RESPONSE_SCHEMA)
                if finish_reason == "length":
                    raise ValueError("model output reached max_tokens before completing JSON")
                proposal = _parse_json_object(raw)
                patch = self._make_patch(city, scope_id, proposal, index)
                result = PatchEngine(self.validator).apply(city, patch)
            except (TypeError, ValueError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
                if isinstance(exc, PatchRejected):
                    detail = exc.validation.to_dict() if exc.validation else None
                    error = f"PatchRejected[{exc.code}]: {exc}; validation={detail}"
                else:
                    error = f"{type(exc).__name__}: {exc}"
            elapsed = time.monotonic() - started
            serialized_messages = tuple(
                {"role": item.role, "content": item.content} for item in messages
            )
            prompt_bytes = json.dumps(
                serialized_messages, sort_keys=True, ensure_ascii=False
            ).encode("utf-8")
            attempts.append(
                AgentAttempt(
                    index=index,
                    prompt_hash=hashlib.sha256(prompt_bytes).hexdigest(),
                    messages=serialized_messages,
                    raw_output=raw,
                    elapsed_s=round(elapsed, 6),
                    error=error,
                    finish_reason=finish_reason,
                    usage=usage,
                )
            )
            if error is None and result is not None and patch is not None:
                return RepairResult(
                    city=result.city,
                    validation=result.validation,
                    patch=patch,
                    touched_entity_ids=result.touched_entity_ids,
                    model_id=self.model_id,
                    attempts=tuple(attempts),
                )
            if index < self.max_attempts:
                messages.extend(
                    [
                        ChatMessage(role="assistant", content=raw[:12000]),
                        ChatMessage(
                            role="user",
                            content=(
                                "The proposed patch was rejected: "
                                f"{error}. Return a corrected, smaller patch."
                            ),
                        ),
                    ]
                )
        raise AgentGenerationError(
            f"Repair agent failed after {self.max_attempts} attempts", attempts
        )

    def _make_patch(
        self, city: City, scope_id: str, proposal: dict[str, Any], attempt: int
    ) -> WorldPatch:
        raw_operations = proposal.get("operations")
        if not isinstance(raw_operations, list) or not raw_operations:
            raise ValueError("repair proposal must contain operations")
        if len(raw_operations) > self.max_operations:
            raise ValueError(
                f"repair proposal exceeds {self.max_operations} operation budget"
            )
        relations = {item.id: item for item in city.world_program.relations}
        nodes = {item.entity_id: item for item in city.world_program.nodes}
        operations = []
        owners = set()
        for item in raw_operations:
            value_text = item["value_json"]
            if not isinstance(value_text, str):
                raise ValueError("value_json must be a JSON-encoded string")
            value = json.loads(value_text)
            if item['op'] == 'add_relation':
                if item['path'] or not isinstance(value,dict) or not {'id','relation_type','source_id','target_ids'} <= set(value):
                    raise ValueError('add_relation requires an empty path and a Relation object. '
                                     'For bounds, room_b_id or other existing entity fields use '
                                     'replace_entity with that field path and JSON-encoded field value.')
            operation = PatchOperation(
                op=str(item["op"]),
                target_id=str(item["target_id"]),
                path=str(item["path"]),
                value=value,
            )
            operations.append(operation)
            if operation.op in {"replace_relation", "remove_relation"}:
                relation = relations.get(operation.target_id)
                if relation is None:
                    raise ValueError(f"unknown relation: {operation.target_id}")
                owners.add(relation.source_id)
            else:
                owners.add(operation.target_id)
        missing = sorted(owners - set(nodes))
        if missing:
            raise ValueError(f"operation owners have no CCWP nodes: {', '.join(missing)}")
        return WorldPatch(
            id=f"agent_repair__{scope_id}__attempt_{attempt:02d}",
            scope_entity_id=scope_id,
            operations=tuple(operations),
            expected_versions={owner: nodes[owner].version for owner in sorted(owners)},
            author=f"RepairAgent:{self.model_id}",
            reason=str(proposal.get("reason", "validator-guided repair")),
        )

    def _context(
        self, city: City, report: ValidationReport, scope_id: str
    ) -> dict[str, Any]:
        graph = DependencyGraph(city)
        allowed = graph.descendants(scope_id)
        entities = entity_index(city)
        error_codes = {item.code for item in report.errors}
        access_slice = (
            "entrance_not_connected" in error_codes
            and error_codes
            <= {
                "entrance_not_connected",
                "end_to_end_access_failed",
                "missing_contract_relation",
            }
        )
        detail_object_ids = {
            node.entity_id
            for node in city.world_program.nodes
            if node.entity_type == "interior_object"
        }
        furnishing_error_codes = {
            "invalid_object_room",
            "invalid_object_size",
            "object_outside_room",
            "stale_room_object_index",
            "interior_object_overlap",
            "object_blocks_door_clearance",
        }
        include_detail_objects = bool(error_codes & furnishing_error_codes)
        context_ids = {scope_id} if access_slice else set(allowed)
        if not include_detail_objects:
            context_ids -= detail_object_ids
        contracts = [
            item
            for item in city.world_program.contracts
            if (
                item.scope_id in context_ids
                or context_ids.intersection(item.subject_ids)
            )
            and (include_detail_objects or item.kind != "furnishing_clearance")
        ]
        external_ids = {
            subject
            for contract in contracts
            for subject in contract.subject_ids
            if subject not in allowed
        }
        relations = [
            item
            for item in city.world_program.relations
            if (
                (item.source_id in context_ids or context_ids.intersection(item.target_ids))
                and (not access_slice or item.relation_type == "accessible_from")
                and (
                    include_detail_objects
                    or (
                        item.source_id not in detail_object_ids
                        and not detail_object_ids.intersection(item.target_ids)
                    )
                )
            )
        ]
        derived = []
        for entity_id in sorted(allowed):
            entity = entities.get(entity_id)
            if isinstance(entity, Building):
                road = min(
                    city.road_network.segments,
                    key=lambda item: point_segment_distance(
                        entity.entrance, item.centerline
                    ),
                )
                derived.append(
                    {
                        "kind": "nearest_road",
                        "building_id": entity.id,
                        "road_id": road.id,
                        "entrance": to_primitive(entity.entrance),
                        "distance_m": round(
                            point_segment_distance(entity.entrance, road.centerline), 6
                        ),
                    }
                )
        return {
            "allowed_patch_scope": scope_id,
            "errors": [
                item
                for item in report.to_dict()["issues"]
                if item["severity"] == "error"
            ],
            "scope_nodes": [
                {
                    "entity_id": node.entity_id,
                    "entity_type": node.entity_type,
                    "parent_id": node.parent_id,
                    "version": node.version,
                    "locked": node.locked,
                    "contract_ids": node.contract_ids,
                    "relation_ids": node.relation_ids,
                }
                for node in city.world_program.nodes
                if node.entity_id in context_ids
            ],
            "scope_entity_summaries": {
                key: _compact_entity(entities[key])
                for key in sorted(context_ids)
                if key in entities
            },
            "external_contract_entities": {
                key: to_primitive(entities[key])
                for key in sorted(external_ids)
                if key in entities
            },
            "contracts": [to_primitive(item) for item in contracts],
            "relations": [to_primitive(item) for item in relations],
            "derived_facts": derived,
            "relation_protocol": {
                "building_pedestrian_access": {
                    "relation_type": "accessible_from",
                    "source": "building_id",
                    "target_ids": ["nearest road_id"],
                    "properties": {
                        "mode": "pedestrian",
                        "entrance": {"x": "building entrance x", "y": "building entrance y"},
                        "distance_m": "derived nearest-road distance_m",
                    },
                    "id": "use the relation_id required by the entrance_access contract",
                },
                "containment": "contains",
                "road_topology": "connects",
                "room_door": "connects_rooms",
                "exterior_door": "connects_exterior",
                "vertical_circulation": "connects_levels",
            },
        }

    def _system_prompt(self, scope_id: str) -> str:
        return (
            "You are CityG's Repair Agent. Return the smallest patch that resolves every "
            "reported error. The deterministic PatchEngine is the final authority. You may "
            f"only modify the subtree {scope_id}. Never invent entity IDs; use the provided "
            "entities, contracts, relations and derived facts. Each operation contains op, "
            "target_id, path, and value_json. value_json must itself be a valid compact JSON "
            "string; use the string 'null' when an operation has no value. For add_relation, "
            "target_id is the source entity, path is empty, and value_json encodes a Relation "
            "with id, relation_type, source_id, target_ids, and properties. Preserve contract "
            "relation IDs. Treat relation_protocol as an exact enum and field contract; do not "
            "guess synonyms. For existing geometry or door endpoints use replace_entity, "
            "target_id=the existing entity ID, path=the exact field (bounds or room_b_id), "
            "and value_json=the JSON-encoded NEW FIELD VALUE, not the whole entity. "
            "For example a bounds value is {min_x:number,min_y:number,max_x:number,max_y:number}; "
            "a room_b_id value is a JSON-quoted existing room ID. Never add a relation to repair "
            "a canonical field. Do not replace contracts, full floors, or room lists. "
            "Reconcile the canonical door endpoint with the existing connects_rooms relation; "
            "for a connector use the actual connected corridor bounds, not arbitrary coordinates. "
            "Keep reason under 160 characters. Do not modify contracts or "
            "unrelated nodes. Return JSON only."
        )


def _compact_entity(entity: Any) -> dict[str, Any]:
    """Serialize patchable fields without recursively duplicating whole subtrees."""

    if isinstance(entity, Building):
        return {
            "entity_type": "building",
            "id": entity.id,
            "name": entity.name,
            "function": entity.function,
            "footprint": to_primitive(entity.footprint),
            "entrance": to_primitive(entity.entrance),
            "metadata": entity.metadata,
            "floor_ids": [item.id for item in entity.floors],
            "vertical_connector_ids": [item.id for item in entity.vertical_connectors],
        }
    if isinstance(entity, Floor):
        return {
            "entity_type": "floor",
            "id": entity.id,
            "level": entity.level,
            "elevation_m": entity.elevation_m,
            "height_m": entity.height_m,
            "metadata": entity.metadata,
            "room_ids": [item.id for item in entity.rooms],
            "door_ids": [item.id for item in entity.doors],
        }
    if isinstance(entity, Room):
        return {
            "entity_type": "room",
            "id": entity.id,
            "name": entity.name,
            "function": entity.function,
            "bounds": to_primitive(entity.bounds),
            "height_m": entity.height_m,
            "object_ids": entity.object_ids,
        }
    if isinstance(entity, Door):
        return {
            "entity_type": "door",
            "id": entity.id,
            "room_a_id": entity.room_a_id,
            "room_b_id": entity.room_b_id,
            "position": to_primitive(entity.position),
            "width_m": entity.width_m,
            "door_type": entity.door_type,
            "interactive": entity.interactive,
        }
    if isinstance(entity, VerticalConnector):
        return {
            "entity_type": "vertical_connector",
            **to_primitive(entity),
        }
    value = to_primitive(entity)
    if isinstance(value, dict):
        value = dict(value)
        value["entity_type"] = type(entity).__name__.lower()
    return value
