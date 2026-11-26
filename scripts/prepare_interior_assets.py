#!/usr/bin/env python3
"""Prepare a bounded, auditable indoor asset pack, without changing runtime selection.

Powered by Poly Haven. Reuses the existing checksum-verified glTF downloader and
normalizer. Staging records are separate from the production asset registry.
"""
import argparse
from dataclasses import replace
import json
import html
import math
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.prepare_exterior_assets import (acquire, prepare_record, write_json, metadata,
    bundle_files, safe_relative, checked_url, checksum, local_files)

ROOT = Path(__file__).resolve().parents[1]
SURFACE_CATEGORIES = {"laptop", "desk_lamp", "alarm_clock", "notebook", "book_bundle", "book",
                      "stationery_bundle", "vase", "small_plant", "basket", "pillow_bundle", "magazine"}


def verify_source(entry, staging):
    for name, info in entry["files"].items():
        path = staging/"sources"/entry["id"]/safe_relative(name)
        if not path.is_file() or checksum(path) != info["md5"] or path.stat().st_size != info["size"]:
            raise ValueError(f"Source missing or changed: {entry['id']}/{name}")


def convert_blend(config, staging, blender):
    plan = json.loads((staging/"download_plan.json").read_text())
    specs = {s["id"]: s for s in config["assets"]}
    for entry in plan["assets"]:
        if entry.get("source_format") != "blend": continue
        verify_source(entry, staging)
        names = sorted({n for v in specs[entry["id"]].get("variants", []) for n in v.get("nodes", [])})
        if not names: raise ValueError("Blender conversion needs explicit object selectors")
        source = staging/"sources"/entry["id"]/f"{entry['id']}_{config['resolution']}.blend"
        output = staging/"converted"/entry["id"]/f"{entry['id']}_{config['resolution']}.gltf"
        output.parent.mkdir(parents=True, exist_ok=True)
        command = [blender, "--background", "--factory-startup", "--disable-autoexec", "--threads", "2",
                   "--python-exit-code", "1", "--python", str(ROOT/"scripts/blender_interior_source.py"),
                   "--", "--source", str(source.resolve()), "--output", str(output.resolve())]
        command.extend(["--bake-materials", "--resolution", "1024"])
        for name in names: command.extend(["--object", name])
        with (output.parent/"conversion.log").open("w") as stream:
            subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=900)
        write_json(output.parent/"conversion_manifest.json", {"source_files": entry["files"],
            "selected_objects": names, "files": local_files(output), "autoexec_disabled": True,
            "material_bake": {"engine": "Cycles CPU", "resolution": 1024, "channels": ["base_color", "roughness", "normal"]}})
        print("Converted", entry["id"], len(names), "selected objects", flush=True)


def build_plan(config, staging):
    entries = []
    seen = set()
    for spec in config["assets"]:
        asset_id = spec["id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", asset_id) or asset_id in seen:
            raise ValueError("Invalid or duplicate indoor source ID")
        seen.add(asset_id)
        files = metadata(asset_id, staging)
        if config["resolution"] in files.get("gltf", {}):
            bundle = bundle_files(asset_id, files, config["resolution"])
            source_format = "gltf"
        else:
            value = files["blend"][config["resolution"]]["blend"]
            bundle = {f"{asset_id}_{config['resolution']}.blend": {k: value[k] for k in ("url", "md5", "size")},
                      **value.get("include", {})}
            source_format = "blend"
        for name, info in bundle.items():
            safe_relative(name); checked_url(info["url"])
            if not re.fullmatch(r"[a-f0-9]{32}", info["md5"]) or type(info["size"]) is not int or info["size"] <= 0:
                raise ValueError("Invalid source checksum/size")
        entry = {**spec, "files": bundle, "source_format": source_format,
                 "size_bytes": sum(int(f["size"]) for f in bundle.values())}
        entries.append(entry)
        print(f"Plan {asset_id} ({source_format}): {entry['size_bytes']/2**20:.1f} MiB", flush=True)
    total = sum(e["size_bytes"] for e in entries)
    if total > config["max_download_mib"]*2**20:
        raise ValueError("Indoor pack exceeds download budget")
    plan = {"schema_version": "cityg.interior_download_plan.v1", "provider": "polyhaven",
            "license_id": "CC0-1.0", "resolution": config["resolution"], "total_bytes": total, "assets": entries}
    write_json(staging/"download_plan.json", plan)
    return plan


def prepare_indoor_record(entry, resolution, staging, budget):
    # Reuse the static normalizer, but do not retain its outdoor taxonomy.
    record = prepare_record({**entry, "id_prefix": "interior", "contexts": entry.get("room_types", [])}, resolution, staging, budget)
    metadata = {k: v for k, v in record.metadata.items() if k not in
                {"outdoor_pack_status", "placement_yaw_offset_deg", "ground_anchor_fraction"}}
    kind = "surface" if entry["category"] in SURFACE_CATEGORIES else "floor"
    metadata.update(indoor_pack_status="candidate", placement_kind=entry.get("placement_kind", kind),
                    runtime_enabled=False, support_annotation_status="unreviewed")
    dimensions = record.dimensions_m
    if "longest_side_m" in entry:
        size = float(entry["longest_side_m"])
        if not math.isfinite(size) or size <= 0:
            raise ValueError("Invalid curated longest side")
        dimensions = tuple(value * size / max(dimensions) for value in dimensions)
        metadata["preparation"] = {**metadata["preparation"],
            "scale_policy": "uniform physical scaling from curated longest side; source proportions preserved"}
    if entry.get("source_format") == "blend":
        metadata["conversion_manifest"] = f"converted/{entry['id']}/conversion_manifest.json"
    return replace(record, asset_id=record.asset_id.replace("prepared_", "interior_", 1),
                   dimensions_m=dimensions,
                   tags=tuple("indoor" if tag == "outdoor" else tag for tag in record.tags),
                   environment="indoor", room_types=tuple(entry.get("room_types", [])),
                   source="polyhaven_interior_prepared", metadata=metadata)


def prepare(config, staging):
    plan = json.loads((staging / "download_plan.json").read_text())
    specs = {entry["id"]: entry for entry in config["assets"]}
    if set(specs) != {entry["id"] for entry in plan["assets"]} or config["resolution"] != plan["resolution"]:
        raise ValueError("Sources changed; rerun plan/download")
    records, failures, pending = [], [], []
    for downloaded in plan["assets"]:
        # Retain verified transport facts, not stale semantic/bundle flags from
        # the first download plan after curation changes the node selection.
        entry = {**{k: downloaded[k] for k in ("files", "source_format", "size_bytes") if k in downloaded},
                 **specs[downloaded["id"]]}
        if entry.get("defer_reason"):
            verify_source(downloaded, staging)
            pending.append({"id": entry["id"], "reason": entry["defer_reason"]})
            continue
        if entry.get("source_format") == "blend":
            verify_source(downloaded, staging)
            source = staging/"converted"/entry["id"]/f"{entry['id']}_{config['resolution']}.gltf"
            manifest_path = source.parent/"conversion_manifest.json"
            if not source.is_file() or not manifest_path.is_file():
                pending.append({"id": entry["id"], "reason": "blend_export_and_component_review_required"})
                continue
            conversion = json.loads(manifest_path.read_text())
            if conversion["source_files"] != downloaded["files"] or local_files(source) != conversion["files"]:
                raise ValueError("Stale or modified Blender conversion")
            entry.update(local_source=str(source.resolve().relative_to(ROOT)), provider="polyhaven", license_id="CC0-1.0",
                         source_url=f"https://polyhaven.com/a/{entry['id']}", files=conversion["files"])
        for variant in entry.get("variants", [{}]):
            selected = {**entry, **variant}
            try:
                record = prepare_indoor_record(selected, config["resolution"], staging, config["max_runtime_triangles"])
                records.append(record)
                print("Prepared", record.asset_id, record.metadata["mesh_validation"]["triangle_count"], flush=True)
            except (ValueError, KeyError, FileNotFoundError) as exc:
                failures.append({"id": entry["id"], "variant": variant, "error": str(exc)})
                print("Rejected", entry["id"], str(exc), flush=True)
    write_json(staging / "candidate_registry.json", {"schema_version": "cityg.assets.v1",
        "assets": [r.to_dict() for r in records]})
    write_json(staging / "audit.json", {"source_count": len(plan["assets"]), "candidate_count": len(records),
        "failures": failures, "pending_conversion": pending, "production_registry_changed": False,
        "assets": [{"asset_id": r.asset_id, "category": r.category, "dimensions_m": r.dimensions_m,
                    "triangles": r.metadata["mesh_validation"]["triangle_count"],
                    "file_size_bytes": r.metadata["file_size_bytes"],
                    "findings": r.metadata["preparation"]["findings"]} for r in records]})
    if failures:
        raise RuntimeError("Some candidates failed preparation; see audit.json")


def gallery(staging):
    from cityg.assets import AssetRegistry
    registry = AssetRegistry(staging/"candidate_registry.json")
    review_path = staging/"visual_review.json"
    review_document = json.loads(review_path.read_text()) if review_path.is_file() else {}
    snapshot = hashlib.sha256((staging/"candidate_registry.json").read_bytes()).hexdigest()
    reviews = review_document.get("assets", {}) if review_document.get("candidate_registry_sha256") == snapshot else {}
    target = staging/"gallery"
    (target/"images").mkdir(parents=True, exist_ok=True)
    cards = []
    for index, record in enumerate(registry.list_all()):
        preview = staging/"review/previews"/f"{record.asset_id}.png"
        image = "<p>Preview unavailable</p>"
        if preview.is_file():
            shutil.copy2(preview, target/"images"/preview.name)
            image = f'<a href="images/{preview.name}"><img src="images/{preview.name}"></a>'
        review = reviews.get(record.asset_id, {"status": "pending", "note": "尚未视觉验收；不自动进入生产库"})
        if review.get("preview_sha256") and (not preview.is_file() or
                hashlib.sha256(preview.read_bytes()).hexdigest() != review["preview_sha256"]):
            review = {"status": "pending", "note": "预览已变更，需重新检查"}
        text = f"{index+1}. {record.asset_id} | {record.category} | {review['status']}"
        cards.append(f'<article data-index="{index}">{image}<h3>{html.escape(text)}</h3>'
            f'<p>{html.escape(review["note"])}</p><p>{html.escape(str(tuple(round(v, 3) for v in record.dimensions_m)))} m (估计) | '
            f'{record.metadata["mesh_validation"]["triangle_count"]} triangles</p>'
            f'<p>{html.escape(", ".join(record.room_types))} | CC0</p>'
            f'<a href="{html.escape(record.metadata["source_url"], quote=True)}">官方来源</a></article>')
    (target/"index.html").write_text('''<!doctype html><meta charset="utf-8"><title>CityG 室内资产准备</title>
<style>body{font:14px system-ui;background:#e8eeeb;margin:16px}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}article{background:white;padding:10px;overflow-wrap:anywhere}article[hidden]{display:none}img{width:100%}h3{font-size:13px}input{padding:10px;width:90%}</style>
<h1>CityG 室内资产候选包</h1><p>Powered by <a href="https://polyhaven.com">Poly Haven</a> · CC0 · 四视图 · 不自动替换生产资产</p>
<p>尺寸来自等比估计，不是实测；“正面”标签在未审核前只代表暂定轴。可直接下载整个 gallery 文件夹离线打开本页。</p>
<input id="filter" placeholder="筛选类别、名称、房间或状态"><main>'''+"".join(cards)+'''</main>
<script>const q=new URLSearchParams(location.search),start=Number(q.get('start')||0),count=Number(q.get('count')||1000);
function filter(){document.querySelectorAll('article').forEach(a=>a.hidden=Number(a.dataset.index)<start||Number(a.dataset.index)>=start+count||!a.textContent.toLowerCase().includes(document.querySelector('input').value.toLowerCase()))}document.querySelector('input').oninput=filter;filter();</script>''', encoding="utf-8")
    print(target/"index.html", flush=True)


def apply_review(staging, review_config):
    """Attach explicit, snapshot-bound human/assistant observations, not auto approval."""
    from cityg.assets import AssetRegistry
    candidate = staging/"candidate_registry.json"
    snapshot = hashlib.sha256(candidate.read_bytes()).hexdigest()
    if snapshot != review_config["candidate_registry_sha256"]:
        raise ValueError("Candidate snapshot changed; inspect new previews before updating review")
    registry = AssetRegistry(candidate)
    decisions = {}
    for group in review_config["decisions"]:
        for source in group["sources"]:
            if source in decisions: raise ValueError("Duplicate source review")
            decisions[source] = {k: v for k, v in group.items() if k != "sources"}
    if set(decisions) != {r.metadata["source_asset_id"] for r in registry.list_all()}:
        raise ValueError("Review must explicitly cover exactly the prepared sources")
    preview_hashes = {r.asset_id: hashlib.sha256((staging/"review/previews"/f"{r.asset_id}.png").read_bytes()).hexdigest()
                      for r in registry.list_all()}
    preview_snapshot = hashlib.sha256(json.dumps(preview_hashes, sort_keys=True).encode()).hexdigest()
    if preview_snapshot != review_config["previews_sha256"]:
        raise ValueError("Preview snapshot changed; re-inspection required")
    records, reviews = [], {}
    overrides = review_config.get("asset_overrides", {})
    if set(overrides) - {r.asset_id for r in registry.list_all()}:
        raise ValueError("Review override refers to an unknown asset")
    for record in registry.list_all():
        decision = {**decisions[record.metadata["source_asset_id"]], **overrides.get(record.asset_id, {})}
        geometry = registry.resolve_path(record.geometry_path)
        if hashlib.sha256(geometry.read_bytes()).hexdigest() != record.metadata["output_sha256"]:
            raise ValueError("GLB changed since preparation")
        preview = staging/"review/previews"/f"{record.asset_id}.png"
        if not preview.is_file(): raise ValueError(f"Missing reviewed preview: {preview}")
        reviews[record.asset_id] = {**decision, "method": "assistant_four_view_inspection",
            "output_sha256": record.metadata["output_sha256"],
            "preview_sha256": hashlib.sha256(preview.read_bytes()).hexdigest(),
            "dimensions_m": record.dimensions_m, "runtime_enabled": False}
        meta = {**record.metadata, "visual_review": reviews[record.asset_id]}
        # This separate snapshot is still a candidate: no production promotion.
        records.append(replace(record, metadata=meta))
    write_json(staging/"visual_review.json", {"candidate_registry_sha256": snapshot,
        "scope": "visual inspection only; runtime placement/support not certified", "assets": reviews})
    write_json(staging/"reviewed_registry.json", {"schema_version": "cityg.assets.v1",
        "assets": [r.to_dict() for r in records]})
    print(f"Recorded {len(reviews)} visual decisions; production registry untouched", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "download", "convert-blend", "prepare", "review", "gallery"])
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/interior_asset_pack.json")
    parser.add_argument("--staging", type=Path, default=ROOT / "assets/prepared/interior_v1")
    parser.add_argument("--review-config", type=Path, default=ROOT / "configs/interior_asset_reviews.json")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    args.staging.mkdir(parents=True, exist_ok=True)
    print("Powered by Poly Haven — indoor candidate preparation; production registry untouched", flush=True)
    if args.action == "review":
        apply_review(args.staging, json.loads(args.review_config.read_text()))
    elif args.action == "convert-blend":
        convert_blend(config, args.staging, args.blender)
    elif args.action == "gallery":
        gallery(args.staging)
    elif args.action == "prepare":
        prepare(config, args.staging)
    else:
        plan = build_plan(config, args.staging)
        print(f"Source download: {plan['total_bytes']/2**20:.1f} MiB", flush=True)
        if args.action == "download":
            acquire(plan, args.staging)


if __name__ == "__main__":
    main()
