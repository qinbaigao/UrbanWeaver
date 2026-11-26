"""Capture compiled top/perspective views of an exact room, without a browser popup."""
import argparse
import asyncio
import json
import hashlib
from pathlib import Path

from cityg.adaptive_review import _render_plan, _start_server, aggregate_visual_reviews
from cityg.editing import resolve_scene
from cityg.observation import AdaptiveObservationPlanner
from cityg.run_provenance import record_stage_start
from cityg.serialization import load_city, save_json
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from cityg.visual_review import VisualReviewAgent


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scene',type=Path,required=True)
    p.add_argument('--room',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--port',type=int,default=5519)
    p.add_argument('--vlm',action='store_true')
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    record_stage_start(args.output)
    source=resolve_scene(args.scene)
    source_hash=hashlib.sha256(source.canonical_path.read_bytes()).hexdigest()
    city=load_city(source.canonical_path)
    manifest=json.loads((source.compiled_path/'geometry_manifest.json').read_text())
    plan=AdaptiveObservationPlanner(max_views=12).plan(city,geometry_manifest=manifest).to_dict()
    views=[v for v in plan['candidates'] if v['kind']=='room_interior' and args.room in v['target_entity_ids']]
    if not views:raise ValueError('No realizable views for target room')
    plan['selected_views']=views;plan['max_views']=len(views)
    save_json(plan,args.output/'observation_plan.json')
    server,thread,url=_start_server(source.compiled_path,args.port)
    try:
        paths=asyncio.run(_render_plan(url,plan,args.output/'images',asset_timeout_ms=180000))
    finally:
        server.shutdown();server.server_close();thread.join(timeout=10)
    if args.vlm:
        agent=VisualReviewAgent(OpenAICompatibleService(ModelEndpoint(
            base_url='http://127.0.0.1:8000/v1',model='cityg-llm',max_tokens=6144,seed=521)))
        review=aggregate_visual_reviews(plan,args.output/'images',agent,batch_size=2,scene_id=city.id)
        save_json(review,args.output/'visual_review.json')
    unchanged=hashlib.sha256(source.canonical_path.read_bytes()).hexdigest()==source_hash
    print(json.dumps({'images':paths,'source_unchanged':unchanged,'automatic_edits':False},ensure_ascii=False))
    if not unchanged:raise RuntimeError('Source scene unexpectedly changed during capture')


if __name__=='__main__':main()
