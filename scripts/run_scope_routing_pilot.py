"""Development M3 scope-routing diagnostic with shared executable strategies.

Compare production smallest-first negotiation against a dependency-count router
and a real-model direct router. This isolates routing, NOT generative replanning.
"""
import argparse
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import random
import time

from cityg.ccwp import entity_index
from cityg.evaluation.method_pilot import make_case, room_count
from cityg.geometry import GeometryCompiler
from cityg.geometry.validation import GeometryValidator
from cityg.planning.baseline import BaselineCityPlanner
from cityg.planning.generation_prototypes import DeferredFurniture
from cityg.planning.negotiation import negotiate, scope_chain
from cityg.planning.scope_requirements import ScopeRequirements
from cityg.run_provenance import source_snapshot
from cityg.schemas import CitySpec
from cityg.serialization import save_json, to_primitive
from cityg.services.interfaces import ChatMessage, ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from cityg.subtree_transactions import FloorSubtreePlanner
from cityg.transactions import descendants, fingerprint, refresh_local_overlay
from cityg.validation import CityValidator
from run_edit_method_pilot import RecordedService


SCENARIOS = ('room_name','single_floor','two_floors','one_attempt',
             'locked_parent','unsupported_count','stale_conflict')
METHODS = ('smallest_first','dependency_direct','model_direct','minimal_capable')


def executor_requirements(task):
    if 'requested_room_name' in task:
        return ScopeRequirements((task['entity_id'],))
    count=task['requested_floor_room_count']
    return ScopeRequirements(tuple(task['target_floor_ids']),('floor','building'),
        None if type(count) is int and 1<=count<=64 else 'Floor executor supports room_count in 1..64')


def make_task(city, scenario):
    task = make_case(city,'single_floor' if scenario=='room_name' else scenario)
    if scenario=='room_name':
        task.update(scenario=scenario,conflict_id=scenario,task_class='repair',
            requested_room_name='协作会议室',authorized_roots=[task['entity_id']],target_floor_ids=[])
    return task


def dependency_scope(task):
    if 'requested_room_name' in task:return 'room'
    return 'building' if len(task['target_floor_ids'])>1 else 'floor'


def task_met(city, task):
    entities = entity_index(city)
    if 'requested_room_name' in task:
        return entities[task['entity_id']].name == task['requested_room_name']
    return all(room_count(entities[key])==task['requested_floor_room_count']
               for key in task['target_floor_ids'])


def strategy(city, scope, task):
    allowed = descendants(city,[scope])
    if 'requested_room_name' in task:
        if task['entity_id'] not in allowed:raise ValueError('Requested room outside candidate scope')
        before=deepcopy(city)
        entity_index(city)[task['entity_id']].name=task['requested_room_name']
        return refresh_local_overlay(before,city,[task['entity_id']])
    targets = [key for key in task['target_floor_ids'] if key in allowed]
    if not targets:raise ValueError('Candidate scope cannot repartition a floor')
    for key in targets:
        city=FloorSubtreePlanner().replace(city,key,{'room_count':task['requested_floor_room_count']}).city
    return city


def model_scope(city, task, service):
    entities=entity_index(city)
    # No scenario labels, expected outcomes, or evaluator answers reach the model.
    payload={'request':({'room_id':task['entity_id'],'new_display_name':task['requested_room_name']}
                       if 'requested_room_name' in task else
                       {'floor_ids':task['target_floor_ids'],'non_corridor_rooms_per_floor':task['requested_floor_room_count']}),
        'scope_chain':scope_chain(city,task['entity_id']),
        'execution_contract':{'one_selected_entity_per_attempt':True,
            'batching_multiple_floor_scopes':False,
            'candidates':[{'scope_type':kind,'entity_id':key,
                'covered_requested_floor_ids':[f for f in task['target_floor_ids']
                    if f in descendants(city,[key])]}
                for kind,key in scope_chain(city,task['entity_id'])]},
        'authorized_roots':task['authorized_roots'],
        'current_room_counts':{f.id:room_count(f) for f in entities[task['building_id']].floors},
        'capability':{'floor_room_count_range':[1,64],
            'room':'Can edit room display name, cannot change floor partition.',
            'floor':'Can edit contained rooms and repartition this floor only.',
            'building':'Can edit contained rooms and repartition multiple contained floors.'}}
    response=service.complete_with_metadata([
        ChatMessage(role='system',content='Choose the smallest scope capable of the complete requested change. '
            'Exactly ONE entity from scope_chain is selected per attempt, NOT a level/type to repeat '
            'over multiple entities. Read the execution_contract candidate coverage. '
            'Return room, floor, or building and a brief reason. This is a scope requirement, not permission '
            'to execute: an independent engine enforces authority, stale versions, capability, geometry, '
            'and the entire requested result. If the request exceeds authority or capability, still '
            'identify its required scope and explain the limit; do not reduce the requested change.'),
        ChatMessage(role='user',content=json.dumps(payload,ensure_ascii=False))],
        {'type':'object','additionalProperties':False,'properties':{
            'scope':{'type':'string','enum':['room','floor','building']},'reason':{'type':'string'}},
         'required':['scope','reason']})
    result=json.loads(response.content)
    if result['scope'] not in {'room','floor','building'}:raise ValueError('Invalid model scope')
    return result


def run(config, output, seeds):
    output.mkdir(parents=True,exist_ok=False)
    save_json(source_snapshot(),output/'source_provenance.json')
    save_json({'config':config,'seeds':seeds,'scenarios':SCENARIOS,'methods':METHODS,
               'selector_max_tokens':512},output/'config.json')
    rows=[]
    def publish():
        aggregates={}
        for method in METHODS:
            group=[r for r in rows if r['method']==method]
            aggregates[method]={'trials':len(group),
                'repair_tasks':sum(r['task_class']=='repair' for r in group),
                'verified_repairs':sum(r.get('verified_repair',False) for r in group),
                'guard_tasks':sum(r['task_class']=='safe_nonexecution' for r in group),
                'safe_nonexecution':sum(r.get('safe_nonexecution',False) for r in group),
                'candidate_attempts':sum(r.get('candidate_attempts',0) for r in group),
                'compile_calls':sum(r.get('compile_calls',0) for r in group),
                'model_calls':sum(r.get('model_calls',0) for r in group)}
        save_json({'evidence_type':'development_scope_policy_diagnostic','rows':rows,'summary':aggregates,
            'expected_trials':len(seeds)*len(SCENARIOS)*len(METHODS),
            'limitations':['All methods share deterministic subtree candidates and acceptance gates.',
                'The room-local task edits metadata only; it is not furniture/geometric repair evidence.',
                'Targets/counts are structured and make direct dependency routing easy.',
                'Model calls differ intentionally; report routing cost separately, not an equal-cost superiority claim.',
                'Minimal-capable routing is integrated for generation adjacent-room coordination; direct model routing remains experimental.',
                'No human or independent simulator judge; shared geometry validator plus separately recomputed goals.']},
            output/'summary.json')
    publish()
    for seed in seeds:
        city=BaselineCityPlanner(floor_detail_agent=DeferredFurniture()).plan(CitySpec(
            building_count=2,min_floors=2,max_floors=2,width_m=180,depth_m=140,seed=seed))
        save_json(city,output/f'fixtures/{seed}.json')
        for scenario in SCENARIOS:
            task=make_task(city,scenario)
            order=list(METHODS);random.Random(f'{seed}:{scenario}').shuffle(order)
            for method in order:
                key=f'{seed}_{scenario}_{method}'
                print('scope_start',key,flush=True)
                before=fingerprint(city);compile_calls=[];service=None
                row={'id':key,'seed':seed,'scenario':scenario,'method':method,'task_class':task['task_class']}
                start=time.perf_counter()
                def gate(candidate):
                    tick=time.perf_counter()
                    scene=GeometryCompiler().compile(candidate)
                    result=GeometryValidator().validate(candidate,scene)
                    compile_calls.append(time.perf_counter()-tick)
                    return {'ok':result.ok,'errors':[i.code for i in result.errors]}
                try:
                    if method in {'smallest_first','minimal_capable'}:strategies=dict.fromkeys(('room','floor','building'),strategy)
                    else:
                        if method=='dependency_direct':selected=dependency_scope(task)
                        else:
                            endpoint=replace(ModelEndpoint(**config['endpoint']),seed=seed,max_tokens=512)
                            service=RecordedService(OpenAICompatibleService(endpoint),output/f'traces/{key}.json')
                            selection=model_scope(city,task,service)
                            row['selection']=selection;selected=selection['scope']
                        strategies={selected:strategy};row['selected_scope']=selected
                    candidate,report=negotiate(city,task,authorized_roots=task['authorized_roots'],
                        strategies=strategies,compiled_gate=gate,resolution_gate=task_met,
                        max_attempts=1 if scenario=='one_attempt' else 3,source='user_edit',
                        scope_requirements=executor_requirements(task) if method=='minimal_capable' else None)
                    row['status']=report['status'];row['candidate_attempts']=len(report['attempts'])
                    row['candidate_compile_s']=sum(compile_calls);row['compile_calls']=len(compile_calls)
                    row['source_unchanged']=fingerprint(city)==before
                    row['no_change']=fingerprint(candidate)==before
                    old=list(city.iter_buildings());new=list(candidate.iter_buildings())
                    protected=all((a.footprint,a.entrance,a.vertical_connectors)==
                        (b.footprint,b.entrance,b.vertical_connectors) for a,b in zip(old,new)) and old[1:]==new[1:]
                    target_floors=set(task['target_floor_ids'])
                    if 'requested_room_name' in task:target_floors.add(task['floor_id'])
                    floors={f.id:f for f in candidate.iter_floors()}
                    protected &= all(floors.get(f.id)==f for f in city.iter_floors() if f.id not in target_floors)
                    valid=CityValidator().validate(candidate).ok
                    row['verified_repair']=(task['task_class']=='repair' and report['status']=='resolved'
                        and task_met(candidate,task) and protected and valid and row['source_unchanged'])
                    row['safe_nonexecution']=(task['task_class']=='safe_nonexecution' and row['no_change']
                        and row['source_unchanged'] and valid and report['status']!='resolved')
                    save_json({'task':task,'report':report},output/f'trials/{key}.json')
                except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}'
                row['model_calls']=len(service.calls) if service else 0
                usage=[c.get('completion',{}).get('usage',{}) for c in service.calls] if service else []
                row['usage']={k:sum(u[k] for u in usage) if all(k in u for u in usage) else None
                              for k in ('prompt_tokens','completion_tokens')}
                row['elapsed_s']=time.perf_counter()-start;rows.append(row);publish()
                print('scope_end',key,row.get('status'),row.get('verified_repair'),row.get('error'),flush=True)
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--config',type=Path,default=Path('configs/model_method_pilot.json'))
    p.add_argument('--seeds',type=int,nargs='+',default=[101,202])
    a=p.parse_args();run(json.loads(a.config.read_text()),a.output,a.seeds)
