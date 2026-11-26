"""Attach protocol, street batching and capacity diagnostics to live run outcomes."""
import argparse
import json
from collections import Counter
from pathlib import Path

from cityg.serialization import save_json
from run_analysis44 import read


def summarize(root):
    report=read(root/'summary.json',{})
    for row in report.get('rows',[]):
        programs=root/'runs'/row['id']/'generation/programs'
        street=read(programs/'streetscape_trace.json',{})
        diagnostics=street.get('diagnostics',{})
        segments=read(programs/'streetscape_program.json',{}).get('segments',[])
        ignored_wrappers=0
        for attempt in street.get('attempts',[]):
            try:
                action=json.loads(attempt['raw_output'])
                if action.get('action')!='final':continue
                payload=json.loads(action['program_json'])
                ignored_wrappers+=int(not attempt.get('error') and 'segments' not in payload)
            except (ValueError,KeyError,TypeError):
                pass
        row['streetscape']={
            'roads':len(segments),'full_fallback':bool(street.get('fallback')),
            'local_fallback_roads':len(diagnostics.get('fallback_road_ids',[])),
            'changed_roads':len(diagnostics.get('changed_road_ids',[])),
            'batch_states':dict(Counter(b['status'] for b in diagnostics.get('batches',[]))),
            'strict_wire_contract':any('Do NOT wrap' in m.get('content','')
                for a in street.get('attempts',[]) for m in a.get('messages',[])),
            'silently_ignored_programs':ignored_wrappers,
            'model_calls':len(street.get('attempts',[])),
            'truncated':sum(a.get('finish_reason')=='length' for a in street.get('attempts',[]))}
        capacity=read(programs/'interior_capability_reservation.json',{}).get('capacity_search',{})
        row['capacity_search']=capacity.get('timings',{})
        row['capacity_candidate_count']=sum(len(b.get('candidates',[])) for b in capacity.get('buildings',[]))
        calls=read(root/'runs'/row['id']/'all_model_calls.json',[])
        row['disclosure_requests']=sum('"request_details"' in c.get('completion',{}).get('content','') for c in calls)
    report['interpretation']={
        'development_only':True,'natural_visual_repair_measured_separately':True,
        'original_cohort_not_overwritten':True,
        'runtime_caveat':'Remote service and current prototype library differ from October 21; wall times are not a controlled speedup.',
        'budget_caveat':'Proposal attempts exclude successful disclosures; actual calls/tokens remain reported.'}
    save_json(report,root/'repair_diagnostics.json')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    args=parser.parse_args()
    result=summarize(args.root.resolve())
    for row in result.get('rows',[]):
        print(row['id'],row['status'],row['machine_complete'],row['actual_model_calls'],
              row['usage'],row['streetscape'],flush=True)
