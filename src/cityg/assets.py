"""Local-first asset and material registries.

The registries are deliberately dependency-free.  They do not download or run a
3D model by themselves; providers can populate them during an offline curation
step, while the city compiler can safely fall back to procedural geometry when
an optional asset is unavailable.
"""

from __future__ import annotations

import json
import hashlib
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Protocol
from cityg.progress import progress


def _tokens(value: str | Iterable[str]) -> set[str]:
    if isinstance(value, str):
        values = [value]
    else:
        values = list(value)
    return {
        token
        for value in values
        for token in re.findall(r"[a-z0-9]+", str(value).lower())
        if token
    }


_VALID_ENVIRONMENTS = frozenset({"indoor", "outdoor", "both"})

_INDOOR_CATEGORY_ROOM_TYPES: dict[str, tuple[str, ...]] = {
    "bed": ("bedroom",),
    "bedside_table": ("bedroom",),
    "wardrobe": ("bedroom",),
    "sofa": ("living_room", "reception", "waiting_room"),
    "coffee_table": ("living_room", "reception", "waiting_room"),
    "tv_console": ("living_room",),
    "desk": ("office", "open_office", "study", "control_room"),
    "office_chair": ("office", "open_office", "study", "control_room", "reception"),
    "cabinet": ("office", "open_office", "study", "storage", "service_room"),
    "meeting_table": ("meeting_room",),
    "meeting_chair": ("meeting_room",),
    "bookcase": ("study", "office", "living_room"),
    "kitchen_counter": ("kitchen", "break_room"),
    "dining_table": ("kitchen", "break_room", "living_room"),
    "dining_chair": ("kitchen", "break_room", "living_room"),
    "toilet": ("bathroom", "restroom"),
    "sink": ("bathroom", "restroom", "kitchen"),
    "refrigerator": ("kitchen", "break_room"),
    "oven": ("kitchen",),
    "shower": ("bathroom",),
    "reception_desk": ("reception", "service_hall"),
    "waiting_bench": ("reception", "waiting_room", "service_hall"),
    "checkout_counter": ("shop",),
    "display_shelf": ("shop",),
    "storage_rack": ("storage", "service_room", "utility_room", "workshop"),
    "workbench": ("workshop",),
    "machine_tool": ("workshop",),
    "control_console": ("control_room", "equipment_room"),
    "equipment_cabinet": ("equipment_room", "service_room", "utility_room"),
}

_OUTDOOR_CATEGORIES = frozenset(
    {
        "street_tree", "park_tree", "tree", "shrub", "vegetation", "vehicle",
        "person", "street_light", "street_bench", "street_bin", "street_planter",
        "bollard", "bicycle_rack", "fire_hydrant", "bus_shelter", "traffic_signal",
        "playground", "outdoor_furniture", "metro_entrance",
    }
)


def infer_asset_environment(
    category: str,
    tags: Iterable[str] = (),
    metadata: dict[str, Any] | None = None,
) -> str:
    """Infer a conservative use environment for legacy registry records."""

    normalized = category.strip().lower()
    tag_tokens = _tokens(tags)
    meta = metadata or {}
    if normalized in _OUTDOOR_CATEGORIES or {
        "outdoor", "street", "roadside", "park", "landscape"
    } & tag_tokens or meta.get("outdoor_slot"):
        return "outdoor"
    if normalized in _INDOOR_CATEGORY_ROOM_TYPES or {
        "indoor", "interior", "furniture"
    } & tag_tokens:
        return "indoor"
    return "both"


def infer_asset_room_types(category: str) -> tuple[str, ...]:
    """Return compatible room functions when a legacy record lacks labels."""

    return _INDOOR_CATEGORY_ROOM_TYPES.get(category.strip().lower(), ())


@dataclass(frozen=True)
class AssetRecord:
    """A normalized, reusable visual/simulation asset."""

    asset_id: str
    category: str
    tags: tuple[str, ...] = ()
    dimensions_m: tuple[float, float, float] | None = None
    geometry_path: str | None = None
    collision_path: str | None = None
    preview_path: str | None = None
    material_id: str | None = None
    source: str = "procedural"
    license_id: str = "internal"
    quality_score: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    environment: str = "auto"
    room_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.asset_id.strip():
            raise ValueError("asset_id must not be empty")
        if not self.category.strip():
            raise ValueError("category must not be empty")
        if self.environment == "auto":
            object.__setattr__(
                self,
                "environment",
                infer_asset_environment(self.category, self.tags, self.metadata),
            )
        if not self.room_types:
            object.__setattr__(self, "room_types", infer_asset_room_types(self.category))
        if self.environment not in _VALID_ENVIRONMENTS:
            raise ValueError("environment must be indoor, outdoor, or both")
        if any(not item.strip() for item in self.room_types):
            raise ValueError("room_types must not contain empty values")
        if self.dimensions_m is not None:
            if len(self.dimensions_m) != 3 or any(value <= 0 for value in self.dimensions_m):
                raise ValueError("dimensions_m must contain three positive values")
        if not 0.0 <= self.quality_score <= 1.0:
            raise ValueError("quality_score must be within [0, 1]")

    @property
    def has_geometry(self) -> bool:
        return bool(self.geometry_path)

    def supports(self, *, environment: str | None = None, room_type: str | None = None) -> bool:
        """Whether this asset is admissible in the requested semantic context."""

        if environment and environment not in _VALID_ENVIRONMENTS:
            raise ValueError("environment must be indoor, outdoor, or both")
        if environment and environment != "both" and self.environment not in {environment, "both"}:
            return False
        if room_type and self.room_types and room_type not in self.room_types:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "category": self.category,
            "tags": list(self.tags),
            "environment": self.environment,
            "room_types": list(self.room_types),
            "dimensions_m": list(self.dimensions_m) if self.dimensions_m else None,
            "geometry_path": self.geometry_path,
            "collision_path": self.collision_path,
            "preview_path": self.preview_path,
            "material_id": self.material_id,
            "source": self.source,
            "license_id": self.license_id,
            "quality_score": self.quality_score,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetRecord":
        dimensions = data.get("dimensions_m")
        category = str(data["category"])
        tags = tuple(str(item) for item in data.get("tags", ()))
        metadata = dict(data.get("metadata", {}))
        return cls(
            asset_id=str(data["asset_id"]),
            category=category,
            tags=tags,
            environment=str(
                data.get("environment")
                or infer_asset_environment(category, tags, metadata)
            ),
            room_types=tuple(
                str(item)
                for item in data.get("room_types", infer_asset_room_types(category))
            ),
            dimensions_m=tuple(float(item) for item in dimensions) if dimensions else None,
            geometry_path=data.get("geometry_path"),
            collision_path=data.get("collision_path"),
            preview_path=data.get("preview_path"),
            material_id=data.get("material_id"),
            source=str(data.get("source", "unknown")),
            license_id=str(data.get("license_id", "unknown")),
            quality_score=float(data.get("quality_score", 1.0)),
            metadata=metadata,
        )


class AssetRegistry:
    """Persistent local registry with deterministic token-based retrieval."""

    def __init__(self, manifest_path: str | Path | None = None) -> None:
        self.manifest_path = Path(manifest_path) if manifest_path else None
        self._records: dict[str, AssetRecord] = {}
        if self.manifest_path and self.manifest_path.is_file():
            self.load(self.manifest_path)

    def register(self, record: AssetRecord, *, overwrite: bool = False) -> AssetRecord:
        if record.asset_id in self._records and not overwrite:
            existing = self._records[record.asset_id]
            if existing != record:
                raise ValueError(f"Asset already registered: {record.asset_id}")
            return existing
        self._records[record.asset_id] = record
        self._autosave()
        return record

    def register_many(self, records: Iterable[AssetRecord], *, overwrite: bool = False) -> None:
        # Avoid rewriting a large registry after every record during bulk asset
        # curation. Preserve the public autosave behaviour and commit once.
        destination = self.manifest_path
        self.manifest_path = None
        try:
            for record in records:
                self.register(record, overwrite=overwrite)
        finally:
            self.manifest_path = destination
        if destination is not None:
            self.save(destination)

    def remove_many(self, asset_ids: Iterable[str]) -> int:
        """Remove a bounded set of records and persist the registry once."""

        removed = 0
        for asset_id in set(asset_ids):
            if self._records.pop(asset_id, None) is not None:
                removed += 1
        if removed and self.manifest_path is not None:
            self.save(self.manifest_path)
        return removed

    def get(self, asset_id: str) -> AssetRecord | None:
        return self._records.get(asset_id)

    def require(self, asset_id: str) -> AssetRecord:
        record = self.get(asset_id)
        if record is None:
            raise KeyError(f"Asset not found: {asset_id}")
        return record

    def resolve_path(self, value: str | Path) -> Path:
        """Resolve a registry-relative path against the manifest directory."""
        path = Path(value)
        if path.is_absolute() or self.manifest_path is None:
            return path
        return self.manifest_path.parent / path

    def list_all(self) -> list[AssetRecord]:
        return [self._records[key] for key in sorted(self._records)]

    def search(
        self,
        query: str | Iterable[str],
        *,
        category: str | None = None,
        limit: int = 5,
        require_geometry: bool = False,
        required_tokens: Iterable[str] = (),
        environment: str | None = None,
        room_type: str | None = None,
    ) -> list[tuple[AssetRecord, float]]:
        """Return deterministic lexical candidates until an embedding index exists."""
        if limit <= 0:
            return []
        wanted = _tokens(query)
        required = _tokens(required_tokens)
        category_tokens = _tokens(category) if category else set()
        ranked: list[tuple[float, AssetRecord]] = []
        for record in self._records.values():
            # Staging-only indoor downloads must never enter scene selection.
            # Legacy records without an explicit switch retain their behavior.
            if record.metadata.get("runtime_enabled") is False:
                continue
            if require_geometry and not record.has_geometry:
                continue
            # Filter semantics before probing external geometry on disk. Large
            # parcel passes repeat a few category queries thousands of times;
            # checking unrelated indoor GLBs dominates that otherwise cheap work.
            if category and record.category != category:
                continue
            if not record.supports(environment=environment, room_type=room_type):
                continue
            if (
                require_geometry
                and record.metadata.get("external_content")
                and record.geometry_path
                and not self.resolve_path(record.geometry_path).is_file()
            ):
                # External records may be distributed as metadata while users
                # download the actual pack locally. Missing files must fall
                # back cleanly instead of producing broken scene references.
                continue
            searchable = _tokens([record.asset_id, record.category, *record.tags])
            if required and not (required & searchable):
                continue
            overlap = len(wanted & searchable)
            category_overlap = len(category_tokens & _tokens(record.category))
            # Quality is only a tie-breaker; semantic overlap remains dominant.
            context_score = 0.0
            if environment and record.environment == environment:
                context_score += 0.2
            if room_type and room_type in record.room_types:
                context_score += 0.35
            score = overlap + 0.25 * category_overlap + context_score + 0.01 * record.quality_score
            if score > 0 or not wanted:
                ranked.append((score, record))
        ranked.sort(key=lambda item: (-item[0], item[1].asset_id))
        return [(record, round(score, 6)) for score, record in ranked[:limit]]

    def save(self, path: str | Path | None = None) -> Path:
        destination = Path(path) if path else self.manifest_path
        if destination is None:
            raise ValueError("A manifest path is required")
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "cityg.assets.v1",
            "assets": [record.to_dict() for record in self.list_all()],
        }
        destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.manifest_path = destination
        return destination

    def load(self, path: str | Path) -> None:
        source = Path(path)
        payload = json.loads(source.read_text(encoding="utf-8"))
        if payload.get("schema_version") not in {None, "cityg.assets.v1"}:
            raise ValueError(f"Unsupported asset registry schema: {payload.get('schema_version')}")
        self._records = {
            record.asset_id: record
            for record in (AssetRecord.from_dict(item) for item in payload.get("assets", []))
        }
        self.manifest_path = source

    def _autosave(self) -> None:
        if self.manifest_path:
            self.save(self.manifest_path)


def choose_asset_variant(
    candidates: Iterable[tuple[AssetRecord, float]],
    selection_key: str,
    *,
    semantic_window: float = 0.25,
    max_triangle_count: int | None = None,
    premium_probability: float = 0.58,
) -> AssetRecord | None:
    """Choose a deterministic, quality-aware visual variant.

    Lexical relevance remains a hard gate. Within that semantic window,
    photorealistic assets are sampled frequently but not exclusively, so a
    large scene exposes multiple curated models instead of repeating the first
    registry hit everywhere.
    """

    if not 0.0 <= premium_probability <= 1.0:
        raise ValueError("premium_probability must be within [0, 1]")
    # Exclude non-runtime records before finding the best relevance score.
    # A highly relevant rejected/manual asset must not crowd out ready ones.
    ranked = [item for item in candidates
              if item[0].metadata.get("runtime_enabled") is not False
              and item[0].metadata.get("outdoor_pack_status") not in {"rejected", "candidate"}
              and not item[0].metadata.get("manual_only") and "manual_only" not in item[0].tags]
    if not ranked:
        return None
    best_score = max(score for _record, score in ranked)
    viable = [
        record
        for record, score in ranked
        if score >= best_score - semantic_window
        and record.metadata.get("outdoor_pack_status") not in {"rejected", "candidate"}
        and (
            max_triangle_count is None
            or not isinstance(record.metadata.get("mesh_validation"), dict)
            or int(record.metadata["mesh_validation"].get("triangle_count", 0))
            <= max_triangle_count
        )
    ]
    if not viable:
        return None
    premium = [
        record
        for record in viable
        if record.quality_score >= 0.90
        or record.metadata.get("style") == "photorealistic_pbr"
    ]
    digest = hashlib.sha256(selection_key.encode("utf-8")).digest()
    roll = int.from_bytes(digest[:2], "big") % 100
    pool = premium if premium and roll < round(premium_probability * 100) else viable
    return pool[int.from_bytes(digest[2:6], "big") % len(pool)]


class AssetProvider(Protocol):
    """Optional acquisition backend used only after local registry lookup."""

    name: str

    def acquire(
        self,
        query: str,
        *,
        category: str | None = None,
        dimensions_m: tuple[float, float, float] | None = None,
    ) -> AssetRecord | None:
        ...


class AssetResolver:
    """Local-first resolver with pluggable generation/retrieval providers.

    Providers are intentionally passive objects.  The resolver never performs
    network access on its own; an application must explicitly install a provider
    that has been configured for that purpose.
    """

    def __init__(
        self,
        registry: AssetRegistry,
        providers: Iterable[AssetProvider] = (),
        *,
        max_provider_calls: int | None = None,
        strict_provider_errors: bool = True,
    ) -> None:
        if max_provider_calls is not None and max_provider_calls < 0:
            raise ValueError("max_provider_calls must be non-negative or None")
        self.registry = registry
        self.providers = tuple(providers)
        self.max_provider_calls = max_provider_calls
        self.strict_provider_errors = strict_provider_errors
        self._provider_calls = 0
        self._generated_assets = 0
        self._local_hits = 0
        self._budget_skips = 0
        self._negative_cache: set[
            tuple[str, str | None, tuple[float, float, float] | None, str | None, str | None]
        ] = set()
        self._failures: list[dict[str, str]] = []

    def resolve(
        self,
        query: str,
        *,
        category: str | None = None,
        dimensions_m: tuple[float, float, float] | None = None,
        provider_names: Iterable[str] | None = None,
        environment: str | None = None,
        room_type: str | None = None,
    ) -> AssetRecord | None:
        local = self.registry.search(
            query,
            category=category,
            limit=1,
            require_geometry=True,
            environment=environment,
            room_type=room_type,
        )
        if local:
            self._local_hits += 1
            return local[0][0]
        key = (query, category, dimensions_m, environment, room_type)
        if key in self._negative_cache:
            return None
        allowed = set(provider_names) if provider_names is not None else None
        for provider in self.providers:
            if allowed is not None and provider.name not in allowed:
                continue
            if (
                self.max_provider_calls is not None
                and self._provider_calls >= self.max_provider_calls
            ):
                self._budget_skips += 1
                self._negative_cache.add(key)
                return None
            self._provider_calls += 1
            progress('资产补全', '本地未命中，调用配置的资产 provider',
                     category=category, provider=provider.name, call=self._provider_calls)
            try:
                record = provider.acquire(
                    query,
                    category=category,
                    dimensions_m=dimensions_m,
                )
            except Exception as error:
                progress('资产补全', 'provider 失败；详情见资产日志', error_type=type(error).__name__)
                self._failures.append(
                    {
                        "provider": provider.name,
                        "category": category or "",
                        "error_type": type(error).__name__,
                        "message": str(error),
                    }
                )
                if self.strict_provider_errors:
                    raise
                continue
            if record is not None:
                # Generated assets inherit the bounded request context so later
                # retrieval cannot silently reuse indoor furniture outdoors (or
                # vice versa). Provider protocols remain intentionally simple.
                record = replace(
                    record,
                    environment=(environment or record.environment),
                    room_types=(
                        record.room_types
                        or ((room_type,) if room_type else ())
                    ),
                    tags=tuple(
                        dict.fromkeys(
                            (
                                *record.tags,
                                *((environment,) if environment else ()),
                                *((room_type,) if room_type else ()),
                            )
                        )
                    ),
                )
                self.registry.register(record, overwrite=True)
                self._generated_assets += 1
                progress('资产补全', '已入库', asset=record.asset_id)
                return record
        self._negative_cache.add(key)
        return None

    def stats(self) -> dict[str, Any]:
        """Return an auditable snapshot of local hits and bounded acquisitions."""
        return {
            "provider_names": [provider.name for provider in self.providers],
            "max_provider_calls": self.max_provider_calls,
            "provider_calls": self._provider_calls,
            "generated_assets": self._generated_assets,
            "local_hits": self._local_hits,
            "budget_skips": self._budget_skips,
            "negative_cache_entries": len(self._negative_cache),
            "failures": list(self._failures),
        }


@dataclass(frozen=True)
class MaterialRecord:
    """A PBR material with an explicit color fallback for lightweight viewers."""

    material_id: str
    display_color: tuple[float, float, float]
    roughness: float = 0.7
    metallic: float = 0.0
    opacity: float = 1.0
    base_color_path: str | None = None
    normal_path: str | None = None
    roughness_path: str | None = None
    ambient_occlusion_path: str | None = None
    source: str = "internal"
    license_id: str = "internal"
    texture_scale_m: float | None = None

    def __post_init__(self) -> None:
        if len(self.display_color) != 3 or any(not 0.0 <= value <= 1.0 for value in self.display_color):
            raise ValueError("display_color must contain three values within [0, 1]")
        if not 0.0 <= self.roughness <= 1.0 or not 0.0 <= self.metallic <= 1.0:
            raise ValueError("roughness and metallic must be within [0, 1]")
        if not 0.0 <= self.opacity <= 1.0:
            raise ValueError("opacity must be within [0, 1]")

    @property
    def has_pbr_textures(self) -> bool:
        return bool(
            self.base_color_path
            or self.normal_path
            or self.roughness_path
            or self.ambient_occlusion_path
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "material_id": self.material_id,
            "display_color": list(self.display_color),
            "roughness": self.roughness,
            "metallic": self.metallic,
            "opacity": self.opacity,
            "base_color_path": self.base_color_path,
            "normal_path": self.normal_path,
            "roughness_path": self.roughness_path,
            "ambient_occlusion_path": self.ambient_occlusion_path,
            "source": self.source,
            "license_id": self.license_id,
            "texture_scale_m": self.texture_scale_m,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MaterialRecord":
        return cls(
            material_id=str(data["material_id"]),
            display_color=tuple(float(item) for item in data["display_color"]),
            roughness=float(data.get("roughness", 0.7)),
            metallic=float(data.get("metallic", 0.0)),
            opacity=float(data.get("opacity", 1.0)),
            base_color_path=data.get("base_color_path"),
            normal_path=data.get("normal_path"),
            roughness_path=data.get("roughness_path"),
            ambient_occlusion_path=data.get("ambient_occlusion_path"),
            source=str(data.get("source", "unknown")),
            license_id=str(data.get("license_id", "unknown")),
            texture_scale_m=(
                float(data["texture_scale_m"])
                if data.get("texture_scale_m") is not None
                else None
            ),
        )


class MaterialLibrary:
    """Persistent local material registry; absent textures remain valid colors."""

    def __init__(self, manifest_path: str | Path | None = None) -> None:
        self.manifest_path = Path(manifest_path) if manifest_path else None
        self.environment_path: str | None = None
        self._records: dict[str, MaterialRecord] = {}
        if self.manifest_path and self.manifest_path.is_file():
            self.load(self.manifest_path)

    def register(self, record: MaterialRecord, *, overwrite: bool = False) -> MaterialRecord:
        if record.material_id in self._records and not overwrite:
            existing = self._records[record.material_id]
            if existing != record:
                raise ValueError(f"Material already registered: {record.material_id}")
            return existing
        self._records[record.material_id] = record
        self._autosave()
        return record

    def get(self, material_id: str) -> MaterialRecord | None:
        return self._records.get(material_id)

    def list_all(self) -> list[MaterialRecord]:
        return [self._records[key] for key in sorted(self._records)]

    def set_environment(self, path: str | Path | None) -> None:
        self.environment_path = str(path) if path is not None else None
        self._autosave()

    def resolve_path(self, path: str | Path) -> Path:
        candidate = Path(path)
        if candidate.is_absolute() or self.manifest_path is None:
            return candidate
        return (self.manifest_path.parent / candidate).resolve()

    def save(self, path: str | Path | None = None) -> Path:
        destination = Path(path) if path else self.manifest_path
        if destination is None:
            raise ValueError("A manifest path is required")
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "cityg.materials.v1",
            "environment_path": self.environment_path,
            "materials": [record.to_dict() for record in self.list_all()],
        }
        destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.manifest_path = destination
        return destination

    def load(self, path: str | Path) -> None:
        source = Path(path)
        payload = json.loads(source.read_text(encoding="utf-8"))
        if payload.get("schema_version") not in {None, "cityg.materials.v1"}:
            raise ValueError(f"Unsupported material library schema: {payload.get('schema_version')}")
        records = [MaterialRecord.from_dict(item) for item in payload.get("materials", [])]
        self._records = {record.material_id: record for record in records}
        self.environment_path = payload.get("environment_path")
        self.manifest_path = source

    def _autosave(self) -> None:
        if self.manifest_path:
            self.save(self.manifest_path)


__all__ = [
    "AssetRecord",
    "AssetRegistry",
    "AssetProvider",
    "AssetResolver",
    "MaterialRecord",
    "MaterialLibrary",
]
