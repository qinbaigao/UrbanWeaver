"""Two fixed-budget cold main-script runs; preserve failures, no defect hunting.

Census deterministic room facts separately from VLM proposals. A zero defect
count means repair effectiveness is unmeasured, never perfect success.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from cityg.run_provenance import source_snapshot
from cityg.serialization import load_city,save_json
from cityg.validation.visual_grounding import room_facts


def census(run):
    scene=run/'final/openusd/city.json'
    if not scene.is_file():return {'status':'no_final_scene','rooms':[]}
    city=load_city(scene);rows=[]
    for room in city.iter_rooms():
        if room.metadata.get('room_design',{}).get('status')!='accepted':continue
        facts=room_facts(city,room.id)
        rows.append({'room_id':room.id,'supported':facts['supported'],
            'reason':facts.get('reason'),'state_hash':facts.get('state_hash'),
            'failed_checks':[c for c in facts.get('checks',[]) if c['ok'] is False],
            'unknown_checks':[c for c in facts.get('checks',[]) if c['ok'] is None]})
    path=run/'visual_review/adaptive_review_report.json'
    review=json.loads(path.read_text()) if path.is_file() else {}
    findings=review.get('review',{}).get('aggregated_issues',[])
    after=review.get('review_after',{})
    return {'status':'censused','scene_phase':'before_review','rooms':rows,'accepted_design_rooms':len(rows),
        'supported_rooms':sum(r['supported'] for r in rows),
        'structural_failed_checks':sum(len(r['failed_checks']) for r in rows),
        'structural_unknown_checks':sum(len(r['unknown_checks']) for r in rows),
        'vlm_findings':findings,'touched_entity_ids':review.get('touched_entity_ids',[]),
        'review_report_available':bool(review),'review_status':review.get('review',{}).get('status'),
        'after_review_status':after.get('status'),
        'manual_visual_truth_available':False,'repair_success_rate':None,
        'note':'Only supported structural predicates; no visual defect recall or human truth implied.'}


def run(output,manifest,config,*,audit_only=False):
    if audit_only:
        state=json.loads((output/'sampling_report.json').read_text())
        for row in state['cases']:row['census']=census(output/row['id'])
        save_json(state,output/'sampling_report.json');return
    output.mkdir(parents=True,exist_ok=False)
    save_json(source_snapshot(),output/'source_provenance.json');save_json(manifest,output/'frozen_cases.json')
    cases=[]
    def publish():
        save_json({'configured':len(manifest['cases']),
            'attempted':sum('exit_code' in c for c in cases),'cases':cases,
            'split':manifest['split'],'sampling_stop':manifest['sampling_stop']},output/'sampling_report.json')
    publish()
    env={**os.environ,'CITYG_CONFIG':str(config.resolve()),'PYTHONPATH':'src',
        'NO_PROXY':'127.0.0.1,localhost','no_proxy':'127.0.0.1,localhost'}
    for case in manifest['cases']:
        if shutil.disk_usage(output).free<10*1024**3:
            cases.append({'id':case['id'],'status':'not_run_disk_budget'});publish();continue
        print('START',case['id'],flush=True);start=time.monotonic()
        with (output/(case['id']+'.log')).open('w') as log:
            process=subprocess.run(['bash','scripts/run_cityg_pipeline.sh',case['instruction'],str(output/case['id'])],
                                   env=env,stdout=log,stderr=subprocess.STDOUT)
        row={'id':case['id'],'exit_code':process.returncode,'elapsed_s':time.monotonic()-start,
             'census':census(output/case['id'])};cases.append(row)
        publish()
        print('END',case['id'],process.returncode,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--manifest',type=Path,default=Path('configs/natural_issue_cases.json'))
    p.add_argument('--config',type=Path,default=Path('configs/natural_issue_sampling.env'))
    p.add_argument('--audit-only',action='store_true')
    a=p.parse_args();run(a.output.resolve(),json.loads(a.manifest.read_text()),a.config,audit_only=a.audit_only)
