#!/usr/bin/env python3
"""Summarize the three scale smoke runs into a reproducible evidence table."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _city_counts(path: Path) -> dict[str, int]:
    city = _load(path) or {}
    districts = city.get("districts", [])
    buildings = [building for district in districts for parcel in district.get("parcels", []) for building in parcel.get("buildings", [])]
    floors = [floor for building in buildings for floor in building.get("floors", [])]
    rooms = [room for floor in floors for room in floor.get("rooms", [])]
    return {"buildings": len(buildings), "floors": len(floors), "rooms": len(rooms)}


def summarize(root: Path) -> dict:
    scales = {}
    for scale in (12, 30, 60):
        normal_dir = root / f"scale{scale}_normal_v2"
        if not normal_dir.is_dir():
            normal_dir = root / f"scale{scale}_normal"
        repair_dir = root / f"scale{scale}_repair"
        normal = _load(normal_dir / "run.json") or {}
        repair = _load(repair_dir / "run.json") or {}
        normal_metrics = _load(normal_dir / "final" / "openusd" / "compile_metrics.json") or {}
        repair_metrics = _load(repair_dir / "final" / "openusd" / "compile_metrics.json") or {}
        normal_counts = _city_counts(normal_dir / "final" / "openusd" / "city.json")
        repair_counts = _city_counts(repair_dir / "final" / "openusd" / "city.json")
        scales[str(scale)] = {
            "normal": {
                "status": normal.get("status"),
                "elapsed_s": normal.get("elapsed_s"),
                "metrics": normal.get("metrics", {}),
                "counts": normal_counts,
                "compile_metrics": normal_metrics,
                "portable_viewer": (normal_dir / "viewer" / "index.html").is_file(),
            },
            "repair": {
                "status": repair.get("status"),
                "elapsed_s": repair.get("elapsed_s"),
                "metrics": repair.get("metrics", {}),
                "counts": repair_counts,
                "compile_metrics": repair_metrics,
                "injected_error_case": repair.get("configuration", {}).get("injected_error_case"),
                "repair_history": repair.get("repair_history", []),
                "portable_viewer": (repair_dir / "viewer" / "index.html").is_file(),
            },
        }
    return {
        "protocol_version": "cityg.milestone_smoke.v1",
        "root": str(root.resolve()),
        "scales": scales,
        "environment_note": "The first scale12_normal attempt was blocked by the managed sandbox loopback policy; scale12_normal_v2 was rerun with approved local vLLM access and is the canonical result.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = summarize(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Milestone report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
