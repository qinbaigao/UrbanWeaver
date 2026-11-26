"""Replay final-artifact demand checks without querying any planning model."""
import argparse
import json
from pathlib import Path

from cityg.evaluation.floor_semantics import evaluate_floor_requirements
from cityg.serialization import city_from_dict, load_city, save_json


def evaluate(run,output):
    if output.exists():raise FileExistsError(output)
    frozen=json.loads((run/'frozen_tasks.json').read_text())
    tasks={t['id']:t for t in frozen['tasks']}
    original=json.loads((run/'summary.json').read_text());rows=[]
    for row in original['rows']:
        trial=json.loads((run/'trials'/(row['id']+'.json')).read_text())
        if not row.get('compiled'):
            rows.append({'id':row['id'],'status':'not_compiled','passed':False,
                         'original_passed':row['passed']});continue
        fixture=json.loads((run/'fixtures'/(tasks[row['task']]['fixture']+'.json')).read_text())
        case=run/'cases'/row['id']
        report=evaluate_floor_requirements(city_from_dict(fixture['city']),load_city(case/'city.json'),
            fixture['target'],json.loads((case/'door_geometry.json').read_text()),trial['contract'])
        rows.append({'id':row['id'],'status':'evaluated','passed':report['passed'],
            'original_passed':row['passed'],'evaluation':report})
    result={'rows':rows,'completed':len(rows),
        'consistent_with_original':all(r['passed']==r['original_passed'] for r in rows),
        'model_calls':0,'scope':'Saved realized cities and compiled panels; no planner receipt used.'}
    save_json(result,output)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();r=evaluate(args.run,args.output)
    print('Tasks:',r['completed'],'consistent:',r['consistent_with_original'])
