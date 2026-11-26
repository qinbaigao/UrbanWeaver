"""Semantic annotations for reusable facade modules and attachments.

Downloaded content remains under ``assets/incoming``.  This module builds a
compact, machine-readable index that Building/VLM agents can inspect without
loading hundreds of meshes or their textures into context.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from cityg.asset_curation import _document_bounds, _document_metrics, _read_gltf


_POLYHAVEN_NODE_LIBRARIES = frozenset(
    {
        "modular_urban_apartments_facade",
        "modular_factory_facade",
        "modular_fire_escape",
        "modular_metal_gutter",
        "modular_airduct_circular_01",
        "exterior_aircon_unit",
        "rollershutter_door",
        "rollershutter_window_01",
        "rollershutter_window_02",
        "rollershutter_window_03",
    }
)


@dataclass(frozen=True)
class FacadeSourcePack:
    source_id: str
    directory: str
    source_url: str
    license_id: str
    style: str
    realism_level: str
    geometry_glob: str
    source_front_axis: str
    front_axis_confidence: str
    quality_score: float


_KENNEY_PACKS = (
    FacadeSourcePack(
        source_id="kenney_modular_buildings_2_1",
        directory="kenney_modular-buildings",
        source_url="https://kenney.nl/assets/modular-buildings",
        license_id="CC0-1.0",
        style="stylized_low_poly",
        realism_level="stylized",
        geometry_glob="Models/GLB format/*.glb",
        source_front_axis="+Z",
        front_axis_confidence="medium",
        quality_score=0.72,
    ),
    FacadeSourcePack(
        source_id="kenney_building_kit_1_0",
        directory="kenney_building-kit",
        source_url="https://kenney.nl/assets/building-kit",
        license_id="CC0-1.0",
        style="stylized_low_poly",
        realism_level="stylized",
        geometry_glob="Models/GLB format/*.glb",
        source_front_axis="+X",
        front_axis_confidence="medium",
        quality_score=0.70,
    ),
)


def _tokens(value: str) -> tuple[str, ...]:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    value = re.sub(r"([A-Za-z])(\d)", r"\1_\2", value)
    value = re.sub(r"(\d)([A-Za-z])", r"\1_\2", value)
    return tuple(re.findall(r"[a-z0-9]+", value.lower()))


def _slug(value: str) -> str:
    return "_".join(_tokens(value)) or "asset"


def _semantic_type(name: str) -> str:
    words = set(_tokens(name))
    joined = "_".join(_tokens(name))
    if "sample" in words and words & {"house", "tower"}:
        return "reference_building"
    if "fire_escape" in joined:
        if "stairs" in words:
            return "fire_escape_stairs"
        if "ladder" in words:
            return "fire_escape_ladder"
        if "platform" in words:
            return "fire_escape_platform"
        return "fire_escape_railing"
    if "airduct" in joined or "vent" in words and "window" not in words:
        return "hvac_duct"
    if "aircon" in joined or words & {"ac", "hvac"}:
        return "exterior_hvac_unit"
    if "pipe" in words:
        return "exterior_service_pipe"
    if "gutter" in joined or words & {"downspout", "funnel", "outlet"}:
        return "rainwater_module"
    if "camera" in words or "cctv" in words:
        return "security_camera"
    if "light" in words:
        return "exterior_light"
    if "utility" in words and "box" in words:
        return "utility_box"
    if words & {"balcony", "balconies"}:
        return "balcony_bay"
    if words & {"awning", "awnings", "canopy", "canopies"}:
        return "awning_module"
    if "barricade" in words:
        return "opening_security_panel"
    if "roof" in words:
        return "roof_module"
    if "rollershutter" in joined or "shutter" in words or "garage" in words:
        return "service_door_bay" if "door" in words or "garage" in words else "shutter_bay"
    if "door" in words and "window" in words:
        if words & {"wall", "building", "dado"}:
            return "entrance_bay"
        return "door_insert"
    if "window" in words:
        if words & {"wall", "building", "dado"}:
            return "window_bay"
        return "window_insert"
    if "door" in words or "doorway" in words:
        if words & {"wall", "building", "dado"}:
            return "entrance_bay"
        return "door_insert"
    if words & {"cornice", "crown"}:
        return "cornice_trim"
    if "stairs" in words or "steps" in words:
        return "exterior_stairs"
    if "column" in words or "pier" in words:
        return "facade_column"
    if words & {"dado", "base", "plating", "border"}:
        return "facade_band"
    if "floor" in words:
        return "structural_floor_module"
    if "wall" in words or "building" in words:
        return "wall_module"
    return "facade_detail"


def _asset_family(semantic_type: str) -> str:
    if semantic_type in {"reference_building", "structural_floor_module"}:
        return "reference_or_structure"
    if semantic_type.startswith("roof") or semantic_type == "rainwater_module":
        return "roof_edge_system"
    if semantic_type.startswith("fire_escape") or semantic_type in {
        "exterior_hvac_unit", "hvac_duct", "exterior_service_pipe", "security_camera", "exterior_light", "utility_box"
    }:
        return "facade_attachment"
    if semantic_type in {"window_insert", "door_insert"}:
        return "opening_insert"
    return "facade_module"


def _compatibility(semantic_type: str, source_asset_id: str) -> tuple[str, ...]:
    if source_asset_id == "modular_factory_facade" or semantic_type in {
        "service_door_bay", "shutter_bay", "hvac_duct", "opening_security_panel"
    }:
        return ("industrial", "commercial", "mixed_use")
    if source_asset_id == "modular_urban_apartments_facade" or semantic_type == "balcony_bay":
        return ("residential", "mixed_use", "commercial")
    if semantic_type in {"security_camera", "exterior_light", "utility_box", "rainwater_module", "exterior_service_pipe"}:
        return ("residential", "commercial", "mixed_use", "public_service", "industrial")
    return ("residential", "commercial", "mixed_use", "public_service")


def _zones(semantic_type: str) -> tuple[str, ...]:
    if semantic_type in {"door_insert", "entrance_bay", "service_door_bay", "opening_security_panel", "awning_module"}:
        return ("ground", "podium")
    if semantic_type in {"cornice_trim"}:
        return ("podium", "crown", "roofline")
    if semantic_type in {"roof_module", "rainwater_module"}:
        return ("roofline", "roof")
    if semantic_type in {"exterior_hvac_unit", "hvac_duct", "exterior_service_pipe"}:
        return ("service_facade", "roof")
    if semantic_type in {"security_camera", "exterior_light", "utility_box"}:
        return ("ground", "service_facade", "rear_facade")
    if semantic_type.startswith("fire_escape"):
        return ("shaft", "rear_facade", "service_facade")
    if semantic_type == "reference_building":
        return ("whole_building_reference",)
    return ("podium", "shaft")


def _placement(semantic_type: str) -> dict[str, Any]:
    wall = {
        "mount_surface": "wall",
        "anchor": "surface_center",
        "facing_rule": "front_faces_outward_from_facade",
        "frontage_roles": ["primary", "secondary", "rear"],
    }
    if semantic_type in {"roof_module"}:
        return {
            "mount_surface": "roof",
            "anchor": "roof_grid",
            "facing_rule": "align_to_roof_slope_or_edge",
            "frontage_roles": ["roof"],
        }
    if semantic_type == "rainwater_module":
        return {
            "mount_surface": "roof_edge_or_wall",
            "anchor": "roof_edge_snap",
            "facing_rule": "follow_roof_edge_and_gravity",
            "frontage_roles": ["secondary", "rear", "roof"],
        }
    if semantic_type in {"utility_box"}:
        return {
            "mount_surface": "ground_or_wall",
            "anchor": "service_zone",
            "facing_rule": "access_panel_faces_service_clearance",
            "frontage_roles": ["rear", "service"],
        }
    if semantic_type == "reference_building":
        return {
            "mount_surface": "ground",
            "anchor": "reference_only",
            "facing_rule": "reference_only",
            "frontage_roles": [],
        }
    if semantic_type in {"door_insert", "entrance_bay", "service_door_bay"}:
        wall.update(anchor="wall_opening", frontage_roles=["primary", "secondary", "service"])
    elif semantic_type == "opening_security_panel":
        wall.update(anchor="wall_opening", frontage_roles=["secondary", "rear", "service"])
    elif semantic_type in {"window_insert", "window_bay", "shutter_bay"}:
        wall.update(anchor="wall_opening")
    elif semantic_type in {"awning_module", "balcony_bay"}:
        wall.update(anchor="facade_bay")
    elif semantic_type.startswith("fire_escape"):
        wall.update(anchor="vertical_service_grid", frontage_roles=["rear", "service"])
    elif semantic_type in {"exterior_hvac_unit", "hvac_duct", "exterior_service_pipe"}:
        wall.update(anchor="service_grid", frontage_roles=["rear", "service", "roof"])
    return wall


def _repeatability(semantic_type: str) -> dict[str, Any]:
    horizontal = {
        "mode": "horizontal_grid",
        "repeatable": True,
        "stretch_axes": [],
        "mirroring_allowed": True,
    }
    if semantic_type in {"wall_module", "facade_band", "cornice_trim", "facade_column"}:
        horizontal["stretch_axes"] = ["local_horizontal"]
        return horizontal
    if semantic_type in {"window_bay", "window_insert", "balcony_bay", "shutter_bay"}:
        return horizontal
    if semantic_type.startswith("fire_escape"):
        return {"mode": "vertical_stack", "repeatable": True, "stretch_axes": [], "mirroring_allowed": True}
    if semantic_type in {"rainwater_module", "hvac_duct", "exterior_service_pipe"}:
        return {"mode": "path_or_grid", "repeatable": True, "stretch_axes": ["module_axis"], "mirroring_allowed": True}
    if semantic_type in {"roof_module"}:
        return {"mode": "roof_grid", "repeatable": True, "stretch_axes": ["local_horizontal"], "mirroring_allowed": True}
    return {"mode": "single", "repeatable": False, "stretch_axes": [], "mirroring_allowed": False}


def _selection_status(semantic_type: str) -> str:
    if semantic_type in {"reference_building", "structural_floor_module"}:
        return "reference_only"
    if semantic_type == "facade_detail":
        return "needs_semantic_review"
    return "usable"


def _orientation_mode(semantic_type: str) -> str:
    if semantic_type in {"rainwater_module", "hvac_duct", "exterior_service_pipe"}:
        return "path_tangent"
    if semantic_type == "roof_module":
        return "roof_alignment"
    if semantic_type in {"facade_column", "cornice_trim"}:
        return "multi_face_module"
    if semantic_type in {"reference_building", "structural_floor_module"}:
        return "reference_only"
    return "front_normal"


def _design_languages(source_asset_id: str, style: str) -> tuple[str, ...]:
    if source_asset_id == "modular_factory_facade" or "rollershutter" in source_asset_id:
        return ("industrial", "warehouse", "weathered_urban", "adaptive_reuse")
    if source_asset_id == "modular_urban_apartments_facade":
        return ("urban_residential", "mixed_use_block", "contemporary_masonry")
    if style == "stylized_low_poly":
        return ("generic_modular", "stylized", "concept_preview")
    return ("contemporary_urban", "weathered_utility")


def classify_facade_asset(
    name: str,
    *,
    source_asset_id: str,
    source_id: str,
    style: str,
    realism_level: str,
    source_front_axis: str,
    front_axis_confidence: str,
    extent_xyz: Iterable[float],
    selector: dict[str, Any],
    geometry_path: str,
    license_id: str,
    source_url: str,
    quality_score: float,
    technical: dict[str, Any],
    native_scale_confidence: str = "medium",
) -> dict[str, Any]:
    """Classify one facade file or addressable glTF node."""

    semantic_type = _semantic_type(name)
    tokens = _tokens(name)
    raw_extent = [max(1e-6, float(value)) for value in extent_xyz]
    planar_geometry = min(raw_extent) <= 1e-5
    extent = [round(max(1e-5, value), 5) for value in raw_extent]
    status = _selection_status(semantic_type)
    orientation_mode = _orientation_mode(semantic_type)
    material_variant = next(
        (token for token in tokens if token in {"graffiti", "rusted", "brown", "white", "round", "square"}),
        "default",
    )
    identity = f"facade_{_slug(source_id)}_{_slug(source_asset_id)}"
    if _slug(name) != _slug(source_asset_id):
        identity += f"_{_slug(name)}"
    return {
        "asset_id": identity,
        "source_id": source_id,
        "source_asset_id": source_asset_id,
        "display_name": name.replace("_", " ").strip(),
        "geometry_path": geometry_path,
        "selector": selector,
        "semantic_type": semantic_type,
        "asset_family": _asset_family(semantic_type),
        "tags": list(dict.fromkeys((*tokens, semantic_type, style, realism_level, "outdoor", "facade"))),
        "environment": "outdoor",
        "compatible_building_functions": list(_compatibility(semantic_type, source_asset_id)),
        "compatible_facade_zones": list(_zones(semantic_type)),
        "placement": _placement(semantic_type),
        "orientation": {
            "source_coordinate_system": "right_handed_y_up_gltf",
            "source_up_axis": "+Y",
            "source_front_axis": source_front_axis,
            "canonical_coordinate_system": "right_handed_z_up",
            "canonical_up_axis": "+Z",
            "canonical_front_axis": "+X",
            "alignment_mode": orientation_mode,
            "axis_meaning": (
                "outward_surface_normal"
                if orientation_mode == "front_normal"
                else "module_alignment_reference"
            ),
            "front_axis_review_applicable": orientation_mode in {"front_normal", "multi_face_module"},
            "confidence": front_axis_confidence,
            "visual_review_required": front_axis_confidence != "high",
        },
        "scale": {
            "native_extent_xyz": extent,
            "native_units": "meters" if native_scale_confidence == "high" else "source_module_units",
            "native_scale_confidence": native_scale_confidence,
            "planar_geometry": planar_geometry,
            "minimum_render_thickness_m": 0.03 if planar_geometry else None,
            "preserve_aspect_ratio": True,
            "recommended_uniform_scale_range": [0.85, 1.15] if realism_level == "photoreal_pbr" else [0.7, 1.5],
        },
        "repeatability": _repeatability(semantic_type),
        "appearance": {
            "style": style,
            "realism_level": realism_level,
            "material_variant": material_variant,
            "pbr_textured": bool(technical.get("texture_count", 0)),
            "compatible_design_languages": list(_design_languages(source_asset_id, style)),
        },
        "quality": {
            "score": quality_score,
            "semantic_confidence": "high" if status != "needs_semantic_review" else "low",
            "orientation_confidence": front_axis_confidence,
        },
        "selection_status": status,
        "technical": technical,
        "provenance": {
            "source_url": source_url,
            "license_id": license_id,
            "redistribution_policy": "redistributable_cc0",
        },
    }


def _mesh_bounds(document: dict[str, Any], mesh_index: int) -> dict[str, list[float]]:
    accessors = document.get("accessors", [])
    meshes = document.get("meshes", [])
    if mesh_index < 0 or mesh_index >= len(meshes):
        return {"min": [-0.5, -0.5, -0.5], "max": [0.5, 0.5, 0.5], "extent": [1.0, 1.0, 1.0]}
    lows: list[list[float]] = []
    highs: list[list[float]] = []
    for primitive in meshes[mesh_index].get("primitives", []):
        index = primitive.get("attributes", {}).get("POSITION")
        if index is None or index >= len(accessors):
            continue
        accessor = accessors[index]
        if len(accessor.get("min", [])) >= 3 and len(accessor.get("max", [])) >= 3:
            lows.append([float(value) for value in accessor["min"][:3]])
            highs.append([float(value) for value in accessor["max"][:3]])
    if not lows:
        return {"min": [-0.5, -0.5, -0.5], "max": [0.5, 0.5, 0.5], "extent": [1.0, 1.0, 1.0]}
    low = [min(value[index] for value in lows) for index in range(3)]
    high = [max(value[index] for value in highs) for index in range(3)]
    return {
        "min": low,
        "max": high,
        "extent": [max(1e-6, high[index] - low[index]) for index in range(3)],
    }


def _technical(document: dict[str, Any], bounds: dict[str, list[float]], mesh_index: int | None = None) -> dict[str, Any]:
    if mesh_index is None:
        metrics = _document_metrics(document, bounds)
        return {key: metrics[key] for key in ("mesh_count", "material_count", "texture_count", "triangle_count", "skin_count", "animation_count")}
    mesh = document.get("meshes", [])[mesh_index]
    accessors = document.get("accessors", [])
    triangles = 0
    material_ids: set[int] = set()
    for primitive in mesh.get("primitives", []):
        if "material" in primitive:
            material_ids.add(int(primitive["material"]))
        index = primitive.get("indices")
        if index is not None and index < len(accessors):
            triangles += int(accessors[index].get("count", 0)) // 3
        else:
            index = primitive.get("attributes", {}).get("POSITION")
            if index is not None and index < len(accessors):
                triangles += int(accessors[index].get("count", 0)) // 3
    return {
        "mesh_count": 1,
        "material_count": len(material_ids),
        "texture_count": len(document.get("textures", [])),
        "triangle_count": triangles,
        "skin_count": len(document.get("skins", [])),
        "animation_count": len(document.get("animations", [])),
    }


def _polyhaven_records(project_root: Path) -> list[dict[str, Any]]:
    root = project_root / "assets" / "incoming" / "facade_models_polyhaven"
    records: list[dict[str, Any]] = []
    for manifest_path in sorted(root.glob("*/source.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        source_asset_id = str(manifest["asset_id"])
        geometry = manifest_path.parent / str(manifest["entrypoint"])
        document, _ = _read_gltf(geometry)
        relative = str(geometry.relative_to(project_root))
        common = {
            "source_asset_id": source_asset_id,
            "source_id": "polyhaven",
            "style": "photoreal_weathered_pbr",
            "realism_level": "photoreal_pbr",
            "source_front_axis": "+Z",
            "front_axis_confidence": "medium",
            "geometry_path": relative,
            "license_id": str(manifest.get("license_id", "CC0-1.0")),
            "source_url": str(manifest.get("source_page", "https://polyhaven.com/")),
            "quality_score": 0.92,
            "native_scale_confidence": "high",
        }
        if source_asset_id in _POLYHAVEN_NODE_LIBRARIES:
            for node_index, node in enumerate(document.get("nodes", [])):
                mesh_index = node.get("mesh")
                if mesh_index is None:
                    continue
                name = str(node.get("name") or f"node_{node_index}").strip()
                bounds = _mesh_bounds(document, int(mesh_index))
                records.append(
                    classify_facade_asset(
                        name,
                        extent_xyz=bounds["extent"],
                        selector={"kind": "gltf_node", "node_index": node_index, "node_name": name},
                        technical=_technical(document, bounds, int(mesh_index)),
                        **common,
                    )
                )
        else:
            bounds = _document_bounds(document)
            records.append(
                classify_facade_asset(
                    str(manifest.get("display_name", source_asset_id)),
                    extent_xyz=bounds["extent"],
                    selector={"kind": "whole_asset"},
                    technical=_technical(document, bounds),
                    **common,
                )
            )
    return records


def _kenney_records(project_root: Path) -> list[dict[str, Any]]:
    incoming = project_root / "assets" / "incoming"
    records: list[dict[str, Any]] = []
    for pack in _KENNEY_PACKS:
        package_root = incoming / pack.directory
        for geometry in sorted(package_root.glob(pack.geometry_glob)):
            document, _ = _read_gltf(geometry)
            bounds = _document_bounds(document)
            records.append(
                classify_facade_asset(
                    geometry.stem,
                    source_asset_id=geometry.stem,
                    source_id=pack.source_id,
                    style=pack.style,
                    realism_level=pack.realism_level,
                    source_front_axis=pack.source_front_axis,
                    front_axis_confidence=pack.front_axis_confidence,
                    extent_xyz=bounds["extent"],
                    selector={"kind": "whole_asset"},
                    geometry_path=str(geometry.relative_to(project_root)),
                    license_id=pack.license_id,
                    source_url=pack.source_url,
                    quality_score=pack.quality_score,
                    technical=_technical(document, bounds),
                    native_scale_confidence="low",
                )
            )
    return records


def build_facade_asset_annotations(project_root: str | Path) -> dict[str, Any]:
    """Build deterministic annotations for all supported local facade packs."""

    root = Path(project_root).resolve()
    records = [*_polyhaven_records(root), *_kenney_records(root)]
    records.sort(key=lambda item: item["asset_id"])
    if len({item["asset_id"] for item in records}) != len(records):
        raise ValueError("duplicate facade asset IDs generated")

    def counts(field: str) -> dict[str, int]:
        return dict(sorted(Counter(str(item[field]) for item in records).items()))

    return {
        "schema_version": "cityg.facade_asset_annotations.v1",
        "annotation_policy": {
            "method": "deterministic_name_and_pack_semantics_v1",
            "agent_context": "progressive_disclosure_summary_then_candidate_records",
            "visual_review_policy": "review medium/low orientation confidence before production placement",
            "source_content_mutated": False,
        },
        "summary": {
            "asset_count": len(records),
            "source_counts": counts("source_id"),
            "semantic_type_counts": counts("semantic_type"),
            "selection_status_counts": counts("selection_status"),
        },
        "assets": records,
    }


def save_facade_asset_annotations(payload: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return destination


class FacadeAssetIndex:
    """Read-only, progressive-disclosure retrieval over facade annotations."""

    def __init__(self, payload: dict[str, Any]) -> None:
        if payload.get("schema_version") != "cityg.facade_asset_annotations.v1":
            raise ValueError("unsupported facade annotation schema")
        self.payload = payload
        self.assets = tuple(payload.get("assets", ()))

    @classmethod
    def load(cls, path: str | Path) -> "FacadeAssetIndex":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    @property
    def summary(self) -> dict[str, Any]:
        return dict(self.payload.get("summary", {}))

    def candidates(
        self,
        query: str = "",
        *,
        building_function: str | None = None,
        facade_zone: str | None = None,
        semantic_types: Iterable[str] = (),
        realism_level: str | None = None,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        """Return compact, semantically filtered candidates for an agent call."""

        if limit <= 0:
            return []
        wanted = set(_tokens(query))
        allowed_types = set(semantic_types)
        ranked: list[tuple[float, str, dict[str, Any]]] = []
        for record in self.assets:
            if record.get("selection_status") != "usable":
                continue
            if building_function and building_function not in record.get(
                "compatible_building_functions", ()
            ):
                continue
            if facade_zone and facade_zone not in record.get("compatible_facade_zones", ()):
                continue
            if allowed_types and record.get("semantic_type") not in allowed_types:
                continue
            if realism_level and record.get("appearance", {}).get("realism_level") != realism_level:
                continue
            searchable = set(
                _tokens(
                    " ".join(
                        (
                            str(record.get("display_name", "")),
                            str(record.get("semantic_type", "")),
                            *[str(tag) for tag in record.get("tags", ())],
                        )
                    )
                )
            )
            overlap = len(wanted & searchable)
            if wanted and overlap == 0:
                continue
            score = overlap * 2.0 + float(record.get("quality", {}).get("score", 0.0))
            ranked.append((score, str(record["asset_id"]), record))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [self._compact(record, score) for score, _, record in ranked[:limit]]

    @staticmethod
    def _compact(record: dict[str, Any], score: float) -> dict[str, Any]:
        """Strip provenance/mesh detail before exposing candidates to an LLM."""

        return {
            "asset_id": record["asset_id"],
            "display_name": record["display_name"],
            "semantic_type": record["semantic_type"],
            "source_id": record["source_id"],
            "compatible_facade_zones": record["compatible_facade_zones"],
            "placement": record["placement"],
            "repeatability": record["repeatability"],
            "orientation": record["orientation"],
            "appearance": record["appearance"],
            "quality_score": record["quality"]["score"],
            "vlm_visual_quality_score": record["quality"].get(
                "vlm_visual_quality_score"
            ),
            "orientation_review_required": record["orientation"].get(
                "visual_review_required", True
            ),
            "retrieval_score": round(score, 5),
        }


__all__ = [
    "build_facade_asset_annotations",
    "classify_facade_asset",
    "FacadeAssetIndex",
    "save_facade_asset_annotations",
]
