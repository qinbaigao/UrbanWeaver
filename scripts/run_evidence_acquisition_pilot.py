"""Bounded real-scene evidence selection diagnostic, NOT visual quality recall.

Question: does a furniture category exist in the compiled room? Saved images
may occlude it. Raw structural inventories can settle this predicate; a strong
direct-inventory baseline tests whether an agent is necessary at all.
"""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random

from cityg.evidence_acquisition import EvidenceAction, EvidenceSession
from cityg.run_provenance import source_snapshot
from cityg.serialization import load_city, save_json
from cityg.services.interfaces import ChatMessage, ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from cityg.visual_evidence import render_evidence_ready
from run_edit_method_pilot import RecordedService

METHODS=('fixed_view','all_evidence','budgeted_joint','direct_inventory')


def run(source,output,config):
    output.mkdir(parents=True,exist_ok=False)
    save_json(source_snapshot(),output/'source_provenance.json')
    scene=source/'final/openusd';review=source/'visual_review'
    paths=[scene/'city.json',scene/'geometry_manifest.json',review/'observation_plan_before.json',
           review/'observations_before/asset_load_status.json']
    hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    city=load_city(paths[0]);manifest=json.loads(paths[1].read_text())
    plan=json.loads(paths[2].read_text());statuses=json.loads(paths[3].read_text())['views']
    views=[v for v in plan['selected_views'] if v['kind']=='room_interior']
    # Recompute truth from actual compiled primitive owners, NOT the tested
    # model, reported issues or a predicate verdict attached to the query.
    owners={p['owner_id'] for p in manifest['primitives']}
    version=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
    rows=[]
    save_json({'config':config,'methods':METHODS,'predicate':'compiled category presence',
        'seed':101,'max_completion_tokens':512,'max_model_calls':1,'acquisition_budget':6,
        'cost_proxy':{'query':2,'view':4},'image_budget':1,
        'queries_precomputed_from_saved_scene':True,'images_precomputed':True},output/'protocol.json')
    for index,view in enumerate(views):
        target=view['target_entity_ids'][0]
        image=review/'observations_before'/(view['view_id']+'.png')
        hashes[str(image.resolve())]=hashlib.sha256(image.read_bytes()).hexdigest()
        if not render_evidence_ready(statuses.get(view['view_id'],{})):
            raise ValueError('Unready source image; do not evaluate it as complete visual evidence')
        objects=[o for f in city.iter_floors() for o in f.objects if o.room_id==target]
        inventory=[{'object_id':o.id,'category':o.category} for o in objects if o.id in owners]
        if sorted(o['object_id'] for o in inventory)!=sorted(view['semantic_context']['compiled_object_ids']):
            raise ValueError('Saved screenshot context and current compiled inventory disagree')
        # One present but possibly occluded category and one absent category per
        # room. No test label appears in IDs, query content, prompts or schemas.
        categories=['bookcase','bed']
        if 'bookcase' not in {o['category'] for o in inventory} or 'bed' in {o['category'] for o in inventory}:
            raise ValueError('Fixture does not match the declared balanced presence protocol')
        for category in categories:
            expected='present' if any(o.category==category and o.id in owners for o in objects) else 'absent'
            methods=list(METHODS);random.Random(f'{index}:{category}').shuffle(methods)
            for method in methods:
                key=f'{index}_{category}_{method}';print('acquisition_start',key,flush=True)
                row={'id':key,'method':method,'room_id':target,'category':category,
                     'ground_truth':expected,'correct':False,'wrong_assertion':False,'unknown':False}
                service=None;images=();evidence={};receipt=None
                try:
                    query=EvidenceAction('compiled_inventory','query',target,version,('compiled_presence',),2)
                    photo=EvidenceAction('detail_view','view',target,version,('visual_presence',),4)
                    def provider(action):
                        return {'target_id':target,'version':version,'ready':True,'supports':action.supports,
                            'data':inventory if action.kind=='query' else {'image':str(image),'view_id':view['view_id']}}
                    if method=='budgeted_joint':
                        session=EvidenceSession(target,version,['compiled_presence'],budget=6,max_views=1)
                        while (action:=session.choose([query,photo])) is not None:
                            session.acquire(action,provider)
                        receipt=session.report()
                        evidence={'compiled_inventory':inventory,'inventory_complete':True} if receipt['complete'] else {}
                        row['acquisition_cost']=receipt['estimated_cost']
                    elif method in {'all_evidence','direct_inventory'}:
                        evidence={'compiled_inventory':inventory,'inventory_complete':True}
                        row['acquisition_cost']=6 if method=='all_evidence' else 2
                    else:row['acquisition_cost']=4
                    if method in {'fixed_view','all_evidence'}:images=(image,)
                    if method=='direct_inventory':
                        # Baseline uses the raw query like any consumer, never
                        # the separate expected label or reported VLM issues.
                        answer={'verdict':'present' if any(o['category']==category for o in evidence['compiled_inventory']) else 'absent',
                                'reason':'Exhaustive compiled inventory lookup'}
                    else:
                        endpoint=replace(ModelEndpoint(**config['endpoint']),seed=101,max_tokens=512)
                        service=RecordedService(OpenAICompatibleService(endpoint),output/f'traces/{key}.json')
                        response=service.complete_with_metadata([
                            ChatMessage(role='system',content='Inspect whether the specified category exists in the compiled room, '
                                'NOT whether it is visible from the current camera. A complete compiled inventory can establish '
                                'presence or absence; occlusion or an incomplete camera view cannot establish absence. If evidence '
                                'is insufficient return unknown. Do not invent object IDs. Give a short reason, then a consistent verdict.'),
                            ChatMessage(role='user',content=json.dumps({'room_id':target,'requested_category':category,
                                'evidence':evidence}),image_paths=images)],
                            {'type':'object','additionalProperties':False,'properties':{
                                'reason':{'type':'string','maxLength':200},
                                'verdict':{'type':'string','enum':['present','absent','unknown']}},
                             'required':['reason','verdict']})
                        if response.finish_reason=='length':raise ValueError('Truncated reply')
                        answer=json.loads(response.content)
                    row.update(answer=answer,correct=answer['verdict']==expected,
                        wrong_assertion=answer['verdict'] not in {expected,'unknown'},unknown=answer['verdict']=='unknown')
                    if receipt:save_json(receipt,output/f'receipts/{key}.json')
                except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}'
                row['images']=len(images);row['model_calls']=len(service.calls) if service else 0
                usage=[c.get('completion',{}).get('usage',{}) for c in service.calls] if service else []
                row['prompt_tokens']=sum(u.get('prompt_tokens',0) for u in usage)
                row['completion_tokens']=sum(u.get('completion_tokens',0) for u in usage)
                rows.append(row)
                summary={m:{'trials':len(g:=[r for r in rows if r['method']==m]),
                    **{k:sum(r.get(k,0) for r in g) for k in ('correct','wrong_assertion','unknown','model_calls',
                        'images','prompt_tokens','completion_tokens','acquisition_cost')}} for m in METHODS}
                save_json({'rows':rows,'summary':summary,'evidence_type':'bounded_compiled_presence_acquisition_diagnostic',
                    'limitations':['Single generated scene, four saved views; not four independent scenes.',
                        'Compiled presence has structural ground truth; aesthetics and screenshot visibility do not.',
                        'This predicate is exactly query-answerable: compare against direct lookup, not only image-only.',
                        'No injected visual defect, no new capture, no scene mutation or repair credit.',
                        'Shared budget is proxy cost and image/call caps, not an exact matched-token experiment.',
                        'Generic scheduler is a library/pilot, not yet wired into full production review.']},output/'summary.json')
                print('acquisition_end',key,row['correct'],row['unknown'],row.get('error'),flush=True)
    save_json({'hashes':hashes,'source_unchanged':all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
        for p,h in hashes.items())},output/'input_provenance.json')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=Path('outputs/paper_e2e_expansion_20261011_v1/residential_public_s101/generation'))
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--config',type=Path,default=Path('configs/model_method_pilot.json'))
    a=p.parse_args();run(a.source,a.output,json.loads(a.config.read_text()))
