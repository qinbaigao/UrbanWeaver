"""Offline replay of up to ten existing Room Agent designs with metric constraints.

No model calls or asset generation. Reuses previous semantic plans; failed room
transactions retain the original room and are explicitly reported, not passed.
"""
import argparse
from pathlib import Path

from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.planning.interiors import FloorDetailAgent, FurnishingProgram
from cityg.planning.room_design import RoomDesign
from cityg.planning.room_constraints import WALL_DEFAULTS, wall_contact
from cityg.serialization import load_city, save_json
from cityg.services import OpenUSDBackend
from cityg.validation import CityValidator
from cityg.viewer import export_portable_viewer


def contact_report(objects, room):
    return [{"id":o.id,"category":o.category,"contact_side":wall_contact(o,room,{})[0],
             "contact_gap_m":round(wall_contact(o,room,{})[1],4)}
            for o in objects if o.category in WALL_DEFAULTS and o.id==o.metadata.get("group_anchor_id")]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()): parser.error("Output must be absent or empty")
    args.output.mkdir(parents=True,exist_ok=True)
    city=load_city(args.input)
    detail=FloorDetailAgent()
    traces=[]; targets=[]
    for b in city.iter_buildings():
        for f in b.floors:
            for r in f.rooms:
                data=r.metadata.get("room_design",{})
                if data.get("status")=="accepted" and len(targets)<10:
                    targets.append((b,f,r,data))
    for b,f,r,data in targets:
        print("Replaying",r.id,flush=True)
        before=[o for o in f.objects if o.room_id==r.id]
        trace={"room_id":r.id,"function":r.function,"before":contact_report(before,r)}
        try:
            design=RoomDesign.from_dict({k:v for k,v in data.items() if k in RoomDesign.__dataclass_fields__},detail.catalog)
            program=FurnishingProgram(r.id,r.function,data.get("style","neutral"),data.get("density",.4),(),design=design)
            detail.program_overrides={r.id:program}
            stats=detail.populate_rooms(city,{r.id},seed=17)
            trace["stats"]=stats
            trace["status"]="accepted" if not stats["furnishing_non_degradation_gate_rejected_room_count"] else "rejected"
        except Exception as exc:
            trace.update(status="rejected",error=str(exc))
        trace["after"]=contact_report([o for o in f.objects if o.room_id==r.id],r)
        traces.append(trace)
        save_json(traces,args.output/"room_constraints.json")
        print(trace["status"],trace.get("error",""),flush=True)
    city.world_program=build_world_program(city,producer="room_constraints_offline",seed=17)
    compiler=GeometryCompiler()
    scene=compiler.compile(city)
    report=CityValidator().validate(city); geometry=GeometryValidator().validate(city,scene)
    save_json({"llm_used":False,"vlm_used":False,"asset_generation_used":False,
               "attempted_rooms":len(traces),"accepted_rooms":sum(t["status"]=="accepted" for t in traces),
               "city_validation":report.to_dict(),"geometry_validation":geometry.to_dict()},args.output/"report.json")
    if not report.ok or not geometry.ok: raise RuntimeError("Scene validation failed")
    OpenUSDBackend(compiler).compile(city,args.output/"scene",_scene_override=scene)
    save_json(report.to_dict(),args.output/"scene/validation_report.json")
    export_portable_viewer(args.output/"scene",args.output/"viewer")
    accepted={t["room_id"] for t in traces if t["status"]=="accepted"}
    selected=sorted((r for _,_,r,_ in targets if r.id in accepted),key=lambda r:(r.function!="bedroom",r.function!="office",r.id))[:3]
    save_json({"selected_views":[{"view_id":f"room_{i}_{preset}","kind":"room_interior","mode":"room",
                "target_entity_ids":[r.id],"room_camera_preset":preset,"render_profile":"presentation",
                "appearance":"presentation"} for i,r in enumerate(selected) for preset in ("top","cutaway")]},args.output/"observation.json")
    print("Viewer:",args.output/"viewer",flush=True)


if __name__=="__main__": main()
