"""Natural-language, versioned editing of an existing CityG scene.

The editor deliberately sits above :mod:`cityg.repair`: an LLM proposes a
small typed plan, while deterministic target binding, patch scope checks,
validation and compilation decide whether anything is committed.  In
particular, a plan that reports an ambiguous reference is persisted and
returned to the caller without changing the source scene.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from copy import deepcopy
from dataclasses import replace
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

from cityg.agents.requirement import AgentAttempt, AgentGenerationError, _parse_json_object
from cityg.assets import AssetResolver, AssetRegistry
from cityg.ccwp import DependencyGraph, build_world_program, entity_index
from cityg.naming import alias_index, annotate_city_identities, identity_registry
from cityg.geometry import GeometryCompiler
from cityg.planning.interiors import FloorDetailAgent
from cityg.refinement.building import BuildingRefinementAgent, apply_building_refinement
from cityg.refinement.room import RoomProgramAgent
from cityg.repair import ENTITY_PATCH_FIELDS, NODE_PATCH_PATHS, PatchEngine, PatchOperation, PatchRejected, WorldPatch
from cityg.schemas import Building, City, District, Floor, InteriorObject, Parcel, ProvenanceRecord, Room, VerticalConnector
from cityg.serialization import load_city, save_json, to_primitive
from cityg.services import OpenUSDBackend
from cityg.services.interfaces import ChatMessage, TextReasoningService
from cityg.validation import CityValidator
from cityg.edit_constraints import explicit_edit_constraints, validate_edit_plan_constraints, check_edit_constraints
from cityg.subtree_transactions import (
    BuildingSubtreePlanner,
    FloorSubtreePlanner,
    UrbanSubgraphPlanner,
)


EDIT_PLAN_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {
            "type": "string",
            "enum": ["apply", "needs_clarification", "replan_required"],
        },
        "reason": {"type": "string"},
        "clarification": {"type": "string"},
        "targets": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "description": {"type": "string"},
                    "resolved_ids": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number"},
                },
                "required": ["description", "resolved_ids", "confidence"],
            },
        },
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
        "visual_checks": {"type": "array", "items": {"type": "string"}},
        "asset_requests": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "description": {"type": "string"},
                    "category": {"type": "string"},
                    "target_id": {"type": "string"},
                    "dimensions_m": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    "environment": {"type": "string", "enum": ["indoor", "outdoor", "both"]},
                    "room_type": {"type": "string"},
                },
                "required": ["description", "category", "target_id", "dimensions_m", "environment", "room_type"],
            },
        },
        "replan_requests": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "kind": {"type": "string", "enum": [
                        "room_furnishing", "building_profile", "floor_layout",
                        "building_subtree", "urban_subgraph", "building_site",
                    ]},
                    "target_id": {"type": "string"},
                    "details": {"type": "string"},
                },
                "required": ["kind", "target_id", "details"],
            },
        },
    },
    "required": [
        "status", "reason", "clarification", "targets", "operations", "visual_checks",
        "asset_requests", "replan_requests",
    ],
}


@dataclass(frozen=True)
class SceneReference:
    requested_path: str
    canonical_path: Path
    run_root: Path
    compiled_path: Path | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_path": self.requested_path,
            "canonical_path": str(self.canonical_path),
            "run_root": str(self.run_root),
            "compiled_path": str(self.compiled_path) if self.compiled_path else None,
        }


def resolve_scene(path: str | Path) -> SceneReference:
    """Resolve a run directory, compiled directory, or canonical ``city.json``."""

    requested = Path(path).expanduser().resolve()
    if not requested.exists():
        raise ValueError(f"Scene path does not exist: {requested}")
    if requested.is_file():
        if requested.name != "city.json":
            raise ValueError("Scene file must be city.json")
        canonical = requested
        run_root = _infer_run_root(requested.parent)
    else:
        compiled_hint = requested / "geometry_manifest.json"
        if compiled_hint.is_file() and (requested / "city.json").is_file():
            canonical = requested / "city.json"
            run_root = _infer_run_root(requested)
        else:
            # A successful main pipeline publishes its last VLM result here.
            # Do not silently edit the earlier generation checkpoint instead.
            review_report = next((p for p in (
                requested/'visual_review/adaptive_review_report.json',
                requested/'adaptive_review_report.json') if p.is_file()), None)
            if review_report is not None:
                report = json.loads(review_report.read_text())
                published = review_report.parent/'openusd_after'
                if (report.get('rendered_inventory_acceptance', {}).get('ok') is not True
                        or not (published/'city.json').is_file()
                        or not (published/'geometry_manifest.json').is_file()):
                    raise ValueError('Completed visual review has no valid published scene package')
                run_root = requested.parent if requested.name == 'visual_review' else requested
                return SceneReference(str(path), published/'city.json', run_root, published)
            candidates = (
                requested / "final" / "city.json",
                requested / "final" / "openusd" / "city.json",
                requested / "city.json",
            )
            canonical = next((item for item in candidates if item.is_file()), None)
            if canonical is None:
                raise ValueError(
                    "Scene directory must contain final/city.json, final/openusd/city.json, or city.json"
                )
            run_root = requested
    compiled = _find_compiled_root(canonical, requested)
    return SceneReference(str(path), canonical, run_root, compiled)


def _infer_run_root(directory: Path) -> Path:
    if directory.name == "openusd" and directory.parent.name == "final":
        return directory.parent.parent
    if directory.name == "final":
        return directory.parent
    return directory


def _find_compiled_root(canonical: Path, requested: Path) -> Path | None:
    candidates = []
    if requested.is_dir():
        candidates.append(requested)
    candidates.extend(
        [
            canonical.parent,
            canonical.parent / "openusd",
            canonical.parent.parent / "openusd",
        ]
    )
    for candidate in candidates:
        if (candidate / "geometry_manifest.json").is_file() and (candidate / "city.json").is_file():
            return candidate
    return None


@dataclass(frozen=True)
class EditPlanResult:
    status: str
    reason: str
    clarification: str
    targets: tuple[dict[str, Any], ...]
    operations: tuple[dict[str, Any], ...]
    visual_checks: tuple[str, ...]
    asset_requests: tuple[dict[str, Any], ...]
    replan_requests: tuple[dict[str, Any], ...]
    model_id: str
    attempts: tuple[AgentAttempt, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "cityg.edit_plan.v1",
            "status": self.status,
            "reason": self.reason,
            "clarification": self.clarification,
            "targets": list(self.targets),
            "operations": list(self.operations),
            "visual_checks": list(self.visual_checks),
            "asset_requests": list(self.asset_requests),
            "replan_requests": list(self.replan_requests),
            "model_id": self.model_id,
            "attempts": [asdict(item) for item in self.attempts],
        }


class EditAgent:
    """Convert a user instruction into a bounded, ambiguity-aware edit plan."""

    def __init__(
        self,
        service: TextReasoningService,
        *,
        model_id: str = "unknown",
        max_attempts: int = 3,
        max_operations: int = 12,
        min_binding_confidence: float = 0.80,
    ) -> None:
        if max_attempts < 1 or max_operations < 1:
            raise ValueError("edit budgets must be positive")
        self.service = service
        self.model_id = model_id
        self.max_attempts = max_attempts
        self.max_operations = max_operations
        self.min_binding_confidence = min_binding_confidence

    def plan(self, city: City, instruction: str) -> EditPlanResult:
        if not instruction.strip():
            raise ValueError("Edit instruction must not be empty")
        deictic = _deictic_clarification(city, instruction)
        try:
            constraints=explicit_edit_constraints(city,instruction)
        except ValueError as exc:
            constraints=[]
            deictic=str(exc)
        limits = {'floor_room_count': 64, 'building_floor_count': 128,
                  'building_rooms_per_floor': 64}
        unsupported=next((c for c in constraints if c['kind'] in limits
                          and not 1<=c['expected']<=limits[c['kind']]),None)
        if deictic is None and unsupported is not None:
            unit = '层' if unsupported['kind'] == 'building_floor_count' else '个房间'
            deictic=(f"明确要求 {unsupported['expected']} {unit}，当前替换仅支持 1～{limits[unsupported['kind']]}，且还需几何验证。"
                     "本次不编辑，不会减少数量或改用原房间数。请调整要求或先扩展规划器能力。")
        if deictic is not None:
            # Do not ask the model to guess a referent that the deterministic
            # index already proves is non-unique.  This is the hard safety
            # boundary for phrases such as “这栋楼” and “这块空地”.
            return EditPlanResult(
                status="needs_clarification",
                reason="Unsupported explicit count." if unsupported else "The instruction contains a non-unique deictic reference.",
                clarification=deictic,
                targets=(),
                operations=(),
                visual_checks=(),
                asset_requests=(),
                replan_requests=(),
                model_id=self.model_id,
                attempts=(),
            )
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=self._system_prompt()),
            ChatMessage(
                role="user",
                content=json.dumps(
                    {"instruction": instruction.strip(), "scene_index": _scene_index(city, instruction),
                     "explicit_postconditions":constraints},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            ),
        ]
        attempts: list[AgentAttempt] = []
        for index in range(1, self.max_attempts + 1):
            started = time.monotonic()
            raw = ""
            finish_reason = None
            usage: dict[str, Any] = {}
            error: str | None = None
            candidate: dict[str, Any] | None = None
            try:
                method = getattr(self.service, "complete_with_metadata", None)
                if callable(method):
                    completion = method(messages, EDIT_PLAN_RESPONSE_SCHEMA)
                    raw, finish_reason, usage = completion.content, completion.finish_reason, completion.usage
                else:
                    raw = self.service.complete(messages, EDIT_PLAN_RESPONSE_SCHEMA)
                if finish_reason == "length":
                    raise ValueError("model output reached max_tokens before completing JSON")
                candidate = _normalize_plan(_parse_json_object(raw), self.max_operations)
                from cityg.edit_constraints import explicit_entity_ids
                self._validate_plan(city, candidate, explicit_ids=explicit_entity_ids(city,instruction))
                validate_edit_plan_constraints(candidate,constraints)
            except (TypeError, ValueError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
                error = f"{type(exc).__name__}: {exc}"
            serialized = tuple({"role": item.role, "content": item.content} for item in messages)
            prompt_hash = hashlib.sha256(
                json.dumps(serialized, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            attempts.append(
                AgentAttempt(
                    index=index,
                    prompt_hash=prompt_hash,
                    messages=serialized,
                    raw_output=raw,
                    elapsed_s=round(time.monotonic() - started, 6),
                    error=error,
                    finish_reason=finish_reason,
                    usage=usage,
                )
            )
            if error is None and candidate is not None:
                return EditPlanResult(
                    status=candidate["status"],
                    reason=candidate["reason"],
                    clarification=candidate["clarification"],
                    targets=tuple(candidate["targets"]),
                    operations=tuple(candidate["operations"]),
                    visual_checks=tuple(candidate["visual_checks"]),
                    asset_requests=tuple(candidate["asset_requests"]),
                    replan_requests=tuple(candidate["replan_requests"]),
                    model_id=self.model_id,
                    attempts=tuple(attempts),
                )
            if index < self.max_attempts:
                messages.extend(
                    [
                        ChatMessage(role="assistant", content=raw[:12000]),
                        ChatMessage(role="user", content=f"Correct the edit plan. Validation error: {error}"),
                    ]
                )
        raise AgentGenerationError(f"Edit agent failed after {self.max_attempts} attempts", attempts)

    def _validate_plan(self, city: City, plan: dict[str, Any], *, explicit_ids=None) -> None:
        status = plan["status"]
        entities = entity_index(city)
        ids = set(entities)
        aliases = alias_index(city)

        def canonical(value: Any) -> str:
            candidate = str(value)
            if candidate in ids:
                return candidate
            matches = aliases.get(candidate, ())
            if len(matches) == 1:
                return matches[0]
            return candidate

        for target in plan["targets"]:
            confidence = float(target["confidence"])
            resolved = [canonical(item) for item in target["resolved_ids"]]
            target["resolved_ids"] = resolved
            if confidence < self.min_binding_confidence:
                raise ValueError(
                    f"ambiguous target '{target['description']}' has confidence {confidence:.2f}"
                )
            if not resolved or any(item not in ids for item in resolved):
                raise ValueError("target binding contains an unknown or empty entity ID")
        grounded_ids = {
            item for target in plan["targets"] for item in target["resolved_ids"]
        }
        omitted_targets = not plan['targets']
        if status != "apply":
            if plan["operations"] or plan["asset_requests"]:
                raise ValueError("non-apply edit plans must not contain patch operations or asset requests")
            if status == "replan_required" and not plan["replan_requests"]:
                raise ValueError("replan_required plans must contain replan_requests")
            for request in plan["replan_requests"]:
                request["target_id"] = canonical(request["target_id"])
                if request["target_id"] not in ids:
                    raise ValueError(f"unknown replan target: {request['target_id']}")
                # Qwen occasionally emits a structurally valid replan request
                # but omits the redundant ``targets`` array when the request
                # already contains an exact canonical ID.  Ground that explicit
                # ID deterministically rather than asking the model to repeat
                # itself; ambiguous natural-language targets still fail below.
                if (omitted_targets and request["target_id"] not in grounded_ids
                        and request["target_id"] in (explicit_ids or set())):
                    plan["targets"].append({
                        "description": request["target_id"],
                        "resolved_ids": [request["target_id"]],
                        "confidence": 1.0,
                    })
                    grounded_ids.add(request["target_id"])
                if request["target_id"] not in grounded_ids:
                    raise ValueError(f"replan target {request['target_id']} is not grounded")
                target = entities[request["target_id"]]
                valid = {
                    "room_furnishing": isinstance(target, Room),
                    "building_profile": isinstance(target, Building),
                    "floor_layout": isinstance(target, Floor),
                    "building_subtree": isinstance(target, Building),
                    "building_site": isinstance(target, Building),
                    "urban_subgraph": isinstance(target, (City, District, Parcel)),
                }.get(request["kind"], False)
                if not valid:
                    raise ValueError(
                        f"replan kind {request['kind']} is incompatible with target {request['target_id']}"
                    )
            return
        if not plan["operations"]:
            raise ValueError("apply edit plan must contain operations")
        for request in plan["asset_requests"]:
            request["target_id"] = canonical(request["target_id"])
            if request["target_id"] not in ids:
                raise ValueError(f"asset request targets an unknown entity: {request['target_id']}")
            if request["target_id"] not in grounded_ids:
                raise ValueError(f"asset request target {request['target_id']} is not grounded")
            if len(request["dimensions_m"]) != 3 or any(value <= 0 for value in request["dimensions_m"]):
                raise ValueError("asset request dimensions_m must contain three positive numbers")
            if request["environment"] not in {"indoor", "outdoor", "both"}:
                raise ValueError("asset request environment must be indoor, outdoor, or both")
        for operation in plan["operations"]:
            # Validate the nested JSON while the model can still correct its
            # proposal. Never guess whether an unquoted token is a string,
            # number or malformed object during transaction execution.
            try:
                json.loads(operation["value_json"])
            except (TypeError, ValueError) as error:
                raise ValueError(
                    'operation.value_json must encode valid JSON; string values '
                    'must include JSON quotation marks, e.g. "New name"'
                ) from error
            operation["target_id"] = canonical(operation["target_id"])
            if operation["target_id"] not in ids:
                raise ValueError(f"unknown edit target: {operation['target_id']}")
            if operation["target_id"] not in grounded_ids:
                raise ValueError(
                    f"edit target {operation['target_id']} is not covered by a grounded target"
                )
            entity=entities[operation['target_id']]
            canonical_operation=_material_field_alias(entity,operation)
            op,path=canonical_operation['op'],canonical_operation['path']
            allowed=next((fields for cls,fields in ENTITY_PATCH_FIELDS.items() if isinstance(entity,cls)),())
            if op=='replace_entity' and path not in allowed:
                raise ValueError(f'Unpatchable entity field {path}; allowed top-level fields: {sorted(allowed)}')
            if op=='replace_node' and path not in NODE_PATCH_PATHS:
                # Existing name/function aliases are resolved again at commit;
                # do not allow arbitrary nested CCWP paths through this check.
                alias='name' if path=='display_name' else path
                if alias not in allowed:
                    raise ValueError(f'Unpatchable CCWP field {path}; node paths: {sorted(NODE_PATCH_PATHS)}. '
                                     'Building material uses appearance_plan.material_family.')

    def _system_prompt(self) -> str:
        return (
            "You are CityG's Edit Planning Agent. Convert one user instruction into a "
            "strict JSON edit plan over the supplied scene index. Never invent IDs. "
            "If a phrase such as 'this building', 'that open area', 'the building' or "
            "'the room' cannot be resolved to exactly one confident entity from the "
            "index, return status='needs_clarification', leave operations empty, and "
            "write a concise Chinese clarification. Use status='replan_required' for "
            "structural changes; then provide a replan_requests entry with kind "
            "room_furnishing, building_profile, floor_layout, building_subtree, or "
            "urban_subgraph, or building_site. For translating a building with its contents, resizing an exterior-only shell, or resizing a furnished building "
            "inside its existing parcel, use building_site with details JSON containing area_m2, aspect_ratio "
            "(width/depth; omit unless explicitly changing shape), "
            "allow_aspect_adjustment=true only if the user allows changing the aspect ratio at fixed area, "
            "offset_x_m, offset_y_m as needed. Omitted values preserve existing dimensions/position; "
            "do not invent aspect_ratio=1 for an area-only edit. Preserve furniture dimensions and inventory; request local floor/room replanning for a furnished tower or compound massing; "
            "do not use site adaptation to erase interiors. Site moves revalidate urban relationships, "
            "setbacks, access, floors and cores. If the instruction adds, removes, or rearranges furniture "
            "inside a room, always use status='replan_required' with kind='room_furnishing' "
            "instead of add_relation (relations are only for existing CCWP links). Only use status='apply' "
            "for low-risk edits. Every target must include resolved IDs and confidence "
            ">= 0.80. Asset requests must name a target object when a generated or "
            "retrieved asset should be bound. Operations use value_json as a JSON-encoded "
            'value, including escaped quotation marks for a string such as a name. '
            'For a building material edit use replace_entity with path appearance_plan.material_family '
            'and a brick/plaster/stone/metal/glass string. This is a narrow deep-merge alias preserving '
            'the rest of metadata; do not replace all metadata or invent arbitrary nested node paths. '
            "Return JSON only."
        )


def _normalize_plan(raw: dict[str, Any], max_operations: int) -> dict[str, Any]:
    known = {
        "status", "reason", "clarification", "targets", "operations", "visual_checks",
        "asset_requests", "replan_requests",
    }
    unknown = sorted(set(raw) - known)
    if unknown:
        raise ValueError(f"Unknown edit plan fields: {', '.join(unknown)}")
    status = str(raw.get("status", ""))
    if status not in {"apply", "needs_clarification", "replan_required"}:
        raise ValueError("edit plan status must be apply, needs_clarification, or replan_required")
    targets = raw.get("targets", [])
    operations = raw.get("operations", [])
    if not isinstance(targets, list) or not isinstance(operations, list):
        raise ValueError("targets and operations must be arrays")
    if len(operations) > max_operations:
        raise ValueError(f"edit plan exceeds {max_operations} operation budget")
    return {
        "status": status,
        "reason": str(raw.get("reason", ""))[:500],
        "clarification": str(raw.get("clarification", ""))[:1000],
        "targets": [
            {
                "description": str(item.get("description", "")),
                "resolved_ids": [str(value) for value in item.get("resolved_ids", [])],
                "confidence": float(item.get("confidence", 0.0)),
            }
            for item in targets
            if isinstance(item, dict)
        ],
        "operations": [
            {
                "op": str(item.get("op", "")),
                "target_id": str(item.get("target_id", "")),
                "path": str(item.get("path", "")),
                "value_json": str(item.get("value_json", "null")),
            }
            for item in operations
            if isinstance(item, dict)
        ],
        "visual_checks": [str(value) for value in raw.get("visual_checks", [])],
        "asset_requests": [
            {
                "description": str(item.get("description", "")),
                "category": str(item.get("category", "")),
                "target_id": str(item.get("target_id", "")),
                "dimensions_m": [float(value) for value in item.get("dimensions_m", [1, 1, 1])],
                "environment": str(item.get("environment", "both")),
                "room_type": str(item.get("room_type", "")),
            }
            for item in raw.get("asset_requests", [])
            if isinstance(item, dict)
        ],
        "replan_requests": [
            {
                "kind": str(item.get("kind", "")),
                "target_id": str(item.get("target_id", "")),
                "details": str(item.get("details", "")),
            }
            for item in raw.get("replan_requests", [])
            if isinstance(item, dict)
        ],
    }


def _scene_index(city: City, instruction: str = "") -> list[dict[str, Any]]:
    """Create a compact, deterministic index suitable for target grounding."""

    # City-scale scenes may contain tens of thousands of furniture objects.
    # Include all structural entities, but expand objects only for an
    # explicitly mentioned room/object (or a small furniture sample).  The
    # editor still validates IDs against the complete canonical city after the
    # model responds; this is a prompt-size optimization, not a permission to
    # invent hidden entities.
    stable_ids = set(re.findall(
        r"(?:city|district|parcel|building|floor|room|door|object|road_segment|junction)[_:-][A-Za-z0-9_.-]+",
        instruction or "", flags=re.IGNORECASE,
    ))
    identities = identity_registry(city)
    aliases = alias_index(city)
    # Also recognize the additive identity forms.  Full paths are intentionally
    # matched as one token so a room-level edit receives its local furniture
    # context instead of the city-scale compact index.
    stable_ids.update(re.findall(r"cityg:[A-Za-z0-9_]+:[A-Fa-f0-9]{8,}", instruction or ""))
    stable_ids.update(re.findall(
        r"(?:city|district|parcel|building|floor|room|interior_object|vertical_connector|door|road_segment|junction)/[A-Za-z0-9_.:/-]+",
        instruction or "",
    ))
    stable_ids = {
        canonical_id
        for alias in stable_ids
        for canonical_id in aliases.get(alias, (alias,))
    }
    focus_rooms = set(stable_ids)
    parent_map = {entity.id: parent for entity, _, parent in city.iter_entities()}
    type_map = {entity.id: entity_type for entity, entity_type, _ in city.iter_entities()}
    focused_ids: set[str] = set()
    # Keep the complete urban/building index for grounding, but expose only
    # the relevant structural depth for an explicit target.  A building edit
    # does not need hundreds of room/object records; a room edit does need its
    # local objects.  This keeps prompts well below vLLM's context limit.
    for target_id in stable_ids:
        if target_id not in type_map:
            continue
        target_type = type_map[target_id]
        allowed_descendants = {
            "building": {"floor"},
            "floor": {"room", "door"},
            "room": {"interior_object", "door"},
            "interior_object": set(),
        }.get(target_type, set())
        focused_ids.add(target_id)
        for entity, entity_type, _ in city.iter_entities():
            cursor: str | None = entity.id
            while cursor is not None and cursor != target_id:
                cursor = parent_map.get(cursor)
            if cursor == target_id and entity_type in allowed_descendants:
                focused_ids.add(entity.id)
        cursor = target_id
        while parent_map.get(cursor) is not None:
            cursor = parent_map[cursor]  # type: ignore[assignment]
            focused_ids.add(cursor)
    for entity, entity_type, _ in city.iter_entities():
        if entity_type != "room":
            continue
        cursor: str | None = entity.id
        while cursor is not None:
            if cursor in stable_ids:
                focus_rooms.add(entity.id)
                break
            cursor = parent_map.get(cursor)
    include_all_objects = bool(re.search(r"家具|物体|桌|椅|沙发|柜|object|furniture|sofa|chair|desk", instruction or "", re.I))
    object_budget = 160 if include_all_objects and not focus_rooms else None
    result: list[dict[str, Any]] = []
    object_seen = 0
    for entity, entity_type, parent_id in city.iter_entities():
        if focused_ids and entity_type not in {"city", "district", "parcel", "building"} and entity.id not in focused_ids:
            continue
        if entity_type == "interior_object":
            if focus_rooms and entity.room_id not in focus_rooms and entity.id not in stable_ids:
                continue
            if object_budget is not None and object_seen >= object_budget:
                continue
            object_seen += 1
        item: dict[str, Any] = {
            "id": entity.id,
            "type": entity_type,
            "parent_id": parent_id,
        }
        identity = identities.get(entity.id)
        if identity:
            item.update(
                {
                    "entity_type": identity["entity_type"],
                    "uid": identity["uid"],
                    "path": identity["path"],
                    "display_name": identity["display_name"],
                }
            )
        if isinstance(entity, City):
            item["name"] = entity.name
            item["bounds"] = to_primitive(entity.bounds)
            item['urban_requirements'] = entity.metadata.get('urban_requirements', [])
        elif isinstance(entity, Building):
            item.update(
                {
                    "name": entity.name,
                    "function": entity.function,
                    "footprint": to_primitive(entity.footprint),
                    "floor_count": len(entity.floors),
                    "center": to_primitive(entity.footprint.center),
                }
            )
            if entity.id in stable_ids:
                item['appearance_plan']=deepcopy(entity.metadata.get('appearance_plan',{}))
                parent_parcel = next((p for p in city.iter_parcels()
                                      if any(b.id == entity.id for b in p.buildings)), None)
                if parent_parcel is not None:
                    item['parcel_bounds'] = to_primitive(parent_parcel.bounds)
                    item['parcel_setback_m'] = city.metadata.get('parcel_setback_m', 4.0)
                item['has_furnished_floors'] = any(f.objects for f in entity.floors)
                item['massing_style'] = entity.metadata.get('massing_style', 'bar')
                item['orientation_deg'] = entity.metadata.get('orientation_deg', 0)
                scope = city.metadata.get('interior_scope')
                if scope is not None:
                    item['enabled_interior_levels'] = scope['building_levels'].get(entity.id, [])
        elif isinstance(entity, Floor):
            item.update({"level": entity.level, "height_m": entity.height_m, "room_count": len(entity.rooms)})
        elif isinstance(entity, Room):
            # Room indices can be very large in a city-scale scene.  Stable
            # IDs, parent and semantic function are sufficient for grounding;
            # detailed bounds remain available through city.json after a target
            # has been selected.  Keeping this compact avoids exhausting the
            # model context before it can emit a plan.
            item.update({"function": entity.function})
        elif isinstance(entity, InteriorObject):
            item.update({"category": entity.category, "room_id": entity.room_id})
        elif hasattr(entity, "function"):
            item["function"] = getattr(entity, "function")
        result.append(item)
    return result


def _deictic_clarification(city: City, instruction: str) -> str | None:
    """Return a Chinese clarification for an unqualified deictic phrase.

    The LLM still handles richer descriptions (for example “最高的办公楼”),
    but a bare “这栋楼/这个房间/这块空地” is rejected when the scene has more
    than one plausible entity.  Stable IDs in the instruction opt into normal
    model planning.
    """

    stable_id = re.search(
        r"(?:city|district|parcel|building|floor|room|door|object|road_segment|junction)[_:-][A-Za-z0-9_.-]+",
        instruction,
        flags=re.IGNORECASE,
    )
    if stable_id:
        return None
    checks = (
        (r"这(?:栋|幢|座)楼|那(?:栋|幢|座)楼|该楼|the building|this building|that building", len(list(city.iter_buildings())), "楼"),
        (r"这(?:一)?层|该楼层|这个楼层|the floor|this floor|that floor", len(list(city.iter_floors())), "楼层"),
        (r"这(?:个)?房间|该房间|这个房间|the room|this room|that room", len(list(city.iter_rooms())), "房间"),
        (r"这块空地|那块空地|该空地|the open area|this open area|that open area", len(list(city.iter_parcels())), "空地/地块"),
    )
    for pattern, count, label in checks:
        if re.search(pattern, instruction, flags=re.IGNORECASE) and count != 1:
            return f"“{label}”的指代不明确；当前场景有 {count} 个候选，请提供稳定实体 ID（例如 building_03）或更具体的位置/功能描述。"
    return None


def _material_field_alias(entity, operation):
    """One explicit semantic field alias, not a general nested metadata writer."""
    if (operation['op'] in {'replace_entity','replace_node'} and operation['path']=='display_name'
            and isinstance(entity,(City,District,Building,Room))):
        return {**operation,'op':'replace_entity','path':'name'}
    if (operation['op'] not in {'replace_entity','replace_node'} or operation['path'] not in
            {'appearance_plan.material_family','metadata.appearance_plan.material_family'}):
        return operation
    from cityg.architecture import MATERIAL_FAMILIES, validate_appearance_plan
    value=json.loads(operation['value_json'])
    if not isinstance(entity,Building) or value not in MATERIAL_FAMILIES:
        raise ValueError('Material alias requires a building and a supported material family')
    metadata=deepcopy(entity.metadata)
    metadata.setdefault('appearance_plan',{})['material_family']=value
    validate_appearance_plan(metadata['appearance_plan'])
    return {**operation,'op':'replace_entity','path':'metadata',
            'value_json':json.dumps(metadata,ensure_ascii=False)}


def apply_edit_plan(city: City, plan: EditPlanResult, *, patch_id: str | None = None, memory_store=None):
    """Apply an accepted low-risk plan transactionally through PatchEngine."""

    if plan.status != "apply":
        raise ValueError(f"Cannot apply edit plan with status {plan.status}")
    operations = []
    owners: set[str] = set()
    relations = {item.id: item for item in city.world_program.relations}
    nodes = {item.entity_id: item for item in city.world_program.nodes}
    canonical_entities = entity_index(city)
    for raw in plan.operations:
        # Some instruct models naturally interpret a building's name/function
        # as a CCWP node field.  Normalize those two safe aliases to the
        # canonical entity so an otherwise valid edit is not rejected merely
        # because it chose the overlay vocabulary.
        entity = canonical_entities.get(raw.get("target_id"))
        raw = _material_field_alias(entity, raw)
        raw_path = raw.get("path")
        if raw.get("op") in {"replace_node", "add_relation"}:
            # ``display_name`` is an agent/UI alias for the canonical ``name``
            # field.  ``add_relation`` with a scalar name is a common model
            # mistake; converting it here keeps the edit transactional while
            # preserving strict relation validation for genuine relations.
            if raw_path == "display_name" and isinstance(entity, (City, District, Building, Room)):
                raw = {**raw, "op": "replace_entity", "path": "name"}
            elif raw_path in {"name", "function", "metadata"} and isinstance(
                entity, (District, Building, Room, Floor, VerticalConnector, InteriorObject)
            ):
                raw = {**raw, "op": "replace_entity"}
            elif raw.get("op") == "add_relation" and raw_path and hasattr(entity, "metadata"):
                # Another frequent model form is ``add_relation`` with a
                # scalar metadata field (for example
                # ``facade_style_override``).  Treat it as a metadata merge;
                # genuine relations use an empty path and a mapping value.
                current_metadata = dict(getattr(entity, "metadata", {}) or {})
                current_metadata[str(raw_path)] = json.loads(raw["value_json"])
                raw = {
                    **raw,
                    "op": "replace_entity",
                    "path": "metadata",
                    "value_json": json.dumps(current_metadata, ensure_ascii=False),
                }
        operation = PatchOperation(
            op=raw["op"], target_id=raw["target_id"], path=raw["path"], value=json.loads(raw["value_json"])
        )
        operations.append(operation)
        if operation.op in {"replace_relation", "remove_relation"}:
            relation = relations.get(operation.target_id)
            if relation is None:
                raise PatchRejected("unknown_target", f"Unknown relation {operation.target_id}")
            owners.add(relation.source_id)
        else:
            owners.add(operation.target_id)
    unknown = sorted(owners - set(nodes))
    if unknown:
        raise PatchRejected("unknown_target", f"Unknown edit target(s): {unknown}")
    scope = DependencyGraph(city).lowest_common_ancestor(owners) or city.id
    expected_versions = {owner: nodes[owner].version for owner in owners}
    patch = WorldPatch(
        id=patch_id or f"edit__{city.id}__{int(time.time())}",
        scope_entity_id=scope,
        operations=tuple(operations),
        expected_versions=expected_versions,
        author="cityg_edit_agent",
        reason=plan.reason,
    )
    applied = PatchEngine(CityValidator()).apply(city, patch, source='user_edit', memory_store=memory_store)
    # PatchEngine preserves the canonical CCWP overlay but does not know about
    # the additive naming registry. Refresh it before serializing this version
    # so a rename or metadata replacement cannot leave stale display names or
    # dangling identities in city.json.
    annotate_city_identities(applied.city)
    return applied, patch


def _resolve_asset_requests(
    city: City,
    plan: EditPlanResult,
    resolver: AssetResolver | None,
) -> tuple[EditPlanResult, list[dict[str, Any]]]:
    """Resolve requested assets and turn successful object requests into patches."""

    outcomes: list[dict[str, Any]] = []
    extra_operations: list[dict[str, Any]] = []
    entities = entity_index(city)
    if plan.asset_requests and resolver is None:
        return plan, [
            {"request": request, "status": "deferred", "reason": "asset resolver is not configured"}
            for request in plan.asset_requests
        ]
    for request in plan.asset_requests:
        target = entities.get(request["target_id"])
        if not isinstance(target, InteriorObject):
            outcomes.append({"request": request, "status": "deferred", "reason": "asset target must be an interior object"})
            continue
        try:
            record = resolver.resolve(
                request["description"],
                category=request["category"] or None,
                dimensions_m=tuple(request["dimensions_m"]),
                environment=request["environment"],
                room_type=request["room_type"] or None,
            )
        except Exception as error:
            outcomes.append({"request": request, "status": "failed", "reason": f"{type(error).__name__}: {error}"})
            continue
        if record is None:
            outcomes.append({"request": request, "status": "missing", "reason": "no local or provider asset"})
            continue
        extra_operations.append({
            "op": "replace_entity",
            "target_id": target.id,
            "path": "asset_id",
            "value_json": json.dumps(record.asset_id),
        })
        outcomes.append({"request": request, "status": "resolved", "asset_id": record.asset_id, "source": record.source})
    if extra_operations:
        plan = replace(plan, operations=tuple([*plan.operations, *extra_operations]))
    return plan, outcomes


def _site_compile_receipt(current, proposed, target_id, metadata, room_compiler):
    from cityg.geometry import GeometryValidator
    from cityg.validation.local_room import building_compilation_gate
    scene = room_compiler.compile(proposed)
    checked = GeometryValidator().validate(proposed, scene)
    receipt = {'ok': checked.ok, 'geometry': checked.to_dict()}
    target = next(b for b in proposed.iter_buildings() if b.id == target_id)
    objects = [o for f in target.floors for o in f.objects]
    joint = metadata.get('coordination')
    if joint is not None:
        from cityg.planning.floor_repartition import _check_compiled_access
        from cityg.planning.interior_scope import floor_enabled
        floors = [f for f in target.floors if f.objects or f.id in joint['revised_floors']]
        if not floors:
            floors = [f for f in target.floors if floor_enabled(proposed, target, f)]
        for floor in floors:
            _check_compiled_access(scene, target, floor, floor)
        receipt['compiled_access_floors'] = [f.id for f in floors]
    if checked.ok and objects:
        from cityg.planning.site_furniture import compiled_furniture_preserved
        from cityg.schemas import Point2D
        before_scene = room_compiler.compile(current,building_ids={target_id})
        request_values = metadata['request']
        shift = (Point2D(request_values.get('offset_x_m',0),request_values.get('offset_y_m',0))
                 if metadata['operation']=='translate' else None)
        receipt['checked_furniture_primitives'] = compiled_furniture_preserved(
            before_scene, scene, objects, shift)
    if checked.ok and metadata['operation']=='resize' and any(f.objects for f in target.floors):
        if not room_compiler.include_interiors:
            raise ValueError('Furnished resizing requires interior compilation')
        retention = building_compilation_gate(current,target_id,room_compiler)(proposed)
        receipt.update(ok=retention['ok'], room_retention=retention)
    return receipt


def _apply_replans(
    city: City,
    requests: Sequence[dict[str, Any]],
    service: TextReasoningService,
    *,
    model_id: str,
    asset_resolver: AssetResolver | None,
    room_compiler=None,
    trace_sink=None,
    memory_store=None,
) -> tuple[City, list[str], list[dict[str, Any]]]:
    """Apply supported local re-plans; unsupported requests remain deferred."""

    current = city
    touched: list[str] = []
    traces: list[dict[str, Any]] = []
    for request in requests:
        kind = request["kind"]
        target_id = request["target_id"]
        if kind == "building_profile":
            agent = BuildingRefinementAgent(service, model_id=model_id, max_attempts=2, memory_store=memory_store)
            plan, attempts = agent.propose(
                current, target_id, visual_feedback={"edit_instruction": request["details"]}
            )
            from cityg.validation.local_room import building_compilation_gate
            result = apply_building_refinement(current, plan, source='user_edit',
                memory_store=memory_store,
                compiled_gate=building_compilation_gate(current, target_id, room_compiler)
                              if room_compiler is not None else None)
            current = result.city
            touched.append(target_id)
            traces.append({
                "kind": kind,
                "target_id": target_id,
                "plan": asdict(plan),
                "attempts": [asdict(item) for item in attempts],
                "patch": to_primitive(result.patch),
                "transaction": result.transaction_report,
            })
            continue
        if kind == "room_furnishing":
            target = next(
                (
                    (building, floor, room)
                    for building in current.iter_buildings()
                    for floor in building.floors
                    for room in floor.rooms
                    if room.id == target_id
                ),
                None,
            )
            if target is None:
                raise ValueError(f"unknown room replan target: {target_id}")
            building, floor, room = target
            trace = {'kind':kind, 'target_id':target_id, 'status':'planning'}
            traces.append(trace)
            try:
                program_result = RoomProgramAgent(
                    service, model_id=model_id, max_attempts=2, asset_resolver=asset_resolver,
                    memory_store=memory_store
                ).propose(current, building, floor, room, visual_feedback=request["details"])
            except Exception as error:
                trace.update(status='rejected', error=str(error),
                    attempts=[asdict(a) for a in getattr(error, 'attempts', [])])
                if trace_sink: trace_sink(traces)
                raise
            trace.update(status='proposed', program=to_primitive(program_result.program),
                raw=program_result.raw, attempts=[asdict(a) for a in program_result.attempts])
            if trace_sink: trace_sink(traces)
            from cityg.refinement.room_commit import commit_room_program
            from cityg.validation.local_room import room_compilation_gate
            try:
                committed, _ = commit_room_program(current, room.id, program_result.program,
                    asset_resolver=asset_resolver, seed=17, source='user_edit',
                    memory_store=memory_store,
                    compiled_gate=room_compilation_gate(current, room.id, room_compiler)
                                  if room_compiler is not None else None)
            except Exception as error:
                trace.update(status='rejected', error=str(error))
                if trace_sink: trace_sink(traces)
                raise
            current = committed.city
            touched.append(target_id)
            trace.update(status='accepted', transaction=committed.report)
            if trace_sink: trace_sink(traces)
            continue
        if kind in {"floor_layout", "building_subtree", "urban_subgraph", "building_site"}:
            from cityg.planning.building_site import BuildingSitePlanner
            from cityg.transactions import MutationProposal, accept_candidate, fingerprint, refresh_local_overlay
            mutation = MutationProposal.bind(current, [target_id], source='user_edit', kind=kind,
                proposal_id=f'{kind}__{target_id}__{fingerprint(current)[:16]}',
                preserve_inventory=(kind == 'building_site'))
            planner = {
                "floor_layout": FloorSubtreePlanner(),
                "building_subtree": BuildingSubtreePlanner(),
                "urban_subgraph": UrbanSubgraphPlanner(),
                "building_site": BuildingSitePlanner(),
            }[kind]
            # Details are intentionally passed as an opaque semantic payload;
            # planners accept either a JSON-like mapping or a conservative
            # natural-language fallback.  This lets the LLM describe intent
            # without emitting absolute room coordinates.
            def accept_result(result, gate=None):
                candidate = refresh_local_overlay(current, result.city, [target_id])
                accepted = accept_candidate(current, mutation, lambda _: candidate,
                                            memory_store=memory_store, compiled_gate=gate)
                return result, accepted

            if kind == 'building_site':
                from cityg.planning.building_site import CompiledSiteConflict
                if room_compiler is None:
                    raise ValueError('Building site edits require a compiled geometry gate')

                def finish_site(result):
                    def gate(proposed):
                        try:
                            receipt = _site_compile_receipt(current, proposed, target_id, result.metadata, room_compiler)
                        except ValueError as error:
                            raise CompiledSiteConflict(str(error)) from error
                        if not receipt['ok']:
                            raise CompiledSiteConflict('Site geometry or room retention failed compiled acceptance')
                        return receipt
                    return accept_result(result, gate)

                result, accepted = planner.replace(current, target_id, details=request['details'],
                    exterior_only=not room_compiler.include_interiors, service=service,
                    model_id=model_id, finish=finish_site)
            else:
                result, accepted = accept_result(planner.replace(current, target_id, details=request['details']))
            current = accepted.city
            touched.extend(result.replaced_ids)
            traces.append({
                "kind": kind,
                "target_id": target_id,
                "status": "applied",
                "created_ids": list(result.created_ids),
                "removed_ids": list(result.removed_ids),
                "replaced_ids": list(result.replaced_ids),
                "metadata": dict(result.metadata),
                "transaction": accepted.report,
            })
            continue
        traces.append({
            "kind": kind,
            "target_id": target_id,
            "status": "deferred",
            "reason": "unsupported subtree replacement kind",
        })
    # A compound request may touch the same root via both a profile refinement
    # and a structural transaction; keep the audit list deterministic and
    # duplicate-free without changing the underlying transaction semantics.
    return current, list(dict.fromkeys(touched)), traces


def _refresh_world_program(city: City, changed_ids: set[str], *, producer: str) -> None:
    """Rebuild CCWP after local object regeneration while preserving history."""

    previous = city.world_program
    old_nodes = {node.entity_id: node for node in previous.nodes}
    program = build_world_program(city, producer=producer, seed=None)
    history = {record.id: deepcopy(record) for record in previous.provenance}
    for record in program.provenance:
        history.setdefault(record.id, record)
    program.provenance = list(history.values())
    for node in program.nodes:
        old = old_nodes.get(node.entity_id)
        if old is not None:
            node.version = old.version + (1 if node.entity_id in changed_ids else 0)
            node.locked = old.locked
            node.provenance_ids = list(old.provenance_ids)
        if node.entity_id in changed_ids:
            provenance_id = f"prov_edit_replan__{producer}__{node.entity_id}__{node.version}"
            if provenance_id not in history:
                record = ProvenanceRecord(
                    id=provenance_id,
                    entity_id=node.entity_id,
                    producer=producer,
                    operation="edit_replan",
                    parent_record_ids=list(node.provenance_ids),
                )
                program.provenance.append(record)
                history[provenance_id] = record
            node.provenance_ids.append(provenance_id)
    city.world_program = program


@dataclass(frozen=True)
class EditRunResult:
    status: str
    scene: SceneReference
    output_dir: Path
    plan: EditPlanResult
    touched_entity_ids: tuple[str, ...] = ()
    output_city: Path | None = None
    output_compiled: Path | None = None
    error: str | None = None


@dataclass(frozen=True)
class BatchEditResult:
    status: str
    output_dir: Path
    steps: tuple[EditRunResult, ...]
    error: str | None = None


def run_batch_edit(
    scene_path: str | Path,
    instructions: Sequence[str],
    output_dir: str | Path,
    service: TextReasoningService,
    **kwargs: Any,
) -> BatchEditResult:
    """Apply a sequence of edits as versioned steps, stopping on ambiguity."""

    output = Path(output_dir).expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output directory is not empty: {output}")
    clean = [str(item).strip() for item in instructions if str(item).strip()]
    if not clean:
        raise ValueError("batch edit requires at least one instruction")
    output.mkdir(parents=True, exist_ok=True)
    current: str | Path = scene_path
    steps: list[EditRunResult] = []
    for index, instruction in enumerate(clean, start=1):
        step_dir = output / "steps" / f"step_{index:02d}"
        result = run_edit(current, instruction, step_dir, service, **kwargs)
        steps.append(result)
        if result.status != "applied":
            payload = {
                "status": "paused",
                "failed_step": index,
                "reason": result.error,
                "steps": [
                    {"status": item.status, "output_dir": str(item.output_dir)}
                    for item in steps
                ],
            }
            save_json(payload, output / "batch_result.json")
            return BatchEditResult("paused", output, tuple(steps), result.error)
        current = result.output_dir
    latest = steps[-1].output_dir
    for name in ("final", "viewer"):
        source = latest / name
        if source.exists():
            shutil.copytree(source, output / name, dirs_exist_ok=True)
    save_json(
        {
            "status": "applied",
            "step_count": len(steps),
            "steps": [
                {"status": item.status, "output_dir": str(item.output_dir), "touched_entity_ids": list(item.touched_entity_ids)}
                for item in steps
            ],
        },
        output / "batch_result.json",
    )
    return BatchEditResult("applied", output, tuple(steps))


def rollback_scene(
    scene_path: str | Path,
    output_dir: str | Path,
    *,
    target_scene: str | Path | None = None,
    backend: str = "openusd",
    no_viewer: bool = False,
) -> Path:
    """Create a new version from an explicit scene or the recorded base scene."""

    source = resolve_scene(scene_path)
    target = resolve_scene(target_scene) if target_scene is not None else _base_reference(source)
    output = Path(output_dir).expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    city = load_city(target.canonical_path)
    save_json(
        {"rollback_source": source.to_dict(), "restored_scene": target.to_dict()},
        output / "rollback_ref.json",
    )
    final = output / "final"
    output_city = final / "city.json"
    save_json(city, output_city)
    validator = CityValidator()
    report = validator.validate(city)
    save_json(report.to_dict(), output / "validation_after.json")
    if not report.ok:
        raise ValueError(f"rollback target is invalid: {len(report.errors)} validation error(s)")
    if backend == "manifest":
        compiled = final
    elif backend == "openusd":
        compiled = final / "openusd"
        # Roll back the visual compilation contract as well as canonical data:
        # facade modules and exterior-only scope must match the target version.
        compiler = _edit_compiler(target, None)
        previous_manifest = (target.compiled_path/'geometry_manifest.json'
                             if target.compiled_path is not None else None)
        if previous_manifest is not None and previous_manifest.is_file():
            from cityg.geometry.incremental import scene_from_manifest
            previous = scene_from_manifest(json.loads(previous_manifest.read_text()))
            # Re-export the saved realized scene, not a fresh asset selection
            # from a pruned portable registry (which can change decorations).
            OpenUSDBackend(geometry_compiler=compiler).compile(city, compiled, _scene_override=previous)
        else:
            OpenUSDBackend(geometry_compiler=compiler).compile(city, compiled)
    else:
        raise ValueError(f"unsupported rollback backend: {backend}")
    if not no_viewer and backend == "openusd":
        from cityg.viewer import export_portable_viewer

        export_portable_viewer(compiled, output / "viewer")
    save_json({"status": "rolled_back", "output_city": str(output_city), "output_compiled": str(compiled)}, output / "rollback_result.json")
    return output


def _base_reference(source: SceneReference) -> SceneReference:
    metadata_path = source.run_root / "base_scene_ref.json"
    if not metadata_path.is_file():
        raise ValueError("no base_scene_ref.json found; pass --to explicitly")
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    canonical = data.get("canonical_path")
    if not canonical:
        raise ValueError("base_scene_ref.json does not contain canonical_path")
    return resolve_scene(canonical)


def _edit_compiler(reference, resolver):
    from cityg.assets import MaterialLibrary
    from cityg.asset_bindings import merge_pinned_registries
    from cityg.compilation_context import restore_facade_runtime
    registry = resolver.registry if resolver is not None else None
    materials = None
    metadata = {}
    if reference.compiled_path is not None:
        root = reference.compiled_path
        registry = merge_pinned_registries(root/'assets/asset_registry.json', registry)
        material_path = root/'assets/material_library.json'
        materials = MaterialLibrary(material_path) if material_path.is_file() else None
        manifest = root/'geometry_manifest.json'
        if manifest.is_file():
            metadata = json.loads(manifest.read_text())['metadata']
    return GeometryCompiler(asset_registry=registry, material_library=materials,
        include_interiors=bool(metadata.get('interiors_compiled', True)),
        facade_asset_runtime=restore_facade_runtime(metadata, registry))


def _edit_asset_context(reference, resolver):
    """Use the scene's pinned assets for planning, not only for compilation.

    A plain agent-edit invocation has no explicit global registry. It must
    nevertheless preserve metric GLB placement in a furnished scene. The
    default resolver is detached and local-only: no asset generation authority
    is inferred from the presence of a compiled scene package.
    """
    from copy import copy
    from cityg.asset_bindings import merge_pinned_registries
    pinned = (reference.compiled_path / 'assets/asset_registry.json'
              if reference.compiled_path is not None else None)
    if pinned is None or not pinned.is_file():
        return resolver
    registry = merge_pinned_registries(pinned, resolver.registry if resolver else None)
    if resolver is None:
        return AssetResolver(registry, (), max_provider_calls=0)
    detached = copy(resolver)
    detached.registry = registry
    return detached


def run_edit(scene_path, instruction, output_dir, service, **options) -> EditRunResult:
    """Publish one complete edit bundle with a same-filesystem directory rename.

    Compilation/review work occurs in a private sibling staging directory.
    Failed work is retained for diagnosis, never exposed as final/city.json.
    The source scene remains read-only throughout this operation.
    """
    import tempfile
    output = Path(output_dir).expanduser().resolve()
    if output.exists():
        if any(output.iterdir()):
            raise ValueError(f"output directory is not empty: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    reference = resolve_scene(scene_path)
    source_hash = _city_hash(reference.canonical_path)
    staging = Path(tempfile.mkdtemp(prefix=f'.{output.name}.pending-', dir=output.parent))
    try:
        import sqlite3
        from cityg.memory import MemoryStore
        with MemoryStore(staging/'memory.sqlite') as memory:
            # Each edit branches memory just like the scene. SQLite backup also
            # includes committed WAL content, without mutating source records.
            previous_memory = next((p for p in (reference.run_root/'memory.sqlite',
                Path(str(reference.run_root)+'.memory.sqlite')) if p.is_file()), None)
            if previous_memory is not None:
                connection = sqlite3.connect(previous_memory.as_uri()+'?mode=ro', uri=True)
                try: connection.backup(memory.connection)
                finally: connection.close()
            result = _run_edit_staged(scene_path, instruction, staging, service,
                                      memory_store=memory, **options)
            memory.relocate_artifact_paths(str(staging), str(output))
        if _city_hash(reference.canonical_path) != source_hash:
            raise PatchRejected('stale_proposal', 'Source scene changed during edit planning/compilation')
        if result.output_city is not None:
            conditions=explicit_edit_constraints(load_city(reference.canonical_path),instruction)
            checked=check_edit_constraints(load_city(result.output_city),conditions)
            save_json(checked,staging/'edit_postconditions.json')
            if not checked['ok']:
                raise PatchRejected('edit_requirement_unmet','Published candidate does not meet explicit original edit requirements')
        # Export packages use relative asset links; JSON audit/manifests may
        # additionally contain absolute paths to this bundle. Relocate those
        # before publication, without modifying binary assets or source files.
        for path in staging.rglob('*.json'):
            original = path.read_text(encoding='utf-8')
            relocated = original.replace(str(staging), str(output))
            if relocated != original:
                path.write_text(relocated, encoding='utf-8')
        if output.exists():
            output.rmdir()  # only the already-checked empty destination
        staging.rename(output)
        def published(path):
            return output/path.relative_to(staging) if path is not None else None
        return replace(result, output_dir=output, output_city=published(result.output_city),
                       output_compiled=published(result.output_compiled))
    except Exception as error:
        save_json({'status': 'failed_unpublished', 'error': f'{type(error).__name__}: {error}',
                   'source_unchanged': _city_hash(reference.canonical_path) == source_hash,
                   'diagnostic_directory': str(staging)}, staging/'publication_failure.json')
        raise


def _run_edit_staged(
    scene_path: str | Path,
    instruction: str,
    output_dir: str | Path,
    service: TextReasoningService,
    *,
    model_id: str = "unknown",
    backend: str = "openusd",
    timeout_s: float = 180.0,
    no_viewer: bool = False,
    max_attempts: int = 3,
    asset_resolver: AssetResolver | None = None,
    visual_review: bool = False,
    auto_vlm_refine: bool = False,
    review_base_url: str = "http://127.0.0.1:8000/v1",
    review_model: str | None = None,
    review_max_views: int = 6,
    memory_store=None,
) -> EditRunResult:
    """Run planning, local patch/replan, validation and versioned compilation."""

    reference = resolve_scene(scene_path)
    output = Path(output_dir).expanduser().resolve()
    memory_files = {'memory.sqlite', 'memory.sqlite-wal', 'memory.sqlite-shm'} if memory_store is not None else set()
    if output.exists() and any(p.name not in memory_files for p in output.iterdir()):
        raise ValueError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    from cityg.run_provenance import record_stage_start
    record_stage_start(output)
    city = load_city(reference.canonical_path)
    source_hash = _city_hash(reference.canonical_path)
    validator = CityValidator()
    before = validator.validate(city)
    agent = EditAgent(service, model_id=model_id, max_attempts=max_attempts)
    try:
        plan = agent.plan(city, instruction)
    except AgentGenerationError as exc:
        save_json({'status':'planning_failed','error':str(exc),
                   'attempts':[asdict(a) for a in exc.attempts]}, output / 'edit_plan_failure.json')
        raise
    save_json(reference.to_dict(), output / "base_scene_ref.json")
    save_json({"instruction": instruction, "source_city_hash": source_hash}, output / "edit_request.json")
    save_json(plan.to_dict(), output / "edit_plan.json")
    save_json(before.to_dict(), output / "validation_before.json")
    if plan.status == "needs_clarification":
        result = EditRunResult(plan.status, reference, output, plan, error=plan.clarification or plan.reason)
        save_json({"status": result.status, "reason": result.error, "touched_entity_ids": []}, output / "edit_result.json")
        return result
    asset_resolver = _edit_asset_context(reference, asset_resolver)
    plan, asset_outcomes = _resolve_asset_requests(city, plan, asset_resolver)
    if _city_hash(reference.canonical_path) != source_hash:
        raise PatchRejected('stale_proposal', 'Source scene changed while Agent planned the edit')
    save_json(asset_outcomes, output / "asset_resolution.json")
    save_json(plan.to_dict(), output / "edit_plan_effective.json")
    patch = None
    changed: list[str] = []
    try:
        if plan.status == "apply":
            patch_token = hashlib.sha256(
                f"{city.id}|{instruction}|{output}".encode("utf-8")
            ).hexdigest()[:16]
            applied, patch = apply_edit_plan(city, plan, patch_id=f"edit__{city.id}__{patch_token}",
                                             memory_store=memory_store)
            edited_city = applied.city
            validation_after = applied.validation
            changed = list(applied.touched_entity_ids)
        elif plan.status == "replan_required":
            room_compiler = _edit_compiler(reference, asset_resolver) if backend == 'openusd' else None
            if asset_resolver is not None and room_compiler is not None:
                from copy import copy
                asset_resolver = copy(asset_resolver)
                asset_resolver.registry = room_compiler.asset_registry
            edited_city, changed, replan_traces = _apply_replans(
                city,
                plan.replan_requests,
                service,
                model_id=model_id,
                asset_resolver=asset_resolver,
                room_compiler=room_compiler,
                trace_sink=lambda rows: save_json(rows, output/'replan_trace.json'),
                memory_store=memory_store,
            )
            if not changed and any(item.get("status") == "deferred" for item in replan_traces):
                result = EditRunResult(
                    "replan_required",
                    reference,
                    output,
                    plan,
                    error="No requested structural edit is enabled in the current editor",
                )
                save_json(
                    {
                        "status": result.status,
                        "reason": result.error,
                        "replan_trace": replan_traces,
                        "touched_entity_ids": [],
                    },
                    output / "edit_result.json",
                )
                return result
            validation_after = validator.validate(edited_city)
            save_json(replan_traces, output / "replan_trace.json")
            if not validation_after.ok:
                raise PatchRejected(
                    "post_validation_failed",
                    f"Local replan has {len(validation_after.errors)} validation error(s)",
                    validation_after,
                )
        else:
            raise ValueError(f"unsupported edit plan status: {plan.status}")
        checked=check_edit_constraints(edited_city,explicit_edit_constraints(city,instruction))
        save_json(checked,output/'edit_postconditions.json')
        if not checked['ok']:
            raise PatchRejected('edit_requirement_unmet','Candidate does not meet explicit original edit requirements')
    except (PatchRejected, ValueError, json.JSONDecodeError) as error:
        save_json({"status": "rejected", "error": str(error)}, output / "edit_result.json")
        raise
    final = output / "final"
    output_city = final / "city.json"
    save_json(edited_city, output_city)
    if patch is not None:
        save_json(to_primitive(patch), output / "patch.json")
    save_json(validation_after.to_dict(), output / "validation_after.json")
    compiled_path: Path | None = None
    if backend == "openusd":
        compiled_path = final / "openusd"
        compiler = _edit_compiler(reference, asset_resolver)
        backend_impl = OpenUSDBackend(geometry_compiler=compiler)
        # Moving an entrance or footprint also affects parcel landscaping and access paths.
        site_changed = any(request['kind'] == 'building_site' for request in plan.replan_requests)
        if reference.compiled_path is not None and not site_changed:
            backend_impl.compile_incremental(edited_city, compiled_path, reference.compiled_path, changed)
        else:
            backend_impl.compile(edited_city, compiled_path)
    elif backend == "manifest":
        compiled_path = final
    else:
        raise ValueError(f"unsupported edit backend: {backend}")
    if not no_viewer and compiled_path is not None and backend == "openusd":
        from cityg.viewer import export_portable_viewer

        export_portable_viewer(compiled_path, output / "viewer")
    if visual_review and backend == "openusd" and compiled_path is not None:
        review_root = output / "visual_review"
        promotion_started = False
        try:
            from cityg.adaptive_review import run_adaptive_review

            review_facades = None
            if compiler.facade_asset_runtime is not None:
                review_facades = output/'review_facade_index.json'
                save_json(compiler.facade_asset_runtime.index.payload, review_facades)
            review = run_adaptive_review(
                compiled_path,
                review_root,
                base_url=review_base_url,
                model=review_model or model_id,
                timeout=timeout_s,
                max_tokens=1536,
                max_views=max(1, review_max_views),
                max_building_refinements=1 if auto_vlm_refine else 0,
                max_room_refinements=1 if auto_vlm_refine else 0,
                max_room_layout_refinements=1 if auto_vlm_refine else 0,
                max_streetscape_refinements=1 if auto_vlm_refine else 0,
                enable_archetype_contact_sheets=False,
                asset_registry=(
                    asset_resolver.registry.manifest_path
                    if asset_resolver is not None
                    else None
                ),
                generate_missing_assets=False,
                facade_asset_index=review_facades,
                memory_store_path=memory_store.path if memory_store else None,
            )
            promoted = False
            if auto_vlm_refine and review.get("touched_entity_ids"):
                refined_path = Path(str(review.get("city_refined", "")))
                if refined_path.is_file():
                    promotion_started = True
                    edited_city = load_city(refined_path)
                    save_json(edited_city, output_city)
                    backend_impl.compile(edited_city, compiled_path)
                    if not no_viewer:
                        from cityg.viewer import export_portable_viewer

                        export_portable_viewer(compiled_path, output / "viewer")
                    changed.extend(str(item) for item in review["touched_entity_ids"])
                    promoted = True
            save_json(
                {"status": "completed", "auto_refine": auto_vlm_refine, "promoted": promoted, "report": str(review_root / "adaptive_review_report.json")},
                output / "visual_review_result.json",
            )
        except Exception as error:
            if promotion_started:
                # Promotion may have changed the compiled package. Abort the
                # entire unpublished transaction instead of claiming success.
                raise
            # VLM review is an optional gate; it must never destroy a valid edit.
            save_json(
                {"status": "unavailable", "error": f"{type(error).__name__}: {error}"},
                output / "visual_review_result.json",
            )
    if backend == 'openusd' and reference.compiled_path is not None:
        from cityg.validation.rendered_inventory import rendered_inventory_preserved
        source_manifest = reference.compiled_path/'geometry_manifest.json'
        after_manifest = compiled_path/'geometry_manifest.json'
        if source_manifest.is_file():
            representation = rendered_inventory_preserved(city, edited_city,
                json.loads(source_manifest.read_text()), json.loads(after_manifest.read_text()))
            save_json(representation, output/'rendered_inventory_acceptance.json')
            if not representation['ok']:
                raise PatchRejected('mesh_binding_lost', 'Edit dropped existing compiled asset bindings')
    save_json(edited_city, output_city)
    save_json(
        {
            "status": "applied",
            "touched_entity_ids": changed,
            "output_city": str(output_city),
            "output_compiled": str(compiled_path) if compiled_path else None,
            "visual_checks": list(plan.visual_checks),
            "asset_resolution": asset_outcomes,
        },
        output / "edit_result.json",
    )
    return EditRunResult("applied", reference, output, plan, tuple(changed), output_city, compiled_path)


def _city_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = [
    "EDIT_PLAN_RESPONSE_SCHEMA",
    "EditAgent",
    "EditPlanResult",
    "EditRunResult",
    "BatchEditResult",
    "SceneReference",
    "apply_edit_plan",
    "resolve_scene",
    "run_edit",
    "run_batch_edit",
    "rollback_scene",
]
