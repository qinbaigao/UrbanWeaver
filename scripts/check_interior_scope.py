"""Audit selective-interior outputs; pipeline exit status alone is insufficient."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from cityg.planning.interior_scope import floor_enabled
from cityg.serialization import load_city, save_json
from cityg.validation import CityValidator
from cityg.observation import _RealizedRoomIndex


def audit(scene_path: Path, *, buildings: int, detailed_buildings: int, hero_rooms: int):
    city = load_city(scene_path / "city.json")
    geometry = json.loads((scene_path / "geometry_manifest.json").read_text())
    primitives = geometry["primitives"]
    realized = _RealizedRoomIndex(city, geometry)
    levels = city.metadata.get("interior_scope", {}).get("building_levels", {})
    actual_buildings = list(city.iter_buildings())
    errors = []
    rooms = []
    active_floors = []
    assets = Counter()
    inactive_layers = set()
    for building in actual_buildings:
        for floor in building.floors:
            if not floor_enabled(city, building, floor):
                inactive_layers.add(f"floor:{floor.id}")
                if floor.objects:
                    errors.append(f"unselected floor has furniture: {floor.id}")
                continue
            active_floors.append(floor.id)
            for room in floor.rooms:
                if room.metadata.get("detail_tier") != "hero":
                    continue
                objects = [o for o in floor.objects if o.room_id == room.id]
                design = room.metadata.get("room_design", {})
                accepted = (design.get("status") == "accepted"
                            and not room.metadata.get("room_design_rejected") and bool(objects))
                visible_ids = set(realized.compiled_object_ids(room.id))
                missing_ids = sorted({o.id for o in objects}-visible_ids)
                frame_ok = realized.frame(building,floor,room) is not None
                if not frame_ok or missing_ids:
                    errors.append(f"hero room not fully realized: {room.id}; frame={frame_ok}, missing_objects={len(missing_ids)}")
                rooms.append({"room_id": room.id, "building_id": building.id,
                              "floor_level": floor.level, "function": room.function,
                              "accepted": accepted, "object_count": len(objects),
                              "realized_frame": frame_ok, "missing_compiled_objects": missing_ids,
                              "refinement_status": room.metadata.get("refinement_status"),
                              "constraint_checks": design.get("constraint_checks"),
                              "asset_ids": sorted({o.asset_id for o in objects})})
                assets.update(o.asset_id for o in objects)
    leaked = [p["id"] for p in primitives if p["layer_id"] in inactive_layers]
    if leaked:
        errors.append(f"geometry leaked into unselected floors: {len(leaked)}")
    if len(actual_buildings) != buildings:
        errors.append(f"building count {len(actual_buildings)} != {buildings}")
    if len(levels) != detailed_buildings:
        errors.append(f"interior building count {len(levels)} != {detailed_buildings}")
    accepted_count = sum(r["accepted"] for r in rooms)
    if accepted_count < hero_rooms:
        errors.append(f"only {accepted_count}/{hero_rooms} accepted hero rooms")
    checks = {"validation_report": CityValidator().validate(city).to_dict()}
    if not checks["validation_report"]["ok"]:
        errors.append("canonical city validation failed")
    for name in ("geometry_validation_report", "usd_validation_report",
                 "interaction_smoke_report"):
        path = scene_path / f"{name}.json"
        checks[name] = json.loads(path.read_text()) if path.is_file() else {"missing": True}
        if checks[name].get("ok") is not True:
            errors.append(f"{name} missing or failed")
    return {"ok": not errors, "errors": errors, "scene": str(scene_path.resolve()),
            "building_count": len(actual_buildings), "interior_scope": levels,
            "compiled_floors": active_floors, "selected_hero_rooms": len(rooms),
            "accepted_hero_rooms": accepted_count, "rooms": rooms,
            "hero_asset_instances": dict(assets), "checks": checks,
            "indoor_asset_fit_warnings": geometry.get("metadata", {}).get("indoor_asset_fit_warnings", []),
            "limitations": "Canonical/compiled scope and furnishing acceptance checks; not a visual quality certification."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scene", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--buildings", type=int, default=10)
    parser.add_argument("--detailed-buildings", type=int, default=3)
    parser.add_argument("--hero-rooms", type=int, default=10)
    args = parser.parse_args()
    report = audit(args.scene, buildings=args.buildings, detailed_buildings=args.detailed_buildings,
                   hero_rooms=args.hero_rooms)
    save_json(report, args.output)
    print(json.dumps({k: report[k] for k in ("ok", "errors", "building_count", "accepted_hero_rooms")}, ensure_ascii=False))
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
