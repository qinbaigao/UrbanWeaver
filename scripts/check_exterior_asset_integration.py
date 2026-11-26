#!/usr/bin/env python3
"""Offline, four-building exterior regression for prepared assets (no LLM/VLM)."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.planning import BaselineCityPlanner
from cityg.schemas import CitySpec, ZoneSpec
from cityg.serialization import save_json
from cityg.services import OpenUSDBackend
from cityg.validation import CityValidator
from cityg.viewer import export_portable_viewer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--export-viewer", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="Recompile this script's own prior test output without deleting files")
    parser.add_argument("--candidate-registry", type=Path, help="Report only promoted members of this preparation batch")
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        marker = args.output / "asset_integration_report.json"
        if (not args.refresh or not marker.is_file() or
                json.loads(marker.read_text()).get("scope") != "offline_asset_integration_not_end_to_end_agent_run"):
            parser.error("Output must be absent/empty, or use --refresh on this script's own marked test output")
    root = Path(__file__).resolve().parents[1]
    registry = AssetRegistry(root / "assets/asset_registry.json")
    materials = MaterialLibrary(root / "assets/material_library.json")
    spec = CitySpec(name="exterior_asset_integration", width_m=260, depth_m=240,
                    building_count=4, min_floors=2, max_floors=4, rooms_per_floor=2,
                    open_space_ratio=.3, seed=29, zones=(
                        ZoneSpec("homes", "residential", 1),
                        ZoneSpec("shops", "commercial", 1),
                        ZoneSpec("public", "public_service", 1)))
    city = BaselineCityPlanner().plan(spec)
    compiler = GeometryCompiler(asset_registry=registry, material_library=materials, include_interiors=False)
    scene = compiler.compile(city)
    city_report = CityValidator().validate(city)
    geometry_report = GeometryValidator().validate(city, scene)
    used = Counter(p.metadata["asset_id"] for p in scene.primitives if p.metadata.get("asset_id"))
    prepared = [r for r in registry.list_all() if r.source.endswith("_exterior_prepared")]
    if args.candidate_registry:
        candidate_ids = {r.asset_id for r in AssetRegistry(args.candidate_registry).list_all()}
        prepared = [r for r in prepared if r.asset_id in candidate_ids]
    selected = {r.asset_id: used[r.asset_id] for r in prepared if used[r.asset_id]}
    invalid = [key for key in used if (r := registry.get(key)) and (
        r.metadata.get("outdoor_pack_status") in {"candidate", "rejected"} or "manual_only" in r.tags)]
    report = {
        "scope": "offline_asset_integration_not_end_to_end_agent_run",
        "building_count": len(list(city.iter_buildings())), "interiors_compiled": False,
        "llm_used": False, "vlm_used": False,
        "city_validation": city_report.to_dict(), "geometry_validation": geometry_report.to_dict(),
        "prepared_available": len(prepared), "prepared_used_unique": len(selected),
        "prepared_instance_count": sum(selected.values()), "prepared_usage": selected,
        "prepared_not_selected": [r.asset_id for r in prepared if not used[r.asset_id]],
        "unapproved_or_manual_assets_used": invalid,
        "ok": city_report.ok and geometry_report.ok and bool(selected) and not invalid,
    }
    save_json(report, args.output / "asset_integration_report.json")
    if not report["ok"]:
        raise RuntimeError("Asset integration failed; see report")
    if args.export_viewer:
        backend = OpenUSDBackend(compiler)
        save_json(city_report.to_dict(), args.output / "scene/validation_report.json")
        backend.compile(city, args.output / "scene", _scene_override=scene)
        if args.refresh and (args.output / "viewer").exists():
            backup = args.output / ("viewer_previous_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"))
            (args.output / "viewer").rename(backup)
        export_portable_viewer(args.output / "scene", args.output / "viewer")
    print(f"Prepared assets used: {len(selected)} types / {sum(selected.values())} instances")
    print(args.output / "asset_integration_report.json")


if __name__ == "__main__":
    main()
