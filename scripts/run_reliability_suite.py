"""Frozen small cold generations + chained edits, retaining every failure.

Uses the ordinary main script, never weakens per-case targets to rescue a run.
No deletion, resumption into existing outputs, or implicit browser opening.
--cases limits a debugging subset; omitted cases remain explicitly untested.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time
import traceback

from cityg.run_provenance import record_stage_start, source_snapshot
from cityg.serialization import load_city, save_json
from verify_unified_acceptance import audit


ROOT=Path(__file__).resolve().parents[1]


def frozen_core(snapshot):
    return {k:v for k,v in snapshot['file_sha256'].items()
            if k.startswith(('src/','configs/','viewer/src/'))
            or k=='scripts/run_cityg_pipeline.sh'}


def execute(command, log, env):
    started=time.monotonic()
    with log.open('w') as stream:
        result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
    return {'command':command,'exit_code':result.returncode,'elapsed_s':round(time.monotonic()-started,2),
            'log':str(log)}


def instruction_for(case, common, seed):
    return (case['instruction']+'\n'+common+'\n'+
        '\n'.join(f'{k}={v}' for k,v in {'building_count':case['buildings'],
            'width_m':case['width_m'],'depth_m':case['depth_m'],
            'min_floors':2,'max_floors':3,'seed':seed}.items()))


def edit_checks(run, output, env):
    review=json.loads((run/'visual_review/adaptive_review_report.json').read_text())
    city=load_city(review['city_refined']);building=next(city.iter_buildings())
    floor=building.floors[0]
    old_material=building.metadata.get('appearance_plan',{}).get('material_family')
    palette=building.metadata.get('appearance_plan',{}).get('context',{}).get('material_palette',[])
    alternatives=[v for v in (palette or ['brick','plaster','stone','metal','glass']) if v!=old_material]
    # Positive material tests must respect the accepted architecture contract.
    # A singleton palette instead tests safe refusal, never an implicit rewrite
    # of the district's accepted palette just to get an edit to pass.
    material=alternatives[0] if alternatives else ('plaster' if old_material!='plaster' else 'brick')
    instructions=[('rename',f'仅将 id={building.id} 的建筑显示名称改为“验收楼甲”，其它内容不变。',{'applied'}),
        ('material',f'仅将 id={building.id} 的 appearance_plan.material_family 改为 {material}，保留形状、入口、楼层和室内陈设。',
         {'applied'} if alternatives else {'needs_clarification','rejected','replan_required'}),
        ('ambiguous','把这栋楼改漂亮一点。',{'needs_clarification'}),
        ('infeasible_floor',f'将 id={floor.id} 的楼层改为10000个独立办公室，保持现有楼板大小、入口、核心筒及家具尺度，不允许减少数量。',
         {'rejected','needs_clarification','replan_required'})]
    current=run;rows=[]
    for key,text,expected in instructions:
        target=output/key
        result=execute([sys.executable,'-m','cityg','agent-edit','--scene',str(current),
            '--instruction',text,'--output',str(target),'--max-tokens','6144',
            '--max-attempts','3','--no-viewer'],output/(key+'.log'),env)
        report_path=target/'edit_result.json'
        report=json.loads(report_path.read_text()) if report_path.is_file() else {}
        status=report.get('status','missing_result')
        row={**result,'kind':key,'instruction':text,'output':str(target),'status':status,
             'expected_status':sorted(expected),'ok':status in expected}
        if status!='applied': row['ok'] &= not (target/'final').exists()
        if status=='applied':
            final=load_city(target/'final/city.json')
            b=next(b for b in final.iter_buildings() if b.id==building.id)
            if key=='rename': row['ok'] &= b.name=='验收楼甲'
            elif key=='material':
                row['ok'] &= b.metadata.get('appearance_plan',{}).get('material_family')==material
            current=target
        rows.append(row)
        save_json(rows,output/'edit_checks.json')
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--manifest',type=Path,default=ROOT/'configs/reliability_cases.json')
    p.add_argument('--config',type=Path,default=ROOT/'configs/reliability_acceptance.env')
    p.add_argument('--cases',nargs='+',help='Exact case IDs such as residential_public_s101')
    args=p.parse_args();root=args.output.resolve()
    if root.exists(): p.error('Use a fresh output directory; failed cases are never overwritten')
    manifest=json.loads(args.manifest.read_text())
    matrix=[(c,s,f'{c["id"]}_s{s}') for c in manifest['cases'] for s in manifest['seeds']]
    if args.cases and set(args.cases)-{key for _,_,key in matrix}: p.error('Unknown case ID')
    selected=[r for r in matrix if not args.cases or r[2] in args.cases]
    root.mkdir(parents=True)
    record_stage_start(root);save_json(manifest,root/'frozen_manifest.json')
    frozen=frozen_core(source_snapshot())
    env={**os.environ,'PYTHONPATH':str(ROOT/'src'),'NO_PROXY':'127.0.0.1,localhost',
         'no_proxy':'127.0.0.1,localhost'}
    rows=[]
    def publish():
        save_json({'manifest_sha256':hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
            'configured_case_count':len(matrix),'selected_case_count':len(selected),'cases':rows,
            'not_run':[key for _,_,key in matrix if key not in {r['id'] for r in rows}],
            'all_selected_passed':len(rows)==len(selected) and all(r.get('ok') for r in rows),
            'all_configured_passed':len(rows)==len(matrix) and all(r.get('ok') for r in rows),
            'claims':manifest['claims']},root/'suite_report.json')
    publish()
    for case,seed,key in selected:
        if frozen_core(source_snapshot())!=frozen:
            rows.append({'id':key,'ok':False,'status':'not_run_source_changed'});publish();break
        if shutil.disk_usage(root).free<8*1024**3:
            rows.append({'id':key,'ok':False,'status':'not_run_disk_budget'});publish();break
        folder=root/key;folder.mkdir();record_stage_start(folder)
        instruction=instruction_for(case,manifest['common_instruction'],seed)
        (folder/'instruction.txt').write_text(instruction,encoding='utf-8')
        config=folder/'pipeline.env'
        config.write_text('source '+shlex.quote(str(args.config.resolve()))+'\n'+
                          f'MODEL_SEED={seed}\nREVIEW_SEED={seed}\n',encoding='utf-8')
        print(f'START {key}',flush=True)
        execution=execute(['bash','scripts/run_cityg_pipeline.sh',instruction,str(folder/'generation')],
                          folder/'pipeline.log',{**env,'CITYG_CONFIG':str(config)})
        row={'id':key,'execution':execution,'ok':False};rows.append(row)
        try:
            run=folder/'generation'
            edits=[]
            if execution['exit_code']==0:
                edits=edit_checks(run,folder,env)
            row['edits']=edits
            physics=None
            stage=run/'visual_review/openusd_after/usd/city.usda'
            python=ROOT/'.venv-ovphysx/bin/python'
            if stage.is_file() and python.is_file():
                physics=folder/'physics.json'
                row['physics_execution']=execute([str(python),'scripts/ovphysx_runtime_check.py',
                    str(stage),'--report',str(physics)],folder/'physics.log',env)
                if not physics.is_file(): physics=None
            report=audit(run,buildings=case['buildings'],rooms=manifest['fine_rooms'],
                edit_paths=[r['output'] for r in edits if r['status'] in {'applied','needs_clarification'}],
                physics_report=physics,pipeline_exit_code=execution['exit_code'])
            save_json(report,folder/'acceptance_audit.json')
            row['ok']=report['ok'] and bool(edits) and all(r['ok'] for r in edits)
            row['physics_runtime_tested']=report['physics_runtime_tested']
            row['failed_checks']=[c for c in report['checks'] if not c['ok']]
            versions=[frozen_core(json.loads(p.read_text())) for p in folder.rglob('source_provenance.json')]
            row['frozen_core_verified']=all(v==frozen for v in versions) and frozen_core(source_snapshot())==frozen
            row['ok'] &= row['frozen_core_verified'] and report['physics_runtime_tested']
        except Exception as error:
            row['error']=f'{type(error).__name__}: {error}'
            (folder/'audit_error.txt').write_text(traceback.format_exc())
        publish();print(f'END {key}: ok={row["ok"]}, exit={execution["exit_code"]}',flush=True)
    return 0 if len(rows)==len(selected) and all(r.get('ok') for r in rows) else 3


if __name__=='__main__': raise SystemExit(main())
