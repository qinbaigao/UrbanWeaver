#!/usr/bin/env python3
"""Build an isolated GLB review registry from verified source acquisitions.

No promotion, decimation, animation baking, FBX conversion or inferred placement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

from cityg.assets import AssetRecord
from cityg.asset_curation import _read_gltf, _canonicalize_document, _document_metrics, _write_glb
from cityg.facade_runtime import _selected_bounds
from scripts.download_review_sources import blob_hash
from scripts.prepare_exterior_assets import write_json


def canonicalize_review(document, bounds, asset_id, front_axis):
    if front_axis not in {"+Z", "-Z"}:
        raise ValueError(f"Unsupported reviewed source front: {front_axis}")
    normalized = _canonicalize_document(document, bounds, asset_id=asset_id,
                                       source_up_axis="+Y", source_forward_axis=front_axis)
    # The shared helper records source axes but always maps source +Z to +X.
    # Apply an actual half-turn for sources whose visible front is -Z.
    if front_axis == "-Z":
        for scene in normalized["scenes"]:
            for root in scene["nodes"]:
                matrix = normalized["nodes"][root]["matrix"]
                for index in (0, 4, 8, 12, 1, 5, 9, 13):
                    matrix[index] *= -1
    return normalized


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=Path("assets/incoming/exterior_v3_sources"))
    parser.add_argument("--output", type=Path, default=Path("assets/prepared/exterior_v3/source_review"))
    parser.add_argument("--config", type=Path, default=Path("configs/exterior_review_sources_v3.json"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((args.sources / "acquisition_manifest.json").read_text())
    config = json.loads(args.config.read_text())
    annotations = {(p["repo"], g["id"]): g for p in config["providers"] for g in p["groups"]}
    expected = {r["relative"]: r for r in manifest["files"]}
    records = []
    for group in manifest["groups"]:
        if group["status"] != "downloaded_pending_conversion_review":
            continue
        annotation = annotations.get((group["repo"], group["id"]), {})
        group = {**group, **annotation}
        for relative in group["local_files"]:
            if not relative.endswith(".glb"):
                continue
            path = args.sources / relative
            if blob_hash(path) != expected[relative]["sha"]:
                raise ValueError(f"Source changed: {path}")
            document, buffers = _read_gltf(path)
            roots = document["scenes"][document.get("scene", 0)]["nodes"]
            low, high = _selected_bounds(document, roots)
            extent = [high[i] - low[i] for i in range(3)]
            if any(not math.isfinite(v) or v <= 0 for v in extent):
                raise ValueError(f"Invalid source bounds: {path}")
            bounds = {"min": list(low), "max": list(high), "extent": extent}
            asset_id = f"review_v3_{group['id']}"
            metrics = _document_metrics(document, bounds)
            front_axis = group.get("source_forward_axis", "+Z")
            source_scale = float(group.get("source_meters_per_unit", 1.0))
            if not math.isfinite(source_scale) or source_scale <= 0:
                raise ValueError("Invalid source unit scale")
            normalized = canonicalize_review(document, bounds, asset_id, front_axis)
            binary = _write_glb(normalized, buffers, path.parent)
            sha = hashlib.sha256(binary).hexdigest()
            destination = args.output / "glb" / f"{asset_id}_{sha[:12]}.glb"
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                destination.write_bytes(binary)
            elif hashlib.sha256(destination.read_bytes()).hexdigest() != sha:
                raise ValueError(f"Changed review payload: {destination}")
            records.append(AssetRecord(asset_id, group["category"],
                tags=(group["id"], "manual_only", "source_review"), environment="outdoor",
                geometry_path=os.path.relpath(destination, args.output),
                dimensions_m=tuple(v * source_scale for v in (extent[2], extent[0], extent[1])),
                license_id=group["license_id"], source=group["repo"], quality_score=.5,
                metadata={"outdoor_pack_status": "candidate", "source_url": group["source_url"],
                    "upstream_asset_metadata": document.get("asset", {}),
                    "source_file": os.path.relpath(path, args.output), "source_git_blob_sha": expected[relative]["sha"],
                    "orientation": {"canonical_up_axis": "+Z", "canonical_forward_axis": "+X",
                                    "orientation_confidence": "unreviewed"},
                    "source_meters_per_unit": source_scale,
                    "scale_policy": "source units with explicit curated unit conversion; verify physical size before placement",
                    "front_policy": f"source {front_axis}; explicit override where visually checked",
                    "mesh_validation": metrics, "required_extensions": document.get("extensionsRequired", []),
                    "extensions_used": document.get("extensionsUsed", []),
                    "automatic_runtime_placement": False, "output_sha256": sha}).to_dict())
    write_json(args.output / "candidate_registry.json", {"schema_version": "cityg.assets.v1", "assets": records})
    print(f"Prepared {len(records)} isolated review GLBs; production registry unchanged")


if __name__ == "__main__":
    main()
