"""Curated, auditable outdoor asset pack support.

The outdoor pack is a set of semantic slots rather than a folder of anonymous
meshes.  A slot describes how an asset is used, its physical size, whether a
generative provider is acceptable, and the minimum quality expected by CityG.
The pack builder resolves local assets first and can optionally fill bounded,
generation-safe slots through an explicitly configured provider.
"""

from __future__ import annotations

import json
import hashlib
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable

from cityg.assets import AssetProvider, AssetRecord, AssetRegistry, AssetResolver
from cityg.asset_curation import ExternalAssetSourceCatalog


_SLOT_REQUIRED_TOKENS: dict[str, frozenset[str]] = {
    "street_tree_deciduous": frozenset({"deciduous", "broadleaf", "common"}),
    "street_tree_columnar": frozenset({"columnar", "fastigiate", "narrow"}),
    "park_tree_broadleaf": frozenset({"broadleaf", "canopy", "shade"}),
    "ornamental_shrub": frozenset({"shrub", "bush", "ornamental"}),
    "street_light_modern": frozenset({"streetlight", "street_light", "lamp", "light"}),
    "street_bench_wood_metal": frozenset({"bench", "seating"}),
    "street_bench_retro": frozenset({"bench", "retro"}),
    "street_bin_modern": frozenset({"bin", "trash", "waste"}),
    "street_bin_dumpster": frozenset({"dumpster", "waste"}),
    "planter_large": frozenset({"planter"}),
    "planter_suburban": frozenset({"planter", "suburban"}),
    "small_sign_wayfinding": frozenset({"sign", "wayfinding"}),
    "low_hedge": frozenset({"shrub", "hedge"}),
    "flower_cluster": frozenset({"flower", "group", "cluster"}),
    "bollard_simple": frozenset({"bollard"}),
    "bicycle_rack": frozenset({"bicycle", "bike", "rack"}),
    "fire_hydrant": frozenset({"hydrant"}),
    "bus_shelter": frozenset({"shelter", "bus_stop"}),
    "traffic_signal": frozenset({"signal", "traffic_light"}),
    "sedan_modern": frozenset({"sedan"}),
    "suv_modern": frozenset({"suv"}),
    "delivery_van": frozenset({"delivery", "van"}),
    "city_bus": frozenset({"bus"}),
    "pedestrian_walking": frozenset({"walking", "walk"}),
    "pedestrian_standing": frozenset({"standing", "idle"}),
    "playground_climber": frozenset({"playground", "climber", "slide"}),
}

def _external_slot_match(record: AssetRecord, slot_id: str) -> bool:
    """Require downloaded assets to match the requested concrete subtype."""

    if not record.metadata.get("external_content"):
        return True
    stable_text = " ".join(
        str(value)
        for value in (
            record.asset_id,
            record.metadata.get("subtype", ""),
            record.metadata.get("semantic_class", ""),
            record.metadata.get("source_relative_path", ""),
        )
    ).lower()
    stable_tokens = set(stable_text.replace("-", "_").split())
    stable_tokens.update(
        token
        for piece in stable_text.replace("/", "_").split("_")
        for token in piece.split()
    )
    required = _SLOT_REQUIRED_TOKENS.get(slot_id, frozenset())
    return not required or bool(required & stable_tokens)


@dataclass(frozen=True)
class OutdoorAssetSlot:
    slot_id: str
    category: str
    query: str
    dimensions_m: tuple[float, float, float]
    tags: tuple[str, ...]
    use: str
    min_quality: float = 0.55
    generation_allowed: bool = True
    preferred_source: str = "generated_or_curated"

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "category": self.category,
            "query": self.query,
            "dimensions_m": list(self.dimensions_m),
            "tags": list(self.tags),
            "use": self.use,
            "min_quality": self.min_quality,
            "generation_allowed": self.generation_allowed,
            "preferred_source": self.preferred_source,
        }


def default_outdoor_slots() -> tuple[OutdoorAssetSlot, ...]:
    """Return the first production-oriented CityG outdoor asset vocabulary."""

    return (
        OutdoorAssetSlot("street_tree_deciduous", "street_tree", "mature deciduous urban street tree with realistic trunk and leafy crown", (4.6, 4.6, 7.2), ("tree", "deciduous", "street", "summer"), "street vegetation", generation_allowed=False, preferred_source="curated"),
        OutdoorAssetSlot("street_tree_columnar", "street_tree", "columnar urban street tree with narrow crown", (3.2, 3.2, 7.8), ("tree", "columnar", "street"), "street vegetation", generation_allowed=False, preferred_source="curated"),
        OutdoorAssetSlot("park_tree_broadleaf", "park_tree", "large broadleaf park tree with natural branching", (7.0, 7.0, 10.0), ("tree", "broadleaf", "park"), "park vegetation", generation_allowed=False, preferred_source="curated"),
        OutdoorAssetSlot("ornamental_shrub", "shrub", "dense ornamental landscape shrub", (1.25, 1.25, 0.9), ("shrub", "ornamental", "landscape"), "landscape understorey", generation_allowed=False, preferred_source="curated"),
        OutdoorAssetSlot("street_light_modern", "street_light", "modern urban LED street light, slim dark metal pole, single luminaire, isolated object", (0.8, 0.8, 5.2), ("light", "lamp", "modern", "street"), "roadside lighting"),
        OutdoorAssetSlot("street_bench_wood_metal", "street_bench", "contemporary outdoor public bench, timber slats and dark metal frame, isolated object", (1.9, 0.62, 0.86), ("bench", "wood", "metal", "public"), "street seating"),
        OutdoorAssetSlot("street_bench_retro", "street_bench", "retro urban park bench, isolated object", (1.9, 0.62, 0.86), ("bench", "retro", "street"), "street seating variation", generation_allowed=False, preferred_source="curated"),
        OutdoorAssetSlot("street_bin_modern", "street_bin", "small modern covered public waste receptacle, dark powder coated metal, no roof, no kiosk, no stall, isolated object", (0.48, 0.48, 0.95), ("bin", "waste", "street", "metal"), "street sanitation"),
        OutdoorAssetSlot("street_bin_dumpster", "street_bin", "closed urban dumpster for service area, isolated object", (1.4, 0.9, 1.2), ("dumpster", "waste", "service"), "service-area sanitation", generation_allowed=False, preferred_source="curated"),
        OutdoorAssetSlot("planter_large", "street_planter", "large rectangular urban planter with green ornamental plants, stone and metal materials, isolated object", (1.45, 0.62, 0.85), ("planter", "greenery", "street"), "public-space greenery"),
        OutdoorAssetSlot("planter_suburban", "street_planter", "suburban flower planter with low greenery, isolated object", (1.2, 0.65, 0.7), ("planter", "suburban", "flower"), "residential greenery", generation_allowed=False, preferred_source="curated"),
        OutdoorAssetSlot("small_sign_wayfinding", "small_sign", "small pedestrian wayfinding sign, isolated object", (0.55, 0.12, 1.65), ("sign", "wayfinding", "pedestrian"), "park and plaza navigation", generation_allowed=False, preferred_source="curated"),
        OutdoorAssetSlot("low_hedge", "shrub", "low clipped hedge segment for sidewalk or plaza edge", (1.5, 0.55, 0.75), ("shrub", "hedge", "low"), "landscape edge planting", generation_allowed=False, preferred_source="curated"),
        OutdoorAssetSlot("flower_cluster", "plant", "cluster of flowering plants for a public flower bed", (0.8, 0.8, 0.55), ("flower", "cluster", "group"), "flower beds", generation_allowed=False, preferred_source="curated"),
        OutdoorAssetSlot("bollard_simple", "bollard", "short modern street bollard, dark metal with reflective strip, isolated object", (0.20, 0.20, 0.9), ("bollard", "street", "safety"), "pedestrian protection"),
        OutdoorAssetSlot("bicycle_rack", "bicycle_rack", "stainless steel inverted U bicycle rack for four bicycles, isolated object", (2.2, 0.7, 0.85), ("bicycle", "rack", "street"), "cycle parking"),
        OutdoorAssetSlot("fire_hydrant", "fire_hydrant", "realistic municipal fire hydrant, red painted metal, isolated object", (0.45, 0.45, 0.9), ("hydrant", "emergency", "street"), "emergency infrastructure"),
        OutdoorAssetSlot("bus_shelter", "bus_shelter", "modern glass and dark metal bus shelter with bench and roof, isolated structure", (4.5, 1.65, 2.65), ("bus", "shelter", "transit", "glass"), "public transport"),
        OutdoorAssetSlot("traffic_signal", "traffic_signal", "urban three-light traffic signal on slim pole, isolated object", (0.75, 0.75, 4.2), ("traffic", "signal", "junction"), "junction control"),
        OutdoorAssetSlot("sedan_modern", "vehicle", "modern compact sedan passenger car, realistic painted body and windows, isolated vehicle", (4.55, 1.82, 1.48), ("vehicle", "sedan", "car", "modern"), "traffic snapshot", generation_allowed=False, preferred_source="curated"),
        OutdoorAssetSlot("suv_modern", "vehicle", "modern mid-size SUV passenger car, realistic painted body and windows, isolated vehicle", (4.75, 1.95, 1.72), ("vehicle", "suv", "car", "modern"), "traffic snapshot", generation_allowed=False, preferred_source="curated"),
        OutdoorAssetSlot("delivery_van", "vehicle", "modern urban delivery van, realistic painted body and windows, isolated vehicle", (5.25, 2.05, 2.35), ("vehicle", "van", "delivery"), "traffic snapshot", generation_allowed=False, preferred_source="curated"),
        OutdoorAssetSlot("city_bus", "vehicle", "modern low-floor city transit bus, realistic livery and windows, isolated vehicle", (11.8, 2.55, 3.25), ("vehicle", "bus", "transit"), "traffic snapshot", generation_allowed=False, preferred_source="curated"),
        OutdoorAssetSlot("pedestrian_walking", "person", "casually dressed adult pedestrian walking, neutral pose, isolated full body", (0.62, 0.48, 1.75), ("person", "pedestrian", "walking"), "sidewalk population", generation_allowed=False, preferred_source="curated"),
        OutdoorAssetSlot("pedestrian_standing", "person", "casually dressed adult pedestrian standing, neutral pose, isolated full body", (0.58, 0.46, 1.72), ("person", "pedestrian", "standing"), "sidewalk population", generation_allowed=False, preferred_source="curated"),
        OutdoorAssetSlot("playground_climber", "playground", "compact colorful public playground climbing frame with slide, isolated structure", (5.2, 4.2, 3.1), ("playground", "slide", "park", "children"), "park activity"),
    )


def import_outdoor_asset(
    registry: AssetRegistry,
    *,
    slot_id: str,
    geometry: str | Path,
    asset_root: str | Path,
    source: str,
    license_id: str,
    preview: str | Path | None = None,
    quality_score: float = 0.8,
) -> AssetRecord:
    """Copy one licensed local asset into the self-contained CityG pack."""

    slots = {item.slot_id: item for item in default_outdoor_slots()}
    if slot_id not in slots:
        raise ValueError(f"Unknown outdoor asset slot: {slot_id}")
    slot = slots[slot_id]
    source_path = Path(geometry)
    if not source_path.is_file() or source_path.stat().st_size == 0:
        raise ValueError(f"Outdoor geometry is missing or empty: {source_path}")
    digest = hashlib.sha256(source_path.read_bytes()).hexdigest()[:12]
    destination_dir = Path(asset_root) / slot_id / digest
    destination_dir.mkdir(parents=True, exist_ok=True)
    target = destination_dir / f"asset{source_path.suffix.lower()}"
    if not target.exists():
        shutil.copy2(source_path, target)
    preview_target = None
    if preview is not None:
        preview_path = Path(preview)
        if not preview_path.is_file():
            raise ValueError(f"Outdoor preview is missing: {preview_path}")
        preview_target = destination_dir / f"preview{preview_path.suffix.lower()}"
        if not preview_target.exists():
            shutil.copy2(preview_path, preview_target)
    def registry_path(path: Path | None) -> str | None:
        if path is None:
            return None
        resolved = path.resolve()
        if registry.manifest_path is not None:
            try:
                return str(resolved.relative_to(registry.manifest_path.parent.resolve()))
            except ValueError:
                pass
        return str(resolved)
    record = AssetRecord(
        asset_id=f"outdoor_{slot_id}_{digest}",
        category=slot.category,
        tags=tuple(dict.fromkeys((*slot.tags, slot.slot_id, "outdoor", "curated"))),
        dimensions_m=slot.dimensions_m,
        geometry_path=registry_path(target),
        preview_path=registry_path(preview_target),
        source=source,
        license_id=license_id,
        quality_score=quality_score,
        metadata={
            "outdoor_slot": slot.slot_id,
            "outdoor_use": slot.use,
            "preferred_source": slot.preferred_source,
            "imported_content": True,
            "content_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            "target_dimensions_m": list(slot.dimensions_m),
        },
    )
    registry.register(record, overwrite=True)
    return record


@dataclass(frozen=True)
class OutdoorAssetAudit:
    slot_id: str
    status: str
    asset_id: str | None
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "status": self.status,
            "asset_id": self.asset_id,
            "reasons": list(self.reasons),
        }


class OutdoorAssetPackBuilder:
    """Resolve, optionally acquire, tag, and audit outdoor asset slots."""

    def __init__(
        self,
        registry: AssetRegistry,
        providers: Iterable[AssetProvider] = (),
        *,
        max_generated_assets: int = 0,
    ) -> None:
        self.registry = registry
        self.resolver = AssetResolver(
            registry,
            providers=providers,
            max_provider_calls=max_generated_assets,
            strict_provider_errors=False,
        )

    def build(
        self,
        output: str | Path,
        *,
        slots: Iterable[OutdoorAssetSlot] | None = None,
        generate: bool = False,
        force_generation: bool = False,
    ) -> dict[str, Any]:
        selected_slots = tuple(slots or default_outdoor_slots())
        audits: list[OutdoorAssetAudit] = []
        for slot in selected_slots:
            record = self._local_record(slot)
            acquired = False
            if record is None and generate and (slot.generation_allowed or force_generation):
                record = self.resolver.resolve(
                    slot.query,
                    category=slot.category,
                    dimensions_m=slot.dimensions_m,
                    environment="outdoor",
                )
                acquired = record is not None
            if record is None:
                audits.append(OutdoorAssetAudit(slot.slot_id, "missing", None, ("no matching geometry",)))
                continue
            if acquired or record.metadata.get("outdoor_slot") != slot.slot_id:
                record = self._tag_record(record, slot)
            if acquired and not slot.generation_allowed:
                record = replace(
                    record,
                    metadata={**record.metadata, "generation_experiment": True},
                )
            reasons = self._quality_reasons(record, slot)
            candidate = bool(
                record.metadata.get("generation_experiment")
                and record.metadata.get("manual_review_status") != "accepted"
            )
            record = replace(
                record,
                metadata={
                    **record.metadata,
                    "outdoor_pack_status": (
                        "rejected" if reasons else "candidate" if candidate else "ready"
                    ),
                    "outdoor_quality_reasons": list(reasons),
                },
            )
            self.registry.register(record, overwrite=True)
            audits.append(
                OutdoorAssetAudit(
                    slot.slot_id,
                    "rejected" if reasons else "candidate" if candidate else "ready",
                    record.asset_id,
                    tuple(reasons),
                )
            )

        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        ready = sum(item.status == "ready" for item in audits)
        slot_lookup = {slot.slot_id: slot for slot in selected_slots}
        source_catalog = ExternalAssetSourceCatalog()
        payload = {
            "schema_version": "cityg.outdoor_assets.v1",
            "summary": {
                "slot_count": len(selected_slots),
                "ready_count": ready,
                "candidate_count": sum(item.status == "candidate" for item in audits),
                "missing_count": sum(item.status == "missing" for item in audits),
                "rejected_count": sum(item.status == "rejected" for item in audits),
                "coverage": round(ready / max(1, len(selected_slots)), 6),
            },
            "slots": [slot.to_dict() for slot in selected_slots],
            "audit": [item.to_dict() for item in audits],
            "external_discovery": {
                "policy": "search_on_demand_explicit_download",
                "requests": [
                    source_catalog.search_plan(
                        slot_lookup[item.slot_id].query,
                        category=slot_lookup[item.slot_id].category,
                    )
                    for item in audits
                    if item.status in {"missing", "rejected"}
                ],
            },
            "resolver": self.resolver.stats(),
        }
        destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if self.registry.manifest_path is not None:
            self.registry.save()
        return payload

    def _local_record(self, slot: OutdoorAssetSlot) -> AssetRecord | None:
        exact = [
            record
            for record in self.registry.list_all()
            if record.has_geometry
            and record.category == slot.category
            and record.metadata.get("outdoor_slot") == slot.slot_id
            and _external_slot_match(record, slot.slot_id)
        ]
        if exact:
            return sorted(exact, key=lambda item: (-item.quality_score, item.asset_id))[0]
        candidates = self.registry.search(
            (slot.slot_id, slot.query, *slot.tags),
            category=slot.category,
            limit=5,
            require_geometry=True,
        )
        # A generated/curated record may already be bound to a concrete slot.
        # Do not let broad category/tag search silently reuse (and retag) it for
        # a different semantic slot (e.g. a sedan becoming a city bus).
        compatible = [
            item
            for item, _score in candidates
            if item.metadata.get("outdoor_slot") in (None, slot.slot_id)
            and _external_slot_match(item, slot.slot_id)
        ]
        return compatible[0] if compatible else None

    def _tag_record(self, record: AssetRecord, slot: OutdoorAssetSlot) -> AssetRecord:
        tags = tuple(dict.fromkeys((*record.tags, *slot.tags, slot.slot_id, "outdoor", "cityg_pack")))
        return replace(
            record,
            category=slot.category,
            tags=tags,
            environment="outdoor",
            room_types=(),
            dimensions_m=record.dimensions_m or slot.dimensions_m,
            metadata={
                **record.metadata,
                "outdoor_slot": slot.slot_id,
                "outdoor_use": slot.use,
                "preferred_source": slot.preferred_source,
                "target_dimensions_m": list(slot.dimensions_m),
            },
        )

    def _quality_reasons(self, record: AssetRecord, slot: OutdoorAssetSlot) -> list[str]:
        reasons: list[str] = []
        if record.metadata.get("manual_review_status") == "rejected":
            reasons.append(
                "manual review rejected: "
                + str(record.metadata.get("manual_review_reason", "unspecified"))
            )
        if record.quality_score < slot.min_quality:
            reasons.append(f"quality_score {record.quality_score:.3f} < {slot.min_quality:.3f}")
        if not record.geometry_path:
            reasons.append("geometry_path is absent")
        else:
            path = self.registry.resolve_path(record.geometry_path)
            if not path.is_file() or path.stat().st_size == 0:
                reasons.append("geometry file is missing or empty")
            elif path.suffix.lower() not in {".glb", ".gltf", ".usd", ".usda", ".usdc"}:
                reasons.append(f"unsupported geometry format: {path.suffix}")
            elif path.suffix.lower() == ".glb":
                with path.open("rb") as handle:
                    if handle.read(4) != b"glTF":
                        reasons.append("invalid GLB header")
        if not record.license_id or record.license_id.lower() in {"unknown", "none"}:
            reasons.append("license is not declared")
        if record.dimensions_m is None:
            reasons.append("physical dimensions are not declared")
        if record.source.startswith("hunyuan") and record.metadata.get("texture_status") != "generated":
            reasons.append("generated asset has no generated texture")
        return reasons


__all__ = [
    "OutdoorAssetAudit",
    "OutdoorAssetPackBuilder",
    "OutdoorAssetSlot",
    "default_outdoor_slots",
    "import_outdoor_asset",
]
