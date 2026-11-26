"""Offline curve integration check; no LLM, VLM, downloads or browser launch."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler
from cityg.observation import AdaptiveObservationPlanner
from cityg.paths import PlanarPath2D, sample_cubic_bezier
from cityg.pipeline import GenerationPipeline
from cityg.schemas import Bounds2D, City, CitySpec, Junction, Point2D, RoadNetwork, RoadSegment
from cityg.serialization import save_json
from cityg.services import OpenUSDBackend
from cityg.usd import UsdaWriter
from cityg.viewer import export_portable_viewer


def junction_fixture() -> City:
    """One gentle S-shaped main street, split only at two true branch junctions."""
    trunk = PlanarPath2D(sample_cubic_bezier(Point2D(15, 95), Point2D(70, 30),
                                           Point2D(130, 150), Point2D(205, 85)))
    stations = (0, trunk.length*.33, trunk.length*.67, trunk.length)
    points = [trunk.point(s) for s in stations]
    junctions = [Junction(f"junction_{i}", p) for i, p in enumerate(points)]
    roads = [RoadSegment(f"main_{i}", f"junction_{i}", f"junction_{i+1}",
                        trunk.slice(a, b).points, road_class="collector", width_m=14,
                        sidewalk_width_m=2.5, parking_allowed=False)
             for i, (a, b) in enumerate(zip(stations, stations[1:]))]
    for index, start, end, controls in (
        (1, points[1], Point2D(70, 175), (Point2D(60, 112), Point2D(78, 150))),
        (2, points[2], Point2D(150, 15), (Point2D(151, 66), Point2D(142, 38))),
    ):
        terminal = f"terminal_{index}"
        junctions.append(Junction(terminal, end))
        roads.append(RoadSegment(f"branch_{index}", f"junction_{index}", terminal,
            sample_cubic_bezier(start, *controls, end), road_class="local", width_m=8,
            sidewalk_width_m=2, parking_allowed=False))
    city = City("curved_junction_fixture", "Curved main street + two branches",
                Bounds2D(0, 0, 220, 190), RoadNetwork(junctions, roads))
    city.world_program = build_world_program(city, producer="offline_curve_fixture", seed=12)
    return city


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--local-assets", action="store_true", help="Use already-downloaded assets, without downloading or generating any")
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
    spec = CitySpec.from_dict(json.loads((root / "examples/curved_roads_smoke.json").read_text()))
    result = GenerationPipeline(simulation_backend=OpenUSDBackend(geometry_compiler=compiler)).run(spec, output)
    if not result.ok:
        raise RuntimeError(result.validation.to_dict())
    viewer = export_portable_viewer(output, output / "viewer")
    save_json(AdaptiveObservationPlanner(include_room_views=False).plan(result.city), output / "observation_plan.json")
    print(f"Four-building scene: {viewer}", flush=True)
    # The isolated fixture intentionally has no buildings: write it directly,
    # since the full pipeline requires at least one building and its payloads.
    city = junction_fixture()
    scene = compiler.compile(city)
    fixture = output / "junction_fixture"
    save_json(city, fixture / "city.json")
    save_json(scene, fixture / "geometry_manifest.json")
    save_json(scene.navigation, fixture / "navigation.json")
    save_json({"state_machines": scene.state_machines}, fixture / "interactions.json")
    backend = OpenUSDBackend(geometry_compiler=compiler)
    backend._export_asset_registry(scene, fixture)
    backend._export_material_library(scene, fixture)
    UsdaWriter().write(city, scene, fixture / "usd")
    export_portable_viewer(fixture, fixture / "viewer")
    save_json({"llm": "skipped_offline", "vlm": "skipped_offline", "interiors_compiled": False,
        "building_count": len(list(result.city.iter_buildings())),
        "curved_road_count": sum(len(r.centerline) > 2 for r in result.city.road_network.segments),
        "fixture_road_count": len(city.road_network.segments),
        "fixture_navigation_nodes": len(scene.navigation.nodes),
    }, output / "curve_smoke_report.json")
    print(f"Curved main street + branches: {fixture / 'viewer'}", flush=True)


if __name__ == "__main__":
    main()
