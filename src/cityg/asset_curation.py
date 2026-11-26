"""Dependency-free curation of downloaded glTF/GLB asset packs.

The curation layer deliberately separates redistributable CityG code from
locally downloaded content.  It creates canonical, self-contained GLBs under a
local cache, records provenance and licenses, and exposes search plans for
high-quality remote sources without silently downloading from them.
"""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote_plus

from cityg.assets import AssetRecord, AssetRegistry


_JSON_CHUNK = 0x4E4F534A
_BIN_CHUNK = 0x004E4942


@dataclass(frozen=True)
class ExternalAssetSource:
    source_id: str
    name: str
    homepage: str
    search_url_template: str
    api_url: str | None
    formats: tuple[str, ...]
    license_policy: str
    download_mode: str
    strengths: tuple[str, ...]
    notes: str

    def search_url(self, query: str) -> str:
        return self.search_url_template.format(query=quote_plus(query))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "name": self.name,
            "homepage": self.homepage,
            "search_url_template": self.search_url_template,
            "api_url": self.api_url,
            "formats": list(self.formats),
            "license_policy": self.license_policy,
            "download_mode": self.download_mode,
            "strengths": list(self.strengths),
            "notes": self.notes,
        }


def default_external_sources() -> tuple[ExternalAssetSource, ...]:
    """High-quality sources retained for demand-driven asset discovery."""

    return (
        ExternalAssetSource(
            source_id="polyhaven",
            name="Poly Haven",
            homepage="https://polyhaven.com/",
            search_url_template="https://polyhaven.com/models?q={query}",
            api_url="https://api.polyhaven.com/assets",
            formats=("gltf", "blend", "fbx"),
            license_policy="CC0-1.0 assets; retain source metadata",
            download_mode="manual_or_public_api",
            strengths=("photorealistic", "pbr", "vegetation", "street_props", "architecture"),
            notes="Preferred first source for close-view photorealistic static assets.",
        ),
        ExternalAssetSource(
            source_id="sketchfab",
            name="Sketchfab downloadable glTF",
            homepage="https://sketchfab.com/features/gltf",
            search_url_template=(
                "https://sketchfab.com/search?type=models&features=downloadable&q={query}"
            ),
            api_url="https://api.sketchfab.com/v3/search",
            formats=("gltf", "glb", "usdz"),
            license_policy=(
                "Per-model license; prefer CC0/CC-BY and retain attribution. "
                "Do not auto-accept NC, ND, Editorial, or Standard assets."
            ),
            download_mode="authenticated_manual_or_api",
            strengths=("vehicles", "people", "rare_objects", "animated", "photogrammetry"),
            notes="Use when curated packs and Poly Haven do not cover a requested concept.",
        ),
        ExternalAssetSource(
            source_id="khronos_gltf_assets",
            name="Khronos glTF Sample Assets",
            homepage="https://github.khronos.org/glTF-Assets/",
            search_url_template=(
                "https://github.com/KhronosGroup/glTF-Sample-Assets/search?q={query}&type=code"
            ),
            api_url="https://api.github.com/repos/KhronosGroup/glTF-Sample-Assets/contents/Models",
            formats=("gltf", "glb"),
            license_policy="Per-model license recorded in the sample catalog",
            download_mode="manual_or_github_api",
            strengths=("format_validation", "pbr_features", "animation", "viewer_regression"),
            notes="Compatibility/reference source, not the primary city-content library.",
        ),
    )


class ExternalAssetSourceCatalog:
    def __init__(self, sources: Iterable[ExternalAssetSource] | None = None) -> None:
        self.sources = tuple(sources or default_external_sources())

    def search_plan(self, query: str, *, category: str | None = None) -> dict[str, Any]:
        tokens = set(_tokens(f"{query} {category or ''}"))

        def score(source: ExternalAssetSource) -> tuple[int, str]:
            overlap = len(tokens & set(source.strengths))
            if {"vehicle", "vehicles", "person", "people", "animated"} & tokens:
                overlap += 5 if source.source_id == "sketchfab" else 0
            if {"realistic", "photorealistic", "pbr", "vegetation", "tree"} & tokens:
                overlap += 3 if source.source_id == "polyhaven" else 0
            if {"validation", "gltf", "viewer", "compatibility"} & tokens:
                overlap += 4 if source.source_id == "khronos_gltf_assets" else 0
            return (-overlap, source.source_id)

        ranked = sorted(self.sources, key=score)
        return {
            "schema_version": "cityg.external_asset_search.v1",
            "query": query,
            "category": category,
            "policy": "discovery_only_explicit_download",
            "sources": [
                {
                    **source.to_dict(),
                    "search_url": source.search_url(query),
                }
                for source in ranked
            ],
        }

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(
                {
                    "schema_version": "cityg.external_asset_sources.v1",
                    "download_policy": "explicit_user_or_agent_action_only",
                    "sources": [source.to_dict() for source in self.sources],
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        return destination


@dataclass(frozen=True)
class _PackSpec:
    directory: str
    source_id: str
    source_url: str
    license_id: str
    license_file: str
    style: str
    globs: tuple[str, ...]
    quality_score: float


_PACKS = (
    _PackSpec(
        "kenney_city_kit_commercial",
        "kenney_city_commercial_2_1",
        "https://kenney.nl/assets/city-kit-commercial",
        "CC0-1.0",
        "License.txt",
        "stylized_low_poly",
        ("Models/GLB format/detail-*.glb",),
        0.78,
    ),
    _PackSpec(
        "kenney_city_kit_suburban",
        "kenney_city_suburban_2_0",
        "https://kenney.nl/assets/city-kit-suburban",
        "CC0-1.0",
        "License.txt",
        "stylized_low_poly",
        ("Models/GLB format/planter.glb", "Models/GLB format/tree-*.glb"),
        0.78,
    ),
    _PackSpec(
        "kenney_minigolf_kit",
        "kenney_minigolf_1_0",
        "https://kenney.nl/assets/minigolf-kit",
        "CC0-1.0",
        "License.txt",
        "stylized_low_poly",
        (
            "Models/GLB format/castle.glb",
            "Models/GLB format/windmill.glb",
            "Models/GLB format/structure-windmill.glb",
        ),
        0.72,
    ),
    _PackSpec(
        "opengameart_lamp_bench_trashcan",
        "opengameart_lamp_bench_trashcan_cc0",
        "https://opengameart.org/content/lamp-post-bench-trashcan",
        "CC0-1.0",
        "README.txt",
        "photorealistic_pbr",
        ("GLTF/*.gltf",),
        0.86,
    ),
    _PackSpec(
        "kenney_retro_urban_kit",
        "kenney_retro_urban_1_0",
        "https://kenney.nl/assets/retro-urban-kit",
        "CC0-1.0",
        "License.txt",
        "stylized_low_poly",
        (
            "Models/GLB format/detail-bench.glb",
            "Models/GLB format/detail-dumpster-*.glb",
            "Models/GLB format/detail-light-*.glb",
            "Models/GLB format/tree-*.glb",
        ),
        0.76,
    ),
    _PackSpec(
        "kenney_car-kit",
        "kenney_car_kit_3_1",
        "https://www.kenney.nl/assets/car-kit",
        "CC0-1.0",
        "License.txt",
        "stylized_low_poly",
        ("Models/GLB format/*.glb",),
        0.78,
    ),
    _PackSpec(
        "kenney_city-kit-roads",
        "kenney_city_roads_2_0",
        "https://kenney.nl/assets/city-kit-roads",
        "CC0-1.0",
        "License.txt",
        "stylized_low_poly",
        ("Models/GLB format/*.glb",),
        0.76,
    ),
    _PackSpec(
        "kenney_nature-kit",
        "kenney_nature_2_1",
        "https://kenney.nl/assets/nature-kit",
        "CC0-1.0",
        "License.txt",
        "stylized_low_poly",
        ("Models/GLTF format/*.glb",),
        0.74,
    ),
    _PackSpec(
        "Stylized Nature MegaKit[Standard]",
        "quaternius_stylized_nature_standard",
        "https://quaternius.com/packs/stylizednaturemegakit.html",
        "CC0-1.0",
        "License_Standard.txt",
        "stylized_pbr",
        ("glTF/*.gltf",),
        0.82,
    ),
    _PackSpec(
        "polyhaven-outdoor-models",
        "polyhaven_outdoor_models",
        "https://polyhaven.com/models",
        "CC0-1.0",
        "License.txt",
        "photorealistic_pbr",
        ("*/*.gltf",),
        0.96,
    ),
    _PackSpec(
        "Universal Base Characters[Standard]",
        "quaternius_universal_characters_standard",
        "https://quaternius.com/packs/universalbasecharacters.html",
        "CC0-1.0",
        "License_Standard.txt",
        "stylized_rigged",
        (
            "Base Characters/Godot - UE/*.gltf",
            "Hairstyles/Rigged to Head Bone/glTF (Godot -Unreal)/*.gltf",
        ),
        0.82,
    ),
)


@dataclass(frozen=True)
class CuratedAsset:
    record: AssetRecord
    source_path: str
    cache_path: str
    converted: bool


class IncomingAssetCurator:
    """Canonicalize supported incoming packs and populate an AssetRegistry."""

    def __init__(
        self,
        registry: AssetRegistry,
        *,
        incoming_root: str | Path,
        cache_root: str | Path,
        source_catalog: ExternalAssetSourceCatalog | None = None,
    ) -> None:
        self.registry = registry
        self.incoming_root = Path(incoming_root)
        self.cache_root = Path(cache_root)
        self.source_catalog = source_catalog or ExternalAssetSourceCatalog()

    def curate(self, manifest_path: str | Path, *, limit: int | None = None) -> dict[str, Any]:
        if not self.incoming_root.is_dir():
            raise ValueError(f"Incoming asset directory does not exist: {self.incoming_root}")
        if limit is not None and limit <= 0:
            raise ValueError("limit must be positive")
        self.cache_root.mkdir(parents=True, exist_ok=True)
        curated: list[CuratedAsset] = []
        packages: list[dict[str, Any]] = []
        remaining = limit
        for spec in _PACKS:
            package_root = self.incoming_root / spec.directory
            if not package_root.is_dir():
                packages.append({"source_id": spec.source_id, "status": "not_downloaded", "count": 0})
                continue
            paths = sorted(
                {
                    path
                    for pattern in spec.globs
                    for path in package_root.glob(pattern)
                    if path.is_file()
                },
                key=lambda path: path.as_posix().lower(),
            )
            if remaining is not None:
                paths = paths[:remaining]
            package_assets = [self._curate_one(path, package_root, spec) for path in paths]
            curated.extend(package_assets)
            packages.append(
                {
                    "source_id": spec.source_id,
                    "directory": spec.directory,
                    "status": "processed",
                    "count": len(package_assets),
                    "license_id": spec.license_id,
                    "license_file": str(package_root / spec.license_file),
                    "source_url": spec.source_url,
                }
            )
            if remaining is not None:
                remaining -= len(package_assets)
                if remaining <= 0:
                    break

        processed_sources = {
            item["source_id"] for item in packages if item.get("status") == "processed"
        }
        stale_ids = [
            record.asset_id
            for record in self.registry.list_all()
            if record.metadata.get("external_content")
            and record.source in processed_sources
        ]
        removed_record_count = self.registry.remove_many(stale_ids)
        self.registry.register_many((item.record for item in curated), overwrite=True)
        referenced_cache = {Path(item.cache_path).resolve() for item in curated}
        pruned_cache_count = 0
        for source_id in processed_sources:
            source_cache = self.cache_root / source_id
            if not source_cache.is_dir():
                continue
            for cached in source_cache.glob("*.glb"):
                if cached.resolve() not in referenced_cache:
                    cached.unlink()
                    pruned_cache_count += 1
        category_counts: dict[str, int] = {}
        for item in curated:
            category_counts[item.record.category] = category_counts.get(item.record.category, 0) + 1
        payload = {
            "schema_version": "cityg.incoming_asset_curation.v1",
            "incoming_root": str(self.incoming_root.resolve()),
            "cache_root": str(self.cache_root.resolve()),
            "asset_count": len(curated),
            "converted_gltf_count": sum(item.converted for item in curated),
            "replaced_registry_record_count": removed_record_count,
            "pruned_derived_cache_count": pruned_cache_count,
            "category_counts": dict(sorted(category_counts.items())),
            "packages": packages,
            "assets": [
                {
                    "asset_id": item.record.asset_id,
                    "category": item.record.category,
                    "dimensions_m": list(item.record.dimensions_m or ()),
                    "source_path": item.source_path,
                    "cache_path": item.cache_path,
                    "converted": item.converted,
                    "tags": list(item.record.tags),
                    "orientation": item.record.metadata.get("orientation"),
                    "technical": item.record.metadata.get("mesh_validation"),
                }
                for item in curated
            ],
            "external_sources": [source.to_dict() for source in self.source_catalog.sources],
        }
        destination = Path(manifest_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return payload

    def _curate_one(self, path: Path, package_root: Path, spec: _PackSpec) -> CuratedAsset:
        input_bytes = path.read_bytes()
        input_hash = hashlib.sha256(input_bytes).hexdigest()
        document, buffers = _read_gltf(path)
        raw_bounds = _document_bounds(document)
        classification = _classify(path.stem, spec.source_id, raw_bounds)
        cache_dir = self.cache_root / spec.source_id
        cache_dir.mkdir(parents=True, exist_ok=True)
        slug = _slug(path.stem)
        asset_id = f"external_{spec.source_id}_{slug}_{input_hash[:10]}"
        cache_path = cache_dir / f"{slug}_{input_hash[:10]}.glb"
        canonical_document = _canonicalize_document(
            document,
            raw_bounds,
            asset_id=asset_id,
            source_up_axis="+Y",
            source_forward_axis=classification["source_forward_axis"],
        )
        output_bytes = _write_glb(canonical_document, buffers, path.parent)
        if not cache_path.is_file() or cache_path.read_bytes() != output_bytes:
            cache_path.write_bytes(output_bytes)
        geometry_path = _registry_relative(self.registry, cache_path)
        source_relative = str(path.relative_to(self.incoming_root))
        license_path = package_root / spec.license_file
        document_metrics = _document_metrics(document, raw_bounds)
        tags = tuple(
            dict.fromkeys(
                (
                    *classification["tags"],
                    spec.source_id,
                    spec.style,
                    "curated",
                    "external",
                    "download_required",
                )
            )
        )
        record = AssetRecord(
            asset_id=asset_id,
            category=classification["category"],
            tags=tags,
            dimensions_m=classification["dimensions_m"],
            geometry_path=geometry_path,
            source=spec.source_id,
            license_id=spec.license_id,
            quality_score=spec.quality_score,
            metadata={
                "external_content": True,
                "redistribution_policy": "download_required",
                "source_url": spec.source_url,
                "source_pack": spec.source_id,
                "source_relative_path": source_relative,
                "source_license_path": str(license_path.relative_to(self.incoming_root)),
                "input_sha256": input_hash,
                "output_sha256": hashlib.sha256(output_bytes).hexdigest(),
                "style": spec.style,
                "semantic_class": classification["semantic_class"],
                "subtype": classification["subtype"],
                "placement_rules": classification["placement_rules"],
                "orientation": {
                    "source_coordinate_system": "right_handed_y_up_gltf",
                    "source_up_axis": "+Y",
                    "source_forward_axis": classification["source_forward_axis"],
                    "canonical_coordinate_system": "right_handed_z_up_unit_bounds",
                    "canonical_up_axis": "+Z",
                    "canonical_forward_axis": "+X",
                    "pivot": "bounds_center",
                    "orientation_confidence": classification["orientation_confidence"],
                },
                "conversion": {
                    "input_format": path.suffix.lower().lstrip("."),
                    "output_format": "glb",
                    "embedded_external_buffers_and_textures": True,
                    "canonicalized": True,
                },
                "mesh_validation": document_metrics,
            },
        )
        return CuratedAsset(record, source_relative, str(cache_path), path.suffix.lower() == ".gltf")


def _registry_relative(registry: AssetRegistry, path: Path) -> str:
    resolved = path.resolve()
    if registry.manifest_path is not None:
        try:
            return str(resolved.relative_to(registry.manifest_path.parent.resolve()))
        except ValueError:
            pass
    return str(resolved)


def _tokens(value: str) -> list[str]:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return [item for item in re.findall(r"[a-z0-9]+", value.lower()) if item]


def _slug(value: str) -> str:
    result = "_".join(_tokens(value))
    return result[:80] or "asset"


def _classify(name: str, source_id: str, bounds: dict[str, list[float]]) -> dict[str, Any]:
    words = set(_tokens(name))
    joined = "_".join(_tokens(name))
    category = "outdoor_prop"
    semantic = "outdoor_prop"
    subtype = joined
    dimensions = _plausible_dimensions(bounds)
    placement = {"allowed_contexts": ["outdoor_public_space"], "orientation": "free"}
    source_forward_axis = "+Z"
    orientation_confidence = "medium"
    tags: list[str] = list(_tokens(name))

    if "quaternius_universal_characters" in source_id:
        if {"fullbody", "male", "female"} & words and "hair" not in words and "eyebrows" not in words:
            # Keep rigged source characters out of static street placement
            # until a pose/animation baking stage produces usable snapshots.
            category, semantic, subtype = "person_rigged_source", "pedestrian", "base_character"
            dimensions = (0.68, 0.48, 1.78)
            placement = {"allowed_contexts": ["sidewalk", "plaza", "park", "interior"], "orientation": "walking_direction"}
        else:
            category, semantic, subtype = "person_accessory", "character_accessory", "hair_or_eyebrows"
            dimensions = (0.32, 0.28, 0.24)
            placement = {"allowed_contexts": ["character_attachment"], "orientation": "head_bone"}
        tags.extend(("rigged", "humanoid"))
    elif "kenney_car" in source_id:
        if words & {"sedan", "suv", "van", "ambulance", "firetruck", "taxi", "police", "truck", "tractor", "hatchback", "race", "kart", "delivery", "garbage"}:
            category, semantic = "vehicle", "vehicle"
            subtype, dimensions = _vehicle_subtype_dimensions(words)
            placement = {"allowed_contexts": ["road_lane", "parking_lot", "service_area"], "orientation": "parallel_to_lane"}
            orientation_confidence = "medium"
        elif words & {"wheel", "debris", "bumper", "drivetrain", "bolt", "nut", "plate", "spoiler"}:
            category, semantic, subtype = "vehicle_part", "vehicle_part", "vehicle_debris"
            dimensions = (0.8, 0.8, 0.45)
        elif "cone" in words:
            category, semantic, subtype = "construction_prop", "traffic_cone", "traffic_cone"
            dimensions = (0.45, 0.45, 0.75)
    elif "kenney_retro_urban" in source_id and words & {"light", "lamp"}:
        category, semantic, subtype = "street_light", "street_light", "urban_detail_light"
        dimensions = (0.55, 0.55, 5.2)
        placement = {
            "allowed_contexts": ["sidewalk", "median", "plaza", "park"],
            "orientation": "parallel_to_road",
        }
        tags.extend(("street_furniture", "pedestrian_scale"))
        orientation_confidence = "high"
    elif "city_roads" in source_id:
        if "light" in words:
            category, semantic, subtype = "street_light", "street_light", joined
            dimensions = (0.55, 0.55, 6.4)
            placement = {"allowed_contexts": ["sidewalk", "median", "plaza"], "orientation": "parallel_to_road"}
        elif "sign" in words:
            category, semantic, subtype = "traffic_sign", "traffic_sign", joined
            dimensions = (2.6, 0.5, 4.8)
            placement = {"allowed_contexts": ["roadside", "median"], "orientation": "faces_traffic"}
        elif "construction" in words:
            category, semantic, subtype = "construction_prop", "construction_prop", joined
            dimensions = (1.5, 0.5, 1.0)
        elif "pillar" in words or "bridge" in words:
            category, semantic, subtype = "bridge_module", "bridge_module", joined
            placement = {"allowed_contexts": ["road_bridge"], "orientation": "road_axis"}
        else:
            category, semantic, subtype = "road_module", "road_module", joined
            placement = {"allowed_contexts": ["road_network"], "orientation": "road_axis"}
    elif "opengameart_lamp_bench_trashcan" in source_id:
        # This download is a deliberately bundled street vignette rather than
        # a single prop. Keep it searchable for manual composition, but do not
        # let bench/bin resolvers place the whole bundle as one object.
        category, semantic, subtype = "streetscape_bundle", "streetscape_bundle", "lamp_bench_trashcan"
        placement = {
            "allowed_contexts": ["manual_vignette", "showcase"],
            "orientation": "free",
        }
        tags.extend(("street_furniture", "bundle", "manual_only"))
        orientation_confidence = "medium"
    else:
        if "bench" in words:
            category, semantic, subtype = "street_bench", "street_furniture", "bench"
            dimensions = (1.8, 0.62, 0.92)
            placement = {
                "allowed_contexts": ["sidewalk", "park", "plaza", "building_setback"],
                "orientation": "faces_walkway",
            }
            tags.extend(("seating", "pedestrian_scale"))
            orientation_confidence = "high"
        elif words & {"planter", "flowerbox", "flower_box"}:
            category, semantic, subtype = "street_planter", "landscape_container", "planter"
            dimensions = _vegetation_dimensions(bounds, minimum=(0.7, 0.45, 0.35), maximum=(3.0, 1.5, 1.4))
            placement = {
                "allowed_contexts": ["sidewalk", "park", "plaza", "building_setback"],
                "orientation": "parallel_to_walkway",
            }
            tags.extend(("flower_box", "low_planting"))
            orientation_confidence = "high"
        elif words & {"dumpster", "trashcan", "trash", "waste", "garbage", "bin"}:
            category, semantic, subtype = "street_bin", "waste_container", "public_bin"
            dimensions = (0.7, 0.7, 1.1)
            placement = {
                "allowed_contexts": ["sidewalk", "park", "plaza", "service_area"],
                "orientation": "faces_walkway",
            }
            tags.extend(("waste", "street_furniture"))
            orientation_confidence = "medium"
        elif "sign" in words or "wayfinding" in words:
            category, semantic, subtype = "small_sign", "wayfinding_sign", "small_wayfinding"
            dimensions = (0.55, 0.12, 1.65)
            placement = {
                "allowed_contexts": ["sidewalk", "park", "plaza", "building_setback"],
                "orientation": "faces_walkway",
            }
            tags.extend(("wayfinding", "pedestrian_scale", "street_furniture"))
            orientation_confidence = "medium"
        elif "tree" in words or words & {"pine", "fir", "sapling"}:
            if "shrub" in words:
                category, semantic, subtype = "shrub", "landscape_shrub", "ornamental"
                dimensions = _vegetation_dimensions(bounds, minimum=(0.8, 0.8, 0.6), maximum=(2.4, 2.4, 1.8))
                placement = {"allowed_contexts": ["park", "plaza", "building_setback", "median"], "orientation": "free"}
                tags.extend(("hedge", "low_planting"))
            elif "dead" in words:
                category, semantic, subtype = "park_tree", "park_tree", "dead_tree"
            elif "palm" in words:
                category, semantic, subtype = "park_tree", "park_tree", "palm_tree"
                tags.extend(("tropical", "ornamental"))
            elif words & {"twisted", "quiver"}:
                category, semantic, subtype = "park_tree", "park_tree", "ornamental_tree"
            else:
                category, semantic, subtype = (
                    "street_tree",
                    "street_tree",
                    "conifer" if words & {"pine", "fir"} else "deciduous",
                )
                if subtype == "deciduous":
                    tags.append("broadleaf")
                if "small" in words and "polyhaven" in source_id:
                    tags.extend(("ornamental", "small_canopy"))
            dimensions = _vegetation_dimensions(bounds, minimum=(3.2, 3.2, 5.2), maximum=(8.0, 8.0, 11.0))
            placement = {"allowed_contexts": ["sidewalk_tree_pit", "park", "plaza"], "orientation": "free"}
            orientation_confidence = "high"
        elif words & {"bush", "shrub", "searsia"}:
            category, semantic, subtype = "shrub", "landscape_shrub", "flowering" if "flowers" in words else "ornamental"
            dimensions = _vegetation_dimensions(bounds, minimum=(0.8, 0.8, 0.6), maximum=(2.4, 2.4, 1.8))
            placement = {"allowed_contexts": ["park", "plaza", "building_setback", "median"], "orientation": "free"}
        elif "street" in words and words & {"lamp", "light", "lamppost"}:
            category, semantic, subtype = "street_light", "street_light", "heritage"
            dimensions = (0.8, 0.8, 4.2)
            placement = {
                "allowed_contexts": ["sidewalk", "park", "plaza"],
                "orientation": "faces_walkway",
            }
            tags.extend(("heritage", "pedestrian_scale", "ornamental"))
            orientation_confidence = "high"
        elif words & {"flower", "clover", "fern", "plant", "grass", "petal", "mushroom"}:
            category, semantic, subtype = "plant", "landscape_plant", next(iter(sorted(words & {"flower", "clover", "fern", "plant", "grass", "petal", "mushroom"})))
            dimensions = _vegetation_dimensions(bounds, minimum=(0.25, 0.25, 0.12), maximum=(1.6, 1.6, 1.4))
            placement = {"allowed_contexts": ["park", "planter", "garden", "building_setback"], "orientation": "free"}
        elif words & {"rock", "pebble", "cliff", "stone"} or "rock" in joined or "cliff" in joined:
            category, semantic, subtype = "rock", "landscape_rock", "cliff" if "cliff" in joined else "rock"
            dimensions = _vegetation_dimensions(bounds, minimum=(0.35, 0.35, 0.2), maximum=(8.0, 8.0, 5.0))
            placement = {"allowed_contexts": ["park", "landscape", "waterfront"], "orientation": "free"}
        elif "bridge" in joined:
            category, semantic, subtype = "bridge_module", "pedestrian_bridge", joined
            placement = {"allowed_contexts": ["park_path", "waterfront"], "orientation": "path_axis"}

    tags.extend((category, semantic, subtype))
    return {
        "category": category,
        "semantic_class": semantic,
        "subtype": subtype,
        "dimensions_m": tuple(round(max(0.01, float(item)), 4) for item in dimensions),
        "placement_rules": placement,
        "source_forward_axis": source_forward_axis,
        "orientation_confidence": orientation_confidence,
        "tags": tuple(dict.fromkeys(tags)),
    }


def _vehicle_subtype_dimensions(words: set[str]) -> tuple[str, tuple[float, float, float]]:
    if "firetruck" in words:
        return "fire_truck", (8.6, 2.55, 3.25)
    if "garbage" in words:
        return "garbage_truck", (8.2, 2.5, 3.1)
    if "ambulance" in words:
        return "ambulance", (5.8, 2.15, 2.65)
    if "delivery" in words or "van" in words:
        return "delivery_van", (5.25, 2.05, 2.35)
    if "truck" in words:
        return "truck", (6.2, 2.35, 2.65)
    if "tractor" in words:
        return "tractor", (4.2, 2.25, 2.55)
    if "suv" in words:
        return "suv", (4.75, 1.95, 1.72)
    if "taxi" in words:
        return "taxi", (4.55, 1.82, 1.48)
    if "police" in words:
        return "police_car", (4.65, 1.88, 1.58)
    if "hatchback" in words:
        return "hatchback", (4.25, 1.78, 1.5)
    if "kart" in words:
        return "kart", (2.0, 1.3, 0.8)
    if "race" in words:
        return "race_car", (4.6, 1.95, 1.25)
    return "sedan", (4.55, 1.82, 1.48)


def _plausible_dimensions(bounds: dict[str, list[float]]) -> tuple[float, float, float]:
    extent = bounds["extent"]
    # glTF is Y-up; CityG canonical order is forward/length, width, height.
    dims = (extent[2], extent[0], extent[1])
    if min(dims) <= 0 or max(dims) > 100:
        return (1.0, 1.0, 1.0)
    return tuple(float(item) for item in dims)


def _vegetation_dimensions(
    bounds: dict[str, list[float]],
    *,
    minimum: tuple[float, float, float],
    maximum: tuple[float, float, float],
) -> tuple[float, float, float]:
    raw = _plausible_dimensions(bounds)
    return tuple(min(max(raw[index], minimum[index]), maximum[index]) for index in range(3))


def _read_gltf(path: Path) -> tuple[dict[str, Any], list[bytes]]:
    if path.suffix.lower() == ".gltf":
        document = json.loads(path.read_text(encoding="utf-8"))
        return document, [_read_uri(path.parent, item.get("uri")) for item in document.get("buffers", [])]
    data = path.read_bytes()
    if len(data) < 20 or data[:4] != b"glTF":
        raise ValueError(f"Invalid GLB header: {path}")
    _magic, version, total_length = struct.unpack_from("<4sII", data, 0)
    if version != 2 or total_length != len(data):
        raise ValueError(f"Unsupported or truncated GLB: {path}")
    offset = 12
    document: dict[str, Any] | None = None
    binary_chunks: list[bytes] = []
    while offset + 8 <= len(data):
        length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        chunk = data[offset : offset + length]
        offset += length
        if chunk_type == _JSON_CHUNK:
            document = json.loads(chunk.rstrip(b" \t\r\n\0").decode("utf-8"))
        elif chunk_type == _BIN_CHUNK:
            binary_chunks.append(chunk)
    if document is None:
        raise ValueError(f"GLB has no JSON chunk: {path}")
    buffers: list[bytes] = []
    embedded_index = 0
    for item in document.get("buffers", []):
        uri = item.get("uri")
        if uri:
            buffers.append(_read_uri(path.parent, uri))
        else:
            if embedded_index >= len(binary_chunks):
                raise ValueError(f"GLB buffer is missing: {path}")
            buffers.append(binary_chunks[embedded_index][: int(item.get("byteLength", len(binary_chunks[embedded_index])) )])
            embedded_index += 1
    return document, buffers


def _read_uri(parent: Path, uri: str | None) -> bytes:
    if not uri:
        return b""
    if uri.startswith("data:"):
        header, encoded = uri.split(",", 1)
        return base64.b64decode(encoded) if ";base64" in header else encoded.encode("utf-8")
    return _resolve_resource(parent, uri).read_bytes()


def _resolve_resource(parent: Path, uri: str) -> Path:
    """Resolve small naming mistakes present in some downloaded glTF packs."""

    names = [uri]
    if "_png.png" in uri:
        names.append(uri.replace("_png.png", ".png"))
    for name in names:
        direct = parent / name
        if direct.is_file():
            return direct
    for ancestor in (parent, *tuple(parent.parents)[:3]):
        for directory in (ancestor / "Textures", ancestor / "Textures" / "Normals Unity - Godot"):
            for name in names:
                candidate = directory / Path(name).name
                if candidate.is_file():
                    return candidate
    raise FileNotFoundError(parent / uri)


def _document_bounds(document: dict[str, Any]) -> dict[str, list[float]]:
    lows: list[list[float]] = []
    highs: list[list[float]] = []
    accessors = document.get("accessors", [])
    for mesh in document.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            accessor_index = primitive.get("attributes", {}).get("POSITION")
            if accessor_index is None or accessor_index >= len(accessors):
                continue
            accessor = accessors[accessor_index]
            if len(accessor.get("min", [])) >= 3 and len(accessor.get("max", [])) >= 3:
                lows.append([float(item) for item in accessor["min"][:3]])
                highs.append([float(item) for item in accessor["max"][:3]])
    if not lows:
        return {"min": [-0.5, -0.5, -0.5], "max": [0.5, 0.5, 0.5], "extent": [1.0, 1.0, 1.0]}
    low = [min(item[index] for item in lows) for index in range(3)]
    high = [max(item[index] for item in highs) for index in range(3)]
    extent = [max(1e-6, high[index] - low[index]) for index in range(3)]
    return {"min": low, "max": high, "extent": extent}


def _document_metrics(document: dict[str, Any], bounds: dict[str, list[float]]) -> dict[str, Any]:
    triangle_count = 0
    accessors = document.get("accessors", [])
    for mesh in document.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            accessor_index = primitive.get("indices")
            if accessor_index is not None and accessor_index < len(accessors):
                triangle_count += int(accessors[accessor_index].get("count", 0)) // 3
            else:
                position_index = primitive.get("attributes", {}).get("POSITION")
                if position_index is not None and position_index < len(accessors):
                    triangle_count += int(accessors[position_index].get("count", 0)) // 3
    return {
        "mesh_count": len(document.get("meshes", [])),
        "node_count": len(document.get("nodes", [])),
        "material_count": len(document.get("materials", [])),
        "texture_count": len(document.get("textures", [])),
        "skin_count": len(document.get("skins", [])),
        "animation_count": len(document.get("animations", [])),
        "triangle_count": triangle_count,
        "raw_bounds": bounds,
        "glb_validated": True,
    }


def _canonicalize_document(
    document: dict[str, Any],
    bounds: dict[str, list[float]],
    *,
    asset_id: str,
    source_up_axis: str,
    source_forward_axis: str,
) -> dict[str, Any]:
    result = json.loads(json.dumps(document))
    low, high, extent = bounds["min"], bounds["max"], bounds["extent"]
    center = [(low[index] + high[index]) / 2.0 for index in range(3)]
    ex, ey, ez = extent
    # glTF source: X right, Y up, Z forward. CityG canonical unit bounds:
    # X forward, Y width/right, Z up. Matrices in glTF are column-major.
    matrix = [
        0.0, 1.0 / ex, 0.0, 0.0,
        0.0, 0.0, 1.0 / ey, 0.0,
        1.0 / ez, 0.0, 0.0, 0.0,
        -center[2] / ez, -center[0] / ex, -center[1] / ey, 1.0,
    ]
    nodes = result.setdefault("nodes", [])
    scenes = result.setdefault("scenes", [{"nodes": list(range(len(nodes)))}])
    for index, scene in enumerate(scenes):
        original = list(scene.get("nodes", []))
        root_index = len(nodes)
        nodes.append(
            {
                "name": f"CityGCanonicalRoot_{index}",
                "matrix": matrix,
                "children": original,
                "extras": {
                    "cityg_asset_id": asset_id,
                    "source_up_axis": source_up_axis,
                    "source_forward_axis": source_forward_axis,
                    "canonical_up_axis": "+Z",
                    "canonical_forward_axis": "+X",
                },
            }
        )
        scene["nodes"] = [root_index]
    result.setdefault("asset", {}).setdefault("extras", {}).update(
        {
            "cityg_canonicalized": True,
            "cityg_coordinate_system": "right_handed_z_up_unit_bounds",
            "cityg_asset_id": asset_id,
        }
    )
    return result


def _write_glb(document: dict[str, Any], buffers: list[bytes], resource_dir: Path) -> bytes:
    result = json.loads(json.dumps(document))
    binary = bytearray()
    buffer_offsets: list[int] = []
    for payload in buffers:
        while len(binary) % 4:
            binary.append(0)
        buffer_offsets.append(len(binary))
        binary.extend(payload)
    for view in result.get("bufferViews", []):
        old_buffer = int(view.get("buffer", 0))
        if old_buffer >= len(buffer_offsets):
            raise ValueError(f"bufferView references missing buffer {old_buffer}")
        view["byteOffset"] = buffer_offsets[old_buffer] + int(view.get("byteOffset", 0))
        view["buffer"] = 0

    for image in result.get("images", []):
        uri = image.get("uri")
        if not uri:
            continue
        if uri.startswith("data:"):
            header, encoded = uri.split(",", 1)
            payload = base64.b64decode(encoded) if ";base64" in header else encoded.encode("utf-8")
            mime_type = header[5:].split(";", 1)[0] or "application/octet-stream"
        else:
            payload = _resolve_resource(resource_dir, uri).read_bytes()
            mime_type = mimetypes.guess_type(uri)[0] or "application/octet-stream"
        while len(binary) % 4:
            binary.append(0)
        offset = len(binary)
        binary.extend(payload)
        result.setdefault("bufferViews", []).append(
            {"buffer": 0, "byteOffset": offset, "byteLength": len(payload)}
        )
        image.pop("uri", None)
        image["bufferView"] = len(result["bufferViews"]) - 1
        image["mimeType"] = mime_type

    while len(binary) % 4:
        binary.append(0)
    result["buffers"] = [{"byteLength": len(binary)}]
    json_bytes = json.dumps(result, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    while len(json_bytes) % 4:
        json_bytes += b" "
    total = 12 + 8 + len(json_bytes) + 8 + len(binary)
    return b"".join(
        (
            struct.pack("<4sII", b"glTF", 2, total),
            struct.pack("<II", len(json_bytes), _JSON_CHUNK),
            json_bytes,
            struct.pack("<II", len(binary), _BIN_CHUNK),
            bytes(binary),
        )
    )


__all__ = [
    "ExternalAssetSource",
    "ExternalAssetSourceCatalog",
    "IncomingAssetCurator",
    "default_external_sources",
]
