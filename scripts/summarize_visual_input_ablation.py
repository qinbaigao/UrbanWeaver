"""Score primary defect type + affected group, separately from normal false alarms.

Truth is consumed only here, after model calls. This is a strict typed metric;
secondary valid contract deviations and misclassified descriptions require the
human reading documented in the accompanying report.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
from cityg.serialization import save_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fixtures',type=Path,default=Path('analysis_results/easy_visual_defects_20261023'))
    p.add_argument('--runs',type=Path,nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();groups=defaultdict(list)
    expected={'blocked_entry':'door_blocked','outside':'outside','overlap':'overlap'}
    production={'room_access_blocked':'door_blocked','room_object_outside':'outside',
                'room_group_misaligned':'alignment'}
    for run in args.runs:
        for row in json.loads((run/'results.json').read_text()):
            truth=json.loads((args.fixtures/row['case']/'private_truth.json').read_text())
            types=[(i.get('kind',production.get(i.get('issue_code'))),
                    i.get('group_ids',i.get('target_group_ids',[]))) for i in row.get('issues',[])]
            want=expected.get(truth['condition'])
            hit=bool(want and row['available'] and any(k==want and 'storage' in ids for k,ids in types))
            groups[row['arm']].append({'case':row['case'],'seed':row['seed'],'condition':truth['condition'],
                'available':row['available'],'primary_typed_hit':hit,'issue_count':len(types),
                'normal_false_alarm':truth['condition']=='clean' and bool(types),
                'model_calls':row['model_calls'],'tokens':row['tokens'],
                'elapsed_s':row['elapsed_s']})
    summary={}
    for arm,rows in groups.items():
        summary[arm]={'rows':rows,'defect_trials':sum(r['condition']!='clean' for r in rows),
            'primary_typed_hits':sum(r['primary_typed_hit'] for r in rows),
            'normal_trials':sum(r['condition']=='clean' for r in rows),
            'normal_false_alarms':sum(r['normal_false_alarm'] for r in rows),
            'unavailable':sum(not r['available'] for r in rows),
            'model_calls':sum(r['model_calls'] for r in rows),'tokens':sum(r['tokens'] for r in rows)}
    save_json({'definition':__doc__,'arms':summary},args.output)
    for arm,r in summary.items():print(arm,{k:v for k,v in r.items() if k!='rows'})


if __name__=='__main__':main()
