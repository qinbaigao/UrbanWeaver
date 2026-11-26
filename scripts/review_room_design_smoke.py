"""Review captured room presets and optionally exercise one bounded room repair.

Supply an existing run_room_design_smoke output and its headless screenshots.
No city-wide regeneration, asset generation, or automatic desktop browser.
"""
import argparse
import json
from pathlib import Path

from cityg.adaptive_review import aggregate_visual_reviews
from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler
from cityg.planning.interiors import FloorDetailAgent
from cityg.refinement.room import RoomProgramAgent
from cityg.serialization import load_city, save_json
from cityg.services import OpenAICompatibleService, OpenUSDBackend
from cityg.services.interfaces import ModelEndpoint
from cityg.validation import CityValidator
from cityg.viewer import export_portable_viewer
from cityg.visual_review import VisualReviewAgent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run",type=Path)
    parser.add_argument("--images",type=Path,required=True)
    parser.add_argument("--plan",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--repair",action="store_true")
    args=parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()): parser.error("Output must be absent or empty")
    args.output.mkdir(parents=True,exist_ok=True)
    city=load_city(args.run/"scene/city.json")
    manifest=json.loads((args.run/"scene/geometry_manifest.json").read_text())
    compiled_objects={p["owner_id"] for p in manifest["primitives"] if p["semantic_class"].startswith("furniture_")}
    index={r.id:(b,f,r) for b in city.iter_buildings() for f in b.floors for r in f.rooms}
    plan=json.loads(args.plan.read_text())
    # Intact top + interior views provide complementary evidence. Cutaway
    # screenshots are presentation-only here, not evidence of missing walls.
    views=[]; rooms=set()
    for view in plan["selected_views"]:
        rid=next((i for i in view["target_entity_ids"] if i in index),None)
        if not rid or view.get("room_camera_preset")=="cutaway": continue
        if rid not in rooms and len(rooms)>=2: continue
        rooms.add(rid)
        b,f,r=index[rid]
        views.append({**view,"semantic_context":{
            "room_design":r.metadata.get("room_design"),"room_function":r.function,
            "camera_preset":view.get("room_camera_preset"),"geometry_source":"procedural_furniture",
            "compiled_object_ids":[o.id for o in f.objects if o.room_id==rid and o.id in compiled_objects],
            "furniture_groups":[{"object_id":o.id,"category":o.category,
                "anchor_id":o.metadata.get("group_anchor_id"),"group_id":o.metadata.get("group_id")}
                for o in f.objects if o.room_id==rid]}})
    if not views: raise ValueError("No room observations to review")
    service=OpenAICompatibleService(ModelEndpoint("http://127.0.0.1:8000/v1","cityg-llm",
        timeout_s=240,max_tokens=6000,temperature=.2,seed=17))
    review=aggregate_visual_reviews({"selected_views":views},args.images,
        VisualReviewAgent(service),scene_id=city.id,batch_size=2)
    save_json(review,args.output/"visual_review.json")
    eligible=[i for i in review["aggregated_issues"] if i.get("entity_id") in rooms
              and i.get("category")=="room" and i.get("severity") in {"warning","error"}
              and i.get("confidence",0)>=.75 and i.get("binding_confidence",0)>=.75]
    print(f"VLM: {review['available_batches']}/{review['batch_count']} batches, {len(eligible)} repairable issues",flush=True)
    if not args.repair or not eligible: return
    issue=eligible[0]; rid=issue["entity_id"]; b,f,r=index[rid]
    result=RoomProgramAgent(service,max_attempts=3).propose(city,b,f,r,use_cache=False,
        visual_feedback={"issues":[i for i in eligible if i["entity_id"]==rid]})
    stats=FloorDetailAgent(program_overrides={rid:result.program}).populate_rooms(city,{rid},seed=17)
    save_json({"program":result.raw,"stats":stats,"room_design":r.metadata.get("room_design")},args.output/"repair.json")
    city.world_program=build_world_program(city,producer="room_design_vlm_smoke",seed=17)
    backend=OpenUSDBackend(GeometryCompiler())
    backend.compile_incremental(city,args.output/"scene",args.run/"scene",[rid])
    save_json(CityValidator().validate(city).to_dict(),args.output/"scene/validation_report.json")
    export_portable_viewer(args.output/"scene",args.output/"viewer")
    save_json({"selected_views":[v for v in plan["selected_views"] if rid in v["target_entity_ids"]]},args.output/"observation.json")
    print("Room repair exported; re-render observation.json for post-repair review",flush=True)


if __name__=="__main__": main()
