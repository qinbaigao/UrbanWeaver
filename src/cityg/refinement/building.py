"""LLM-assisted building personalization with deterministic commit authority.

The agent only proposes a small metadata contract.  It never edits floors,
rooms, connectors, or geometry directly; :class:`PatchEngine` remains the
single authority that versions and validates the world.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

from cityg.agents.requirement import AgentAttempt, AgentGenerationError, _parse_json_object
from cityg.buildings import BuildingSelectionContext, BuildingSelector
from cityg.buildings.catalog import catalog_by_id
from cityg.facade_assets import FacadeAssetIndex
from cityg.planning.highrise import HIGHRISE_MASSING_VARIANTS
from cityg.memory import MemoryQuery, MemoryStore
from cityg.repair import PatchEngine, PatchOperation, PatchRejected, WorldPatch
from cityg.schemas import Building, City
from cityg.architecture import DESIGN_LANGUAGES, MATERIAL_FAMILIES, make_appearance_plan, validate_appearance_plan
from cityg.envelopes import ENVELOPE_SCHEMA, envelope_config, validate_envelope
from cityg.serialization import to_primitive
from cityg.services.interfaces import ChatMessage, TextReasoningService
from cityg.validation import CityValidator, ValidationReport


BUILDING_REFINEMENT_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "building_id": {"type": "string"},
        "reason": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "adjustments": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "massing_variant": {
                    "type": ["string", "null"],
                    "enum": [*sorted(HIGHRISE_MASSING_VARIANTS), None],
                },
                "facade_style_override": {"type": ["string", "null"]},
                "archetype_id": {"type": ["string", "null"]},
                "design_language": {"type": ["string", "null"], "enum": [*DESIGN_LANGUAGES, None]},
                "material_family": {"type": ["string", "null"], "enum": [*MATERIAL_FAMILIES, None]},
                "envelope_adjustment": {**ENVELOPE_SCHEMA, "type": ["object", "null"]},
                "facade_asset_ids": {
                    "type": ["array", "null"],
                    "items": {"type": "string"},
                    "maxItems": 2,
                },
                "podium_floors": {"type": ["integer", "null"], "minimum": 0, "maximum": 6},
            },
            "required": [
                "massing_variant",
                "facade_style_override",
                "podium_floors",
                "facade_asset_ids",
            ],
        },
    },
    "required": ["building_id", "reason", "confidence", "adjustments"],
}


@dataclass(frozen=True)
class BuildingRefinementPlan:
    building_id: str
    reason: str
    adjustments: dict[str, Any]
    confidence: float = 1.0
    normalization_notes: tuple[str, ...] = ()

    def validate(self, building: Building) -> None:
        if building.id != self.building_id:
            raise ValueError("refinement plan targets a different building")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be within [0, 1]")
        unknown = sorted(set(self.adjustments) - {
            "massing_variant", "facade_style_override", "podium_floors", "archetype_id",
            "facade_asset_ids", "design_language", "envelope_adjustment", "material_family",
        })
        if unknown:
            raise ValueError(f"unsupported building adjustment(s): {', '.join(unknown)}")
        envelope = envelope_config(building)
        proposed_envelope = self.adjustments.get("envelope_adjustment")
        if proposed_envelope is not None:
            if not envelope or not proposed_envelope:
                raise ValueError("envelope adjustment requires an existing exterior-only envelope and nonempty config")
            validate_envelope(proposed_envelope)
        if envelope and any(self.adjustments.get(k) is not None for k in
                            ("archetype_id", "massing_variant", "podium_floors", "facade_asset_ids")):
            raise ValueError("legacy massing/module changes do not apply to exterior loft envelopes")
        language = self.adjustments.get("design_language")
        if language is not None:
            current = building.metadata.get("appearance_plan") or make_appearance_plan(building, {})
            validate_appearance_plan({**current, "language": language})
        material = self.adjustments.get('material_family')
        if material is not None:
            current = building.metadata.get('appearance_plan') or make_appearance_plan(building, {})
            validate_appearance_plan({**current, 'material_family': material})
        massing = self.adjustments.get("massing_variant")
        if massing is not None and massing not in HIGHRISE_MASSING_VARIANTS:
            raise ValueError(f"unsupported high-rise massing variant: {massing}")
        if massing is not None and len(building.floors) < 10:
            raise ValueError("massing_variant is only meaningful for high-rise buildings")
        podium = self.adjustments.get("podium_floors")
        if podium is not None:
            if not isinstance(podium, int) or not 0 <= podium <= 6:
                raise ValueError("podium_floors must be an integer in [0, 6]")
            if len(building.floors) < 10 and podium:
                raise ValueError("podium_floors is only meaningful for high-rise buildings")
        facade = self.adjustments.get("facade_style_override")
        if facade is not None and (not isinstance(facade, str) or not facade.strip()):
            raise ValueError("facade_style_override must be a non-empty string")
        archetype_id = self.adjustments.get("archetype_id")
        if archetype_id is not None:
            if not isinstance(archetype_id, str) or not archetype_id.strip():
                raise ValueError("archetype_id must be a non-empty string")
            archetype = catalog_by_id().get(archetype_id)
            if archetype is None:
                raise ValueError(f"unknown building archetype: {archetype_id}")
            if (building.metadata.get('interior_layout_contract')
                    and archetype.massing_style != 'bar'):
                raise ValueError('Detailed rectangular interior contract forbids nonrectangular massing; refine facade only')
            context = BuildingSelectionContext.from_building(building)
            if not archetype.supports(
                context.function,
                context.floor_count,
                context.width_m,
                context.depth_m,
            ):
                raise ValueError("archetype_id is incompatible with the realized building")
            if context.prototype_id and archetype.prototype_ids and context.prototype_id not in archetype.prototype_ids:
                raise ValueError("archetype_id is incompatible with the building prototype")
        facade_asset_ids = self.adjustments.get("facade_asset_ids")
        if facade_asset_ids is not None:
            if not isinstance(facade_asset_ids, (list, tuple)):
                raise ValueError("facade_asset_ids must be an array")
            if len(facade_asset_ids) > 2 or any(
                not isinstance(item, str) or not item.strip()
                for item in facade_asset_ids
            ):
                raise ValueError("facade_asset_ids must contain at most two non-empty IDs")
            if len(set(facade_asset_ids)) != len(facade_asset_ids):
                raise ValueError("facade_asset_ids must be unique")


def _normalize_adjustments(
    building: Building, adjustments: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Apply only safe, deterministic normalization before strict validation.

    The model schema is intentionally shared by low/mid/high-rise buildings, so
    a model may occasionally emit a high-rise field for a smaller building even
    after receiving corrective feedback.  Those fields cannot affect geometry
    on a non-high-rise building and are removed rather than allowing an optional
    refinement to abort the canonical build.  All normalization is recorded in
    the plan trace and refinement history.
    """
    normalized = dict(adjustments)
    notes: list[str] = []
    if len(building.floors) < 10:
        for key in ("massing_variant", "podium_floors"):
            value = normalized.get(key)
            if value not in (None, 0):
                notes.append(f"dropped {key} for non-high-rise building")
            normalized.pop(key, None)
    return normalized, notes


@dataclass(frozen=True)
class BuildingRefinementResult:
    city: City
    plan: BuildingRefinementPlan
    validation: ValidationReport
    patch: WorldPatch
    attempts: tuple[AgentAttempt, ...] = field(default_factory=tuple)
    model_id: str = "deterministic"
    transaction_report: dict = field(default_factory=dict)

    def trace_dict(self) -> dict[str, Any]:
        return {
            "agent": "building_refinement",
            "model_id": self.model_id,
            "plan": asdict(self.plan),
            "patch": to_primitive(self.patch),
            "post_validation": self.validation.to_dict(),
            "attempts": [asdict(item) for item in self.attempts],
            "transaction": self.transaction_report,
        }


def select_refinement_candidates(
    city: City, *, max_candidates: int = 8, include_highrise: bool = True
) -> list[str]:
    """Select a small, reproducible set rather than invoking an agent per building."""
    if max_candidates < 1:
        raise ValueError("max_candidates must be positive")
    buildings = list(city.iter_buildings())
    scored: list[tuple[tuple[int, int, str], str]] = []
    for building in buildings:
        highrise = len(building.floors) >= 10
        landmark = bool(building.metadata.get("height_contract", {}).get("landmark"))
        corner = bool(building.metadata.get("parcel_role") in {"corner", "frontage"})
        if include_highrise and highrise:
            priority = 0
        elif landmark:
            priority = 1
        elif corner:
            priority = 2
        else:
            priority = 3
        scored.append(((priority, -len(building.floors), building.id), building.id))
    return [item[1] for item in sorted(scored)[:max_candidates]]


class BuildingRefinementAgent:
    """Ask an LLM for a constrained plan; do not mutate the city in this class."""

    def __init__(
        self,
        service: TextReasoningService,
        *,
        model_id: str = "unknown",
        validator: CityValidator | None = None,
        max_attempts: int = 2,
        memory_store: MemoryStore | None = None,
        facade_asset_index: FacadeAssetIndex | None = None,
    ) -> None:
        self.service = service
        self.model_id = model_id
        self.validator = validator or CityValidator()
        self.max_attempts = max(1, max_attempts)
        self.memory_store = memory_store
        self.facade_asset_index = facade_asset_index

    def propose(
        self,
        city: City,
        building_id: str,
        *,
        visual_feedback: dict[str, Any] | None = None,
    ) -> tuple[BuildingRefinementPlan, tuple[AgentAttempt, ...]]:
        building = next((item for item in city.iter_buildings() if item.id == building_id), None)
        if building is None:
            raise KeyError(building_id)
        prompt = self._prompt(city, building, visual_feedback=visual_feedback)
        is_highrise = len(building.floors) >= 10
        messages = [
            ChatMessage(role="system", content=(
                "You are a constrained CityG building personalization agent. "
                "Only choose facade/massing metadata adjustments. Preserve floors, rooms, "
                "connectors, footprint and entrance. Return JSON matching the schema. "
                "massing_variant and podium_floors are HIGH-RISE-ONLY: when the target "
                "has fewer than 10 floors, both fields MUST be null. For a high-rise, "
                "podium_floors must be within the existing high-rise contract. "
                "material_family changes appearance_plan.material_family within its accepted context palette. "
                "facade_style_override is only a legacy style/variant selector, NOT a material-family guarantee. "
                "Use material_family for explicit material requests; never invent architecture_profile. design_language changes "
                "the actual opening rhythm and articulation; choose only from the building's "
                "appearance_plan.allowed_languages, or null. Respect region/era/climate context "
                "and compare nearby appearance plans without stereotyped national rules. "
                "For an existing appearance_plan.envelope, use envelope_adjustment (a complete "
                "validated config) for shell changes, or null. Legacy archetype_id, massing_variant, "
                "podium_floors and facade_asset_ids MUST be null for these exterior-only buildings. "
                "Curtain walls override the punched-window design_language; do not change that "
                "label expecting the curtain wall geometry to change. "
                " facade_asset_ids may contain only IDs from the supplied facade_asset_candidates. "
                "When facade_asset_candidates contains any records, facade_asset_ids MUST contain "
                "1-2 exact IDs: one coherent window family and, when available, one entrance; "
                "do not merely mention them in reason. When no candidates are supplied, return null."
                " archetype_id, when used, must be selected from the supplied catalog "
                "and remains subject to deterministic compatibility validation. When "
                "visual_feedback.contact_sheet_comparison.available is true, choose "
                "archetype_id only from that comparison's candidate_archetype_ids "
                "(or return null when none should be committed)."
            )),
            ChatMessage(role="user", content=json.dumps(prompt, ensure_ascii=False, sort_keys=True)),
        ]
        attempts: list[AgentAttempt] = []
        for index in range(1, self.max_attempts + 1):
            started = time.monotonic()
            raw = ""
            error: str | None = None
            finish_reason = None
            usage: dict[str, Any] = {}
            try:
                method = getattr(self.service, "complete_with_metadata", None)
                if callable(method):
                    completion = method(messages, BUILDING_REFINEMENT_RESPONSE_SCHEMA)
                    raw, finish_reason, usage = completion.content, completion.finish_reason, completion.usage
                else:
                    raw = self.service.complete(messages, BUILDING_REFINEMENT_RESPONSE_SCHEMA)
                if finish_reason == "length":
                    raise ValueError("model output reached max_tokens before completing JSON")
                data = _parse_json_object(raw)
                if str(data.get("building_id")) != building_id:
                    raise ValueError("model returned a different building_id")
                adjustments = dict(data.get("adjustments", {}))
                adjustments, normalization_notes = _normalize_adjustments(
                    building, adjustments
                )
                allowed_facade_ids = {
                    str(item["asset_id"])
                    for group in prompt.get("facade_asset_candidates", {}).values()
                    for item in group
                }
                proposed_facade_ids = adjustments.get("facade_asset_ids")
                if proposed_facade_ids is not None:
                    proposed_facade_ids = [str(item) for item in proposed_facade_ids]
                    invalid_facade_ids = sorted(
                        set(proposed_facade_ids) - allowed_facade_ids
                    )
                    if invalid_facade_ids:
                        raise ValueError(
                            "facade_asset_ids are outside supplied candidates: "
                            + ", ".join(invalid_facade_ids)
                        )
                    adjustments["facade_asset_ids"] = proposed_facade_ids
                comparison = (visual_feedback or {}).get(
                    "contact_sheet_comparison", {}
                )
                if comparison.get("available"):
                    allowed_comparison_ids = {
                        str(item)
                        for item in comparison.get("candidate_archetype_ids", [])
                        if str(item)
                    }
                    proposed_archetype = adjustments.get("archetype_id")
                    if (
                        proposed_archetype is not None
                        and str(proposed_archetype) not in allowed_comparison_ids
                    ):
                        raise ValueError(
                            "archetype_id is outside the rendered contact-sheet candidates"
                        )
                plan = BuildingRefinementPlan(
                    building_id=building_id,
                    reason=str(data.get("reason", "")),
                    adjustments={key: value for key, value in adjustments.items() if value is not None},
                    confidence=float(data.get("confidence", 1.0)),
                    normalization_notes=tuple(normalization_notes),
                )
                plan.validate(building)
            except (TypeError, ValueError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
                error = f"{type(exc).__name__}: {exc}"
                plan = None
            prompt_bytes = json.dumps(messages, default=lambda item: asdict(item), sort_keys=True, ensure_ascii=False).encode()
            attempts.append(AgentAttempt(
                index=index,
                prompt_hash=hashlib.sha256(prompt_bytes).hexdigest(),
                messages=tuple({"role": item.role, "content": item.content} for item in messages),
                raw_output=raw,
                elapsed_s=round(time.monotonic() - started, 6),
                error=error,
                finish_reason=finish_reason,
                usage=usage,
            ))
            if error is None and plan is not None:
                return plan, tuple(attempts)
            if index < self.max_attempts:
                messages.extend([
                    ChatMessage(role="assistant", content=raw[:8000]),
                    ChatMessage(role="user", content=f"Correct the JSON proposal. Validation error: {error}"),
                ])
        raise AgentGenerationError(f"Building refinement failed after {self.max_attempts} attempts", attempts)

    def _prompt(
        self,
        city: City,
        building: Building,
        *,
        visual_feedback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        nearby = []
        center = building.footprint.center
        for other in city.iter_buildings():
            if other.id == building.id:
                continue
            distance = ((other.footprint.center.x - center.x) ** 2 + (other.footprint.center.y - center.y) ** 2) ** 0.5
            nearby.append((distance, other))
        memory = []
        if self.memory_store is not None:
            memory = [item.to_dict() for item in self.memory_store.query(
                MemoryQuery(scope_id=building.id, world_version=_node_version(city, building.id),
                            allow_cross_run=True, limit=4)
            )]
        facade_candidates: dict[str, list[dict[str, Any]]] = {}
        if self.facade_asset_index is not None and not envelope_config(building):
            function = "public_service" if building.function == "public" else building.function
            facade_candidates = {
                "podium_windows": self.facade_asset_index.candidates(
                    building_function=function,
                    facade_zone="podium",
                    semantic_types=("window_bay", "window_insert"),
                    limit=4,
                ),
                "shaft_windows": self.facade_asset_index.candidates(
                    building_function=function,
                    facade_zone="shaft",
                    semantic_types=("window_bay", "window_insert"),
                    limit=4,
                ),
                "entrances": self.facade_asset_index.candidates(
                    building_function=function,
                    facade_zone="podium",
                    semantic_types=("entrance_bay", "door_insert"),
                    limit=4,
                ),
            }
        return {
            "building": {
                "id": building.id,
                "function": building.function,
                "footprint": to_primitive(building.footprint),
                "floor_count": len(building.floors),
                "refinement_constraints": {
                    "preserve_rectangular_interior_contract": bool(building.metadata.get('interior_layout_contract')),
                    "is_highrise": len(building.floors) >= 10,
                    "allowed_adjustments": (
                        ["envelope_adjustment", "facade_style_override", "design_language", "material_family"]
                        if envelope_config(building) else
                        ["archetype_id", "facade_style_override", "facade_asset_ids", "massing_variant", "podium_floors", "design_language", "material_family"]
                        if len(building.floors) >= 10
                        else ["archetype_id", "facade_style_override", "facade_asset_ids", "design_language", "material_family"]
                    ),
                    "highrise_only_fields_must_be_null": len(building.floors) < 10,
                },
                "metadata": building.metadata,
                "exterior_envelope_schema": ENVELOPE_SCHEMA if envelope_config(building) else None,
            },
            "nearby_buildings": [
                {"id": item.id, "function": item.function, "floor_count": len(item.floors),
                 "appearance_plan": item.metadata.get("appearance_plan", {})}
                for _, item in sorted(nearby, key=lambda value: value[0])[:4]
            ],
            "building_archetype_catalog": [
                {
                    "archetype_id": item.archetype_id,
                    "family": item.family,
                    "massing_style": item.massing_style,
                    "massing_signature": item.massing_signature,
                    "compatible_functions": list(item.compatible_functions),
                    "facade_style_ids": list(item.facade_style_ids),
                    "massing_parameters": {
                        key: value for key, value in item.massing_parameters
                    },
                }
                for item in BuildingSelector().catalog
                if building.function in item.compatible_functions
                and item.min_floors <= len(building.floors) <= item.max_floors
            ],
            "facade_asset_candidates": facade_candidates,
            "design_language_catalog": DESIGN_LANGUAGES,
            "visual_feedback": visual_feedback or {},
            "city_metadata": {
                "name": city.name,
                "bounds": to_primitive(city.bounds),
                "style": city.metadata.get("layout_style", city.metadata.get("planning_mode")),
            },
            "relevant_memory": memory,
        }


def apply_building_refinement(
    city: City,
    plan: BuildingRefinementPlan,
    *,
    validator: CityValidator | None = None,
    author: str = "building_refinement_agent",
    patch_id: str | None = None,
    attempts: Sequence[AgentAttempt] = (),
    model_id: str = "unknown",
    memory_store=None,
    source: str = 'visual_repair',
    compiled_gate=None,
) -> BuildingRefinementResult:
    building = next((item for item in city.iter_buildings() if item.id == plan.building_id), None)
    if building is None:
        raise KeyError(plan.building_id)
    plan.validate(building)
    metadata = dict(building.metadata)
    history = list(metadata.get("refinement_history", []))
    highrise = dict(metadata.get("highrise", {}))
    archetype_id = plan.adjustments.get("archetype_id")
    if archetype_id is not None:
        selection = BuildingSelector().select(
            BuildingSelectionContext.from_building(building),
            preferred_ids=(str(archetype_id),),
        )
        metadata.update(selection.to_metadata())
        if selection.archetype.massing_variant and len(building.floors) >= 10:
            highrise["massing_variant"] = selection.archetype.massing_variant
    for key, value in plan.adjustments.items():
        if key == "massing_variant":
            highrise["massing_variant"] = value
        elif key == "podium_floors":
            highrise["podium_floors"] = value
        elif key == "archetype_id":
            continue
        elif key == "facade_asset_ids":
            metadata[key] = list(value)
        elif key in {"design_language", "material_family"}:
            if value is None:
                continue
            current = metadata.get("appearance_plan") or make_appearance_plan(building, {})
            field_name = 'language' if key == 'design_language' else 'material_family'
            metadata["appearance_plan"] = {**current, field_name: value, "source": author}
        elif key == "envelope_adjustment":
            if value is not None:
                metadata["appearance_plan"] = {**metadata["appearance_plan"], "envelope": dict(value), "source": author}
                expected = city.metadata.get('morphology_contract', {}).get('building_envelopes', {}).get(building.id)
                if expected is not None:
                    metadata['morphology_envelope_revision'] = {
                        'original': dict(expected), 'accepted': dict(value),
                        'author': author, 'reason': plan.reason,
                    }
        else:
            metadata[key] = value
    if highrise:
        metadata["highrise"] = highrise
    history.append({
        "reason": plan.reason,
        "adjustments": dict(plan.adjustments),
        "confidence": plan.confidence,
        "normalization_notes": list(plan.normalization_notes),
    })
    metadata["refinement_history"] = history[-8:]
    patch = WorldPatch(
        id=patch_id or f"building_refine__{plan.building_id}__{len(history):02d}",
        scope_entity_id=plan.building_id,
        operations=(PatchOperation("replace_entity", plan.building_id, "metadata", metadata),),
        expected_versions={plan.building_id: _node_version(city, plan.building_id)},
        author=author,
        reason=plan.reason,
    )
    result = PatchEngine(validator or CityValidator()).apply(city, patch, source=source,
        memory_store=memory_store, compiled_gate=compiled_gate)
    return BuildingRefinementResult(
        city=result.city,
        plan=plan,
        validation=result.validation,
        patch=patch,
        attempts=tuple(attempts),
        model_id=model_id,
        transaction_report=result.transaction_report,
    )


def _node_version(city: City, entity_id: str) -> int:
    for node in city.world_program.nodes:
        if node.entity_id == entity_id:
            return node.version
    raise KeyError(entity_id)


__all__ = [
    "BUILDING_REFINEMENT_RESPONSE_SCHEMA",
    "BuildingRefinementAgent",
    "BuildingRefinementPlan",
    "BuildingRefinementResult",
    "apply_building_refinement",
    "select_refinement_candidates",
]
