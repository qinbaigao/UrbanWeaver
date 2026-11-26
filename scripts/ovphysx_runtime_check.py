"""Validate a compiled CityG OpenUSD package with ovphysx in CPU-only mode.

Run this script in the separate ``cityg-ovphysx`` environment. It never imports
ovphysx from CityG core and calls ``PhysX.set_cpu_mode(True)`` before creating an
instance, so no CUDA driver or RTX GPU is required.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import re
import resource
import sys
import time
from pathlib import Path


EXPECTED_OVPHYSX_VERSION = "0.5.9"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate CityG with ovphysx CPU")
    parser.add_argument("stage", type=Path, help="Path to the root city.usda layer")
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--physics-steps", type=int, default=600)
    parser.add_argument("--physics-dt", type=float, default=1.0 / 60.0)
    parser.add_argument("--max-z-drift-m", type=float, default=0.10)
    parser.add_argument("--joint-probe-velocity-mps", type=float, default=3.0)
    parser.add_argument("--joint-probe-steps", type=int, default=30)
    parser.add_argument("--max-joint-probe-z-drift-m", type=float, default=0.01)
    parser.add_argument("--raycast-samples", type=int, default=12)
    parser.add_argument("--active-floor-id")
    parser.add_argument("--allow-version-mismatch", action="store_true")
    return parser


def _identifier(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_]", "_", value)
    return result if result and not result[0].isdigit() else f"_{result}"


def _load_manifests(stage_path: Path) -> tuple[dict, dict]:
    output_root = stage_path.parent.parent
    city_path = output_root / "city.json"
    geometry_path = output_root / "geometry_manifest.json"
    if not city_path.is_file() or not geometry_path.is_file():
        raise FileNotFoundError(
            "city.json and geometry_manifest.json must be next to the usd directory"
        )
    return (
        json.loads(city_path.read_text(encoding="utf-8")),
        json.loads(geometry_path.read_text(encoding="utf-8")),
    )


def _floor_owners(city: dict) -> dict[str, tuple[str, str]]:
    owners: dict[str, tuple[str, str]] = {}
    for district in city.get("districts", []):
        for parcel in district.get("parcels", []):
            for building in parcel.get("buildings", []):
                for floor in building.get("floors", []):
                    owners[floor["id"]] = (district["id"], building["id"])
    return owners


def _physics_paths(
    city: dict, geometry: dict, active_floor_id: str | None = None
) -> tuple[list[str], list[str]]:
    owners = _floor_owners(city)
    floor_by_layer = {
        layer["id"]: layer["owner_id"]
        for layer in geometry.get("layers", [])
        if layer.get("layer_type") == "floor"
    }
    bodies: list[str] = []
    joints: list[str] = []
    for primitive in geometry.get("primitives", []):
        if primitive.get("body_type") != "articulated":
            continue
        floor_id = floor_by_layer.get(primitive["layer_id"])
        if active_floor_id is not None and floor_id != active_floor_id:
            continue
        if floor_id not in owners:
            raise ValueError(f"Cannot resolve floor owner for {primitive['id']}")
        district_id, building_id = owners[floor_id]
        parent = "/".join(
            [
                "",
                "City",
                _identifier(district_id),
                _identifier(building_id),
                "Interior",
                _identifier(floor_id),
            ]
        )
        name = _identifier(primitive["id"])
        bodies.append(f"{parent}/{name}")
        joint_name = _identifier("joint_" + primitive["id"])
        joints.append(f"{parent}/{joint_name}")
    return bodies, joints


def _ray_origins(geometry: dict, limit: int) -> list[tuple[float, float, float]]:
    origins = []
    for primitive in geometry.get("primitives", []):
        if not primitive.get("collision_enabled", True):
            continue
        center = primitive["center"]
        origins.append((float(center["x"]), float(center["y"]), float(center["z"]) + 100.0))
        if len(origins) >= limit:
            break
    return origins


def _write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    stage_path = args.stage.expanduser().resolve()
    if not stage_path.is_file():
        raise FileNotFoundError(stage_path)
    if args.physics_steps < 1 or not 0 < args.physics_dt <= 1:
        raise ValueError("physics step settings are invalid")
    if args.raycast_samples < 1 or args.max_z_drift_m < 0:
        raise ValueError("validation thresholds are invalid")
    if (
        args.joint_probe_velocity_mps <= 0
        or args.joint_probe_steps < 1
        or args.max_joint_probe_z_drift_m < 0
    ):
        raise ValueError("joint probe settings are invalid")

    errors: list[str] = []
    warnings: list[str] = []
    report: dict = {
        "ok": False,
        "runtime": "ovphysx",
        "execution_device": "cpu",
        "stage": str(stage_path),
        "errors": errors,
        "warnings": warnings,
    }

    try:
        import numpy as np
        import ovphysx
        import ovstage
        from ovphysx import PhysX, TensorType
        from ovphysx.types import ObjectType
    except ImportError as error:
        errors.append(f"missing_runtime_dependency:{error}")
        _write_report(args.report, report)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 3

    runtime_version = importlib.metadata.version("ovphysx")
    ovstage_version = importlib.metadata.version("ovstage")
    report.update(
        {
            "runtime_version": runtime_version,
            "ovstage_version": ovstage_version,
            "expected_runtime_version": EXPECTED_OVPHYSX_VERSION,
            "cpu_only_forced": True,
        }
    )
    if runtime_version != EXPECTED_OVPHYSX_VERSION:
        message = f"ovphysx_version_mismatch:{runtime_version}"
        if args.allow_version_mismatch:
            warnings.append(message)
        else:
            errors.append(message)
            _write_report(args.report, report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 2

    physx = None
    stage = None
    binding = None
    velocity_binding = None
    attached = False
    try:
        city, geometry = _load_manifests(stage_path)
        body_paths, joint_paths = _physics_paths(city, geometry, args.active_floor_id)
        if not body_paths:
            errors.append("no_expected_articulated_bodies")

        # This must precede the first PhysX instance. It guarantees that ovphysx
        # never initializes CUDA, even when an NVIDIA GPU/driver is present.
        PhysX.set_cpu_mode(True)
        physx = PhysX()
        stage = ovstage.Stage("cityg-ovphysx-cpu-check")
        if not ovstage.population.available():
            raise RuntimeError("ovstage population bridge is unavailable")

        load_started = time.perf_counter()
        ovstage.population.open_usd(
            stage,
            str(stage_path),
            ordinal=1,
            domains=ovstage.PopulationDomain.PHYSICS,
        )
        stage.advance_write_floor(ordinal=1).wait()
        physx.attach_ovstage(stage, read_ordinal=1)
        attached = True
        physx.step_sync(args.physics_dt)
        load_seconds = time.perf_counter() - load_started

        binding = physx.create_tensor_binding(
            prim_paths=body_paths,
            tensor_type=TensorType.RIGID_BODY_POSE,
        )
        resolved_paths = list(binding.prim_paths)
        if len(resolved_paths) != len(body_paths):
            errors.append(
                f"rigid_body_count_mismatch:{len(resolved_paths)}/{len(body_paths)}"
            )
        invalid_bodies = [
            path for path in body_paths if physx.get_object_type(path) != ObjectType.RIGID_BODY
        ]
        if invalid_bodies:
            errors.append(f"unresolved_rigid_bodies:{len(invalid_bodies)}")

        before = np.zeros(binding.shape, dtype=np.dtype(str(binding.dtype)))
        binding.read(before)
        physics_started = time.perf_counter()
        physx.step_n_sync(args.physics_steps, args.physics_dt)
        physics_wall_seconds = time.perf_counter() - physics_started
        after = np.zeros(binding.shape, dtype=np.dtype(str(binding.dtype)))
        binding.read(after)

        non_finite = int(np.size(after) - np.count_nonzero(np.isfinite(after)))
        max_z_drift = (
            float(np.max(np.abs(after[:, 2] - before[:, 2]))) if binding.count else math.inf
        )
        if non_finite:
            errors.append(f"non_finite_pose_values:{non_finite}")
        if max_z_drift > args.max_z_drift_m:
            errors.append(f"rigid_body_z_drift_exceeded:{max_z_drift:.6g}")

        # A vertical velocity is deliberately applied to every door. Static
        # support alone cannot resist upward motion; a correctly parsed revolute
        # joint must keep each body's hinge at a fixed Z coordinate.
        velocity_binding = physx.create_tensor_binding(
            prim_paths=body_paths,
            tensor_type=TensorType.RIGID_BODY_VELOCITY,
        )
        probe_velocity = np.zeros(
            velocity_binding.shape, dtype=np.dtype(str(velocity_binding.dtype))
        )
        probe_velocity[:, 2] = args.joint_probe_velocity_mps
        velocity_binding.write(probe_velocity)
        physx.step_n_sync(args.joint_probe_steps, args.physics_dt)
        probed = np.zeros(binding.shape, dtype=np.dtype(str(binding.dtype)))
        binding.read(probed)
        joint_probe_z_drift = (
            float(np.max(np.abs(probed[:, 2] - after[:, 2])))
            if binding.count
            else math.inf
        )
        if joint_probe_z_drift > args.max_joint_probe_z_drift_m:
            errors.append(
                f"revolute_joint_probe_failed:{joint_probe_z_drift:.6g}"
            )

        raycast_hits = 0
        for origin in _ray_origins(geometry, args.raycast_samples):
            raycast_hits += bool(
                physx.raycast(origin=origin, direction=(0.0, 0.0, -1.0), distance=200.0)
            )
        if raycast_hits == 0:
            errors.append("no_static_collision_raycast_hits")

        simulated_seconds = args.physics_steps * args.physics_dt
        report.update(
            {
                "ok": not errors,
                "load_seconds": load_seconds,
                "expected_rigid_body_count": len(body_paths),
                "resolved_rigid_body_count": len(resolved_paths),
                "expected_revolute_joint_count": len(joint_paths),
                "joint_constraint_probe_count": len(body_paths),
                "joint_probe_velocity_mps": args.joint_probe_velocity_mps,
                "joint_probe_steps": args.joint_probe_steps,
                "joint_probe_max_z_drift_m": joint_probe_z_drift,
                "activation_mode": "active_floor" if args.active_floor_id else "full",
                "active_floor_id": args.active_floor_id,
                "physics_steps": args.physics_steps,
                "physics_dt_s": args.physics_dt,
                "simulated_seconds": simulated_seconds,
                "physics_wall_seconds": physics_wall_seconds,
                "realtime_factor": simulated_seconds / max(physics_wall_seconds, 1e-9),
                "max_rigid_body_z_drift_m": max_z_drift,
                "non_finite_pose_value_count": non_finite,
                "raycast_sample_count": args.raycast_samples,
                "raycast_hit_count": raycast_hits,
                "process_peak_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            }
        )
    except Exception as error:
        errors.append(f"runtime_exception:{type(error).__name__}:{error}")
        report["ok"] = False
    finally:
        if velocity_binding is not None:
            velocity_binding.destroy()
        if binding is not None:
            binding.destroy()
        if physx is not None and attached:
            physx.detach_ovstage()
        if physx is not None:
            physx.release()
        if stage is not None:
            stage.destroy()
        _write_report(args.report, report)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
