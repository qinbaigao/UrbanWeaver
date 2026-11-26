"""Frozen development-transfer tasks through real floor building and compilation.

Not cold city generation or held-out evaluation: contexts are controlled new
plates in a baseline city. Evaluation labels never enter the agent context.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict, replace
import json
import math
from pathlib import Path
import random
import re
import time

from cityg.agents import AgentGenerationError
from cityg.agents.building_floor import BuildingFloorAgent
from cityg.ccwp import build_world_program
from cityg.design_goals import extract_goals
from cityg.evaluation.floor_baselines import simple_plan
from cityg.evaluation.floor_semantics import evaluate_floor_requirements, fingerprint
from cityg.evaluation.model_repair_pilot import attempt_cost
from cityg.geometry import GeometryCompiler
from cityg.planning.baseline import BaselineCityPlanner
from cityg.planning.programs import (FloorProfile,FloorArchetype,HierarchicalProgram,UrbanProgram,
                                    BuildingProgram,BuildingProfile,FloorProgram)
from cityg.run_provenance import source_snapshot
from cityg.schemas import CitySpec,ZoneSpec,Bounds2D,Point2D
from cityg.serialization import save_json,to_primitive,city_from_dict
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from verify_floor_briefs import realize_profile


METHODS=('deterministic','semantic_score','strong_local_agent','verified_agent')


def cost_total(rows,key):
    values=[r.get('cost',{}).get(key) for r in rows]
    return sum(values) if all(v is not None for v in values) else None


def validate_manifest(manifest,methods):
    if not methods or len(set(methods))!=len(methods) or not set(methods)<=set(METHODS):
        raise ValueError('Choose unique supported methods')
    fixtures=manifest.get('fixtures',[]);tasks=manifest.get('tasks',[])
    if not fixtures or not tasks:raise ValueError('Empty evaluation manifests are not valid tests')
    for rows in (fixtures,tasks):
        ids=[r.get('id') for r in rows]
        if any(not isinstance(i,str) or not re.fullmatch(r'[a-zA-Z0-9_-]+',i) for i in ids):
            raise ValueError('Task and fixture ids must be safe file-name components')
        if len(set(ids))!=len(ids):raise ValueError('Duplicate evaluation ids')
    for row in fixtures:
        if (row.get('entrance') not in ('west','east','north','south')
                or row.get('function') not in ('residential','commercial','public_service')):
            raise ValueError('Unsupported fixture entrance or function')
        for key in ('width','depth'):
            value=row.get(key)
            if type(value) not in (float,int) or not math.isfinite(value) or value<=0:
                raise ValueError('Fixture dimensions must be finite and positive')
        if not isinstance(row.get('functions'),list) or not row['functions']:
            raise ValueError('Fixture must freeze nonempty required functions')
    known={r['id'] for r in fixtures}
    for task in tasks:
        if (task.get('fixture') not in known or task.get('organization') not in ('independent','private_groups')
                or not isinstance(task.get('instruction'),str) or not task['instruction'].strip()):
            raise ValueError('Each task needs a fixture, instruction and frozen organization predicate')


def fixture(row,seed):
    spec=CitySpec(name='semantic_transfer',building_count=4,width_m=280,depth_m=240,
        min_floors=2,max_floors=2,room_count_strategy='adaptive',seed=seed,
        zones=(ZoneSpec('district',row['function'],1.0),))
    city=BaselineCityPlanner().plan(spec);building=next(city.iter_buildings())
    center=building.footprint.center;w,d=row['width'],row['depth']
    building.footprint=Bounds2D(center.x-w/2,center.y-d/2,center.x+w/2,center.y+d/2)
    side=row['entrance'];bb=building.footprint
    building.entrance={'west':Point2D(bb.min_x,center.y),'east':Point2D(bb.max_x,center.y),
        'north':Point2D(center.x,bb.max_y),'south':Point2D(center.x,bb.min_y)}[side]
    axis='y' if side in ('north','south') else 'x'
    building.metadata.update(massing_style='bar',orientation_deg=0,orientation_contract={'orientation_deg':0},
        highrise={'enabled':False},interior_layout_contract={'reserved':True,'circulation_axis':axis,
            'source':'new_scene_rectangular_interior_v1'})
    for connector in building.vertical_connectors:
        connector.bounds=Bounds2D(center.x-1.5,center.y-1.5,center.x+1.5,center.y+1.5)
        connector.metadata['stair_run_axis']=axis
    functions=tuple(row['functions'])
    base=FloorProfile(building.function,'double_loaded_corridor',.18,functions,
        tuple(FloorArchetype(role,8,2,32,30,2.4,functions) for role in ('ground','typical')))
    program=HierarchicalProgram(UrbanProgram(('zone_00',)),BuildingProgram((BuildingProfile(
        building.function,'midpoint',side,'residential_slab' if building.function=='residential' else 'commercial_tower'),)),
        FloorProgram((base,)))
    city.metadata['hierarchical_program']=to_primitive(program)
    initial,_,_=simple_plan(None,building,base,spec,interpret=False)
    city=realize_profile(city,building.id,initial.profile,spec)
    return city,building.id,base,spec


def run(manifest,config,output,methods,*,fixtures_from=None):
    validate_manifest(manifest,methods)
    output.mkdir(parents=True,exist_ok=False)
    save_json(source_snapshot(),output/'source_provenance.json')
    save_json(manifest,output/'frozen_tasks.json');save_json(config,output/'model_config.json')
    if fixtures_from:
        prior=json.loads((fixtures_from/'frozen_tasks.json').read_text())
        if prior!=manifest:raise ValueError('Reused fixtures require the identical frozen task manifest')
        contexts={}
        for row in manifest['fixtures']:
            data=json.loads((fixtures_from/'fixtures'/(row['id']+'.json')).read_text())
            contexts[row['id']]=(city_from_dict(data['city']),data['target'],
                FloorProfile.from_dict(data['base_profile']),CitySpec.from_dict(data['spec']))
        save_json({'fixtures_from':str(fixtures_from.resolve()),'task_manifest_identical':True},output/'fixture_origin.json')
    else:contexts={r['id']:fixture(r,manifest['seed']+i) for i,r in enumerate(manifest['fixtures'])}
    for key,(city,bid,base,spec) in contexts.items():
        save_json({'city':city,'target':bid,'base_profile':base,'spec':spec},output/f'fixtures/{key}.json')
    rows=[]
    jobs=[(task,m) for task in manifest['tasks'] for m in methods];random.Random(619).shuffle(jobs)
    def publish():
        summary={method:{'tasks':len(group:=[r for r in rows if r['method']==method]),
            'compiled':sum(r.get('compiled',False) for r in group),
            'passed':sum(r.get('passed',False) for r in group),
            'model_calls':sum(r.get('cost',{}).get('model_calls',0) for r in group),
            'prompt_tokens':cost_total(group,'prompt_tokens'),
            'completion_tokens':cost_total(group,'completion_tokens')} for method in methods}
        save_json({'completed':len(rows),'expected':len(jobs),'split':manifest['split'],'summary':summary,'rows':rows,
            'limits':['Controlled baseline cities with new plates, not fresh LLM city generation.',
                'No room furnishing, screenshots, physics, or visual quality claim.',
                'Evaluator uses realized doors and compiled panels, not planner satisfaction receipts.',
                'Shared four-call cap: up to two goal extraction calls; planning receives only the remaining budget.',
                'Agent-authored development tasks, not an independent held-out test set.']},output/'summary.json')
    publish()
    for task,method in jobs:
        key=task['id']+'_'+method;print('START',key,flush=True)
        city,bid,base,spec=contexts[task['fixture']];source_hash=fingerprint(city)
        building=next(b for b in city.iter_buildings() if b.id==bid)
        # Freeze evaluator requirements separately. Never send task or expected label to model.
        contract={'levels':[f.level for f in building.floors],'required_functions':list(base.room_function_cycle),
                  'organization':task['organization'],'no_transit_functions':task.get('no_transit_functions',[])}
        instruction=task['instruction']+'\n保留建筑轮廓、入口、核心筒、现有楼层数及必需功能：'+', '.join(base.room_function_cycle)+'。其它建筑不变。'
        endpoint=replace(ModelEndpoint(**config['endpoint']),seed=manifest['seed'],max_tokens=6144)
        agent=BuildingFloorAgent(OpenAICompatibleService(endpoint),model_id=endpoint.model,max_calls=3)
        attempts=[];start=time.monotonic();row={'id':key,'task':task['id'],'method':method,'passed':False}
        try:
            if method!='deterministic':
                goals,trace=extract_goals(agent.service,instruction,max_calls=2);attempts.extend(trace)
                if goals['status']!='extracted':raise ValueError('Goal extraction failed')
                agent.max_calls=4-len(trace)
                agent.design_goals=goals['goals'];row['goals']=goals['goals']
            if method in ('semantic_score','deterministic'):
                program,trace,search=simple_plan(agent,building,base,spec,interpret=method=='semantic_score')
                attempts.extend(trace);row['search']=search
            else:
                agent.semantic_objective_policy='legacy' if method=='strong_local_agent' else 'verified'
                result=agent.plan(building,base,spec);program=result.program;attempts.extend(result.attempts)
            candidate=realize_profile(city,bid,program.profile,spec)
            compiled=to_primitive(GeometryCompiler().compile(candidate,building_ids={bid}))
            evaluation=evaluate_floor_requirements(city,candidate,bid,compiled,contract)
            row.update(compiled=True,passed=evaluation['passed'],evaluation=evaluation,receipt=program.decision_receipt)
            save_json(candidate,output/f'cases/{key}/city.json')
            save_json({'primitives':[p for p in compiled['primitives'] if p['semantic_class']=='door']},
                      output/f'cases/{key}/door_geometry.json')
            save_json(program,output/f'cases/{key}/program.json')
        except AgentGenerationError as exc:attempts.extend(exc.attempts);row['error']=str(exc)
        except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}'
        row.update(cost=attempt_cost(attempts),elapsed_s=time.monotonic()-start,source_unchanged=source_hash==fingerprint(city))
        row['passed'] &= row['source_unchanged']
        save_json({'instruction':instruction,'contract':contract,'attempts':attempts,'result':row},output/f'trials/{key}.json')
        rows.append(row);publish();print('END',key,row['passed'],row.get('error'),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--manifest',type=Path,default=Path('configs/semantic_transfer_cases.json'))
    p.add_argument('--config',type=Path,default=Path('configs/model_method_pilot.json'))
    p.add_argument('--methods',nargs='+',choices=METHODS,default=list(METHODS))
    p.add_argument('--fixtures-from',type=Path)
    a=p.parse_args();run(json.loads(a.manifest.read_text()),json.loads(a.config.read_text()),a.output,a.methods,
                        fixtures_from=a.fixtures_from)
