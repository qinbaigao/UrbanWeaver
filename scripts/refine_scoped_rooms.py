"""Retry selected Room Agent transactions from an exported city, keeping its planning."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

from cityg.assets import AssetRegistry, AssetResolver, MaterialLibrary
from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler
from cityg.planning.interiors import FloorDetailAgent
from cityg.planning.interior_scope import floor_enabled
from cityg.refinement.room import RoomProgramAgent
from cityg.serialization import load_city, save_json
from cityg.services import OpenUSDBackend
from cityg.services.openai_compatible import OpenAICompatibleService
from cityg.services.interfaces import ModelEndpoint
from cityg.viewer import export_portable_viewer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scene", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", default="cityg-llm")
    parser.add_argument("--attempts", type=int, default=6)
    parser.add_argument("--rollback-city", type=Path,
                        help="Pre-refinement city: rollback unrealizable hero rooms and select same-function neighbors")
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Use a fresh recovery output directory")
    args.output.mkdir(parents=True, exist_ok=True)
    city = load_city(args.scene if args.scene.is_file() else args.scene / "city.json")
    if args.rollback_city:
        from cityg.observation import _RealizedRoomIndex
        base = load_city(args.rollback_city)
        if base.id != city.id:
            raise ValueError("Rollback city identity differs")
        source_dir = args.scene.parent if args.scene.is_file() else args.scene
        geometry = json.loads((source_dir / "geometry_manifest.json").read_text())
        realized = _RealizedRoomIndex(city, geometry)
        original = {r.id:(f,r) for b in base.iter_buildings() for f in b.floors for r in f.rooms}
        replacements = []
        for building in city.iter_buildings():
            for floor in building.floors:
                for room in list(floor.rooms):
                    if room.metadata.get("detail_tier") != "hero" or realized.frame(building,floor,room) is not None:
                        continue
                    candidates = [(r,realized.frame(building,floor,r)) for r in floor.rooms
                                  if r.function == room.function and r.metadata.get("detail_tier") != "hero"]
                    candidates = [(r,frame) for r,frame in candidates if frame is not None and min(frame.width,frame.depth)>=2]
                    if not candidates:
                        raise ValueError(f"No realizable same-floor, same-function replacement for {room.id}")
                    replacement, frame = max(candidates,key=lambda pair:(min(pair[1].width,pair[1].depth),pair[0].id))
                    old_floor, old_room = original[room.id]
                    if old_room.bounds != room.bounds or old_room.function != room.function or old_floor.id != floor.id:
                        raise ValueError("Rollback room geometry differs; refusing ambiguous rollback")
                    rejected_design = deepcopy(room.metadata.get("room_design"))
                    room.metadata = deepcopy(old_room.metadata)
                    room.metadata.update(detail_tier="standard",refinement_status="unrealized_rollback",
                                         unrealized_fine_design=rejected_design)
                    floor.objects[:]=[o for o in floor.objects if o.room_id != room.id]
                    restored=deepcopy([o for o in old_floor.objects if o.room_id == room.id])
                    floor.objects.extend(restored)
                    room.object_ids=[o.id for o in restored]
                    replacement.metadata.update(detail_tier="hero",refinement_status="selected")
                    replacements.append({"old_room":room.id,"new_room":replacement.id,
                        "function":room.function,"reason":"compiled_room_frame_unavailable",
                        "realized_dimensions_m":[frame.width,frame.depth]})
        save_json({"baseline":str(args.rollback_city.resolve()),"replacements":replacements},
                  args.output / "selection_repair.json")
    registry = AssetRegistry("assets/asset_registry.json")
    resolver = AssetResolver(registry, (), max_provider_calls=0)
    service = OpenAICompatibleService(ModelEndpoint(args.base_url, args.model,
        timeout_s=240, max_tokens=8192, seed=17))
    agent = RoomProgramAgent(service, model_id=args.model, asset_resolver=resolver, max_attempts=args.attempts)
    trace = []
    for building in city.iter_buildings():
        for floor in building.floors:
            if not floor_enabled(city, building, floor):
                continue
            for room in floor.rooms:
                if room.metadata.get("detail_tier") != "hero":
                    continue
                if room.metadata.get("room_design", {}).get("status") == "accepted":
                    trace.append({"room_id": room.id, "preserved": True})
                    continue
                print("room_start", room.id, room.function, flush=True)
                record = {"room_id": room.id, "function": room.function}
                try:
                    proposal = agent.propose(city, building, floor, room, use_cache=False)
                    save_json(proposal.raw, args.output / "programs" / f"{room.id}.json")
                    save_json([asdict(a) for a in proposal.attempts],
                              args.output / "attempts" / f"{room.id}.json")
                    detail = FloorDetailAgent(asset_resolver=resolver, program_overrides={room.id: proposal.program})
                    # Match the model proposal's deterministic geometric preview.
                    stats = detail.populate_rooms(city, {room.id}, seed=17)
                    accepted = (room.metadata.get("room_design", {}).get("status") == "accepted"
                                and not stats["furnishing_non_degradation_gate_rejected_room_count"])
                    room.metadata["refinement_status"] = "accepted" if accepted else "gate_rejected"
                    record.update(accepted=accepted, stats=stats)
                except Exception as exc:
                    record.update(accepted=False, error=f"{type(exc).__name__}: {exc}",
                                  attempts=[asdict(a) for a in getattr(exc, "attempts", ())])
                trace.append(record)
                save_json({"source": str(args.scene.resolve()), "rooms": trace}, args.output / "recovery_report.json")
                city.world_program = build_world_program(city, producer="room_retry_checkpoint", seed=17)
                save_json(city, args.output / "city_checkpoint.json")
                print("room_end", room.id, record.get("accepted"), record.get("error", ""), flush=True)
    compiler = GeometryCompiler(asset_registry=registry,
        material_library=MaterialLibrary("assets/material_library.json"), include_interiors=True,
        facade_asset_index_path="assets/facades/asset_annotations_reviewed.json")
    OpenUSDBackend(compiler).compile(city, args.output / "openusd")
    export_portable_viewer(args.output / "openusd", args.output / "viewer")
    print("viewer", args.output / "viewer", flush=True)
    if any(r.get("accepted") is False for r in trace):
        raise SystemExit("Some rooms remain unaccepted; see recovery_report.json")


if __name__ == "__main__":
    main()
