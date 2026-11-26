"""VLM check of paired indoor test views with strict room-ID binding and traces."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

from cityg.services import OpenAICompatibleService
from cityg.services.interfaces import ModelEndpoint, ChatMessage
from cityg.serialization import save_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    plan=json.loads((args.run/"observation.json").read_text())
    loads=json.loads((args.run/"screenshots/asset_load_status.json").read_text())["views"]
    groups=defaultdict(list)
    expected=defaultdict(set)
    manifest=args.run/"scene/geometry_manifest.json"
    if manifest.exists():
        for p in json.loads(manifest.read_text())["primitives"]:
            m=p.get("metadata",{})
            if m.get("resolved_asset") and not m.get("surface_subentity"):
                for rid in m.get("room_ids",[]):
                    expected[rid].add(m["asset_category"])
    for view in plan["selected_views"]:
        status=loads[view["view_id"]]
        if not status["ready"] or status["failed"] or status["fallback"]:
            raise ValueError("Unloaded view is not evidence")
        groups[view["target_entity_ids"][0]].append(args.run/"screenshots"/(view["view_id"]+".png"))
        expected[view["target_entity_ids"][0]].update(view.get("expected_asset_categories",[]))
    service=OpenAICompatibleService(ModelEndpoint("http://127.0.0.1:8000/v1","cityg-llm",
        timeout_s=180,max_tokens=2500,temperature=.1,seed=17))
    results=[]
    for rid,images in groups.items():
        if not expected[rid]:raise ValueError("Need expected asset categories to reject empty/occluded views")
        schema={"type":"object","additionalProperties":False,"properties":{
            "room_id":{"type":"string","enum":[rid]},"pass":{"type":"boolean"},
            "confidence":{"type":"number","minimum":0,"maximum":1},
            "visible_categories":{"type":"array","items":{"type":"string"}},
            "issues":{"type":"array","maxItems":4,"items":{"type":"string","maxLength":240}},
            "reason":{"type":"string","maxLength":700}},
            "required":["room_id","pass","confidence","visible_categories","issues","reason"]}
        prompt=(f"Inspect two views of SAME test room {rid}. Reply with concise JSON. "
            "This is intentionally a sparse furniture integration fixture, not a furnished showcase. "
            "Cutaway hides two walls; top view hides ceiling. Do not flag sparsity, deliberately hidden walls, "
            "plain room finishes, or missing optional props. Check visible furniture for wall penetration, "
            "overlap, floating, wrong facing toward a wall, broken meshes/textures, and usable bed/nightstand "
            "or desk/chair relationships. Dark materials/shadows alone are not defects. Do not certify "
            "metric clearance from images. Issues only for visible defects, not generic suggestions; "
            "confidence refers to your visual judgment. Give a short reason citing visible evidence. "
            f"Expected categories: {sorted(expected[rid])}. Report ONLY actually visible categories; "
            "an empty or wall-occluded view cannot pass furniture review.")
        result={"room_id":rid,"images":[str(p) for p in images],"attempts":[],"model":"cityg-llm"}
        import hashlib
        result["image_sha256"]=[hashlib.sha256(p.read_bytes()).hexdigest() for p in images]
        for attempt in range(2):
            try:
                completion=service.complete_with_metadata([ChatMessage("user",prompt,tuple(images))],schema)
                trace={"raw":completion.content,"finish_reason":completion.finish_reason,"usage":completion.usage}
                result["attempts"].append(trace)
                data=json.loads(completion.content)
                if completion.finish_reason!="stop" or data["room_id"]!=rid:
                    raise ValueError("Incomplete or misbound room review")
                result["review"]=data
                result["coverage_ok"]=expected[rid]<=set(data["visible_categories"])
                result["pass"]=data["pass"] is True and data["confidence"]>=.8 and not data["issues"] and result["coverage_ok"]
                break
            except Exception as exc:
                result.setdefault("errors",[]).append(str(exc))
        results.append(result)
        save_json({"scope":"sparse integration fixtures, not exhaustive asset combination review",
                   "rooms":results},args.output)
        print(rid,result.get("review",result.get("errors")),flush=True)
    if not all(r.get("pass") for r in results):
        raise SystemExit("Some room reviews held/failed; see audit")


if __name__=="__main__":main()
