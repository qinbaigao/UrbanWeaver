"""Read-only replay of production review on version-matched saved room views.

This validates compiled inventory integration, not aesthetic accuracy or repair.
No fresh screenshots, asset copies or scene mutations are performed.
"""
import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from cityg.adaptive_review import aggregate_visual_reviews
from cityg.run_provenance import source_snapshot
from cityg.serialization import load_city, save_json
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from cityg.visual_evidence import compiled_inventory_facts, render_evidence_ready, room_visual_contract
from cityg.visual_review import VisualReviewAgent
from run_edit_method_pilot import RecordedService


def ground_saved(output,source):
    from cityg.validation.visual_grounding import ground_review
    summary=json.loads((output/'summary.json').read_text())
    if not all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in summary['hashes'].items()):
        raise ValueError('Source changed; do not ground stale replay')
    city=load_city(source/'final/openusd/city.json')
    grounded=ground_review(city,json.loads((output/'review.json').read_text()))
    save_json(source_snapshot(),output/'grounding_source_provenance.json')
    save_json(grounded,output/'grounded_review.json')
    issues=grounded.get('aggregated_issues',[])
    summary['independently_confirmed_issues']=sum(i.get('independent_verification',{}).get('status')=='confirmed' for i in issues)
    summary['allowed_after_grounding']=sum(i.get('automatic_repair_allowed',False) for i in issues)
    summary['actual_repairs']=0
    save_json(summary,output/'summary.json')
    print(json.dumps({k:v for k,v in summary.items() if k!='hashes'},ensure_ascii=False),flush=True)


def run(source,output,config):
    output.mkdir(parents=True,exist_ok=False)
    save_json(source_snapshot(),output/'source_provenance.json')
    paths=[source/'final/openusd/city.json',source/'final/openusd/geometry_manifest.json',
           source/'visual_review/observation_plan_before.json',
           source/'visual_review/observations_before/asset_load_status.json']
    hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    city=load_city(paths[0]);manifest=json.loads(paths[1].read_text())
    plan=json.loads(paths[2].read_text());statuses=json.loads(paths[3].read_text())['views']
    rooms={r.id:(b,f,r) for b in city.iter_buildings() for f in b.floors for r in f.rooms}
    owners={p['owner_id'] for p in manifest['primitives']}
    views=[];inventory_checks=[];image_dir=paths[3].parent
    for original in plan['selected_views']:
        if original['kind']!='room_interior':continue
        view=deepcopy(original);target=view['target_entity_ids'][0]
        if not render_evidence_ready(statuses.get(view['view_id'],{})):
            raise ValueError('Saved image is not ready')
        b,f,r=rooms[target];objects=[o for o in f.objects if o.room_id==r.id and o.id in owners]
        if sorted(o.id for o in objects)!=sorted(view['semantic_context']['compiled_object_ids']):
            raise ValueError('Saved observation and compiled inventory differ')
        # Add the explicit room binding introduced by the production contract.
        view['semantic_context'].update(room_visual_contract(b,f,r))
        facts=compiled_inventory_facts(view)
        expected=dict(sorted(Counter(o.category for o in objects).items()))
        inventory_checks.append({'view_id':view['view_id'],'room_id':target,
                                 'passed':facts['counts']==expected,'facts':facts,'expected':expected})
        if facts['counts']!=expected:raise ValueError('Direct compiled query disagrees with manifest join')
        image=image_dir/(view['view_id']+'.png')
        hashes[str(image.resolve())]=hashlib.sha256(image.read_bytes()).hexdigest()
        views.append(view)
    if not views:raise ValueError('No saved room views')
    plan={'selected_views':views}
    save_json(plan,output/'replay_plan.json')
    save_json(inventory_checks,output/'inventory_checks.json')
    endpoint=replace(ModelEndpoint(**config['endpoint']),max_tokens=2048,seed=101)
    service=RecordedService(OpenAICompatibleService(endpoint),output/'model_trace.json')
    report=aggregate_visual_reviews(plan,image_dir,VisualReviewAgent(service,max_attempts=2),
                                    scene_id=city.id,batch_size=2)
    save_json(report,output/'review.json')
    summary={'evidence_type':'saved_image_production_review_integration',
        'views':len(views),'inventory_checks_passed':sum(r['passed'] for r in inventory_checks),
        'review_status':report['status'],'available_batches':report['available_batches'],
        'batch_count':report['batch_count'],'model_calls':len(service.calls),
        'reported_issues':len(report.get('aggregated_issues',[])),
        'source_unchanged':all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items()),
        'hashes':hashes,'limitations':['Single old scene and saved views; no new end-to-end run.',
            'Counts certify compiled major furniture, not image visibility or aesthetics.',
            'No scene mutation, independently labelled visual defects or repair success measurement.']}
    save_json(summary,output/'summary.json');print(json.dumps(summary,ensure_ascii=False),flush=True)
    ground_saved(output,source)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=Path('outputs/paper_e2e_expansion_20261011_v1/residential_public_s101/generation'))
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--config',type=Path,default=Path('configs/model_method_pilot.json'))
    p.add_argument('--ground-only',action='store_true',help='Recheck saved report against unchanged source, without model calls')
    a=p.parse_args()
    if a.ground_only:ground_saved(a.output,a.source)
    else:run(a.source,a.output,json.loads(a.config.read_text()))
