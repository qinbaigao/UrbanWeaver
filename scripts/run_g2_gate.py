"""Run the formal Phase 2 gate: structural checks plus ovphysx CPU simulation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from cityg.geometry import GeometryCompiler
from cityg.serialization import load_city, save_json
from cityg.usd import UsdaPackageValidator, UsdaWriter


DEFAULT_RUNTIME_SPECS = (
    "01_residential_neighborhood",
    "05_industrial_logistics",
    "07_compact_vertical_core",
    "10_scalability_stress",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run CityG formal Gate G2")
    parser.add_argument("--spec-dir", type=Path, default=Path("examples/research_specs"))
    parser.add_argument("--work-dir", type=Path, default=Path("outputs/g2_ovphysx"))
    parser.add_argument("--runtime-spec", action="append", dest="runtime_specs")
    parser.add_argument("--queries-per-scene", type=int, default=200)
    parser.add_argument("--physics-steps", type=int, default=600)
    parser.add_argument("--min-realtime-factor", type=float, default=0.5)
    return parser


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.queries_per_scene < 1 or args.physics_steps < 1:
        raise ValueError("query and physics step counts must be positive")
    if args.min_realtime_factor <= 0:
        raise ValueError("min-realtime-factor must be positive")

    script_dir = Path(__file__).resolve().parent
    args.work_dir.mkdir(parents=True, exist_ok=True)
    package_dir = args.work_dir / "packages"
    structural_report_path = args.work_dir / "structural_report.json"
    structural_command = [
        sys.executable,
        str(script_dir / "run_phase2_gate.py"),
        "--spec-dir",
        str(args.spec_dir),
        "--report",
        str(structural_report_path),
        "--keep-usd-dir",
        str(package_dir),
        "--queries-per-scene",
        str(args.queries_per_scene),
    ]
    structural = subprocess.run(structural_command, check=False)
    structural_report = (
        json.loads(structural_report_path.read_text(encoding="utf-8"))
        if structural_report_path.is_file()
        else {"status": "missing"}
    )

    runtime_results = []
    runtime_specs = tuple(args.runtime_specs or DEFAULT_RUNTIME_SPECS)
    for spec_name in runtime_specs:
        source_dir = package_dir / spec_name
        city = load_city(source_dir / "city.json")
        scene = GeometryCompiler().compile(city)
        active_building = next(city.iter_buildings())
        active_floor = active_building.floors[0]
        runtime_package = args.work_dir / "runtime_packages" / spec_name
        save_json(city, runtime_package / "city.json")
        save_json(scene, runtime_package / "geometry_manifest.json")
        UsdaWriter().write(
            city,
            scene,
            runtime_package / "usd",
            active_floor_id=active_floor.id,
        )
        stage = runtime_package / "usd" / "city.usda"
        package_report = UsdaPackageValidator().validate(stage)
        save_json(
            package_report.to_dict(), runtime_package / "usd_validation_report.json"
        )
        if not package_report.ok:
            raise RuntimeError(
                f"Active-floor USD validation failed for {spec_name}"
            )
        report_path = args.work_dir / f"ovphysx_{spec_name}.json"
        log_path = args.work_dir / f"ovphysx_{spec_name}.log"
        command = [
            sys.executable,
            str(script_dir / "ovphysx_runtime_check.py"),
            str(stage),
            "--report",
            str(report_path),
            "--physics-steps",
            str(args.physics_steps),
            "--active-floor-id",
            active_floor.id,
        ]
        with log_path.open("w", encoding="utf-8") as log:
            completed = subprocess.run(
                command, check=False, stdout=subprocess.DEVNULL, stderr=log
            )
        result = (
            json.loads(report_path.read_text(encoding="utf-8"))
            if report_path.is_file()
            else {
                "ok": False,
                "errors": ["missing_ovphysx_report"],
            }
        )
        result["spec"] = spec_name
        result["exit_code"] = completed.returncode
        result["log"] = str(log_path)
        runtime_results.append(result)
        print(
            f"{'OK' if result.get('ok') else 'FAIL'} ovphysx {spec_name}: "
            f"bodies={result.get('resolved_rigid_body_count', 0)}, "
            f"rtf={result.get('realtime_factor', 0):.3f}"
        )

    runtime_ok = all(
        result.get("ok")
        and result.get("realtime_factor", 0) >= args.min_realtime_factor
        and result.get("resolved_rigid_body_count")
        == result.get("expected_rigid_body_count")
        for result in runtime_results
    )
    structural_ok = (
        structural.returncode == 0
        and structural_report.get("status") == "structural_g2_passed"
    )
    report = {
        "status": "g2_passed" if structural_ok and runtime_ok else "failed",
        "primary_representation": "OpenUSD",
        "primary_runtime": "ovphysx CPU",
        "isaac_sim_gate": "optional_not_run",
        "structural_ok": structural_ok,
        "runtime_ok": runtime_ok,
        "runtime_spec_count": len(runtime_results),
        "runtime_specs": runtime_specs,
        "min_realtime_factor": args.min_realtime_factor,
        "structural_report": str(structural_report_path),
        "runtime_results": runtime_results,
    }
    final_report = args.work_dir / "g2_report.json"
    _write(final_report, report)
    print(f"Gate G2 {report['status']}: {final_report}")
    return 0 if report["status"] == "g2_passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
