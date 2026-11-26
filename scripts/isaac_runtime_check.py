"""Isaac Sim 6.0.1 headless validation for a compiled CityG USDA package.

Run this script with Isaac Sim's Python 3.12 environment, not CityG's core Python:

    /path/to/isaacsim/python.sh scripts/isaac_runtime_check.py \
        outputs/isaac_candidate/usd/city.usda \
        --report outputs/isaac_candidate/isaac_runtime_report.json
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import resource
import subprocess
import time
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate CityG in Isaac Sim")
    parser.add_argument("stage", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument(
        "--mode", choices=("overview", "active-building", "full"), default="full"
    )
    parser.add_argument("--physics-steps", type=int, default=600)
    parser.add_argument("--physics-dt", type=float, default=1.0 / 60.0)
    parser.add_argument("--warmup-frames", type=int, default=30)
    parser.add_argument("--render-frames", type=int, default=60)
    parser.add_argument("--max-z-drift-m", type=float, default=0.10)
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    return parser


def _gpu_memory_mb() -> list[int]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return [int(line.strip()) for line in result.stdout.splitlines() if line.strip()]
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


def _wait_for_stage(simulation_app, context, maximum_updates=1000):
    for updates in range(1, maximum_updates + 1):
        simulation_app.update()
        status = context.get_stage_loading_status()
        if len(status) >= 3 and status[2] == 0:
            return updates
    raise RuntimeError("USD stage did not finish loading")


def _apply_load_mode(stage, mode):
    interior_paths = [
        prim.GetPath() for prim in stage.Traverse() if prim.GetName() == "Interior"
    ]
    if mode == "full":
        stage.Load()
        return len(interior_paths)
    for path in interior_paths:
        stage.Unload(path)
    if mode == "active-building" and interior_paths:
        stage.Load(interior_paths[0])
        return 1
    return 0


def _world_positions(stage, UsdGeom, UsdPhysics):
    positions = {}
    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            transform = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(0)
            translation = transform.ExtractTranslation()
            positions[str(prim.GetPath())] = tuple(float(value) for value in translation)
    return positions


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    stage_path = args.stage.expanduser().resolve()
    if not stage_path.is_file():
        raise FileNotFoundError(stage_path)
    if args.physics_steps < 1 or args.warmup_frames < 0 or args.render_frames < 1:
        raise ValueError("Step/frame counts are invalid")
    if not 0 < args.physics_dt <= 1:
        raise ValueError("physics-dt must lie in (0, 1]")

    from isaacsim import SimulationApp

    app_started = time.perf_counter()
    simulation_app = SimulationApp(
        {
            "headless": args.headless,
            "open_usd": str(stage_path),
            "create_new_stage": False,
        }
    )

    # Isaac/Omniverse imports must happen after SimulationApp starts.
    import carb
    import omni.timeline
    import omni.usd
    from isaacsim.core.simulation_manager import SimulationManager
    from pxr import Gf, UsdGeom, UsdPhysics

    errors = []
    warnings = []
    report = {}
    try:
        context = omni.usd.get_context()
        load_updates = _wait_for_stage(simulation_app, context)
        stage = context.get_stage()
        if stage is None:
            raise RuntimeError("Isaac Sim did not create a USD stage")
        payloads_loaded = _apply_load_mode(stage, args.mode)
        load_updates += _wait_for_stage(simulation_app, context)
        load_seconds = time.perf_counter() - app_started

        physics_scene_paths = [
            prim.GetPath() for prim in stage.Traverse() if prim.IsA(UsdPhysics.Scene)
        ]
        if not physics_scene_paths:
            physics_scene = UsdPhysics.Scene.Define(stage, "/PhysicsScene")
            physics_scene.CreateGravityDirectionAttr(Gf.Vec3f(0.0, 0.0, -1.0))
            physics_scene.CreateGravityMagnitudeAttr(9.81)

        prims = list(stage.Traverse())
        collision_prims = [prim for prim in prims if prim.HasAPI(UsdPhysics.CollisionAPI)]
        rigid_prims = [prim for prim in prims if prim.HasAPI(UsdPhysics.RigidBodyAPI)]
        revolute_joints = [prim for prim in prims if prim.IsA(UsdPhysics.RevoluteJoint)]
        if not collision_prims:
            errors.append("no_collision_prims")
        if args.mode != "overview" and not rigid_prims:
            errors.append("no_rigid_bodies_in_active_mode")
        if args.mode != "overview" and len(rigid_prims) != len(revolute_joints):
            errors.append("rigid_body_joint_count_mismatch")

        before = _world_positions(stage, UsdGeom, UsdPhysics)
        SimulationManager.setup_simulation(dt=args.physics_dt, device="cuda:0")
        timeline = omni.timeline.get_timeline_interface()
        timeline.play()
        for _ in range(args.warmup_frames):
            simulation_app.update()

        physics_started = time.perf_counter()
        SimulationManager.step(steps=args.physics_steps)
        physics_wall_seconds = time.perf_counter() - physics_started

        render_started = time.perf_counter()
        for _ in range(args.render_frames):
            simulation_app.update()
        render_wall_seconds = time.perf_counter() - render_started
        timeline.pause()

        after = _world_positions(stage, UsdGeom, UsdPhysics)
        max_z_drift = 0.0
        non_finite_bodies = []
        for prim_path, position in after.items():
            if not all(math.isfinite(value) for value in position):
                non_finite_bodies.append(prim_path)
                continue
            if prim_path in before:
                max_z_drift = max(max_z_drift, abs(position[2] - before[prim_path][2]))
        if non_finite_bodies:
            errors.append("non_finite_rigid_body_transform")
        if max_z_drift > args.max_z_drift_m:
            errors.append("rigid_body_z_drift_exceeded")

        gpu_memory = _gpu_memory_mb()
        simulated_seconds = args.physics_steps * args.physics_dt
        report = {
            "ok": not errors,
            "runtime": "Isaac Sim",
            "runtime_version": importlib.metadata.version("isaacsim"),
            "stage": str(stage_path),
            "mode": args.mode,
            "load_seconds": load_seconds,
            "stage_loading_updates": load_updates,
            "used_layer_count": len(stage.GetUsedLayers()),
            "composed_prim_count": len(prims),
            "collision_prim_count": len(collision_prims),
            "rigid_body_count": len(rigid_prims),
            "revolute_joint_count": len(revolute_joints),
            "payloads_loaded": payloads_loaded,
            "physics_steps": args.physics_steps,
            "physics_dt_s": args.physics_dt,
            "simulated_seconds": simulated_seconds,
            "physics_wall_seconds": physics_wall_seconds,
            "realtime_factor": simulated_seconds / max(physics_wall_seconds, 1e-9),
            "render_frames": args.render_frames,
            "render_wall_seconds": render_wall_seconds,
            "headless_update_fps": args.render_frames / max(render_wall_seconds, 1e-9),
            "max_rigid_body_z_drift_m": max_z_drift,
            "non_finite_rigid_body_count": len(non_finite_bodies),
            "process_peak_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "system_gpu_memory_used_mb": gpu_memory,
            "errors": errors,
            "warnings": warnings,
        }
    except Exception as error:
        errors.append(f"runtime_exception:{type(error).__name__}:{error}")
        report = {
            "ok": False,
            "runtime": "Isaac Sim",
            "stage": str(stage_path),
            "mode": args.mode,
            "errors": errors,
            "warnings": warnings,
        }
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        simulation_app.close()

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
