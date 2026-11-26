"""Evidence-bound HSSD acceptance: VLM review, real placement, additive promotion.

No download, no automatic category/front correction, and no promotion of adapter
or hold records. Visual appearance review is not a physics certification.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cityg.assets import AssetRegistry
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.planning.interiors import ASSET_CATALOG, FloorDetailAgent, FurnishingProgram
from cityg.planning.room_design import RoomDesign
from cityg.planning.surface_items import SURFACE_CATALOG
from cityg.assets import AssetResolver
from cityg.services import OpenAICompatibleService
from cityg.services.interfaces import ChatMessage, ModelEndpoint
from scripts.prepare_exterior_assets import write_json
from scripts.prepare_hssd_assets import sha256
from scripts.run_interior_asset_smoke import fixture_city, check_placements
from scripts.annotate_hssd_assets import validate_decisions

SCHEMA = {"type":"object", "additionalProperties":False, "properties":{
    "asset_id":{"type":"string"}, "decision":{"type":"string","enum":["pass","hold"]},
    "confidence":{"type":"number","minimum":0,"maximum":1},
    "category_match":{"type":"boolean"}, "orientation_match":{"type":"boolean"},
    "complete_standalone_object":{"type":"boolean"},
    "issues":{"type":"array","items":{"type":"string"}}, "reason":{"type":"string"}},
    "required":["asset_id","decision","confidence","category_match","orientation_match",
                "complete_standalone_object","issues","reason"]}


def fingerprint(record):
    return hashlib.sha256(json.dumps(record.to_dict(),sort_keys=True).encode()).hexdigest()


def validator_signature():
    files=[Path(__file__),ROOT/"scripts/run_interior_asset_smoke.py"]
    files.extend((ROOT/"src/cityg").rglob("*.py"))
    return hashlib.sha256(json.dumps({str(p.relative_to(ROOT)):sha256(p)
        for p in sorted(files)},sort_keys=True).encode()).hexdigest()


def validate_review(data, asset_id):
    if set(data)!=set(SCHEMA["required"]) or data["asset_id"]!=asset_id:
        raise ValueError("VLM entity/schema mismatch")
    if data["decision"] not in {"pass","hold"}:
        raise ValueError("Invalid decision")
    if type(data["confidence"]) not in (int,float) or not math.isfinite(data["confidence"]) or not 0<=data["confidence"]<=1:
        raise ValueError("Invalid confidence")
    if any(type(data[k]) is not bool for k in ("category_match","orientation_match","complete_standalone_object")):
        raise ValueError("Invalid verdict field")
    if not isinstance(data["issues"],list) or any(not isinstance(i,str) for i in data["issues"]) or not isinstance(data["reason"],str) or not data["reason"].strip():
        raise ValueError("Missing visual evidence")
    return data


def visual_pass(data):
    return (data["decision"]=="pass" and data["confidence"]>=.8
            and data["category_match"] and data["orientation_match"]
            and data["complete_standalone_object"] and not data["issues"])


def load_trials(stage):
    config=json.loads((ROOT/"configs/hssd_asset_annotations.json").read_text())
    validate_decisions(config,AssetRegistry(stage/"candidate_registry.json"),stage)
    registry=AssetRegistry(stage/"placement_registry.json")
    for r in registry.list_all():
        if r.metadata["curation"]["disposition"]!="trial" or not r.metadata["runtime_enabled"]:
            raise ValueError("Non-trial record in trial registry")
        if sha256(registry.resolve_path(r.geometry_path))!=r.metadata["annotation_geometry_sha256"]:
            raise ValueError("Trial geometry changed")
    return registry


def review_one(record, stage, output, service):
    destination=output/"visual"/(record.asset_id+".json")
    binding=fingerprint(record)
    if destination.exists():
        old=json.loads(destination.read_text())
        if old.get("record_sha256")==binding and old.get("review"):
            validate_review(old["review"],record.asset_id)
            return old
    m=record.metadata
    images=[stage/"review/previews"/(record.asset_id+".png")]
    if m["visual_review"].get("top_preview_sha256"):
        images.append(stage/"review_top/previews"/(record.asset_id+".png"))
    context={"asset_id":record.asset_id,"category":record.category,"room_types":record.room_types,
             "dimensions_m":record.dimensions_m,"placement_kind":m["placement_kind"],
             "front_axis":m["orientation"]["canonical_forward_axis"],
             "front_is_convention":m["orientation"].get("front_axis_is_convention",False)}
    prompt=("Independently inspect this indoor asset's rendered four-view contact sheet. "
        "Assess usable visual quality, correct category, complete standalone geometry, upright pose, "
        "obvious broken/missing textures or detached components, and the declared functional front. "
        "Original image labels FRONT +X describe the provisional camera, not a verified semantic front. "
        "First sheet views are from +X, +Y, -X, -Y respectively (front,right,rear,left). "
        "For a bed functional front is its foot, back is its headboard. For a chair front is the seat opening. "
        "A convention-only axis needs no unique functional front. Plain materials/dark upholstery are not "
        "automatically defects. Do not assert dimensions or collision correctness from images. "
        "Judge it as a reusable static visual asset, not a rigged physical object. If uncertain, hold. "
        "issues must contain actionable defects/uncertainties only, not stylistic preferences. "
        "Return JSON matching the schema; reason must describe visible evidence. Metadata:\n"+json.dumps(context))
    result={"asset_id":record.asset_id,"record_sha256":binding,"model":service.endpoint.model,
            "base_url":service.endpoint.base_url,"image_sha256":[sha256(p) for p in images]}
    try:
        response=service.complete_with_metadata([ChatMessage("user",prompt,tuple(images))],SCHEMA)
        result.update(raw=response.content,finish_reason=response.finish_reason,usage=response.usage)
        if response.finish_reason!="stop":raise ValueError("Incomplete model response")
        result["review"]=validate_review(json.loads(response.content),record.asset_id)
        result["pass"]=visual_pass(result["review"])
    except Exception as exc:
        result.update({"pass":False,"error":f"{type(exc).__name__}: {exc}"})
    write_json(destination,result)
    print("visual",m["curation"]["index"],record.category,result.get("pass",False),flush=True)
    return result


def placement_one(record):
    """Exercise normal metric layout + compiler with exactly this resolved asset."""
    category=record.category; kind=record.metadata["placement_kind"]
    if category not in (ASSET_CATALOG if kind=="floor" else SURFACE_CATALOG):
        return {"pass":False,"reason":"placement_category_not_implemented"}
    city=fixture_city(); building=next(city.iter_buildings()); floor=building.floors[0];room=floor.rooms[1]
    room.function=record.room_types[0];room.metadata.clear()
    building.metadata["orientation_deg"]=17
    registry=AssetRegistry();registry.register(record)
    detail=FloorDetailAgent(asset_resolver=AssetResolver(registry,(),max_provider_calls=0))
    anchor=category if kind=="floor" else "meeting_table"
    groups=({"id":"test","zone":"main","anchor":{"id":"asset","category":anchor},"members":[]},)
    requests=() if kind=="floor" else ({"id":"prop","support_member_id":"asset","surface":"top",
                                      "category":category,"count":1,"placement":"spread"},)
    design=RoomDesign("Individual real asset acceptance", "warm",
        ({"id":"main","position":"center","purpose":"asset placement test"},),groups,surface_items=requests)
    detail.program_overrides={room.id:FurnishingProgram(room.id,room.function,"warm",.5,(),design=design)}
    detail.populate_rooms(city,{room.id},seed=17)
    if room.metadata.get("room_design",{}).get("status")!="accepted":
        raise ValueError("Room layout fallback")
    scene=GeometryCompiler(asset_registry=registry).compile(city)
    hits=[p for p in scene.primitives if p.metadata.get("asset_id")==record.asset_id
          and p.metadata.get("resolved_asset")]
    if len(hits)!=1:raise ValueError(f"Expected one actual mesh, found {len(hits)}")
    p=hits[0]
    if any(not math.isclose(x,y,abs_tol=1e-5) for x,y in zip((p.size.x,p.size.y,p.size.z),record.dimensions_m)):
        raise ValueError("Compiler changed physical dimensions")
    if not math.isclose(p.center.z-p.size.z/2,0,abs_tol=1e-5) and kind=="floor":
        raise ValueError("Not grounded")
    checks=check_placements(scene,[room.id]) if kind=="surface" else []
    if kind=="surface" and (not checks or not all(c["ok"] for c in checks)):
        raise ValueError("Support contact/containment failed")
    validation=GeometryValidator().validate(city,scene)
    if not validation.ok:raise ValueError("Compiled geometry validation failed")
    return {"pass":True,"room_type":room.function,"building_yaw_deg":17,
            "scope":"one bounded room, one asset, true metric sizes; not all arrangements",
            "primitive_id":p.id,"dimensions_m":record.dimensions_m,"surface_checks":checks,
            "circulation":floor.objects[0].metadata.get("room_circulation"),"geometry_ok":validation.ok}


def placement(records, output):
    results=[]
    for r in records:
        try:result=placement_one(r)
        except Exception as exc:result={"pass":False,"reason":f"{type(exc).__name__}: {exc}"}
        result.update(asset_id=r.asset_id,record_sha256=fingerprint(r))
        results.append(result)
        print("placement",r.metadata["curation"]["index"],r.category,result["pass"],result.get("reason",""),flush=True)
    write_json(output/"placement.json",{"assets":results,"validator_sha256":validator_signature()})


def eligible(record, visual, placement):
    if visual.get("record_sha256")!=fingerprint(record) or placement.get("record_sha256")!=fingerprint(record):
        raise ValueError("Stale acceptance binding")
    review=validate_review(visual.get("review",{}),record.asset_id)
    expected=[record.metadata["visual_review"]["preview_sha256"]]
    if record.metadata["visual_review"].get("top_preview_sha256"):
        expected.append(record.metadata["visual_review"]["top_preview_sha256"])
    if visual.get("image_sha256")!=expected or visual.get("finish_reason")!="stop":
        raise ValueError("Visual evidence mismatch or truncated response")
    return visual_pass(review) and placement.get("pass") is True


def promote(registry, output, production_path):
    placements=json.loads((output/"placement.json").read_text())
    if placements["validator_sha256"]!=validator_signature():
        raise ValueError("Validator changed; rerun placement")
    by_id={r["asset_id"]:r for r in placements["assets"]}
    before=production_path.read_bytes();payload=json.loads(before)
    existing={r["asset_id"] for r in payload["assets"]};additions=[];decisions=[]
    for r in registry.list_all():
        vpath=output/"visual"/(r.asset_id+".json")
        try:
            visual=json.loads(vpath.read_text());passed=eligible(r,visual,by_id[r.asset_id])
            reason="passed" if passed else "visual_or_placement_gate_failed"
        except (ValueError,KeyError,FileNotFoundError) as exc:
            passed=False;reason=str(exc)
        decisions.append({"asset_id":r.asset_id,"category":r.category,"accepted":passed,"reason":reason})
        if not passed:continue
        if r.asset_id in existing:raise ValueError("Existing asset ID; refuse overwrite: "+r.asset_id)
        path=registry.resolve_path(r.geometry_path).resolve()
        if sha256(path)!=r.metadata["annotation_geometry_sha256"]:raise ValueError("Changed GLB")
        meta={**r.metadata,"indoor_pack_status":"production_accepted","external_content":True,
              "redistribution_policy":"download_required","acceptance":{
                  "policy":"vlm_visual_and_individual_metric_placement_v1",
                  "visual_report":os.path.relpath(vpath,production_path.parent),
                  "visual_report_sha256":sha256(vpath),"placement_report_sha256":sha256(output/"placement.json"),
                  "model":visual["model"],"confidence":visual["review"]["confidence"],
                  "accepted_at":datetime.now(timezone.utc).isoformat(),
                  "simulation_scope":"static visual mesh; no dynamics/articulation certification"}}
        additions.append(replace(r,geometry_path=os.path.relpath(path,production_path.parent),
            preview_path=os.path.relpath(ROOT/"assets/prepared/hssd_v1/review/previews"/(r.asset_id+".png"),production_path.parent),
            metadata=meta).to_dict())
    if not additions:raise ValueError("No assets passed; production unchanged")
    backup=output/"production_registry.before.json"
    if backup.exists():raise ValueError("Promotion already attempted; preserve previous backup")
    backup.write_bytes(before)
    if production_path.read_bytes()!=before:raise ValueError("Concurrent registry modification")
    payload["assets"].extend(additions)
    write_json(production_path,payload)
    write_json(output/"promotion.json",{"added_count":len(additions),"previous_count":len(existing),
        "production_sha256":sha256(production_path),"backup":str(backup),"decisions":decisions})
    print("Promoted",len(additions),"assets; previous records preserved",flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action",choices=["visual","placement","promote"])
    p.add_argument("--stage",type=Path,default=ROOT/"assets/prepared/hssd_v1")
    p.add_argument("--output",type=Path,default=ROOT/"assets/prepared/hssd_v1/acceptance")
    p.add_argument("--production",type=Path,default=ROOT/"assets/asset_registry.json")
    p.add_argument("--workers",type=int,default=2)
    p.add_argument("--limit",type=int)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    registry=load_trials(args.stage);records=registry.list_all()
    if args.limit:records=records[:args.limit]
    if args.action=="visual":
        service=OpenAICompatibleService(ModelEndpoint("http://127.0.0.1:8000/v1","cityg-llm",timeout_s=240,
            max_tokens=1500,temperature=.1,seed=17))
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            results=list(pool.map(lambda r:review_one(r,args.stage,args.output,service),records))
        write_json(args.output/"visual_summary.json",{"count":len(results),"passed":sum(r.get("pass",False) for r in results)})
    elif args.action=="placement":placement(records,args.output)
    else:
        if args.limit:p.error("Cannot limit promotion")
        promote(registry,args.output,args.production)


if __name__=="__main__":main()
