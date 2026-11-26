"""Versioned architectural intent and bounded per-building appearance plans.

No country-to-style heuristics: language choices are explicit or supplied by
the agents. Metric facade realization remains the compiler's responsibility.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any
from cityg.envelopes import ENVELOPE_SCHEMA, validate_envelope


DESIGN_LANGUAGES = {
    "framed_grid": "Regular framed openings with restrained floor articulation",
    "horizontal_ribbon": "Wide shallow glazing, horizontal spandrel bands",
    "vertical_piers": "Tall narrow glazing grouped between vertical piers",
    "paired_windows": "Paired openings separated by larger masonry intervals",
    "shaded_bays": "Deep horizontal solar hoods over individual openings",
    "solid_punched": "Smaller punched windows, dominant solid wall and sill detail",
}
MATERIAL_FAMILIES = ("brick", "plaster", "stone", "metal", "glass")
ARCHITECTURE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "expressive_ratio": {"type": "number", "minimum": 0, "maximum": 1},
        "envelope": ENVELOPE_SCHEMA,
        "envelope_palette": {"type": "array", "minItems": 1, "maxItems": 8,
                             "items": ENVELOPE_SCHEMA},
        **{key: {"type": "string", "maxLength": 240}
           for key in ("region", "era", "climate", "district_character")},
        # vLLM's grammar backend need not implement uniqueItems; enforce it below.
        "design_languages": {"type": "array", "maxItems": 6,
                             "items": {"type": "string", "enum": list(DESIGN_LANGUAGES)}},
        "material_palette": {"type": "array", "maxItems": 5,
                             "items": {"type": "string", "enum": list(MATERIAL_FAMILIES)}},
    },
}


def validate_architecture(value: dict) -> None:
    if not isinstance(value, dict):
        raise ValueError("architecture must be an object")
    if set(value) - set(ARCHITECTURE_SCHEMA["properties"]):
        raise ValueError("unknown architecture fields")
    ratio = value.get('expressive_ratio', .2)
    if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not math.isfinite(ratio) or not 0 <= ratio <= 1:
        raise ValueError('architecture.expressive_ratio must be between 0 and 1')
    for key in ("region", "era", "climate", "district_character"):
        if key in value and (not isinstance(value[key], str) or len(value[key]) > 240):
            raise ValueError(f"architecture.{key} must be a short string")
    validate_palette(value.get("design_languages", []))
    validate_envelope(value.get("envelope", {}))
    if 'envelope_palette' in value:
        palette = value['envelope_palette']
        if not isinstance(palette, list) or not 1 <= len(palette) <= 8:
            raise ValueError('envelope_palette must contain 1..8 exterior configurations')
        if value.get('envelope'):
            raise ValueError('choose envelope or envelope_palette, not both')
        for entry in palette:
            if not entry:
                raise ValueError('empty envelope palette entries are not allowed')
            validate_envelope(entry)
    materials = value.get("material_palette", [])
    if (not isinstance(materials, (list, tuple)) or len(materials) > 5
        or any(not isinstance(v, str) or v not in MATERIAL_FAMILIES for v in materials)
        or len(set(materials)) != len(materials)):
        raise ValueError("unsupported material palette")


def validate_palette(palette: Any) -> None:
    if not isinstance(palette, (list, tuple)) or len(palette) > 6:
        raise ValueError("design language palette must contain at most six IDs")
    if any(not isinstance(v, str) or v not in DESIGN_LANGUAGES for v in palette):
        raise ValueError("unsupported design language")
    if len(set(palette)) != len(palette):
        raise ValueError("duplicate design languages")


def stable_index(key: str, count: int) -> int:
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big") % count


def make_appearance_plan(building: Any, context: dict, *, seed: int = 0,
                         ordinal: int = 0, form_ordinal: int | None = None) -> dict:
    validate_architecture(context)
    preferred = building.metadata.get("semantic_design_language_palette", [])
    validate_palette(preferred)
    # An explicit district palette has priority over a shared function profile.
    palette = context.get("design_languages") or preferred
    source = "architectural_context" if context.get("design_languages") else (
        "building_agent_palette" if preferred else "offline_function_palette")
    if not palette:
        palette = {
            "residential": ["paired_windows", "solid_punched", "shaded_bays", "framed_grid"],
            "commercial": ["horizontal_ribbon", "vertical_piers", "framed_grid"],
            "industrial": ["horizontal_ribbon", "solid_punched", "framed_grid"],
        }.get(building.function, list(DESIGN_LANGUAGES))
    # Balanced per-district distribution; no per-window randomness.
    offset = stable_index(f"{seed}:{context.get('district_character', '')}", len(palette))
    language = palette[(ordinal + offset) % len(palette)]
    materials = context.get("material_palette", [])
    envelopes = context.get('envelope_palette', [])
    envelope = (envelopes[ordinal % len(envelopes)] if envelopes else
                context.get('envelope') or building.metadata.get('semantic_envelope_preference', {}))
    form_policy = {'source': 'explicit_envelope' if envelopes or context.get('envelope') else 'legacy'}
    if not envelopes and not context.get('envelope') and 'expressive_ratio' in context:
        ratio = context['expressive_ratio']
        index = ordinal if form_ordinal is None else form_ordinal
        selected = math.floor((index+1)*ratio+1e-9) > math.floor(index*ratio+1e-9)
        if selected and not is_expressive_envelope(envelope):
            shapes = ('chamfered', 'ellipse', 'hexagon', 'trapezoid')
            envelope = {'shape': shapes[stable_index(f'{seed}:{building.id}:form', len(shapes))],
                        'profile': 'straight',
                        'facade_system': 'curtain_wall' if building.function == 'commercial' else 'punched'}
        elif not selected and is_expressive_envelope(envelope):
            envelope = {}  # Preserve the normal catalog massing / building group.
        form_policy = {'source': 'expressive_ratio', 'target_ratio': ratio,
                       'ordinal': index, 'expressive_slot': selected}
    return {
        "version": "cityg.building_appearance.v1", "language": language,
        "context": dict(context), "allowed_languages": list(palette), "source": source,
        "material_family": materials[ordinal % len(materials)] if materials else None,
        "envelope": dict(envelope),
        "form_policy": form_policy,
        "module_variant": stable_index(f"{seed}:{building.id}:module", 1_000_000),
        "articulation_scale": (0.94, 1.0, 1.06)[stable_index(f"{seed}:{building.id}:scale", 3)],
        "face_policy": "entrance_primary_opposite_service",
    }


def is_expressive_envelope(envelope):
    """Ordinary orthogonal catalog groups are not counted as exotic shapes."""
    if not envelope:
        return False
    profile = envelope.get('profile', 'straight')
    return (envelope.get('shape', 'rectangle') != 'rectangle'
            or (profile == 'taper' and envelope.get('top_scale', .72) < 1-1e-9)
            or (profile == 'lean' and (abs(envelope.get('lean_x', .10)) > 1e-9
                                       or abs(envelope.get('lean_y', 0)) > 1e-9)))


def validate_appearance_plan(plan: dict) -> None:
    if not isinstance(plan, dict) or plan.get("version") != "cityg.building_appearance.v1":
        raise ValueError("unsupported building appearance plan")
    if plan.get("language") not in DESIGN_LANGUAGES:
        raise ValueError("unsupported design language")
    validate_architecture(plan.get("context", {}))
    validate_envelope(plan.get("envelope", {}))
    if plan.get("material_family") not in (*MATERIAL_FAMILIES, None):
        raise ValueError("unsupported material family")
    materials = plan.get("context", {}).get("material_palette", [])
    if materials and plan.get("material_family") not in materials:
        raise ValueError("material family outside accepted palette")
    validate_palette(plan.get("allowed_languages", []))
    if plan.get("allowed_languages") and plan["language"] not in plan["allowed_languages"]:
        raise ValueError("appearance language outside accepted palette")
    if plan.get("articulation_scale") not in (0.94, 1.0, 1.06):
        raise ValueError("unsupported facade articulation scale")


def appearance_for_building(building: Any) -> dict:
    plan = building.metadata.get("appearance_plan", {})
    if plan != {}:
        validate_appearance_plan(plan)
    return plan


def merge_architecture(global_context, district_context):
    """A district's single or palette selection replaces either global form."""
    result = {**global_context, **district_context}
    if 'envelope' in district_context:
        result.pop('envelope_palette', None)
    elif 'envelope_palette' in district_context:
        result.pop('envelope', None)
    return result
