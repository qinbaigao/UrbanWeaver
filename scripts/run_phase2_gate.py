"""Run structural G2-A on all ten Phase 2 research scenes."""

from __future__ import annotations

import argparse
import json
import random
import resource
import tempfile
import time
from pathlib import Path

from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.planning import BaselineCityPlanner
from cityg.runtime import ActivationManager, NavigationQuery, run_interaction_smoke
from cityg.schemas import CitySpec
from cityg.serialization import save_json
from cityg.usd import UsdaPackageValidator, UsdaWriter
from cityg.validation import CityValidator


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run CityG structural G2-A")
    parser.add_argument(
        "--spec-dir", type=Path, default=Path("examples/research_specs")
    )
    parser.add_argument(
        "--report", type=Path, default=Path("outputs/phase2_gate_report.json")
    )
    parser.add_argument(
        "--keep-usd-dir",
        type=Path,
        help="Optional directory in which all ten USDA packages are retained",
    )
    parser.add_argument("--queries-per-scene", type=int, default=200)
    return parser


def _sample_paths(scene, count: int, seed: int) -> float:
    query = NavigationQuery(scene.navigation)
    outdoors = [
        node.id for node in scene.navigation.nodes if node.node_type == "outdoor_junction"
    ]
    rooms = [node.id for node in scene.navigation.nodes if node.node_type == "room"]
    rng = random.Random(seed)
    successes = 0
    for _ in range(count):
        start = rng.choice(outdoors)
        end = rng.choice(rooms)
        successes += query.shortest_path(start, end, allow_interaction=True) is not None
    return successes / count


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.queries_per_scene < 1:
        raise ValueError("queries-per-scene must be positive")
    specs = sorted(args.spec_dir.glob("[0-9][0-9]_*.json"))
    if len(specs) != 10:
        raise ValueError(f"Expected 10 research specs, found {len(specs)}")

    planner = BaselineCityPlanner()
    compiler = GeometryCompiler()
    geometry_validator = GeometryValidator()
    usd_writer = UsdaWriter()
    results = []
    prototypes = set()
    total_queries = 0
    total_successes = 0.0

    temporary = None
    if args.keep_usd_dir:
        package_root = args.keep_usd_dir
        package_root.mkdir(parents=True, exist_ok=True)
    else:
        temporary = tempfile.TemporaryDirectory(prefix="cityg-phase2-")
        package_root = Path(temporary.name)

    try:
        for index, spec_path in enumerate(specs):
            data = json.loads(spec_path.read_text(encoding="utf-8"))
            spec = CitySpec.from_dict(data)
            started = time.perf_counter()
            city = planner.plan(spec)
            city_report = CityValidator().validate(city)
            if not city_report.ok:
                print(f"FAIL {spec.name}: semantic validation")
                return 1
            scene = compiler.compile(city)
            geometry_report = geometry_validator.validate(city, scene)
            interaction_report = run_interaction_smoke(scene)
            scene_dir = package_root / spec_path.stem
            save_json(city, scene_dir / "city.json")
            save_json(scene, scene_dir / "geometry_manifest.json")
            usd_paths = usd_writer.write(city, scene, scene_dir / "usd")
            usd_report = UsdaPackageValidator().validate(scene_dir / "usd" / "city.usda")
            if not geometry_report.ok or not interaction_report.ok or not usd_report.ok:
                print(
                    f"FAIL {spec.name}: geometry={geometry_report.ok} "
                    f"interaction={interaction_report.ok} usd={usd_report.ok}"
                )
                return 1

            sampled_ratio = _sample_paths(
                scene, args.queries_per_scene, spec.seed + index
            )
            total_queries += args.queries_per_scene
            total_successes += sampled_ratio * args.queries_per_scene
            activation = ActivationManager(scene)
            building = next(city.iter_buildings())
            floor = building.floors[0]
            overview_count = activation.primitive_count(activation.select("overview"))
            active_floor_count = activation.primitive_count(
                activation.select(
                    "active_floor", building_id=building.id, floor_id=floor.id
                )
            )
            elapsed = time.perf_counter() - started
            prototypes.update(scene.building_prototypes.values())
            result = {
                "spec": spec_path.stem,
                "buildings": len(list(city.iter_buildings())),
                "floors": len(list(city.iter_floors())),
                "rooms": len(list(city.iter_rooms())),
                "primitives": len(scene.primitives),
                "overview_primitives": overview_count,
                "sample_active_floor_primitives": active_floor_count,
                "state_machines": len(scene.state_machines),
                "navigation_nodes": len(scene.navigation.nodes),
                "sampled_path_ratio": sampled_ratio,
                "structural_physics_errors": len(interaction_report.errors),
                "usda_layers": len(usd_paths),
                "reference_arcs": usd_report.metrics["reference_arc_count"],
                "payload_arcs": usd_report.metrics["payload_arc_count"],
                "instanceable_prims": usd_report.metrics["instanceable_prim_count"],
                "usda_bytes": usd_report.metrics["package_bytes"],
                "compile_and_check_seconds": round(elapsed, 6),
            }
            results.append(result)
            print(
                f"OK {spec_path.stem}: {result['buildings']} buildings, "
                f"{result['primitives']} primitives, path={sampled_ratio:.3f}, "
                f"{elapsed:.2f}s"
            )
    finally:
        if temporary is not None:
            temporary.cleanup()

    overall_ratio = total_successes / total_queries
    report = {
        "status": "structural_g2_passed" if overall_ratio >= 0.95 else "failed",
        "scene_count": len(results),
        "all_scenes_have_20_plus_buildings": all(
            result["buildings"] >= 20 for result in results
        ),
        "sampled_query_count": total_queries,
        "outdoor_to_room_path_ratio": overall_ratio,
        "structural_physics_error_count": sum(
            result["structural_physics_errors"] for result in results
        ),
        "building_prototypes": sorted(prototypes),
        "peak_process_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "curves": results,
        "remaining_g2_checks": [
            "Run representative packages with pinned ovphysx in forced CPU-only mode",
            "Record PhysX step RTF, memory, rigid-body drift, and collision queries",
            "Optionally check compatibility with Isaac Sim on a supported RTX GPU",
        ],
    }
    save_json(report, args.report)
    print(
        f"Structural G2-A passed: {len(results)}/10 scenes, {overall_ratio:.3f} path ratio, "
        f"0 structural smoke errors. Report: {args.report}"
    )
    return 0 if report["status"] == "structural_g2_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
