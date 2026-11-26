"""Offline river/bridge/polygon integration test, without model calls or downloads."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.observation import AdaptiveObservationPlanner
from cityg.pipeline import GenerationPipeline
from cityg.schemas import CitySpec
from cityg.serialization import save_json
from cityg.services import OpenUSDBackend
from cityg.viewer import export_portable_viewer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--local-assets", action="store_true", help="Use existing local assets only")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error("Output must be absent or empty; existing results are not overwritten")
    registry, materials = AssetRegistry(), MaterialLibrary()
    if args.local_assets:
        registry.load(root / "assets/asset_registry.json")
        materials.load(root / "assets/material_library.json")
    compiler = GeometryCompiler(asset_registry=registry, material_library=materials, include_interiors=False)
    spec = CitySpec.from_dict(json.loads((root / "examples/waterfront_smoke.json").read_text()))
    result = GenerationPipeline(simulation_backend=OpenUSDBackend(geometry_compiler=compiler)).run(spec, output)
    if not result.ok:
        raise RuntimeError(result.validation.to_dict())
    viewer = export_portable_viewer(output, output / "viewer")
    save_json(AdaptiveObservationPlanner(include_room_views=False).plan(result.city), output / "observation_plan.json")
    save_json({"llm": "skipped_offline", "vlm": "skipped_offline", "interiors_compiled": False,
        "physics_runtime": "not_executed", "building_count": len(list(result.city.iter_buildings())),
        "river_count": len(result.city.rivers), "bridge_count": len(result.city.bridges),
        "polygon_parcel_count": sum(bool(p.boundary) for p in result.city.iter_parcels()),
        "validation": result.validation.to_dict(),
    }, output / "waterfront_smoke_report.json")
    print(f"Waterfront portable viewer: {viewer}", flush=True)


if __name__ == "__main__":
    main()
