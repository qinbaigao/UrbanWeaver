"""Small real Room Agent integration on an existing interior scene (at most ten rooms).

Does not regenerate the city or call asset generation. Existing local assets can
be enabled with --asset-registry. All agent outcomes and rollbacks are recorded.
"""
import argparse
from pathlib import Path

from cityg.assets import AssetRegistry, AssetResolver
from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.planning.interiors import FloorDetailAgent
from cityg.refinement.room import RoomProgramAgent
from cityg.refinement.selection import select_hero_rooms, mark_room_detail
from cityg.serialization import load_city, save_json
from cityg.services import OpenAICompatibleService, OpenUSDBackend
from cityg.services.interfaces import ModelEndpoint
from cityg.validation import CityValidator
from cityg.viewer import export_portable_viewer


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--rooms",type=int,default=10)
    parser.add_argument("--asset-registry",type=Path)
    args=parser.parse_args()
    if not 1<=args.rooms<=10: parser.error("Use 1..10 rooms for this smoke test")
    if args.output.exists() and any(args.output.iterdir()): parser.error("Output must be absent or empty")
    args.output.mkdir(parents=True,exist_ok=True)
    city=load_city(args.input)
    service=OpenAICompatibleService(ModelEndpoint("http://127.0.0.1:8000/v1","cityg-llm",
        timeout_s=240,max_tokens=6000,temperature=.25,seed=17))
    agent=RoomProgramAgent(service,max_attempts=3)
    registry=AssetRegistry(args.asset_registry) if args.asset_registry else None
    resolver=AssetResolver(registry,(),max_provider_calls=0) if registry else None
    selection=select_hero_rooms(city,max_rooms=args.rooms)
    selected=set(selection.room_ids)
    trace=[]
    for building in city.iter_buildings():
        for floor in building.floors:
            for room in floor.rooms:
                if room.id not in selected: continue
                print("RoomAgent",room.id,room.function,flush=True)
                try:
                    result=agent.propose(city,building,floor,room,use_cache=False)
                    detail=FloorDetailAgent(asset_resolver=resolver,program_overrides={room.id:result.program})
                    stats=detail.populate_rooms(city,{room.id},seed=17)
                    status=room.metadata.get("room_design",{}).get("status","legacy")
                    if stats["furnishing_non_degradation_gate_rejected_room_count"]: status="gate_rejected"
                    trace.append({"room_id":room.id,"function":room.function,"status":status,"stats":stats,"program":result.raw})
                except Exception as exc:
                    trace.append({"room_id":room.id,"status":"error","error":str(exc)})
                mark_room_detail(city,{room.id},status=trace[-1]["status"])
                save_json(trace,args.output/"room_trace.json")
                print("  ->",trace[-1]["status"],flush=True)
    city.world_program=build_world_program(city,producer="room_design_smoke",seed=17)
    compiler=GeometryCompiler(asset_registry=registry)
    scene=compiler.compile(city)
    validation=CityValidator().validate(city)
    geometry=GeometryValidator().validate(city,scene)
    report={"scope":"room_agent_integration","llm_used":True,"vlm_used":False,
            "asset_generation_used":False,"selected_rooms":len(selected),
            "accepted_designs":sum(t["status"]=="accepted" for t in trace),
            "city_validation":validation.to_dict(),"geometry_validation":geometry.to_dict()}
    save_json(report,args.output/"report.json")
    if not validation.ok or not geometry.ok: raise RuntimeError("Validation failed; inspect report.json")
    OpenUSDBackend(compiler).compile(city,args.output/"scene",_scene_override=scene)
    save_json(validation.to_dict(),args.output/"scene/validation_report.json")
    export_portable_viewer(args.output/"scene",args.output/"viewer")
    accepted=[t["room_id"] for t in trace if t["status"]=="accepted"]
    views=[{"view_id":f"room_{i}_{preset}","mode":"room","kind":"room_interior",
            "target_entity_ids":[room_id],"room_camera_preset":preset,
            "render_profile":"presentation","appearance":"presentation"}
           for i,room_id in enumerate(accepted[:3]) for preset in ("top","cutaway","eye")]
    save_json({"selected_views":views},args.output/"observation.json")
    print(report,flush=True)


if __name__=="__main__": main()
