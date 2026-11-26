"""Paired input diagnostics on frozen scenes, not a benchmark success-rate claim.

No checker verdicts, injected truth, or repair hints are supplied to the model.
The four compact arms share one prompt/schema and differ only in input fields
and image availability. A fifth arm exercises the existing production context.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import time
import jsonschema

from cityg.serialization import load_city, save_json, to_primitive
from cityg.planning.room_envelope import metric_envelope
from cityg.planning.room_metric_frame import restore_metric_object
from cityg.planning.room_constraints import direction
from cityg.validation.visual_grounding import front_verified
from cityg.services.interfaces import ChatMessage, ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from run_edit_method_pilot import RecordedService
from run_easy_visual_defects import public_context

ARMS=('identity_images','geometry_images','contract_images','contract_text','production','progressive','progressive_neighbors','observe_compare','observe_report')
KINDS=('outside','door_blocked','overlap','alignment','appearance','other')
PROMPT=(
    'Inspect this local room snapshot for actionable problems. Some snapshots are normal. '
    'Return issues=[] when no defect is supported. Use only supplied evidence, not imagined '
    'wall preferences or hidden objects. Images, when supplied, depict the SAME room from '
    'above and obliquely; roof removal is intentional. The oblique wall can occlude furniture. '
    'A desk chair between the desk and the entrance is not necessarily blocking the door: '
    'distance and free passage matter. A chair tucked beneath its own desk can be legitimate; '
    'a tall bookcase through a desktop is not. When geometry is provided it uses a single '
    'local metric frame, not screen pixels. Box intersection is evidence to interpret with '
    'object function and imagery, not automatically a collision. Design constraints, if '
    'provided, are intended requirements; geometry is current state. Distinguish what should '
    'be true from what is true. Report exact affected object/group IDs, evidence sources and '
    'a minimal concrete correction. Do not ask to remove required furniture or change room '
    'boundaries. Do not infer a visual appearance problem from text alone. Unknown remains '
    'unknown. Give concise observations before issues; do not invent coordinates.\n'
)


def target(city):
    return next((b,f,r) for b in city.iter_buildings() for f in b.floors for r in f.rooms
                if r.metadata.get('room_design',{}).get('status')=='accepted')


def local_context(city, arm):
    b,f,r=target(city)
    context=public_context(f,r)
    context['images_provided']=arm!='contract_text'
    if arm=='contract_text':context.pop('views',None)
    if arm=='identity_images':return context
    env=metric_envelope(b,f,r)
    if env['status']!='supported':raise ValueError('Uncertified metric frame')
    bb=env['bounds'];ox,oy=bb.min_x,bb.min_y
    point=lambda p:[round(p.x-ox,4),round(p.y-oy,4)]
    bounds=lambda q:[round(q.min_x-ox,4),round(q.min_y-oy,4),
                     round(q.max_x-ox,4),round(q.max_y-oy,4)]
    objects=[restore_metric_object(o,b,f,r,env) for o in f.objects if o.room_id==r.id]
    context['metric_geometry']={
        'frame':{'origin':'room southwest corner on floor','x':'east; right in top view',
                 'y':'north; up in top view','units':'metres'},
        'room_bounds_xyxy':bounds(bb),'room_height_m':r.height_m,
        'doors':[{'door_id':d.id,'center_xy':point(d.position),'width_m':round(d.width_m,4)}
                 for d in env['floor'].doors if r.id in (d.room_a_id,d.room_b_id)],
        'objects':[{'object_id':o.id,'group_id':o.metadata.get('group_key'),
                    'category':o.category,'center_xy':point(o.position),'bounds_xyxy':bounds(o.bounds),
                    'height_m':round(o.height_m,4),'rotation_deg':round(o.rotation_deg,3),
                    'verified_front_xy':list(direction(o)) if front_verified(o) else None}
                   for o in objects]}
    if arm in ('contract_images','contract_text'):
        design=r.metadata['room_design']
        context['intended_design']={key:deepcopy(design.get(key,[]))
            for key in ('groups','group_relations','reserved_areas','protected_groups')}
        # Category/minimum/target only; cached checks and prototype prose excluded.
        context['intended_design']['inventory']=[{k:v for k,v in item.items()
            if k in ('category','minimum','target')} for item in
            design.get('furnishing_brief',{}).get('items',[])]
    return context


def schema_for(context):
    groups=context['room_group_bindings'];rid=context['allowed_entity_ids'][0]
    gids=[g['group_id'] for g in groups[rid]]
    oids=[o['object_id'] for g in groups[rid] for o in g['objects']]
    fields={
        'kind':{'type':'string','enum':list(KINDS)},
        'room_id':{'type':'string','const':rid},
        'object_ids':{'type':'array','items':{'type':'string','enum':oids},'minItems':1},
        'group_ids':{'type':'array','items':{'type':'string','enum':gids},'minItems':1},
        'description':{'type':'string'},'suggested_action':{'type':'string'},
        'evidence_sources':{'type':'array','items':{'type':'string','enum':['image','geometry','design']},'minItems':1},
        'confidence':{'type':'number','minimum':0,'maximum':1}}
    return {'type':'object','additionalProperties':False,'properties':{
        'observations':{'type':'array','maxItems':6,'items':{'type':'string'}},
        'issues':{'type':'array','maxItems':6,'items':{'type':'object','additionalProperties':False,
            'properties':fields,'required':list(fields)}},
        'uncertainties':{'type':'array','items':{'type':'string'}}},
        'required':['observations','issues','uncertainties']}


def progressive_context(city, hypotheses):
    """Disclose selected groups plus nearby geometry, never injected labels."""
    context=local_context(city,'contract_text')
    wanted=set(hypotheses['groups_to_inspect'])
    objects=context['metric_geometry']['objects']
    selected=[o for o in objects if o['group_id'] in wanted]
    def nearby(o):
        a=o['bounds_xyxy']
        for item in selected:
            b=item['bounds_xyxy']
            dx=max(a[0]-b[2],b[0]-a[2],0);dy=max(a[1]-b[3],b[1]-a[3],0)
            if dx*dx+dy*dy<=1.:return True
        return False
    context['metric_geometry']['objects']=[o for o in objects if o['group_id'] in wanted or nearby(o)]
    context['intended_design']['groups']=[g for g in context['intended_design']['groups'] if g['id'] in wanted]
    context['intended_design']['group_relations']=[g for g in context['intended_design']['group_relations']
        if g.get('subject') in wanted or g.get('target') in wanted]
    context['disclosure']={'requested_groups':sorted(wanted),'nearby_objects_are_read_only':True,
        'omitted_geometry_is_unknown_not_absent':True,
        'disclosed_object_count':len(context['metric_geometry']['objects']),
        'total_object_count':len(objects)}
    context['unverified_visual_hypotheses']=hypotheses
    return context


def shortlist(service, city, fixture):
    context=local_context(city,'identity_images')
    gids=[g['group_id'] for group in context['room_group_bindings'].values() for g in group]
    schema={'type':'object','additionalProperties':False,'properties':{
        'observations':{'type':'array','items':{'type':'string'}},
        'groups_to_inspect':{'type':'array','maxItems':2,'items':{'type':'string','enum':gids}},
        'reason':{'type':'string'}},'required':['observations','groups_to_inspect','reason']}
    prompt=('Look at these two views of the SAME room. This is visual triage, not a final verdict. '
        'Identify at most two furniture groups whose placement or visual realization seems wrong, '
        'or requires local metric information to decide. Do not flag normal chair-to-desk spacing '
        'as a blocked door just because it lies on the same line. Note occlusion and uncertainty. '
        'Roof removal is intentional. A normal room is possible: request no groups if no credible '
        'concern exists. You can request details of an uncertain group rather than invent geometry. '
        'Return only exact group IDs from this identity inventory.\n'+json.dumps(context))
    paths=tuple(fixture/f'images/view_{i:02d}.png' for i in (1,2))
    messages=[ChatMessage(role='user',content=prompt,image_paths=paths)]
    for attempt in range(2):
        response=service.complete_with_metadata(messages,schema)
        try:
            if response.finish_reason=='length':raise ValueError('truncated shortlist')
            data=json.loads(response.content);jsonschema.validate(data,schema)
            return data
        except (ValueError,jsonschema.ValidationError) as error:
            if attempt==1:raise
            messages.append(ChatMessage(role='user',content='Return valid complete JSON: '+str(error)[:300]))


def production_plan(city, fixture):
    from cityg.observation import AdaptiveObservationPlanner
    manifest=json.loads((fixture/'scene/geometry_manifest.json').read_text())
    rid=target(city)[2].id
    candidates=AdaptiveObservationPlanner(max_views=12).plan(city,geometry_manifest=manifest).to_dict()['candidates']
    semantics=next(v['semantic_context'] for v in candidates if v['kind']=='room_interior'
                   and rid in v['target_entity_ids'])
    plan=json.loads((fixture/'render_plan.json').read_text())
    for view in plan['selected_views']:
        view['semantic_context']=deepcopy(semantics)
    return plan


def one(source,output,case,arm,seed,base_url,model,shortlist_source=None,realization_check=False,observation_source=None):
    root=output/arm/case/f'seed_{seed}'
    if (root/'result.json').exists():return json.loads((root/'result.json').read_text())
    fixture=source/case;city=load_city(fixture/'scene/city.json')
    service=RecordedService(OpenAICompatibleService(ModelEndpoint(base_url=base_url,model=model,
        timeout_s=180,max_tokens=4096,seed=seed,enable_thinking=False,temperature=.7,top_p=.8)),root/'calls.json')
    report={'case':case,'arm':arm,'seed':seed,'available':False}
    started=time.monotonic()
    try:
        if arm=='production':
            from cityg.adaptive_review import aggregate_visual_reviews
            from cityg.visual_review import VisualReviewAgent
            result=aggregate_visual_reviews(production_plan(city,fixture),fixture/'images',
                VisualReviewAgent(service,max_images=2,max_attempts=2),scene_id=city.id,batch_size=2)
            save_json(result,root/'production_review.json')
            report.update(available=result.get('available_batches',0)==1,
                          issues=result.get('aggregated_issues',[]))
        else:
            if arm in ('observe_compare','observe_report'):
                # Observer receives NO inventory, names, numeric geometry, or
                # expectations; only the actual top image. Judge then compares
                # this independent, fallible observation with the typed plan.
                if observation_source:
                    prior=observation_source/'observe_compare'/case/f'seed_{seed}'/'independent_observation.json'
                    observed=json.loads(prior.read_text())
                    report['reused_visual_observation']={'path':str(prior),'sha256':hashlib.sha256(prior.read_bytes()).hexdigest()}
                else:
                    caption=service.complete_with_metadata([ChatMessage(role='user',
                        content=('Describe the major objects actually visible in this image, their colors, '
                                 'shapes and positions. Do not guess hidden objects or what should be present. '
                                 'Do not diagnose layout. Keep the description concise and factual.'),
                        image_paths=(fixture/'images/view_01.png',))])
                    if caption.finish_reason=='length':raise ValueError('Truncated independent observation')
                    observed={'view_id':'view_01','description':caption.content}
                save_json(observed,root/'independent_observation.json')
                context=local_context(city,'contract_text')
                context['independent_visual_observation']={**observed,
                    'reliability':'fallible observation; not authoritative geometry or identity'}
            elif arm.startswith('progressive'):
                previous=(shortlist_source/'progressive'/case/f'seed_{seed}'/'visual_shortlist.json') if shortlist_source else None
                if previous:
                    hypotheses=json.loads(previous.read_text())
                    report['reused_visual_shortlist']={'path':str(previous),'sha256':hashlib.sha256(previous.read_bytes()).hexdigest()}
                else:hypotheses=shortlist(service,city,fixture)
                save_json(hypotheses,root/'visual_shortlist.json')
                context=progressive_context(city,hypotheses)
            else:context=local_context(city,arm)
            if realization_check:
                context['inspection_task']=('Also check whether visible asset types agree with their expected '
                    'semantic categories. Metadata is the intended identity and placement; it does NOT '
                    'guarantee the imported mesh actually looks correct. Do not infer unseen appearance '
                    'from names or geometry. Report an observed wrong mesh type as appearance. '
                    'If no images are available, this appearance question is unverifiable.')
            schema=schema_for(context)
            save_json(context,root/'input_context.json')
            paths=() if arm in ('contract_text','observe_compare','observe_report') or arm.startswith('progressive') else tuple(fixture/f'images/view_{i:02d}.png' for i in (1,2))
            extra=('The earlier visual hypotheses are UNVERIFIED. This step has no images. '
                   'Accept, correct or reject them using disclosed local facts. Nearby objects are '
                   'context, not new edit targets. Do not infer collision from unknown geometry.\n') if arm.startswith('progressive') else ''
            if arm=='progressive_neighbors':
                extra+=('You MAY report additional affected objects/groups when their disclosed geometry '
                    'supports a finding. Reporting an affected group is NOT edit authorization. '
                    'A later repair gate must separately authorize changed groups. Distinguish outside '
                    '(bounds beyond room) from alignment (wrong required wall).\n')
            if arm=='observe_compare':
                extra=('Compare the independently described visible objects against the intended semantic '
                    'inventory and local positions. The observer did NOT know the intended inventory. '
                    'Cite image only for evidence from that observation. Flag gross semantic mismatches, '
                    'not harmless naming variations such as desk/table or bookcase/storage cabinet. '
                    'An observation may be mistaken; report uncertainty if identity cannot be bound. '
                    'Do not let a correct numeric placement prove that the mesh has the right appearance.\n')
            messages=[ChatMessage(role='user',content=PROMPT+extra+json.dumps(context,ensure_ascii=False),image_paths=paths)]
            if arm=='observe_report':
                context.pop('intended_design',None)
                context.pop('inspection_task',None)
                context['evidence_availability']={'direct_images':False,'independent_visual_report':True}
                schema['properties']['issues']['items']['properties']['evidence_sources']['items']['enum']=['visual_report','geometry']
                prompt=('You are the semantic comparison role following an independent visual observer. '
                    'You HAVE a textual observation of an actual rendered image, but not the image itself. '
                    'Use visual_report as indirect visual evidence; do not claim to have viewed the pixels. '
                    'The identity inventory and coordinates describe the EXPECTED asset semantics/placement. '
                    'They cannot prove an imported mesh looks correct. Compare the observed object types '
                    'and positions with expected entities. Identify gross semantic contradictions, if any, '
                    'and bind them by spatial relationship. The observer did not see the inventory. '
                    'Do not dismiss observed discrepancies merely because numeric placement is valid. '
                    'Conversely, uncertainty or occlusion is not proof of absence. Storage cabinet/bookcase '
                    'and desk/table naming differences are acceptable; door panels may be described as mats '
                    'and are not missing furniture. Only report gross asset-class mismatches, using kind=appearance. '
                    'A normal scene may have no issues. Recommend checking/replacing a wrong asset binding '
                    'rather than moving correctly placed furniture. These are candidate findings, not edit authorization. '
                    'Return observations, issues, uncertainties.\n'+json.dumps(context,ensure_ascii=False))
                messages=[ChatMessage(role='user',content=prompt)]
                save_json(context,root/'input_context.json')
            attempts=2
            if arm.startswith('progressive') and not hypotheses['groups_to_inspect']:
                attempts=0;report.update(available=True,issues=[],observations=hypotheses['observations'],
                    uncertainties=[],stopped_at='no_visual_candidate')
            for attempt in range(attempts):
                completion=service.complete_with_metadata(messages,schema)
                try:
                    if completion.finish_reason=='length':raise ValueError('truncated response')
                    data=json.loads(completion.content)
                    jsonschema.validate(data,schema)
                    # Strict source checks avoid calling pure-text guesses visual observations.
                    for issue in data['issues']:
                        if (arm=='contract_text' or arm.startswith('progressive')) and 'image' in issue['evidence_sources']:
                            raise ValueError('Text-only arm cannot cite image evidence')
                        if arm=='identity_images' and set(issue['evidence_sources'])-{'image'}:
                            raise ValueError('Identity-only arm cannot cite geometric/design facts')
                        if arm=='geometry_images' and 'design' in issue['evidence_sources']:
                            raise ValueError('No design constraints supplied in geometry-only arm')
                        if arm=='progressive' and not set(issue['group_ids'])<=set(hypotheses['groups_to_inspect']):
                            raise ValueError('Only disclosed candidate groups may become edit targets')
                    report.update(available=True,**data);break
                except (ValueError,jsonschema.ValidationError) as error:
                    if attempt==1:raise
                    messages.append(ChatMessage(role='user',content='Return complete valid JSON. '+str(error)[:500]))
    except Exception as error:report['error']=f'{type(error).__name__}: {error}'
    report['elapsed_s']=round(time.monotonic()-started,3)
    report['model_calls']=len(service.calls)
    report['tokens']=sum(c.get('completion',{}).get('usage',{}).get('total_tokens',0) for c in service.calls)
    if arm=='progressive_neighbors' and report['available']:
        report['additional_affected_groups']=sorted({g for i in report['issues'] for g in i['group_ids']}
                                                  -set(hypotheses['groups_to_inspect']))
    save_json(report,root/'result.json')
    print(case,arm,seed,'available=',report['available'],'issues=',len(report.get('issues',[])),report.get('error',''),flush=True)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=Path('analysis_results/easy_visual_defects_20261023'))
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--base-url',default='http://127.0.0.1:8000/v1')
    p.add_argument('--model',default='cityg-llm')
    p.add_argument('--seeds',type=int,nargs='+',default=[7321,7322])
    p.add_argument('--arms',nargs='+',choices=ARMS,default=list(ARMS[:5]))
    p.add_argument('--jobs',type=int,choices=[1,2],default=2)
    p.add_argument('--shortlist-source',type=Path,help='Reuse frozen first-stage evidence for progressive-neighbors comparison')
    p.add_argument('--realization-check',action='store_true')
    p.add_argument('--observation-source',type=Path)
    args=p.parse_args();source=args.source.resolve();output=args.output.resolve()
    cases=[r['case_id'] for r in json.loads((source/'protocol.json').read_text())['cases']]
    hashes={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest()
        for case in cases for p in [source/case/'scene/city.json',*(source/case/'images').glob('*.png')]}
    config={'source':str(source),'seeds':args.seeds,'arms':args.arms,'base_url':args.base_url,
        'model':args.model,'fixture_sha256':hashes,'prompt':PROMPT,
        'scope':'paired_input_diagnostic; no injected truth or checker verdicts in model context'}
    if args.shortlist_source:config['shortlist_source']=str(args.shortlist_source.resolve())
    if args.realization_check:config['realization_check']=True
    if args.observation_source:config['observation_source']=str(args.observation_source.resolve())
    if (output/'protocol.json').exists():
        if json.loads((output/'protocol.json').read_text())!=config:raise ValueError('Resume config mismatch')
    else:save_json(config,output/'protocol.json')
    work=[(case,arm,seed) for case in cases for arm in args.arms for seed in args.seeds]
    random.Random(42).shuffle(work);results=[]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        jobs=[pool.submit(one,source,output,*task,args.base_url,args.model,args.shortlist_source,args.realization_check,args.observation_source) for task in work]
        for future in as_completed(jobs):
            results.append(future.result());save_json(results,output/'results.json')
    assert all(hashlib.sha256((source/path).read_bytes()).hexdigest()==expected for path,expected in hashes.items())
    print('Completed',len(results),'evaluations; source images/cities unchanged',flush=True)


if __name__=='__main__':main()
