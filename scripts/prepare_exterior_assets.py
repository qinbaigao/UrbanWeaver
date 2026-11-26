#!/usr/bin/env python3
"""Bounded CC0 asset acquisition, additive staging and explicit reviewed promotion.

Powered by Poly Haven (https://polyhaven.com), with explicit local CC0 reuse.
Source files remain untouched;
only reviewed, budget-compliant single props can enter the production registry.
No scene generation, model service, credentials or GPU is required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from cityg.asset_curation import _canonicalize_document, _document_metrics, _read_gltf, _write_glb
from cityg.assets import AssetRecord, AssetRegistry
from cityg.facade_runtime import _selected_bounds, _clone_nodes, _prune_for_nodes, _prune_binary_payloads

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.polyhaven.com"
USER_AGENT = "CityG-exterior-asset-preparation/1.0 (+https://polyhaven.com)"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def checksum(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_relative(name: str) -> Path:
    value = PurePosixPath(name)
    if not name or "\\" in name or value.is_absolute() or ".." in value.parts or ":" in name:
        raise ValueError(f"Unsafe asset path: {name}")
    return Path(*value.parts)


def checked_url(url: str) -> str:
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname not in {"api.polyhaven.com", "dl.polyhaven.org"}
            or parsed.username or parsed.password or parsed.port not in {None, 443}):
        raise ValueError(f"Unexpected provider URL: {url}")
    return url


def fetch(url: str, path: Path, expected: str | None = None, size: int | None = None) -> None:
    checked_url(url)
    if path.is_file() and expected and checksum(path) == expected:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    command = ["curl", "--fail", "--silent", "--show-error", "--location",
               "--proto", "=https", "--proto-redir", "=https", "--retry", "2", "--retry-all-errors",
               "--connect-timeout", "20", "--max-time", "300",
               "--speed-limit", "1024", "--speed-time", "30", "--user-agent", USER_AGENT]
    if size is not None:
        command.extend(["--max-filesize", str(size)])
    subprocess.run([*command, "--output", str(partial), url], check=True)
    if size is not None and partial.stat().st_size != size:
        raise ValueError(f"Size mismatch: {path}")
    if expected and checksum(partial) != expected:
        raise ValueError(f"Checksum mismatch: {path}")
    partial.replace(path)


def metadata(asset_id: str, staging: Path) -> dict:
    path = staging / "metadata" / f"{asset_id}.json"
    if not path.is_file():
        fetch(f"{API}/files/{asset_id}", path, size=None)
    return json.loads(path.read_text())


def bundle_files(asset_id: str, files: dict, resolution: str) -> dict:
    bundle = files["gltf"][resolution]["gltf"]
    result = {f"{asset_id}_{resolution}.gltf": {k: bundle[k] for k in ("url", "md5", "size")}}
    result.update(bundle.get("include", {}))
    for name, entry in result.items():
        safe_relative(name)
        checked_url(entry["url"])
        if not re.fullmatch(r"[a-f0-9]{32}", entry["md5"]) or int(entry["size"]) <= 0:
            raise ValueError(f"Invalid file metadata: {name}")
    return result


def local_source(entry: dict) -> Path:
    """Reuse only explicit, project-owned glTF sources; never follow an output link."""
    path = (ROOT / safe_relative(entry["local_source"])).resolve()
    if not path.is_relative_to((ROOT / "assets").resolve()) or path.suffix != ".gltf":
        raise ValueError("Local sources must be glTF files inside assets/")
    if entry.get("provider") not in {"polyhaven", "opengameart"} or entry.get("license_id") != "CC0-1.0":
        raise ValueError("Local reuse requires a known provider and explicit CC0 provenance")
    if not entry.get("source_url", "").startswith("https://"):
        raise ValueError("Local reuse requires its official source page")
    return path


def local_files(path: Path) -> dict:
    document = json.loads(path.read_text())
    names = {path.name}
    for value in [*document.get("buffers", []), *document.get("images", [])]:
        uri = value.get("uri", "")
        if uri and not uri.startswith("data:"):
            from urllib.parse import unquote
            names.add(str(safe_relative(unquote(uri))))
    result = {}
    for name in sorted(names):
        dependency = (path.parent / name).resolve()
        if not dependency.is_relative_to(path.parent.resolve()):
            raise ValueError(f"Escaping local dependency: {name}")
        result[name] = {"md5": checksum(dependency), "size": dependency.stat().st_size}
    return result


def assemble_roots(document: dict, roots: list[int], translations: dict) -> None:
    """Explicit reviewed kit assembly, in source coordinates; no inferred transforms."""
    for name, position in translations.items():
        matches = [i for i in roots if document["nodes"][i].get("name") == name]
        if len(matches) != 1 or len(position) != 3 or not all(math.isfinite(float(v)) for v in position):
            raise ValueError(f"Invalid/ambiguous root translation: {name}")
        node = document["nodes"][matches[0]]
        if "matrix" in node:
            raise ValueError(f"Matrix node requires transform decomposition: {name}")
        node["translation"] = [float(v) for v in position]


def build_plan(config: dict, staging: Path) -> dict:
    entries = []
    seen = set()
    for spec in config["assets"]:
        asset_id = spec["id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", asset_id) or asset_id in seen:
            raise ValueError(f"Invalid or repeated asset ID: {asset_id}")
        seen.add(asset_id)
        files = (local_files(local_source(spec)) if spec.get("local_source") else
                 bundle_files(asset_id, metadata(asset_id, staging), config["resolution"]))
        entry = {**spec, "files": files, "size_bytes": sum(int(f["size"]) for f in files.values())}
        entries.append(entry)
        print(f"Plan {asset_id}: {entry['size_bytes'] / 2**20:.1f} MiB", flush=True)
    total = sum(entry["size_bytes"] for entry in entries if not entry.get("local_source"))
    if total > config["max_download_mib"] * 2**20:
        raise ValueError(f"Pack exceeds download budget: {total / 2**20:.1f} MiB")
    plan = {"schema_version": "cityg.exterior_download_plan.v1", "provider": config.get("provider", "polyhaven"),
            "license_id": "CC0-1.0", "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "resolution": config["resolution"], "total_bytes": total, "assets": entries}
    write_json(staging / "download_plan.json", plan)
    return plan


def acquire(plan: dict, staging: Path) -> None:
    # Allow room for sources, GLB embedding, previews and temporary files.
    if shutil.disk_usage(staging).free < plan["total_bytes"] * 3 + 1024**3:
        raise ValueError("Insufficient disk headroom for source and canonical copies")
    for entry in plan["assets"]:
        directory = staging / "sources" / entry["id"]
        if entry.get("local_source"):
            source = local_source(entry)
            if local_files(source) != entry["files"]:
                raise ValueError(f"Local source changed since plan: {source}")
            write_json(directory / "source.json", {
                "asset_id": entry["id"], "source": entry["provider"], "license_id": entry["license_id"],
                "source_page": entry["source_url"], "local_source": entry["local_source"],
                "upstream_files": entry["files"], "reused_without_copy": True,
            })
            print(f"Reused {entry['id']} (no download or source copy)", flush=True)
            continue
        for name, info in entry["files"].items():
            fetch(info["url"], directory / safe_relative(name), info["md5"], int(info["size"]))
        write_json(directory / "source.json", {
            "asset_id": entry["id"], "source": "Poly Haven", "license_id": "CC0-1.0",
            "source_page": f"https://polyhaven.com/a/{entry['id']}",
            "source_api": f"{API}/files/{entry['id']}",
            "upstream_files": entry["files"], "resolution": plan["resolution"],
        })
        print(f"Verified {entry['id']}", flush=True)


def exclude_material_primitives(document, excluded):
    """Remove explicitly named optional covers, never an entire source mesh."""
    if not isinstance(excluded, list) or any(not isinstance(name,str) or not name for name in excluded):
        raise ValueError('Material exclusions must be explicit material names')
    if not excluded:
        return
    materials = document.get('materials', [])
    indices = {i for i,m in enumerate(materials) if m.get('name') in excluded}
    if {materials[i].get('name') for i in indices} != set(excluded):
        raise ValueError('Unknown material exclusion; source changed')
    replacements = [[p for p in mesh['primitives'] if p.get('material') not in indices]
                    for mesh in document.get('meshes', [])]
    if any(not primitives for primitives in replacements):
        raise ValueError('Material exclusion would remove a whole mesh')
    for mesh, primitives in zip(document.get('meshes', []), replacements):
        mesh['primitives'] = primitives


def prepare_record(entry: dict, resolution: str, staging: Path, budget: int) -> AssetRecord:
    asset_id = entry["id"]
    input_path = (local_source(entry) if entry.get("local_source") else
                  staging / "sources" / asset_id / f"{asset_id}_{resolution}.gltf")
    directory = input_path.parent
    if entry.get("local_source") and local_files(input_path) != entry["files"]:
        raise ValueError(f"Local source/dependencies changed since plan: {input_path}")
    # Recheck every dependency, including textures: the glTF hash alone is insufficient.
    for name, info in entry["files"].items():
        path = directory / safe_relative(name)
        if not path.is_file() or path.stat().st_size != int(info["size"]) or checksum(path) != info["md5"]:
            raise ValueError(f"Missing or modified source dependency: {path}")
    document, buffers = _read_gltf(input_path)
    # Explicitly reviewed source parts only (e.g. a broken opaque glass cover).
    # Keep the downloaded source untouched and audit the removed materials.
    excluded = entry.get('exclude_materials', [])
    exclude_material_primitives(document, excluded)
    roots = document["scenes"][document.get("scene", 0)]["nodes"]
    if entry.get("nodes"):
        # Require explicit, unique top-level roots: nested nodes need inherited
        # transform baking, which this bounded static importer does not assume.
        selected = []
        for name in entry["nodes"]:
            matches = [i for i in roots if document["nodes"][i].get("name") == name]
            if len(matches) != 1:
                raise ValueError(f"Missing/ambiguous root node {name}: {asset_id}")
            selected.append(matches[0])
        nodes, roots = _clone_nodes(document, selected)
        document = _prune_for_nodes(document, nodes)
        document["scenes"] = [{"nodes": roots}]
        document["scene"] = 0
        document, buffers = _prune_binary_payloads(document, buffers)
    assemble_roots(document, roots, entry.get("root_translations", {}))
    # World bounds, including node transforms, rather than mesh-local accessor bounds.
    low, high = _selected_bounds(document, roots)
    extent = [high[i] - low[i] for i in range(3)]
    if any(not math.isfinite(v) or v <= 1e-6 for v in extent):
        raise ValueError(f"Degenerate model: {asset_id}")
    bounds = {"min": list(low), "max": list(high), "extent": extent}
    metrics = _document_metrics(document, bounds)
    if metrics["skin_count"] or metrics["animation_count"]:
        raise ValueError(f"Static-only preparation cannot bake animations: {asset_id}")
    suffix = f"_{entry['key']}" if entry.get("key") else ""
    if suffix and not re.fullmatch(r"_[A-Za-z0-9_-]+", suffix):
        raise ValueError("Invalid variant key")
    provider = entry.get("provider", "polyhaven")
    style = entry.get("style", "photorealistic_pbr")
    canonical_id = f"{entry.get('id_prefix', 'prepared')}_{provider}_{asset_id}{suffix}"
    normalized = _canonicalize_document(document, bounds, asset_id=canonical_id,
                                        source_up_axis="+Y", source_forward_axis="+Z")
    binary = _write_glb(normalized, buffers, directory)
    output_hash = hashlib.sha256(binary).hexdigest()
    filename = f"{asset_id}{suffix}_{output_hash[:12]}.glb"
    glb_path = staging / "glb" / filename
    glb_path.parent.mkdir(parents=True, exist_ok=True)
    # Content-addressed payloads: re-preparing a selector must not silently
    # overwrite a GLB already referenced by a promoted production record.
    if not glb_path.is_file():
        glb_path.write_bytes(binary)
    elif hashlib.sha256(glb_path.read_bytes()).hexdigest() != output_hash:
        raise ValueError(f"Existing content-addressed payload is corrupt: {glb_path}")
    height = float(entry["height_m"])
    if not math.isfinite(height) or height <= 0:
        raise ValueError(f"Invalid target height: {asset_id}")
    dimensions = (extent[2] / extent[1] * height, extent[0] / extent[1] * height, height)
    findings = ["visual_review_required", "front_axis_review_required", "scale_is_curated_estimate"]
    if metrics["triangle_count"] > budget:
        findings.append("geometry_lod_required")
    if entry.get("manual_only"):
        findings.append("placement_adapter_or_component_extraction_required")
    return AssetRecord(
        asset_id=canonical_id, category=entry["category"],
        tags=tuple(dict.fromkeys([*entry["tags"], asset_id, "outdoor", style, "curated",
                                 *(["manual_only"] if entry.get("manual_only") else [])])),
        dimensions_m=dimensions, geometry_path=f"glb/{filename}",
        source=f"{provider}_exterior_prepared", license_id="CC0-1.0", environment="outdoor",
        quality_score=float(entry.get("quality_score", .92)), metadata={
            "external_content": True, "redistribution_policy": "CC0",
            "style": style, "outdoor_pack_status": "candidate",
            "preserve_physical_proportions": True,
            "placement_yaw_offset_deg": entry.get("placement_yaw_offset_deg", 0),
            "curation_note": entry.get("review_note", ""),
            # Leaf cards and rotated mesh bounds may extend below the authored
            # soil plane. Ground botanical assets by that plane, not card bounds.
            "ground_anchor_fraction": max(0.0, min(1.0, -low[1] / extent[1]))
                if entry["category"] in {"plant", "shrub"} else 0.0,
            "source_url": entry.get("source_url", f"https://polyhaven.com/a/{asset_id}"),
            "source_asset_id": asset_id, "source_manifest": f"sources/{asset_id}/source.json",
            "source_selected_nodes": entry.get("nodes", []),
            "source_excluded_materials": excluded,
            "source_root_translations": entry.get("root_translations", {}),
            "source_files_md5": {name: info["md5"] for name, info in entry["files"].items()},
            "output_sha256": output_hash,
            "subtype": asset_id, "semantic_class": entry["category"],
            "placement_rules": {"allowed_contexts": entry["contexts"], "manual_only": entry.get("manual_only", False)},
            "orientation": {"source_up_axis": "+Y", "source_forward_axis": "+Z",
                            "canonical_up_axis": "+Z", "canonical_forward_axis": "+X",
                            "pivot": "bounds_center", "orientation_confidence": "unreviewed"},
            "mesh_validation": metrics, "file_size_bytes": len(binary),
            "preparation": {"findings": findings, "runtime_triangle_budget": budget,
                            "geometry_decimated": False, "resolution": resolution,
                            "scale_policy": "uniform physical scaling from curated height; source proportions preserved"},
        },
    )


def prepare(plan: dict, staging: Path, budget: int) -> None:
    entries = [
        {**entry, **variant} for entry in plan["assets"]
        for variant in entry.get("variants", [{}])
    ]
    records = [prepare_record(entry, plan["resolution"], staging, budget) for entry in entries]
    # This is a reproducible snapshot of this staging pack only. Production
    # records and old payloads are never pruned; promotion is always additive.
    registry = AssetRegistry()
    registry.register_many(records, overwrite=True)
    write_json(staging / "candidate_registry.json", {
        "schema_version": "cityg.assets.v1", "assets": [r.to_dict() for r in registry.list_all()]})
    write_json(staging / "audit.json", {"asset_count": len(records), "assets": [
        {"asset_id": r.asset_id, "category": r.category,
         "triangles": r.metadata["mesh_validation"]["triangle_count"],
         "dimensions_m": r.dimensions_m, "file_size_bytes": r.metadata["file_size_bytes"],
         "findings": r.metadata["preparation"]["findings"]} for r in records]})
    print(f"Prepared {len(records)} candidates; production registry unchanged", flush=True)


def promote(staging: Path, registry_path: Path, ids: list[str], note: str, budget: int) -> int:
    if not note.strip():
        raise ValueError("Explicit visual review note is required")
    candidate_registry = AssetRegistry(staging / "candidate_registry.json")
    registry = AssetRegistry(registry_path)
    records = []
    for asset_id in ids:
        record = candidate_registry.require(asset_id)
        if "manual_only" in record.tags or record.metadata["mesh_validation"]["triangle_count"] > budget:
            raise ValueError(f"Not safe for automatic placement: {asset_id}")
        geometry = candidate_registry.resolve_path(record.geometry_path).resolve()
        if hashlib.sha256(geometry.read_bytes()).hexdigest() != record.metadata["output_sha256"]:
            raise ValueError(f"Candidate changed since audit: {asset_id}")
        meta = {**record.metadata, "outdoor_pack_status": "ready", "visual_review": {
            "method": "operator_four_view", "note": note, "reviewed_at": datetime.now(timezone.utc).isoformat()}}
        meta["orientation"] = {**record.metadata["orientation"], "orientation_confidence": "medium", "visually_checked": True}
        source_manifest = candidate_registry.resolve_path(meta["source_manifest"]).resolve()
        meta["source_manifest"] = os.path.relpath(source_manifest, registry_path.parent)
        records.append(replace(record, geometry_path=os.path.relpath(geometry, registry_path.parent), metadata=meta))
    if registry_path.is_file():
        backup = staging / "registry_backups" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + ".json")
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(registry_path, backup)
    registry.manifest_path = None
    registry.register_many(records, overwrite=True)
    write_json(registry_path, {"schema_version": "cityg.assets.v1", "assets": [r.to_dict() for r in registry.list_all()]})
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "download", "prepare", "promote"])
    parser.add_argument("--config", type=Path, default=ROOT / "configs/exterior_asset_pack.json")
    parser.add_argument("--staging", type=Path, default=ROOT / "assets/prepared/exterior_v1")
    parser.add_argument("--registry", type=Path, default=ROOT / "assets/asset_registry.json")
    parser.add_argument("--asset-id", action="append", default=[])
    parser.add_argument("--review-note", default="")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    args.staging.mkdir(parents=True, exist_ok=True)
    print("Powered by Poly Haven — exterior preparation with explicit local CC0 reuse", flush=True)
    if args.action == "promote":
        if not args.asset_id:
            parser.error("promote requires explicit --asset-id values")
        count = promote(args.staging, args.registry.resolve(), args.asset_id, args.review_note,
                        config["max_runtime_triangles"])
        print(f"Promoted {count} reviewed assets; previous registry backed up")
        return
    if args.action == "prepare":
        plan = json.loads((args.staging / "download_plan.json").read_text())
        # Reuse verified downloads while allowing offline semantic/selector
        # refinement. The current config must retain exactly the downloaded IDs.
        configured = {item["id"]: item for item in config["assets"]}
        if set(configured) != {item["id"] for item in plan["assets"]} or config["resolution"] != plan["resolution"]:
            raise ValueError("Asset IDs/resolution changed; rerun plan/download first")
        plan["assets"] = [{**entry, **configured[entry["id"]]} for entry in plan["assets"]]
        prepare(plan, args.staging, config["max_runtime_triangles"])
        return
    plan = build_plan(config, args.staging)
    print(f"Total source download: {plan['total_bytes'] / 2**20:.1f} MiB", flush=True)
    if args.action == "download":
        acquire(plan, args.staging)


if __name__ == "__main__":
    main()
