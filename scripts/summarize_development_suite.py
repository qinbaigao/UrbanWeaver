"""Read-only cross-run evidence accounting; never select a passing rerun silently."""
import argparse
from collections import Counter
import json
from pathlib import Path

from cityg.serialization import save_json


def read(path):
    return json.loads(Path(path).read_text())


def core(snapshot):
    return {k:v for k,v in snapshot.items()
        if k.startswith(('src/','configs/','viewer/src/')) or k=='scripts/run_cityg_pipeline.sh'}


def visual_metrics(review):
    attempts=[a for b in review.get('batches',[]) for a in b.get('attempts',[])]
    return {'batches':review.get('batch_count'), 'available_batches':review.get('available_batches'),
        'calls':len(attempts), 'retry_errors':sum(bool(a.get('error')) for a in attempts),
        'issue_count':len(review.get('aggregated_issues',[])),
        'grounding_status':dict(Counter(i.get('independent_verification',{}).get('status','not_measured')
            for i in review.get('aggregated_issues',[]))),
        'usage':{k:sum(a['usage'][k] for a in attempts) if all(k in a.get('usage',{}) for a in attempts) else None
                 for k in ('prompt_tokens','completion_tokens')}}


def summarize(roots):
    rows=[];seen=set();core_versions=[];asset_versions=[]
    for root in roots:
        suite=read(root/'suite_report.json')
        snapshot=read(root/'source_provenance.json')['file_sha256']
        core_versions.append(core(snapshot))
        asset_versions.append(snapshot.get('assets/asset_registry.json'))
        for entry in suite['cases']:
            identity=entry['id']
            if identity in seen:raise ValueError('Duplicate case across supplied runs; choose protocol versions explicitly')
            seen.add(identity);folder=root/identity
            row={'case_id':identity,'source':str(folder),'ok':entry['ok'],
                'pipeline_s':entry.get('execution',{}).get('elapsed_s'),
                'frozen_core_verified':entry.get('frozen_core_verified'),
                'failed_checks':entry.get('failed_checks',[]),'error':entry.get('error'),
                'edits':[{'kind':e['kind'],'status':e['status'],'ok':e['ok']} for e in entry.get('edits',[])]}
            stages=[read(p)['file_sha256'] for p in folder.rglob('source_provenance.json')]
            row['all_recorded_stage_core_match']=bool(stages) and all(core(s)==core(snapshot) for s in stages)
            row['all_recorded_registry_snapshots_match']=bool(stages) and all(
                s.get('assets/asset_registry.json')==snapshot.get('assets/asset_registry.json') for s in stages)
            run=folder/'generation/run.json'
            if run.exists():row['generation']=read(run)['metrics']
            path=folder/'generation/visual_review/adaptive_review_report.json'
            if path.exists():
                review=read(path)
                row.update(before=visual_metrics(review['review']),after=visual_metrics(review['review_after']),
                    touched_entities=len(review['touched_entity_ids']),
                    verified_resolved=review['bounded_outcome']['verified_resolved_issue_count'],
                    followups=dict(Counter(i['status'] for i in review['bounded_outcome']['issue_followup'])),
                    viewer=review['portable_viewer_after'])
            path=folder/'physics.json'
            if path.exists():
                p=read(path)
                row['physics']={k:p.get(k) for k in ('ok','physics_steps','resolved_rigid_body_count',
                    'expected_revolute_joint_count','max_rigid_body_z_drift_m','raycast_hit_count',
                    'raycast_sample_count','physics_wall_seconds','process_peak_rss_kb')}
            rows.append(row)
    return {'evidence_type':'development_engineering_accounting','rows':rows,
        'passed':sum(r['ok'] for r in rows),'completed':len(rows),
        'same_core_across_runs':all(v==core_versions[0] for v in core_versions),
        'same_registry_snapshot_across_runs':bool(asset_versions) and None not in asset_versions
            and len(set(asset_versions))==1,
        'limitations':['Engineering audits, not held-out benchmark or causal mechanism ablation.',
            'Nonconfirmed geometry claims are not automatically human-labeled visual false positives.',
            'No complete defect truth set, so do not derive visual precision or recall.',
            'Before/after issue-count reduction is not a repair metric.',
            'Wall times may include concurrent model and CPU experiments.']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs',type=Path,nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():p.error('Use a new output file to preserve historical accounting')
    report=summarize(a.runs);save_json(report,a.output)
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
