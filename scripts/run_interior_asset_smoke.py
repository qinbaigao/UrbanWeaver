"""Three-room offline integration: real furniture/props, no model or browser popup."""
import argparse
from dataclasses import replace
from pathlib import Path
import math

from cityg.assets import AssetRegistry, AssetResolver
from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.geometry.surface_dressing import surfaces, overlaps
from cityg.planning.interiors import FloorDetailAgent, FurnishingProgram
from cityg.planning.room_design import RoomDesign
from cityg.serialization import load_city, save_json
from cityg.services import OpenUSDBackend
from cityg.validation import CityValidator
from cityg.viewer import export_portable_viewer
from cityg.schemas import CitySpec, Bounds2D, Point2D, Floor, Room, Door
from cityg.planning import BaselineCityPlanner


def dressing(design):
    result=[]
    for g in design.groups:
        for item in [g["anchor"],*g["members"]]:
            requests={
                "desk":[("notebook",1,"front"),("pen",1,"front"),("pencil",1,"left"),
                        ("pencil_cup",1,"back"),("eraser",1,"right"),("monitor",1,"back")],
                "coffee_table":[("vase",1,"left"),("small_plant",1,"right")],
                "bedside_table":[("vase",1,"back"),("notebook",1,"front")],
                "bookcase":[("book",8,"spread")],
            }.get(item["category"],[])
            for category,count,placement in requests:
                result.append({"id":f"prop_{len(result)}","support_member_id":item["id"],
                    "surface":"shelves" if item["category"]=="bookcase" else "top",
                    "category":category,"count":count,"placement":placement})
    return replace(design,surface_items=tuple(result),tabletop=False,protected_groups=())


def fixture_design(function):
    """Explicit new test inventories, not a silent downgrade of a user design."""
    categories = {
        "living_room": ("sofa", "coffee_table", "bookcase"),
        "bedroom": ("bed", "bedside_table"),
        "office": ("desk", "office_chair"),
    }[function]
    anchor, member = categories[:2]
    group={"id":"main","zone":"main","anchor":{"id":"anchor","category":anchor},
        "members":[{"id":"member","category":member,"side":"right" if function=="bedroom" else "front",
                    "slot":0,"gap_m":.30,"face_anchor":function!="bedroom"}]}
    groups=[group]
    if len(categories)>2:
        groups.append({"id":"storage","zone":"main","anchor":{"id":"bookcase","category":categories[2]},"members":[]})
    return dressing(RoomDesign("Offline real-asset placement fixture", "warm",
        ({"id":"main","position":"center","purpose":"asset placement validation"},),tuple(groups),
        furnishing_brief={"occupants":1,"capacity_reason":"One-person bounded offline fixture",
            "items":[{"category":c,"minimum":1,"target":1,"purpose":"test inventory"} for c in categories],
            "tradeoffs":"Separate test fixture, not a refinement or downgrade of the source room."}))


def fixture_city():
    city=BaselineCityPlanner().plan(CitySpec(name="Indoor asset placement lab",width_m=100,depth_m=100,
        building_count=3,min_floors=1,max_floors=1,rooms_per_floor=2,seed=17))
    for b,function,width,yaw in zip(city.iter_buildings(),("living_room","bedroom","office"),(9,8,10),(0,12,-12)):
        x,y=b.footprint.center.x,b.footprint.center.y
        b.footprint=Bounds2D(x-width/2,y-5,x+width/2,y+5)
        b.entrance=Point2D(x,y-5);b.vertical_connectors.clear()
        b.metadata={"massing_style":"bar","orientation_deg":yaw,"massing_parameters":{},
                    "highrise":{"enabled":False},"fixture":"indoor_asset_placement_lab"}
        fid=f"{b.id}_floor_00";rid=f"{fid}_asset_test";cid=f"{fid}_corridor"
        room=Room(rid,f"Asset trial {function}",function,Bounds2D(x-width/2,y-3,x+width/2,y+5))
        room.metadata["room_design"]={"status":"accepted",**fixture_design(function).to_dict()}
        # Limit detail UI to this room, while retaining a valid entrance corridor.
        room.metadata["detail_level"]="hero"
        corridor=Room(cid,"Entry corridor","corridor",Bounds2D(x-width/2,y-5,x+width/2,y-3))
        b.floors=[Floor(fid,0,0,3.2,rooms=[corridor,room],doors=[
            Door(f"{fid}_entry",cid,None,b.entrance,1.2,"exterior"),
            Door(f"{rid}_door",rid,cid,Point2D(x,y-3),.9)])]
    return city


def check_placements(scene, room_ids):
    by_id={p.id:p for p in scene.primitives}
    children=[p for p in scene.primitives if p.metadata.get("surface_subentity")
              and set(p.metadata.get("room_ids",[]))&set(room_ids)]
    checks=[]
    for p in children:
        support=by_id[p.metadata["support_primitive_id"]]
        kind="shelves" if p.metadata["support_kind"]=="shelf" else "top"
        s=next(s for s in surfaces([support],kind) if s.id==p.metadata["support_surface_id"])
        angle=math.radians(-s.yaw); dx=p.center.x-s.center.x;dy=p.center.y-s.center.y
        x=dx*math.cos(angle)-dy*math.sin(angle);y=dx*math.sin(angle)+dy*math.cos(angle)
        relative=math.radians(p.rotation_z_deg-s.yaw)
        w=abs(math.cos(relative))*p.size.x+abs(math.sin(relative))*p.size.y
        d=abs(math.sin(relative))*p.size.x+abs(math.cos(relative))*p.size.y
        bottom=p.center.z-p.size.z/2
        ok=abs(x)+w/2<=s.width/2+1e-6 and abs(y)+d/2<=s.depth/2+1e-6 and bottom>=s.center.z-1e-6
        if p.metadata.get("resolved_asset"): ok=ok and abs(bottom-s.center.z)<1e-6
        if s.clearance_m is not None: ok=ok and p.center.z+p.size.z/2<=s.center.z+s.clearance_m+1e-6
        checks.append({"primitive_id":p.id,"support_id":s.id,"asset_id":p.metadata.get("asset_id"),"ok":ok})
    for i,a in enumerate(children):
        for b in children[i+1:]:
            if a.metadata["subentity_id"]!=b.metadata["subentity_id"] and overlaps(a,b,gap=0):
                checks.append({"pair":[a.id,b.id],"ok":False,"reason":"sibling_overlap"})
    return checks


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input",type=Path,nargs="?",help="Optional existing scene; omitted builds a three-room lab fixture")
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--registry",type=Path,default=Path("assets/prepared/interior_v1/placement_registry.json"))
    parser.add_argument("--replay-existing",action="store_true",help="Try original inventory; never shrink it to force a pass")
    args=parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):parser.error("Use a new output directory")
    args.output.mkdir(parents=True,exist_ok=True)
    city=load_city(args.input) if args.input else fixture_city()
    source_registry=AssetRegistry(args.registry)
    # Resolve paths before detaching the manifest. Support the production
    # registry too, but never persist procedural additions made by the compiler.
    registry=AssetRegistry()
    for record in source_registry.list_all():
        registry.register(replace(record,geometry_path=str(source_registry.resolve_path(record.geometry_path).resolve()))
                          if record.geometry_path else record)
    detail=FloorDetailAgent(asset_resolver=AssetResolver(registry,(),max_provider_calls=0))
    selected=[]; functions=set();trace=[]
    for b in city.iter_buildings():
        for f in b.floors:
            for room in f.rooms:
                if room.function not in {"living_room","bedroom","office"} or room.function in functions:continue
                data=room.metadata.get("room_design",{})
                if data.get("status")!="accepted":continue
                functions.add(room.function);selected.append(room.id)
                design=(dressing(RoomDesign.from_dict({k:v for k,v in data.items() if k in RoomDesign.__dataclass_fields__},detail.catalog))
                        if args.replay_existing else fixture_design(room.function))
                if not args.replay_existing:
                    # Only the disposable in-memory copy is changed. This is
                    # a fresh fixture, never reported as a successful refinement.
                    f.objects[:]=[o for o in f.objects if o.room_id!=room.id]
                    room.object_ids.clear();room.metadata.pop("room_design",None)
                detail.program_overrides={room.id:FurnishingProgram(room.id,room.function,"warm",.5,(),design=design)}
                stats=detail.populate_rooms(city,{room.id},seed=17)
                trace.append({"room_id":room.id,"function":room.function,"stats":stats,
                              "design_status":room.metadata.get("room_design")})
                save_json(trace,args.output/"room_trace.json")
                if stats["furnishing_non_degradation_gate_rejected_room_count"]:raise RuntimeError("Room placement rejected")
                if room.metadata.get("room_design",{}).get("status")!="accepted":raise RuntimeError("Fixture fell back; not a successful design")
                print("Placed",room.id,flush=True)
    if len(selected)!=3:raise RuntimeError("Need accepted living/bedroom/office fixture rooms")
    city.world_program=build_world_program(city,producer="interior_asset_placement_offline",seed=17)
    compiler=GeometryCompiler(asset_registry=registry);scene=compiler.compile(city)
    validation=CityValidator().validate(city);geometry=GeometryValidator().validate(city,scene)
    checks=check_placements(scene,selected)
    report={"llm_used":False,"vlm_used":False,"source_scene":str(args.input),"selected_rooms":selected,
        "scope":"existing room inventory replay" if args.replay_existing else "three new offline inventories in copied room envelopes",
        "trace":trace,"surface_items":{rid:scene.metadata.get("room_surface_items",{}).get(rid) for rid in selected},
        "placement_checks":checks,"city_validation":validation.to_dict(),"geometry_validation":geometry.to_dict()}
    save_json(report,args.output/"report.json")
    if not validation.ok or not geometry.ok or not checks or not all(c["ok"] for c in checks):
        raise RuntimeError("Placement/scene validation failed")
    OpenUSDBackend(compiler).compile(city,args.output/"scene",_scene_override=scene)
    save_json(validation.to_dict(),args.output/"scene/validation_report.json")
    export_portable_viewer(args.output/"scene",args.output/"viewer")
    save_json({"selected_views":[{"view_id":f"room_{i}_{preset}","mode":"room","kind":"room_interior",
        "target_entity_ids":[rid],"room_camera_preset":preset,"render_profile":"presentation","appearance":"presentation"}
        for i,rid in enumerate(selected) for preset in ("top","cutaway")]},args.output/"observation.json")
    closeups=[]
    for p in scene.primitives:
        if p.metadata.get("asset_id") not in {"interior_polyhaven_wooden_bookshelf_worn","interior_polyhaven_metal_office_desk"}:continue
        rid=next((r.id for r in city.iter_rooms() if p.owner_id in r.object_ids),None)
        if rid not in selected:continue
        angle=math.radians(p.rotation_z_deg);x,y,z=p.center.x,p.center.y,p.center.z
        distance=1.6 if "bookcase" in p.metadata["asset_category"] else 1.5
        elevation=.25 if "bookcase" in p.metadata["asset_category"] else .9
        closeups.append({"view_id":f"detail_{p.metadata['asset_category']}","mode":"room","kind":"room_interior",
            "target_entity_ids":[rid],"render_profile":"presentation","appearance":"presentation",
            "camera_position":[x+distance*math.cos(angle),y+distance*math.sin(angle),z+elevation],
            "look_at":[x,y,z+.15],"auto_cutaway":False})
    save_json({"selected_views":closeups},args.output/"closeups.json")
    print("Viewer:",args.output/"viewer",flush=True)


if __name__=="__main__":main()
