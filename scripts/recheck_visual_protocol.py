"""Replay saved images to test VLM binding/response protocol, without editing scenes.

This is not a new end-to-end generation or an automatic repair success test.
"""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from cityg.adaptive_review import aggregate_visual_reviews
from cityg.run_provenance import source_snapshot
from cityg.serialization import load_city, save_json
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from cityg.validation.visual_grounding import ground_review
from cityg.visual_review import VisualReviewAgent


class ExplicitVerdictReviewer(VisualReviewAgent):
    def review(self,prompt,image_paths,*,context=None):
        prompt += (' For EACH pending issue answer whether THAT DEFECT is visible NOW, '
            'not whether its repair was observed. A defect still visible means verdict=present, '
            'even if you have never seen a repair. A defect that cannot be located confidently '
            'means uncertain. not_observed means you do NOT see the defect in adequate current '
            'evidence; it NEVER means "not observed as resolved". Never move a pending issue '
            'into the new issues list; retain its existing issue_key in issue_followups.')
        return super().review(prompt,image_paths,context=context)


def run(source, output, config, *, stages=('before','after'), view_ids=None,
        batch_size=2, seed=101, clarify_verdicts=False):
    source=source.resolve();output.mkdir(parents=True,exist_ok=False)
    save_json(source_snapshot(),output/'source_provenance.json')
    endpoint=replace(ModelEndpoint(**config['endpoint']),seed=seed,max_tokens=6144)
    save_json(config,output/'config.json')
    rows=[]
    for stage in stages:
        plan_path=source/f'observation_plan_{stage}.json'
        images=source/f'observations_{stage}'
        plan=json.loads(plan_path.read_text())
        if view_ids:
            known={v['view_id'] for v in plan['selected_views']}
            if not set(view_ids)<=known:raise ValueError('Unknown requested view IDs')
            plan['selected_views']=[v for v in plan['selected_views'] if v['view_id'] in view_ids]
        paths=[plan_path,images/'asset_load_status.json']+[
            images/(v['view_id']+'.png') for v in plan['selected_views']]
        fingerprints={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        save_json(fingerprints,output/f'{stage}_input_fingerprints.json')
        print('recheck_start',stage,flush=True)
        reviewer=ExplicitVerdictReviewer if clarify_verdicts else VisualReviewAgent
        report=aggregate_visual_reviews(plan,images,
            reviewer(OpenAICompatibleService(endpoint),max_images=batch_size,max_attempts=2),
            scene_id=plan.get('scene_id','unknown'),batch_size=batch_size)
        city_path=(source.parent/'final/openusd/city.json' if stage=='before' else source/'city_refined.json')
        report=ground_review(load_city(city_path),report)
        save_json(report,output/f'{stage}_review.json')
        attempts=[a for b in report['batches'] for a in b.get('attempts',[])]
        rows.append({'stage':stage,'status':report['status'],'batches':len(report['batches']),
            'available_batches':sum(b['available'] for b in report['batches']),
            'actual_model_calls':len(attempts),'retry_errors':[a['error'] for a in attempts if a.get('error')],
            'issues':len(report.get('aggregated_issues',[])),
            'geometry_confirmed':sum(i.get('independent_verification',{}).get('status')=='confirmed'
                for i in report.get('aggregated_issues',[])),
            'usage':{k:sum(a['usage'][k] for a in attempts) if all(k in a.get('usage',{}) for a in attempts) else None
                for k in ('prompt_tokens','completion_tokens')},
            'source_unchanged':all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in fingerprints.items())})
        save_json({'evidence_type':'saved_image_protocol_development_replay','scene_edits':0,
                   'repair_success_measured':False,'endpoint_overrides':{'seed':seed,'max_tokens':6144},
                   'stages':stages,'view_ids':view_ids,'batch_size':batch_size,
                   'clarify_verdicts':clarify_verdicts,
                   'rows':rows},output/'summary.json')
        print('recheck_end',stage,rows[-1],flush=True)
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--config',type=Path,default=Path('configs/model_method_pilot.json'))
    p.add_argument('--stages',nargs='+',choices=['before','after'],default=['before','after'])
    p.add_argument('--view-ids',nargs='+')
    p.add_argument('--batch-size',type=int,choices=[1,2,3,4],default=2)
    p.add_argument('--seed',type=int,default=101)
    p.add_argument('--clarify-verdicts',action='store_true')
    args=p.parse_args()
    rows=run(args.source,args.output,json.loads(args.config.read_text()),stages=args.stages,
             view_ids=args.view_ids,batch_size=args.batch_size,seed=args.seed,clarify_verdicts=args.clarify_verdicts)
    raise SystemExit(0 if all(r['available_batches']==r['batches'] and r['source_unchanged'] for r in rows) else 3)
