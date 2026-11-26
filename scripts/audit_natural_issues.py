"""Read-only audit and unlabelled visual review packet for a frozen sample.

Model proposals are deliberately excluded from the human packet. Structural
checks reuse production code and are not an independent visual ground truth.
"""
import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import shutil

from cityg.serialization import load_city, save_json
from cityg.validation.visual_grounding import room_facts


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path, default=None):
    return json.loads(path.read_text()) if path.is_file() else default


def room_audit(path, references=None):
    if not path.is_file():
        return {'status':'not_available','rooms':[]}
    city=load_city(path); rows=[]
    for room in city.iter_rooms():
        if room.metadata.get('room_design',{}).get('status')!='accepted':
            continue
        facts=room_facts(city,room.id,reference=(references or {}).get(room.id))
        rows.append({'room_id':room.id,**facts})
    return {'status':'checked','city_sha256':digest(path),'rooms':rows,
        'supported_rooms':sum(r['supported'] for r in rows),
        'failed_checks':sum(c['ok'] is False for r in rows for c in r.get('checks',[])),
        'unknown_checks':sum(c['ok'] is None for r in rows for c in r.get('checks',[]))}


def rejected_attempts(run):
    """Count trace attempts, not unique scene defects or successful repairs."""
    rows=[];seen={}
    def walk(value,path,pointer=''):
        if isinstance(value,dict):
            if 'attempts' in value and isinstance(value['attempts'],list):
                for i,attempt in enumerate(value['attempts']):
                    if isinstance(attempt,dict) and attempt.get('error'):
                        key=hashlib.sha256(json.dumps(attempt,sort_keys=True).encode()).hexdigest()
                        source={'trace':str(path.relative_to(run)),'pointer':pointer+'/attempts/'+str(i)}
                        if key in seen:
                            seen[key]['duplicate_trace_sources'].append(source)
                        else:
                            item={**source,'attempt_sha256':key,'error':attempt['error'],
                                  'duplicate_trace_sources':[]}
                            rows.append(item);seen[key]=item
            for k,v in value.items():
                if k!='attempts':walk(v,path,pointer+'/'+k)
        elif isinstance(value,list):
            for i,v in enumerate(value):walk(v,path,pointer+'/'+str(i))
    for folder in ('requirement','programs'):
        for path in sorted((run/folder).glob('*trace.json')):
            walk(read(path),path)
    return rows


def audit_run(run):
    before=room_audit(run/'final/openusd/city.json')
    refs={r['room_id']:r for r in before['rooms'] if r.get('supported')}
    after=room_audit(run/'visual_review/city_refined.json',refs)
    review=read(run/'visual_review/adaptive_review_report.json',{})
    issues=review.get('review',{}).get('aggregated_issues',[])
    proofs=review.get('independent_issue_checks',{})
    return {'before':before,'after':after,'rejected_planning_attempts':rejected_attempts(run),
        'review_report_available':bool(review),
        'review_coverage':{phase:{key:review.get(phase,{}).get(key)
            for key in ('status','batch_count','available_batches','requires_manual_review')}
            for phase in ('review','review_after')},
        'vlm_issue_count':len(issues),'vlm_verification_counts':dict(Counter(
            i.get('independent_verification',{}).get('status','unverified') for i in issues)),
        'confirmed_issue_proofs':proofs,
        'confirmed_issue_count':len(proofs),'resolved_confirmed_issues':sum(p['ok'] for p in proofs.values()),
        'structural_repair_success_rate':sum(p['ok'] for p in proofs.values())/len(proofs) if proofs else None,
        'touched_entity_ids':review.get('touched_entity_ids',[]),
        'visual_repair_success_rate':None,'manual_truth_available':False,
        'scope':'Production structural checker re-evaluation; no independent visual truth or recall claim.'}


def packet_views(run,case_id,packet):
    views=[]
    for phase in ('before','after'):
        review=run/'visual_review'
        plan_path=review/f'observation_plan_{phase}.json'
        # Some refinements replace the final plan path; use the recorded artifact.
        report=read(review/'adaptive_review_report.json',{})
        if phase=='after' and report.get('after_plan'):
            plan_path=Path(report['after_plan'])
        plan=read(plan_path,{})
        image_root=review/f'observations_{phase}'
        if phase=='after' and plan_path.name=='observation_plan_final.json':
            image_root=review/'observations_final'
        load=read(image_root/'asset_load_status.json',{}).get('views',{})
        for view in plan.get('selected_views',[]):
            vid=view['view_id'];source=image_root/(vid+'.png')
            if not source.is_file():continue
            token=f'image_{len(list(packet.glob("*.png"))):04d}'
            target=packet/(token+'.png');shutil.copyfile(source,target)
            state=load.get(vid,{})
            views.append({'image_id':token,'file':target.name,'case_id':case_id,
                'phase':phase,'view_id':vid,'kind':view.get('kind'),
                'target_entity_ids':view.get('target_entity_ids',[]),
                'image_sha256':digest(source),'source':str(source.resolve()),
                'load_status':state,'label':None,'issues':[],
                'visibility':'unlabelled','reviewer':None})
    return views


def audit(sample,output):
    output.mkdir(parents=True,exist_ok=False)
    cases=read(sample/'frozen_cases.json')['cases']
    reports={case['id']:audit_run(sample/case['id']) for case in cases}
    save_json({'cases':reports,'sampling':read(sample/'sampling_report.json'),
        'label_policy':'No generated human labels; VLM proposals are hypotheses.'},output/'audit.json')
    packet=output/'human_review';packet.mkdir();views=[]
    for case in cases:views.extend(packet_views(sample/case['id'],case['id'],packet))
    save_json({'instructions':'Inspect images without consulting VLM proposals. Set label to defect, no_visible_defect, or uncertain; record target, defect description and visibility. No visible defect does not certify unobserved space. Phase is not a method label; review is not an independent annotator by itself.',
        'user_instructions':{case['id']:case.get('instruction') for case in cases},
        'views':views},packet/'labels.json')
    cards=[]
    for v in views:
        targets=v['target_entity_ids'];shown=', '.join(targets[:4])
        if len(targets)>4:shown+=f' … ({len(targets)} targets; see labels.json)'
        title=html.escape(v['image_id']+' | '+str(v['kind'])+' | '+shown)
        cards.append(f'<section><h2>{title}</h2><img loading="lazy" src="{v["file"]}"></section>')
    (packet/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Unlabelled scene audit</title>'
        '<style>body{font:16px sans-serif;max-width:1200px;margin:auto}img{max-width:100%}h2{font-size:16px;overflow-wrap:anywhere}</style>'
        '<h1>Unlabelled scene audit</h1><p>Record labels in labels.json. Model proposals are omitted. '
        'Occluded or unloaded content is uncertain, not missing.</p>'+''.join(cards))
    return reports


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sample',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();reports=audit(args.sample,args.output)
    for name,r in reports.items():
        print(name, 'before',r['before'].get('failed_checks'),'after',r['after'].get('failed_checks'),
              'VLM',r['vlm_issue_count'],'confirmed',r['confirmed_issue_count'])
