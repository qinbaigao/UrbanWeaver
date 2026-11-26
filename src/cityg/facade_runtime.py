"""Runtime selection and portable preparation of facade geometry assets.

The annotation index intentionally remains a source catalog.  This module is
the bridge from that catalog to a compiled CityG scene: it derives a compact
building-specific module plan, extracts addressable glTF nodes into canonical
self-contained GLBs, and registers only the modules actually used by a city.
"""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from cityg.asset_curation import _read_gltf, _write_glb
from cityg.assets import AssetRecord, AssetRegistry
from cityg.facade_assets import FacadeAssetIndex


_WINDOW_TYPES = ("window_bay", "window_insert")
_ENTRANCE_TYPES = ("entrance_bay", "door_insert")
_FACADE_CACHE_VERSION = 2


@dataclass(frozen=True)
class FacadeModuleSelection:
    slot: str
    facade_zone: str
    asset_id: str
    semantic_type: str
    source_id: str
    quality_score: float
    geometry_path: str
    selection_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot": self.slot,
            "facade_zone": self.facade_zone,
            "asset_id": self.asset_id,
            "semantic_type": self.semantic_type,
            "source_id": self.source_id,
            "quality_score": self.quality_score,
            "geometry_path": self.geometry_path,
            "selection_reason": self.selection_reason,
        }


@dataclass(frozen=True)
class FacadeBuildingAssetPlan:
    building_id: str
    selections: tuple[FacadeModuleSelection, ...]
    failures: tuple[str, ...] = ()

    def get(self, slot: str) -> FacadeModuleSelection | None:
        return next((item for item in self.selections if item.slot == slot), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "building_id": self.building_id,
            "selections": [item.to_dict() for item in self.selections],
            "failures": list(self.failures),
        }


def _function_label(value: str) -> str:
    return "public_service" if value == "public" else value


def _tokens(values: Iterable[str]) -> set[str]:
    result: set[str] = set()
    for value in values:
        result.update(
            token
            for token in str(value).lower().replace("-", "_").split("_")
            if token
        )
    return result


class FacadeAssetRuntime:
    """Select, canonicalize, and register facade modules on demand."""

    def __init__(
        self,
        index: FacadeAssetIndex,
        asset_registry: AssetRegistry,
        *,
        project_root: str | Path,
        cache_root: str | Path | None = None,
    ) -> None:
        self.index = index
        self.asset_registry = asset_registry
        self.project_root = Path(project_root).expanduser().resolve()
        self.cache_root = (
            Path(cache_root).expanduser().resolve()
            if cache_root is not None
            else self.project_root / "assets" / "facades" / "cache"
        )
        self._records = {
            str(record["asset_id"]): record for record in self.index.assets
        }
        self._prepared: dict[str, AssetRecord] = {}

    @classmethod
    def load(
        cls,
        index_path: str | Path,
        asset_registry: AssetRegistry,
        *,
        project_root: str | Path | None = None,
        cache_root: str | Path | None = None,
    ) -> "FacadeAssetRuntime":
        source = Path(index_path).expanduser().resolve()
        root = Path(project_root).expanduser().resolve() if project_root else source.parents[2]
        return cls(
            FacadeAssetIndex.load(source),
            asset_registry,
            project_root=root,
            cache_root=cache_root,
        )

    def candidate_summaries(
        self,
        *,
        building_function: str,
        facade_zone: str,
        semantic_types: Iterable[str],
        query: str = "",
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        """Expose an LLM-sized candidate list with VLM evidence included."""

        records = self._ranked_records(
            building_id="agent_preview",
            slot=f"{facade_zone}_preview",
            building_function=building_function,
            facade_zone=facade_zone,
            semantic_types=tuple(semantic_types),
            query=query,
            preferred_ids=(),
        )[:limit]
        return [
            {
                "asset_id": item["asset_id"],
                "semantic_type": item["semantic_type"],
                "source_id": item["source_id"],
                "design_languages": item.get("appearance", {}).get(
                    "compatible_design_languages", []
                ),
                "realism_level": item.get("appearance", {}).get("realism_level"),
                "quality_score": item.get("quality", {}).get("score", 0.0),
                "vlm_visual_quality_score": item.get("quality", {}).get(
                    "vlm_visual_quality_score"
                ),
                "orientation_review_required": item.get("orientation", {}).get(
                    "visual_review_required", True
                ),
            }
            for item in records
        ]

    def plan_for_building(
        self,
        building: Any,
        *,
        zones: Iterable[str],
    ) -> FacadeBuildingAssetPlan:
        metadata = dict(getattr(building, "metadata", {}) or {})
        appearance_plan = metadata.get("appearance_plan", {})
        preferred_ids = tuple(
            str(item) for item in metadata.get("facade_asset_ids", ()) if str(item)
        )
        style_query = " ".join(
            str(value)
            for value in (
                getattr(building, "function", ""),
                metadata.get("facade_style_override", ""),
                metadata.get("massing_style", ""),
                metadata.get("archetype_family", ""),
                appearance_plan.get("language", ""),
                *appearance_plan.get("context", {}).values(),
            )
            if value
        )
        selection_key = "|".join(
            str(value)
            for value in (
                getattr(building, "function", ""),
                metadata.get("facade_style_override", ""),
                getattr(building, "id", ""),
                appearance_plan.get("module_variant", ""),
            )
            if value
        )
        zone_set = set(zones)
        requests: list[tuple[str, str, tuple[str, ...]]] = []
        if "podium" in zone_set:
            requests.extend(
                (
                    ("podium_window", "podium", _WINDOW_TYPES),
                    ("entrance", "podium", _ENTRANCE_TYPES),
                )
            )
        if "shaft" in zone_set:
            requests.append(("shaft_window", "shaft", _WINDOW_TYPES))
        if "crown" in zone_set:
            requests.append(("crown_window", "shaft", _WINDOW_TYPES))

        selections: list[FacadeModuleSelection] = []
        failures: list[str] = []
        used: set[str] = set()
        window_source: str | None = None
        for slot, zone, semantic_types in requests:
            reusable_window = "window" in slot
            ranked = self._ranked_records(
                building_id=selection_key or str(building.id),
                slot="window" if reusable_window else slot,
                building_function=str(building.function),
                facade_zone=zone,
                semantic_types=semantic_types,
                query=style_query,
                preferred_ids=preferred_ids,
                preferred_source=window_source if "window" in slot else None,
            )
            record = (
                ranked[0]
                if reusable_window and ranked
                else next(
                    (item for item in ranked if item["asset_id"] not in used),
                    ranked[0] if ranked else None,
                )
            )
            if record is None:
                continue
            try:
                prepared = self.prepare(record)
            except (FileNotFoundError, KeyError, ValueError, OSError) as error:
                failures.append(f"{slot}:{record['asset_id']}:{type(error).__name__}:{error}")
                continue
            if not reusable_window:
                used.add(str(record["asset_id"]))
            if "window" in slot and window_source is None:
                window_source = str(record.get("source_id", "")) or None
            quality = record.get("quality", {})
            score = float(
                quality.get("vlm_visual_quality_score", quality.get("score", 0.0))
            )
            selections.append(
                FacadeModuleSelection(
                    slot=slot,
                    facade_zone=zone,
                    asset_id=prepared.asset_id,
                    semantic_type=str(record["semantic_type"]),
                    source_id=str(record["source_id"]),
                    quality_score=score,
                    geometry_path=str(prepared.geometry_path),
                    selection_reason=(
                        "building_agent_preference"
                        if record["asset_id"] in preferred_ids
                        else "deterministic_semantic_visual_rank"
                    ),
                )
            )
        return FacadeBuildingAssetPlan(str(building.id), tuple(selections), tuple(failures))

    def _ranked_records(
        self,
        *,
        building_id: str,
        slot: str,
        building_function: str,
        facade_zone: str,
        semantic_types: tuple[str, ...],
        query: str,
        preferred_ids: tuple[str, ...],
        preferred_source: str | None = None,
    ) -> list[dict[str, Any]]:
        function = _function_label(building_function)
        wanted = _tokens((query, slot, function))
        allowed = set(semantic_types)
        scored: list[tuple[float, str, dict[str, Any]]] = []
        for record in self.index.assets:
            if record.get("selection_status") != "usable":
                continue
            if record.get("semantic_type") not in allowed:
                continue
            if function not in record.get("compatible_building_functions", ()):
                continue
            if facade_zone not in record.get("compatible_facade_zones", ()):
                continue
            source = self.project_root / str(record.get("geometry_path", ""))
            if not source.is_file():
                continue
            appearance = record.get("appearance", {})
            quality = record.get("quality", {})
            searchable = _tokens(
                (
                    str(record.get("display_name", "")),
                    str(record.get("semantic_type", "")),
                    *[str(item) for item in record.get("tags", ())],
                    *[
                        str(item)
                        for item in appearance.get("compatible_design_languages", ())
                    ],
                )
            )
            deterministic_quality = float(quality.get("score", 0.0))
            visual_quality = float(
                quality.get("vlm_visual_quality_score", deterministic_quality * 0.9)
            )
            score = deterministic_quality * 2.0 + visual_quality * 0.7
            score += 0.18 * len(wanted & searchable)
            score += 0.30 if appearance.get("pbr_textured") else 0.0
            score += 0.42 if appearance.get("realism_level") == "realistic" else 0.0
            score -= 0.18 if record.get("orientation", {}).get("visual_review_required") else 0.0
            if record.get("asset_id") in preferred_ids:
                score += 20.0
            if preferred_source and record.get("source_id") == preferred_source:
                score += 0.55
            # A small stable jitter prevents every compatible building from
            # receiving the same top-scoring module while preserving replay.
            digest = hashlib.sha256(
                f"{building_id}|{slot}|{record['asset_id']}".encode("utf-8")
            ).digest()
            score += int.from_bytes(digest[:2], "big") / 65535.0 * 0.22
            scored.append((score, str(record["asset_id"]), record))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [record for _, _, record in scored]

    def bind_registry(self, registry: AssetRegistry) -> None:
        """Keep prepared modules and the compiler/export registry in one scope."""
        self.asset_registry = registry
        self._prepared.clear()

    def prepare(self, record: dict[str, Any]) -> AssetRecord:
        asset_id = str(record["asset_id"])
        if asset_id in self._prepared:
            return self._prepared[asset_id]
        existing = self.asset_registry.get(asset_id)
        if existing is not None and existing.geometry_path:
            existing_path = self.asset_registry.resolve_path(existing.geometry_path)
            if existing_path.is_file() and (
                not existing.metadata.get("facade_asset")
                or _cache_is_current(existing_path, asset_id)
            ):
                self._prepared[asset_id] = existing
                return existing
        source = self.project_root / str(record["geometry_path"])
        if not source.is_file():
            raise FileNotFoundError(source)
        self.cache_root.mkdir(parents=True, exist_ok=True)
        destination = self.cache_root / f"{asset_id}.glb"
        if not _cache_is_current(destination, asset_id):
            payload = canonical_facade_glb(source, record)
            destination.write_bytes(payload)
        geometry_path: str
        if self.asset_registry.manifest_path is not None:
            try:
                geometry_path = str(
                    destination.resolve().relative_to(
                        self.asset_registry.manifest_path.parent.resolve()
                    )
                )
            except ValueError:
                geometry_path = str(destination.resolve())
        else:
            geometry_path = str(destination.resolve())
        quality = record.get("quality", {})
        result = AssetRecord(
            asset_id=asset_id,
            category="facade_module",
            tags=tuple(
                dict.fromkeys(
                    (
                        str(record.get("semantic_type", "facade_module")),
                        str(record.get("source_id", "unknown")),
                        *[str(item) for item in record.get("tags", ())],
                    )
                )
            ),
            dimensions_m=(1.0, 1.0, 1.0),
            geometry_path=geometry_path,
            source=str(record.get("source_id", "unknown")),
            license_id=str(record.get("provenance", {}).get("license_id", "unknown")),
            quality_score=float(
                quality.get("vlm_visual_quality_score", quality.get("score", 0.0))
            ),
            environment="outdoor",
            metadata={
                "facade_asset": True,
                "semantic_type": record.get("semantic_type"),
                "compatible_building_functions": record.get(
                    "compatible_building_functions", []
                ),
                "compatible_facade_zones": record.get("compatible_facade_zones", []),
                "orientation": {
                    "canonical_up_axis": "+Z",
                    "canonical_forward_axis": "+X",
                    "source_front_axis": record.get("orientation", {}).get(
                        "source_front_axis"
                    ),
                },
                "source_selector": record.get("selector", {}),
                "source_geometry_path": record.get("geometry_path"),
                "resolved_asset": True,
            },
        )
        self.asset_registry.register(result, overwrite=existing is not None)
        self._prepared[asset_id] = result
        return result


def _identity() -> list[list[float]]:
    return [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]


def _cache_is_current(path: Path, asset_id: str) -> bool:
    if not path.is_file():
        return False
    try:
        document, _ = _read_gltf(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    extras = document.get("asset", {}).get("extras", {})
    return (
        extras.get("cityg_asset_id") == asset_id
        and extras.get("cityg_facade_cache_version") == _FACADE_CACHE_VERSION
    )


def _multiply(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [
        [sum(a[row][index] * b[index][column] for index in range(4)) for column in range(4)]
        for row in range(4)
    ]


def _node_matrix(node: dict[str, Any]) -> list[list[float]]:
    if len(node.get("matrix", ())) == 16:
        raw = [float(item) for item in node["matrix"]]
        return [[raw[column * 4 + row] for column in range(4)] for row in range(4)]
    translation = [float(item) for item in node.get("translation", (0.0, 0.0, 0.0))]
    scale = [float(item) for item in node.get("scale", (1.0, 1.0, 1.0))]
    x, y, z, w = [float(item) for item in node.get("rotation", (0.0, 0.0, 0.0, 1.0))]
    rotation = [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]
    result = _identity()
    for row in range(3):
        for column in range(3):
            result[row][column] = rotation[row][column] * scale[column]
        result[row][3] = translation[row]
    return result


def _transform(matrix: list[list[float]], point: tuple[float, float, float]) -> tuple[float, float, float]:
    value = (*point, 1.0)
    return tuple(sum(matrix[row][index] * value[index] for index in range(4)) for row in range(3))


def _selected_bounds(
    document: dict[str, Any], roots: Iterable[int]
) -> tuple[list[float], list[float]]:
    nodes = document.get("nodes", [])
    meshes = document.get("meshes", [])
    accessors = document.get("accessors", [])
    low = [math.inf, math.inf, math.inf]
    high = [-math.inf, -math.inf, -math.inf]

    def visit(index: int, parent: list[list[float]]) -> None:
        if not 0 <= index < len(nodes):
            return
        node = nodes[index]
        matrix = _multiply(parent, _node_matrix(node))
        mesh_index = node.get("mesh")
        if isinstance(mesh_index, int) and 0 <= mesh_index < len(meshes):
            for primitive in meshes[mesh_index].get("primitives", []):
                position = primitive.get("attributes", {}).get("POSITION")
                if not isinstance(position, int) or not 0 <= position < len(accessors):
                    continue
                accessor = accessors[position]
                minimum, maximum = accessor.get("min"), accessor.get("max")
                if not minimum or not maximum:
                    continue
                for x in (float(minimum[0]), float(maximum[0])):
                    for y in (float(minimum[1]), float(maximum[1])):
                        for z in (float(minimum[2]), float(maximum[2])):
                            point = _transform(matrix, (x, y, z))
                            for axis in range(3):
                                low[axis] = min(low[axis], point[axis])
                                high[axis] = max(high[axis], point[axis])
        for child in node.get("children", []):
            visit(int(child), matrix)

    for root in roots:
        visit(int(root), _identity())
    if any(not math.isfinite(value) for value in (*low, *high)):
        raise ValueError("selected facade node has no bounded mesh geometry")
    return low, high


def _clone_nodes(document: dict[str, Any], roots: Iterable[int]) -> tuple[list[dict[str, Any]], list[int]]:
    source = document.get("nodes", [])
    result: list[dict[str, Any]] = []
    mapped: dict[int, int] = {}

    def clone(index: int) -> int:
        if index in mapped:
            return mapped[index]
        if not 0 <= index < len(source):
            raise ValueError(f"facade selector references invalid node {index}")
        target = deepcopy(source[index])
        new_index = len(result)
        mapped[index] = new_index
        result.append(target)
        target["children"] = [clone(int(child)) for child in target.get("children", [])]
        if not target["children"]:
            target.pop("children", None)
        return new_index

    new_roots = [clone(int(index)) for index in roots]
    return result, new_roots


def _texture_indices(value: Any, context: str = "") -> set[int]:
    result: set[int] = set()
    if isinstance(value, dict):
        if "texture" in context.lower() and isinstance(value.get("index"), int):
            result.add(int(value["index"]))
        for key, item in value.items():
            result.update(_texture_indices(item, str(key)))
    elif isinstance(value, list):
        for item in value:
            result.update(_texture_indices(item, context))
    return result


def _remap_texture_indices(value: Any, mapping: dict[int, int], context: str = "") -> None:
    if isinstance(value, dict):
        if "texture" in context.lower() and isinstance(value.get("index"), int):
            value["index"] = mapping[int(value["index"])]
        for key, item in value.items():
            _remap_texture_indices(item, mapping, str(key))
    elif isinstance(value, list):
        for item in value:
            _remap_texture_indices(item, mapping, context)


def _prune_for_nodes(document: dict[str, Any], nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Remove unrelated meshes and textures while retaining binary buffer indices."""

    result = deepcopy(document)
    result["nodes"] = nodes
    used_meshes = sorted(
        {int(node["mesh"]) for node in nodes if isinstance(node.get("mesh"), int)}
    )
    mesh_map = {old: new for new, old in enumerate(used_meshes)}
    result["meshes"] = [deepcopy(document.get("meshes", [])[old]) for old in used_meshes]
    for node in result["nodes"]:
        if isinstance(node.get("mesh"), int):
            node["mesh"] = mesh_map[int(node["mesh"])]

    used_materials = sorted(
        {
            int(primitive["material"])
            for mesh in result.get("meshes", [])
            for primitive in mesh.get("primitives", [])
            if isinstance(primitive.get("material"), int)
        }
    )
    material_map = {old: new for new, old in enumerate(used_materials)}
    result["materials"] = [
        deepcopy(document.get("materials", [])[old]) for old in used_materials
    ]
    for mesh in result.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            if isinstance(primitive.get("material"), int):
                primitive["material"] = material_map[int(primitive["material"])]

    used_textures = sorted(
        set().union(*(_texture_indices(item, "material") for item in result.get("materials", [])))
        if result.get("materials")
        else set()
    )
    texture_map = {old: new for new, old in enumerate(used_textures)}
    for material in result.get("materials", []):
        _remap_texture_indices(material, texture_map, "material")
    result["textures"] = [
        deepcopy(document.get("textures", [])[old]) for old in used_textures
    ]
    used_images: set[int] = set()
    for texture in result.get("textures", []):
        if isinstance(texture.get("source"), int):
            used_images.add(int(texture["source"]))
        extension_source = texture.get("extensions", {}).get("KHR_texture_basisu", {}).get("source")
        if isinstance(extension_source, int):
            used_images.add(extension_source)
    image_map = {old: new for new, old in enumerate(sorted(used_images))}
    result["images"] = [
        deepcopy(document.get("images", [])[old]) for old in sorted(used_images)
    ]
    for texture in result.get("textures", []):
        if isinstance(texture.get("source"), int):
            texture["source"] = image_map[int(texture["source"])]
        basisu = texture.get("extensions", {}).get("KHR_texture_basisu", {})
        if isinstance(basisu.get("source"), int):
            basisu["source"] = image_map[int(basisu["source"])]
    result.pop("animations", None)
    return result


def _remap_buffer_views(value: Any, mapping: dict[int, int]) -> None:
    if isinstance(value, dict):
        if isinstance(value.get("bufferView"), int):
            value["bufferView"] = mapping[int(value["bufferView"])]
        for item in value.values():
            _remap_buffer_views(item, mapping)
    elif isinstance(value, list):
        for item in value:
            _remap_buffer_views(item, mapping)


def _prune_binary_payloads(
    document: dict[str, Any], buffers: list[bytes]
) -> tuple[dict[str, Any], list[bytes]]:
    """Keep only accessors/buffer views referenced by the extracted meshes."""

    result = deepcopy(document)
    used_accessors: set[int] = set()
    for mesh in result.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            if isinstance(primitive.get("indices"), int):
                used_accessors.add(int(primitive["indices"]))
            used_accessors.update(
                int(item)
                for item in primitive.get("attributes", {}).values()
                if isinstance(item, int)
            )
            for target in primitive.get("targets", []):
                used_accessors.update(
                    int(item) for item in target.values() if isinstance(item, int)
                )
    accessor_map = {
        old: new for new, old in enumerate(sorted(used_accessors))
    }
    source_accessors = result.get("accessors", [])
    result["accessors"] = [
        deepcopy(source_accessors[old]) for old in sorted(used_accessors)
    ]
    for mesh in result.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            if isinstance(primitive.get("indices"), int):
                primitive["indices"] = accessor_map[int(primitive["indices"])]
            primitive["attributes"] = {
                key: accessor_map[int(value)]
                for key, value in primitive.get("attributes", {}).items()
            }
            for target in primitive.get("targets", []):
                for key, value in tuple(target.items()):
                    target[key] = accessor_map[int(value)]

    used_views: set[int] = set()
    for accessor in result.get("accessors", []):
        if isinstance(accessor.get("bufferView"), int):
            used_views.add(int(accessor["bufferView"]))
        sparse = accessor.get("sparse", {})
        for section in (sparse.get("indices", {}), sparse.get("values", {})):
            if isinstance(section.get("bufferView"), int):
                used_views.add(int(section["bufferView"]))
    for image in result.get("images", []):
        if isinstance(image.get("bufferView"), int):
            used_views.add(int(image["bufferView"]))
    # Mesh compression extensions reference buffer views directly.
    def collect_views(value: Any) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("bufferView"), int):
                used_views.add(int(value["bufferView"]))
            for item in value.values():
                collect_views(item)
        elif isinstance(value, list):
            for item in value:
                collect_views(item)
    collect_views(result.get("meshes", []))

    source_views = result.get("bufferViews", [])
    view_map = {old: new for new, old in enumerate(sorted(used_views))}
    new_views: list[dict[str, Any]] = []
    new_buffers: list[bytes] = []
    for old in sorted(used_views):
        view = deepcopy(source_views[old])
        buffer_index = int(view.get("buffer", 0))
        start = int(view.get("byteOffset", 0))
        length = int(view.get("byteLength", 0))
        if not 0 <= buffer_index < len(buffers):
            raise ValueError(f"bufferView references missing buffer {buffer_index}")
        new_buffers.append(buffers[buffer_index][start : start + length])
        view["buffer"] = len(new_buffers) - 1
        view["byteOffset"] = 0
        new_views.append(view)
    result["bufferViews"] = new_views
    _remap_buffer_views(result.get("accessors", []), view_map)
    _remap_buffer_views(result.get("images", []), view_map)
    _remap_buffer_views(result.get("meshes", []), view_map)
    result["buffers"] = [{"byteLength": len(item)} for item in new_buffers]
    return result, new_buffers


def _axis_vector(axis: str) -> tuple[float, float, float]:
    sign = -1.0 if str(axis).startswith("-") else 1.0
    label = str(axis)[-1:].upper()
    if label == "X":
        return (sign, 0.0, 0.0)
    if label == "Y":
        return (0.0, sign, 0.0)
    return (0.0, 0.0, sign)


def _dot(a: tuple[float, float, float], b: Iterable[float]) -> float:
    return sum(a[index] * float(value) for index, value in enumerate(b))


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _canonical_matrix(
    low: list[float], high: list[float], source_front_axis: str
) -> list[float]:
    center = [(low[index] + high[index]) / 2.0 for index in range(3)]
    front = _axis_vector(source_front_axis)
    up = (0.0, 1.0, 0.0)
    if abs(_dot(front, up)) > 0.5:
        raise ValueError("facade front axis cannot be vertical")
    right = _cross(up, front)
    corners = [
        (x, y, z)
        for x in (low[0], high[0])
        for y in (low[1], high[1])
        for z in (low[2], high[2])
    ]
    bases = (front, right, up)
    extents = [
        max(_dot(axis, point) for point in corners)
        - min(_dot(axis, point) for point in corners)
        for axis in bases
    ]
    rows = []
    for axis, extent in zip(bases, extents):
        scale = 1.0 / max(1e-6, extent)
        rows.append([axis[0] * scale, axis[1] * scale, axis[2] * scale, -_dot(axis, center) * scale])
    # glTF matrices are column-major.
    return [rows[row][column] if row < 3 else (1.0 if column == 3 else 0.0) for column in range(4) for row in range(4)]


def canonical_facade_glb(source: str | Path, record: dict[str, Any]) -> bytes:
    """Extract one facade record and return a canonical unit-bounds GLB."""

    path = Path(source)
    document, buffers = _read_gltf(path)
    selector = record.get("selector", {})
    if selector.get("kind") == "gltf_node":
        node_index = int(selector["node_index"])
        roots = [node_index]
    else:
        scene_index = int(document.get("scene", 0))
        scenes = document.get("scenes", [])
        if not scenes:
            roots = list(range(len(document.get("nodes", []))))
        else:
            roots = [int(item) for item in scenes[scene_index].get("nodes", [])]
    low, high = _selected_bounds(document, roots)
    nodes, cloned_roots = _clone_nodes(document, roots)
    result = _prune_for_nodes(document, nodes)
    wrapper_index = len(result["nodes"])
    result["nodes"].append(
        {
            "name": "CityGFacadeCanonicalRoot",
            "matrix": _canonical_matrix(
                low,
                high,
                str(record.get("orientation", {}).get("source_front_axis", "+Z")),
            ),
            "children": cloned_roots,
            "extras": {
                "cityg_asset_id": record["asset_id"],
                "canonical_up_axis": "+Z",
                "canonical_forward_axis": "+X",
            },
        }
    )
    result["scenes"] = [{"name": "CityGFacade", "nodes": [wrapper_index]}]
    result["scene"] = 0
    result.setdefault("asset", {}).setdefault("extras", {}).update(
        {
            "cityg_facade_asset": True,
            "cityg_asset_id": record["asset_id"],
            "cityg_coordinate_system": "right_handed_z_up_unit_bounds",
            "cityg_facade_cache_version": _FACADE_CACHE_VERSION,
        }
    )
    result, selected_buffers = _prune_binary_payloads(result, buffers)
    return _write_glb(result, selected_buffers, path.parent)


__all__ = [
    "FacadeAssetRuntime",
    "FacadeBuildingAssetPlan",
    "FacadeModuleSelection",
    "canonical_facade_glb",
]
