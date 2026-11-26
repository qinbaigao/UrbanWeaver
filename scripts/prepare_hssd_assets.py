#!/usr/bin/env python3
"""Bounded HSSD download and independent candidate preparation; never promotes assets.

Uses the user's local Hugging Face login, pinned revisions, source hashes and
explicit byte budgets. Metadata comes from HSSD, not model-name guesses alone.
No model execution, GPU, scene generation or production registry writes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import re
import shutil
import struct
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.prepare_exterior_assets import write_json, safe_relative
from cityg.asset_curation import _canonicalize_document, _document_metrics, _read_gltf, _write_glb
from cityg.assets import AssetRecord
from cityg.facade_runtime import _selected_bounds

ROOT = Path(__file__).resolve().parents[1]
LICENSE = "CC-BY-NC-4.0"


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else _hash_stream(stream)


def _hash_stream(stream):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def dimensions(row):
    values = [float(v) for v in row["aligned.dims"].split(",")]
    if len(values) != 3 or any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError("Invalid source dimensions")
    return values


def select_assets(rows, files, config):
    """Deterministic category quotas and global cluster deduplication, not quality approval."""
    chosen, gaps, used, clusters = [], [], set(), set()
    total = 0
    for spec in config["categories"]:
        candidates = []
        for row in rows:
            identifier = row["id"]
            if identifier in used or identifier not in files or not re.fullmatch(r"[a-f0-9]{40}", identifier):
                continue
            if row.get("hasMultipleObjects", "").lower() not in {"", "false"} or row.get("decomposedFrom"):
                continue
            tags = {v.strip() for v in row.get("floorplanner-category-tags", "").split(",")}
            text = (row.get("name", "") + " " + row.get("foundIn", "") + " " + " ".join(tags)).lower()
            if any(v in text for v in ("outdoor", "garden", "patio", "set of", "chair set", "pet bed", "bunk bed")):
                continue
            if not (row.get("wnsynsetkey") in spec.get("synsets", []) or
                    row.get("main_category") in spec.get("main_categories", []) or
                    tags.intersection(spec.get("tags_any", []))):
                continue
            try:
                dims = dimensions(row)
            except (ValueError, KeyError):
                continue
            if dims[1] > spec.get("max_height_m", 5) or max(dims) > 6:
                continue
            if not 0 < files[identifier]["size"] <= config["max_asset_bytes"]:
                continue
            # Stable sampling avoids choosing only small files or consecutive variants.
            rank = hashlib.sha256((config["seed"] + identifier).encode()).hexdigest()
            candidates.append((rank, row))
        count = 0
        for _, row in sorted(candidates, key=lambda v: v[0]):
            cluster = {v.strip() for v in row.get("simClusterIds", "").split(",") if v.strip()}
            if cluster.intersection(clusters):
                continue
            entry = files[row["id"]]
            if total + entry["size"] > config["max_download_bytes"]:
                continue
            chosen.append({"id": row["id"], "category": spec["category"],
                           "room_types": spec["room_types"], "placement_kind": spec["placement_kind"],
                           "file": entry, "metadata": row})
            total += entry["size"]
            clusters.update(cluster)
            used.add(row["id"])
            count += 1
            if count >= spec["count"]:
                break
        if count < spec["count"]:
            gaps.append({"category": spec["category"], "requested": spec["count"], "selected": count,
                         "reason": "insufficient eligible distinct source models within budget"})
    return chosen, gaps


def index(config, staging):
    from huggingface_hub import HfApi, hf_hub_download
    api = HfApi(endpoint="https://huggingface.co")
    model_rev = api.repo_info(config["models_repo"], repo_type="dataset").sha
    meta_rev = api.repo_info(config["metadata_repo"], repo_type="dataset").sha
    metadata_path = Path(hf_hub_download(config["metadata_repo"], config["metadata_file"],
        repo_type="dataset", revision=meta_rev, local_dir=staging/"upstream", endpoint="https://huggingface.co"))
    files = {}
    for f in api.list_repo_tree(config["models_repo"], repo_type="dataset", revision=model_rev, recursive=True):
        if not f.path.startswith("objects/") or not f.path.endswith(".glb"):
            continue
        digest = getattr(f.lfs, "sha256", None) if f.lfs else None
        files[Path(f.path).stem] = {"path": f.path, "size": f.size, "sha256": digest, "blob_id": f.blob_id}
    with metadata_path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    selected, gaps = select_assets(rows, files, {**config,
        "max_download_bytes": config["max_download_bytes"] - metadata_path.stat().st_size})
    plan = {"schema_version": "cityg.hssd_download_plan.v1", "models_repo": config["models_repo"],
        "models_revision": model_rev, "metadata_repo": config["metadata_repo"], "metadata_revision": meta_rev,
        "metadata_file": config["metadata_file"], "metadata_sha256": sha256(metadata_path),
        "license_id": LICENSE, "max_download_bytes": config["max_download_bytes"],
        "max_runtime_triangles": config["max_runtime_triangles"],
        "source_bytes": sum(e["file"]["size"] for e in selected), "metadata_bytes": metadata_path.stat().st_size,
        "selection_config": config, "assets": selected, "gaps": gaps}
    write_json(staging/"source_index.json", {"revision": model_rev, "files": files})
    write_json(staging/"download_plan.json", plan)
    print(json.dumps({"assets": len(selected), "source_bytes": plan["source_bytes"], "gaps": gaps}, indent=2))


def validate_plan(plan):
    if plan["models_repo"] != "hssd/hssd-models" or plan["license_id"] != LICENSE:
        raise ValueError("Unexpected source or license")
    if not re.fullmatch(r"[a-f0-9]{40}", plan["models_revision"]):
        raise ValueError("Source revision must be pinned")
    ids = set()
    total = 0
    for entry in plan["assets"]:
        identifier = entry["id"]
        if not re.fullmatch(r"[a-f0-9]{40}", identifier) or identifier in ids:
            raise ValueError("Invalid/duplicate ID")
        ids.add(identifier)
        f = entry["file"]
        path = safe_relative(f["path"])
        if path.parts[0] != "objects" or path.name != identifier + ".glb":
            raise ValueError("Unexpected source path")
        if type(f["size"]) is not int or not 0 < f["size"] <= plan["selection_config"]["max_asset_bytes"]:
            raise ValueError("Invalid asset size")
        if not re.fullmatch(r"[a-f0-9]{64}", f.get("sha256") or "") and not re.fullmatch(r"[a-f0-9]{40}", f.get("blob_id") or ""):
            raise ValueError("Missing upstream content checksum")
        total += f["size"]
    if total != plan["source_bytes"] or total + plan["metadata_bytes"] > min(plan["max_download_bytes"], 2000000000):
        raise ValueError("Download budget exceeded or stale total")


def verify_file(path, entry):
    f = entry["file"]
    if not path.is_file() or path.stat().st_size != f["size"]:
        raise ValueError("Missing/truncated source: " + entry["id"])
    actual = sha256(path)
    if f.get("sha256"):
        good = actual == f["sha256"]
    else:
        payload = path.read_bytes()
        good = hashlib.sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest() == f["blob_id"]
    if not good:
        raise ValueError("Source checksum mismatch: " + entry["id"])
    return actual


def download(plan, staging):
    from huggingface_hub import hf_hub_download
    validate_plan(plan)
    if shutil.disk_usage(staging).free < 5 * 10**9:
        raise ValueError("Less than 5 GB free; choose a different staging disk")
    def one(entry):
        path = staging/"sources"/safe_relative(entry["file"]["path"])
        if not path.is_file():
            path = Path(hf_hub_download(plan["models_repo"], entry["file"]["path"],
                repo_type="dataset", revision=plan["models_revision"], local_dir=staging/"sources",
                endpoint="https://huggingface.co"))
        digest = verify_file(path, entry)
        print("Verified", entry["category"], entry["id"], flush=True)
        return {"id": entry["id"], "sha256": digest, "bytes": path.stat().st_size}
    with ThreadPoolExecutor(max_workers=4) as pool:
        verified = list(pool.map(one, plan["assets"]))
    write_json(staging/"download_receipt.json", {"revision": plan["models_revision"], "assets": verified,
        "verified_bytes": sum(v["bytes"] for v in verified)})


def align_document(document, row):
    """Source semantic axes -> glTF Y-up/Z-front; absent axes remain explicitly assumed."""
    import numpy as np
    if bool(row.get("up")) != bool(row.get("front")):
        raise ValueError("Incomplete source orientation")
    up = np.array([float(v) for v in (row.get("up") or "0,1,0").split(",")])
    front = np.array([float(v) for v in (row.get("front") or "0,0,1").split(",")])
    if up.shape != (3,) or front.shape != (3,) or not np.isfinite([up, front]).all():
        raise ValueError("Invalid source orientation")
    if np.linalg.norm(up) < .9 or np.linalg.norm(front) < .9:
        raise ValueError("Degenerate source orientation")
    up /= np.linalg.norm(up); front /= np.linalg.norm(front)
    if abs(float(up @ front)) > .02:
        raise ValueError("Nonorthogonal source orientation")
    front -= up * (up @ front); front /= np.linalg.norm(front)
    right = np.cross(up, front)
    rotation = np.stack([right, up, front])
    matrix = np.eye(4); matrix[:3, :3] = rotation
    for scene in document["scenes"]:
        roots = list(scene["nodes"])
        scene["nodes"] = [len(document["nodes"])]
        document["nodes"].append({"name": "HSSDSourceAlignment", "matrix": matrix.T.flatten().tolist(), "children": roots})
    return "source_metadata_unreviewed" if row.get("up") else "assumed_gltf_axes_unreviewed"


def prepare_one(entry, plan, staging):
    path = staging/"sources"/safe_relative(entry["file"]["path"])
    source_hash = verify_file(path, entry)
    payload = path.read_bytes()
    if len(payload) < 20 or payload[:4] != b"glTF":
        raise ValueError("Invalid GLB")
    n, kind = struct.unpack_from("<II", payload, 12)
    if kind != 0x4e4f534a:
        raise ValueError("First GLB chunk must be JSON")
    header = json.loads(payload[20:20+n])
    if any(v.get("uri") and not v["uri"].startswith("data:") for k in ("images", "buffers") for v in header.get(k, [])):
        raise ValueError("External GLB dependencies require explicit acquisition")
    document, buffers = _read_gltf(path)
    if document.get("skins") or document.get("animations"):
        raise ValueError("Animated/skinned source needs separate baking")
    if set(document.get("extensionsRequired", [])).intersection({"KHR_draco_mesh_compression", "EXT_meshopt_compression", "KHR_texture_basisu"}):
        raise ValueError("Compressed source needs decoder conversion")
    confidence = align_document(document, entry["metadata"])
    roots = document["scenes"][document.get("scene", 0)]["nodes"]
    low, high = _selected_bounds(document, roots)
    extent = [high[i]-low[i] for i in range(3)]
    if any(not math.isfinite(v) or v < 1e-6 for v in extent):
        raise ValueError("Degenerate geometry")
    bounds = {"min": list(low), "max": list(high), "extent": extent}
    metrics = _document_metrics(document, bounds)
    authored = dimensions(entry["metadata"])
    scale = authored[1] / extent[1]
    physical = [v * scale for v in extent]
    findings = ["visual_review_required", "front_axis_review_required", "support_annotation_required"]
    if max(abs(a/b-1) for a,b in zip(physical, authored)) > .15:
        findings.append("source_dimensions_mismatch")
    if metrics["triangle_count"] > plan["max_runtime_triangles"]:
        findings.append("geometry_lod_required")
    if not document.get("images"):
        findings.append("no_image_textures_review_materials")
    identifier = "interior_hssd_" + entry["id"]
    canonical = _canonicalize_document(document, bounds, asset_id=identifier, source_up_axis="+Y", source_forward_axis="+Z")
    binary = _write_glb(canonical, buffers, path.parent)
    digest = hashlib.sha256(binary).hexdigest()
    dest = staging/"glb"/f"{entry['id']}_{digest[:12]}.glb"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and sha256(dest) != digest:
        raise ValueError("Corrupt existing content-addressed payload")
    if not dest.exists():
        dest.write_bytes(binary)
    return AssetRecord(asset_id=identifier, category=entry["category"],
        tags=("indoor", "hssd", entry["category"], entry["metadata"]["name"]),
        dimensions_m=(physical[2], physical[0], physical[1]), geometry_path="glb/" + dest.name,
        source="hssd_interior_prepared", license_id=LICENSE, environment="indoor",
        room_types=tuple(entry["room_types"]), quality_score=.7,
        metadata={"runtime_enabled": False, "indoor_pack_status": "candidate", "external_content": True,
          "redistribution_policy": "user_download_required", "display_name": entry["metadata"]["name"],
          "source_url": f"https://huggingface.co/datasets/{plan['models_repo']}/blob/{plan['models_revision']}/{entry['file']['path']}",
          "license_url": "https://creativecommons.org/licenses/by-nc/4.0/", "source_asset_id": entry["id"],
          "source_revision": plan["models_revision"], "metadata_revision": plan["metadata_revision"],
          "source_sha256": source_hash, "output_sha256": digest, "source_metadata": entry["metadata"],
          "placement_kind": entry["placement_kind"], "support_annotation_status": "unreviewed",
          "articulation_supported": False, "preserve_physical_proportions": True,
          "orientation": {"canonical_up_axis": "+Z", "canonical_forward_axis": "+X", "pivot": "bounds_center",
                          "orientation_confidence": confidence},
          "mesh_validation": metrics, "file_size_bytes": len(binary),
          "preparation": {"findings": findings, "geometry_decimated": False, "runtime_triangle_budget": plan["max_runtime_triangles"],
                          "scale_policy": "uniform scaling to HSSD aligned height, source proportions preserved",
                          "source_aligned_dimensions_m": authored, "source_to_metres_scale": scale}})


def prepare(plan, staging):
    validate_plan(plan)
    records, failures = [], []
    for entry in plan["assets"]:
        try:
            record = prepare_one(entry, plan, staging)
            records.append(record.to_dict())
            print("Prepared", entry["category"], entry["id"], flush=True)
        except (ValueError, KeyError, OSError) as exc:
            failures.append({"id": entry["id"], "category": entry["category"], "error": str(exc)})
            print("Held", entry["id"], str(exc), flush=True)
    write_json(staging/"candidate_registry.json", {"schema_version": "cityg.assets.v1", "assets": records})
    write_json(staging/"audit.json", {"source_count": len(plan["assets"]), "candidate_count": len(records),
        "failures": failures, "production_registry_changed": False,
        "category_counts": dict(Counter(r["category"] for r in records))})
    print("Candidates", len(records), "held", len(failures), flush=True)


def gallery(staging):
    records = json.loads((staging/"candidate_registry.json").read_text())["assets"]
    reviews = {}
    review_path = staging/"visual_review.json"
    if review_path.exists():
        review = json.loads(review_path.read_text())
        if review["candidate_registry_sha256"] == sha256(staging/"candidate_registry.json"):
            reviews = review["assets"]
    target = staging/"gallery"; (target/"images").mkdir(parents=True, exist_ok=True)
    cards = []
    for record in records:
        meta = record["metadata"]; name = record["asset_id"] + ".png"
        preview = staging/"review/previews"/name
        picture = "预览未完成"
        if preview.is_file():
            shutil.copy2(preview, target/"images"/name)
            picture = f'<a href="images/{name}"><img loading="lazy" src="images/{name}"></a>'
        decision = reviews.get(record["asset_id"], {"status": "pending", "note": "待逐件视觉验收"})
        if decision.get("preview_sha256") and (not preview.is_file() or sha256(preview) != decision["preview_sha256"]):
            decision = {"status": "pending", "note": "预览已变化，旧验收失效"}
        caption = f"{record['category']} | {meta['display_name']}"
        dims = ", ".join(f"{v:.3f}" for v in record["dimensions_m"])
        cards.append(f'<article>{picture}<h3>{html.escape(caption)}</h3><p>{record["asset_id"]}</p>'
          f'<p>{html.escape(decision["status"] + ": " + decision["note"])}</p>'
          f'<p>{dims} m | {meta["mesh_validation"]["triangle_count"]} triangles</p>'
          f'<p>{html.escape(", ".join(record["room_types"]))}</p>'
          f'<p>{html.escape(", ".join(meta["preparation"]["findings"]))}</p>'
          f'<a href="{html.escape(meta["source_url"], quote=True)}">HSSD 来源 · CC BY-NC 4.0</a></article>')
    (target/"index.html").write_text('<!doctype html><meta charset="utf-8"><title>CityG HSSD 首批候选资产</title>'
      '<style>body{font:14px system-ui;margin:20px;background:#e9eeed}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px}article{padding:12px;background:white;overflow-wrap:anywhere}article[hidden]{display:none}img{width:100%}input{padding:10px;width:90%}</style>'
      '<h1>CityG HSSD 首批候选资产</h1><p>独立候选库，尚未启用。尺寸与初始朝向来自 HSSD；正面标签为来源假设，需视觉复核。支撑面、碰撞、开合尚未验收。</p>'
      '<p>CC BY-NC 4.0 · HSSD / Habitat Synthetic Scenes Dataset · 代码与外部素材分离，不将此图库作为无许可限制资源再发布。</p>'
      '<input placeholder="搜索类别、名称或房间" oninput="document.querySelectorAll(\'article\').forEach(a=>a.hidden=!a.textContent.toLowerCase().includes(this.value.toLowerCase()))"><main>'
      + "".join(cards) + '</main>', encoding="utf-8")
    print(target/"index.html")


def review(staging, config):
    """Record explicit visual observations, bound to both registry and inspected PNGs."""
    candidate = staging/"candidate_registry.json"
    if config["candidate_registry_sha256"] != sha256(candidate):
        raise ValueError("Candidate snapshot changed; repeat visual review")
    records = {r["asset_id"]: r for r in json.loads(candidate.read_text())["assets"]}
    decisions = {}
    for entry in config["decisions"]:
        identifier = entry["asset_id"]
        if identifier not in records or identifier in decisions or entry["status"] not in {"hold", "visual_checked"}:
            raise ValueError("Invalid visual decision")
        preview = staging/"review/previews"/(identifier + ".png")
        if sha256(preview) != entry["preview_sha256"] or not entry["note"].strip():
            raise ValueError("Changed preview or missing review evidence")
        decisions[identifier] = {**entry, "runtime_enabled": False}
    write_json(staging/"visual_review.json", {"candidate_registry_sha256": config["candidate_registry_sha256"],
        "assets": decisions, "unlisted_status": "pending", "production_registry_changed": False})
    print("Recorded", len(decisions), "visual observations; no runtime promotion")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["index", "download", "prepare", "gallery", "review"])
    parser.add_argument("--config", type=Path, default=ROOT/"configs/hssd_asset_pack.json")
    parser.add_argument("--staging", type=Path, default=ROOT/"assets/prepared/hssd_v1")
    parser.add_argument("--review-config", type=Path, default=ROOT/"configs/hssd_asset_reviews.json")
    args = parser.parse_args(); args.staging.mkdir(parents=True, exist_ok=True)
    if args.action == "index":
        index(json.loads(args.config.read_text()), args.staging)
    elif args.action == "gallery":
        gallery(args.staging)
    elif args.action == "review":
        review(args.staging, json.loads(args.review_config.read_text()))
    else:
        plan = json.loads((args.staging/"download_plan.json").read_text())
        {"download": download, "prepare": prepare}[args.action](plan, args.staging)


if __name__ == "__main__":
    main()
