"""Offline integration fixture for capacity contracts and support-scoped dressing.

Uses up to three existing hero rooms. Fixture inventories are explicit test data,
NOT model-generated decisions. No vLLM, VLM, asset generation or desktop browser.
"""
import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.planning.furnishing_brief import capacity_context
from cityg.planning.interiors import FloorDetailAgent, FurnishingProgram
from cityg.planning.room_design import RoomDesign
from cityg.serialization import load_city, save_json
from cityg.services import OpenUSDBackend
from cityg.validation import CityValidator
from cityg.viewer import export_portable_viewer


def fixture(room, catalog):
    data = room.metadata["room_design"]
    design = RoomDesign.from_dict({k: v for k, v in data.items() if k in RoomDesign.__dataclass_fields__}, catalog)
    groups = deepcopy(list(design.groups))
    if room.function == "open_office":
        desks = [g for g in groups if g["anchor"]["category"] == "desk"]
        if desks:
            for n in range(len(desks), 6):
                g = deepcopy(desks[0]); g["id"] = f"extra_station_{n}"
                for i in [g["anchor"], *g["members"]]: i["id"] = f"{i['id']}_extra_{n}"
                groups.append(g)
            for g in groups:
                if g["anchor"]["category"] == "desk":
                    g["placement"] = {"mode": "wall", "wall": "north", "contact": "back", "max_gap_m": .2}
    elif room.function == "bedroom":
        bed = next(g for g in groups if g["anchor"]["category"] == "bed")
        groups.append({"id": "reading_storage", "zone": bed["zone"],
                       "anchor": {"id": "reading_bookcase", "category": "bookcase"}, "members": []})
    counts = Counter(i["category"] for g in groups for i in [g["anchor"], *g["members"]])
    brief = {"occupants": counts["desk"] if room.function == "open_office" else 1,
             "capacity_reason": "Offline fixture: capacity matches explicit functional furniture, not an LLM decision.",
             "items": [{"category": k, "minimum": v, "target": v, "purpose": "Functional fixture inventory"}
                       for k, v in sorted(counts.items())],
             "tradeoffs": "Bounded offline fixture: limit office to six wall-facing stations; keep one nightstand to preserve bedside access. Preserve circulation before any later expansion."}
    small = []
    for g in groups:
        for item in [g["anchor"], *g["members"]]:
            c = item["category"]
            pattern = {
                "desk": [("monitor", 1, "back"), ("keyboard", 1, "front"), ("cup", 1, "right")],
                "bookcase": [("book", 8, "spread"), ("file_box", 3, "left")],
                "coffee_table": [("book_stack", 1, "left"), ("cup", 2, "right")],
                "tv_console": [("small_plant", 1, "right")],
                "bedside_table": [("desk_lamp", 1, "back"), ("book_stack", 1, "front")],
            }.get(c, [])
            for category, count, placement in pattern:
                small.append({"id": f"dressing_{len(small)}", "support_member_id": item["id"],
                              "surface": "shelves" if c == "bookcase" else "top", "category": category,
                              "count": count, "placement": placement})
    return replace(design, groups=tuple(groups), furnishing_brief=brief,
                   surface_items=tuple(small), protected_groups=(), tabletop=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()): parser.error("Output must be absent or empty")
    args.output.mkdir(parents=True, exist_ok=True)
    city = load_city(args.input)
    detail = FloorDetailAgent()
    seen, traces, views = set(), [], []
    for building in city.iter_buildings():
        for floor in building.floors:
            for room in floor.rooms:
                if (room.function not in {"bedroom", "living_room", "open_office"} or room.function in seen
                        or room.metadata.get("room_design", {}).get("status") != "accepted"):
                    continue
                seen.add(room.function)
                before = sum(o.room_id == room.id for o in floor.objects)
                print("Enriching", room.id, flush=True)
                trace = {"room_id": room.id, "function": room.function, "before_major_count": before,
                         "capacity_context": capacity_context(room)}
                try:
                    design = fixture(room, detail.catalog)
                    detail.program_overrides = {room.id: FurnishingProgram(room.id, room.function,
                        "warm", .5, (), design=design)}
                    stats = detail.populate_rooms(city, {room.id}, seed=17)
                    trace.update(stats=stats, status="rejected" if stats["furnishing_non_degradation_gate_rejected_room_count"] else "accepted")
                except (ValueError, RuntimeError) as exc:
                    trace.update(status="rejected", error=str(exc))
                trace["after_major_count"] = sum(o.room_id == room.id for o in floor.objects)
                traces.append(trace)
                save_json(traces, args.output/"room_trace.json")
                print(trace, flush=True)
                if trace["status"] == "accepted":
                    views.extend({"view_id": f"{room.function}_{preset}", "mode": "room", "kind": "room_interior",
                        "target_entity_ids": [room.id], "room_camera_preset": preset,
                        "render_profile": "presentation", "appearance": "presentation"} for preset in ("top", "cutaway"))
    city.world_program = build_world_program(city, producer="room_enrichment_offline", seed=17)
    compiler = GeometryCompiler()
    scene = compiler.compile(city)
    validation = CityValidator().validate(city); geometry = GeometryValidator().validate(city, scene)
    save_json({"llm_used": False, "vlm_used": False, "asset_generation_used": False,
        "scope": "three_room_offline_inventory_fixture", "rooms": traces,
        "surface_items": scene.metadata.get("room_surface_items", {}),
        "city_validation": validation.to_dict(), "geometry_validation": geometry.to_dict()}, args.output/"report.json")
    if not validation.ok or not geometry.ok: raise RuntimeError("Scene validation failed")
    OpenUSDBackend(compiler).compile(city, args.output/"scene", _scene_override=scene)
    save_json(validation.to_dict(), args.output/"scene/validation_report.json")
    export_portable_viewer(args.output/"scene", args.output/"viewer")
    save_json({"selected_views": views}, args.output/"observation.json")
    print("Viewer:", args.output/"viewer", flush=True)
    if not traces or any(t["status"] != "accepted" for t in traces):
        raise RuntimeError("Some room fixtures were rejected; inspect room_trace.json (previous rooms retained)")


if __name__ == "__main__":
    main()
