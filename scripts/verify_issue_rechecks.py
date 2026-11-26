"""Render an issue-directed VLM recheck of a frozen existing scene; no edits."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from cityg.adaptive_review import (_geometry_manifest, _local_recheck_plan, _render_plan,
                                  _start_server, aggregate_visual_reviews)
from cityg.issue_rechecks import plan_issue_rechecks
from cityg.review_memory import bounded_review_outcome
from cityg.run_provenance import record_stage_start
from cityg.serialization import load_city, save_json
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from cityg.visual_review import VisualReviewAgent


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('run',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--max-views',type=int,default=16);p.add_argument('--port',type=int,default=5317)
    args=p.parse_args()
    if args.output.exists(): p.error('Use a new output directory')
    root=args.run/'visual_review'
    original=json.loads((root/'adaptive_review_report.json').read_text())
    city_path=Path(original['city_refined']); package=Path(original['openusd_after'])
    digest=hashlib.sha256(city_path.read_bytes()).hexdigest();city=load_city(city_path)
    before=json.loads((root/'observation_plan_before.json').read_text())
    touched=set(original['touched_entity_ids'])
    fresh=_local_recheck_plan(city,touched,args.max_views,geometry_manifest=_geometry_manifest(package))
    plan=plan_issue_rechecks(city,before,original['review'],fresh,max_views=args.max_views,touched=touched)
    record_stage_start(args.output);save_json(plan,args.output/'observation_plan.json')
    server,thread,url=_start_server(package,args.port)
    try:
        asyncio.run(_render_plan(url,plan,args.output/'observations',asset_timeout_ms=180000))
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
    service=OpenAICompatibleService(ModelEndpoint('http://127.0.0.1:8000/v1','cityg-llm',
        max_tokens=6144,timeout_s=180,seed=17))
    after=aggregate_visual_reviews(plan,args.output/'observations',VisualReviewAgent(service,max_images=2),
                                   scene_id=city.id,batch_size=2)
    outcome=bounded_review_outcome(original['review'],after,plan,{},
        current_versions={n.entity_id:n.version for n in city.world_program.nodes})
    report={'mode':'read_only_issue_directed_recheck','scene_mutated':False,
        'source_unchanged':hashlib.sha256(city_path.read_bytes()).hexdigest()==digest,
        'source_sha256':digest,'queue_summary':plan['issue_recheck_summary'],
        'review':after,'outcome':outcome,
        'ok':after['status']=='complete' and hashlib.sha256(city_path.read_bytes()).hexdigest()==digest}
    save_json(report,args.output/'report.json')
    print({k:report[k] for k in ('ok','source_unchanged','queue_summary')},flush=True)
    print({k:outcome[k] for k in ('explicit_rechecked_issue_count','comparable_rechecked_issue_count',
                                  'verified_resolved_issue_count')},flush=True)
    return 0 if report['ok'] else 3


if __name__=='__main__': raise SystemExit(main())
