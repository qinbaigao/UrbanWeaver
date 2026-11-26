"""Read-only diagnostics of all selected cases, including failures and versions.

The execution report remains immutable. Supplemental replays do not turn an
original failed case into a pass. Core source/config changes are explicit.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from cityg.review_memory import bounded_review_outcome
from cityg.serialization import load_city, save_json


def read(path, default=None):
    return json.loads(path.read_text()) if path.is_file() else default


def core_fingerprint(provenance):
    hashes={k:v for k,v in provenance.get('file_sha256',{}).items()
            if k.startswith(('src/','configs/','viewer/src/')) or k=='scripts/run_cityg_pipeline.sh'}
    return hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest() if hashes else None


def stage_fingerprints(root):
    """Include published and rejected edits, not only generation/review stages."""
    return {str(path.relative_to(root)):core_fingerprint(read(path,{}))
            for path in sorted(root.rglob('source_provenance.json'))}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('suite',type=Path);p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    if args.output.exists(): p.error('Use a new report path to preserve earlier evidence')
    manifest=read(args.suite/'frozen_manifest.json');execution=read(args.suite/'suite_report.json')
    rows=[]
    for case in execution['cases']:
        root=args.suite/case['id'];run=root/'generation'
        row={'id':case['id'],'original_case_passed':case['ok'],'execution':case.get('execution')}
        row['status']=case.get('status','completed')
        row['stage_code_fingerprints']=stage_fingerprints(root)
        source=read(run/'source_provenance.json',{})
        visual_source=read(run/'visual_review/source_provenance.json',{})
        row['generation_code_fingerprint']=core_fingerprint(source)
        row['review_code_fingerprint']=core_fingerprint(visual_source)
        runtime=read(run/'run.json',{})
        floor=read(run/'programs/building_floor_programs.json',{})
        prototypes=read(run/'programs/prototype_adaptation.json',{})
        reference=read(run/'programs/room_reference_selection.json',{})
        row.update(generation_status=runtime.get('status'),generation_cost=runtime.get('metrics'),
            floor_accepted=len(floor.get('overrides',{})),floor_fallbacks=floor.get('failed_buildings',{}),
            room_summary=prototypes.get('summary'),room_reference_calls=len(reference.get('attempts',[])),
            room_selection_sources=dict(Counter(r.get('selection_source') for r in prototypes.get('rooms',[]))))
        review=read(run/'visual_review/adaptive_review_report.json')
        if review:
            city=load_city(review['city_refined'])
            row['building_functions']=dict(Counter(b.function for b in city.iter_buildings()))
            row['room_functions']=dict(Counter(r.function for r in city.iter_rooms()))
            row['seed']=city.metadata.get('seed')
            plan=read(run/'visual_review/observation_plan_after.json',{})
            from cityg.validation.visual_grounding import resolution_proofs
            proofs=resolution_proofs(load_city(run/'final/city.json'),city,review['review'])
            current=bounded_review_outcome(review['review'],review['review_after'],plan,review.get('traces',{}),
                current_versions={n.entity_id:n.version for n in city.world_program.nodes},
                deterministic_checks=proofs)
            row['independent_issue_checks_recomputed']=proofs
            row['visual_outcome_recomputed_from_saved_evidence']=current
            row['visual_outcome_statuses']=dict(Counter(r['status'] for r in current['issue_followup']))
            row['visual_model_calls']=sum(b.get('model_calls',1) for stage in ('review','review_after')
                                         for b in review[stage].get('batches',[]))
        failures=[]
        for path in sorted(root.glob('.*.pending-*/publication_failure.json')):
            failures.append({'artifact':str(path),**read(path)})
        row['unpublished_failures']=failures
        row['edits']=read(root/'edit_checks.json',[])
        retry=read(root/'material_retry_audit.json')
        if retry: row['supplemental_material_replay']={'passed':retry['ok'],'does_not_replace_original_result':True}
        physics=read(root/'physics.json',{})
        row['actual_cpu_physics_ok']=physics.get('ok') is True
        rows.append(row)
    fingerprints={value for row in rows for value in row['stage_code_fingerprints'].values() if value}
    executed=[row for row in rows if row.get('execution') is not None]
    report={'mode':'read_only_development_regression_audit','cases':rows,
        'configured_case_count':len(manifest['cases'])*len(manifest['seeds']),
        'completed_cases':len(executed),'original_passes':sum(r['original_case_passed'] for r in executed),
        'original_failures':sum(not r['original_case_passed'] for r in executed),
        'not_run':sorted(set(execution['not_run'])|{r['id'] for r in rows if not r.get('execution')}),
        'core_code_versions':sorted(fingerprints),'single_frozen_core_version':len(fingerprints)==1,
        'all_configured_passed':execution['all_configured_passed'],
        'generalization_proven':False,'all_visual_issues_resolved':False,
        'note':'Current conservative outcome rules re-evaluate saved evidence; no new VLM calls or scene changes.'}
    save_json(report,args.output)
    print({k:report[k] for k in ('completed_cases','original_passes','original_failures','single_frozen_core_version')})


if __name__=='__main__': main()
