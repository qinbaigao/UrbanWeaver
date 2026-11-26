"""Real Building-specific Floor Agent feasibility and soft steerability probe.

Use existing frozen realized plates, core/entrance contracts and global semantic
programs. Preferences are soft and never waive any production acceptance gate.
No rendered-quality or independent synthesis-ablation claim is made here.
"""
import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import random
import time

from cityg.agents import AgentGenerationError
from cityg.agents.building_floor import BuildingFloorAgent
from cityg.design_goals import validate_goals
from cityg.evaluation.model_repair_pilot import attempt_cost
from cityg.planning.floor_brief import required_functions_by_level
from cityg.planning.programs import FloorProfile
from cityg.run_provenance import source_snapshot
from cityg.schemas import CitySpec
from cityg.serialization import _building, save_json
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from profile_method_scaling import digest


PREFERENCES = {
    'neutral':'Choose the functional floor organization best suited to the given building.',
    'independent':'Prefer independent circulation-accessed rooms, with few or no private child rooms. '
                  'Retain every required function and all geometric constraints.',
    'private_groups':'Where feasible for the supplied function and metric plate, prefer private groups: '
                     'an anchor space with private child rooms, rather than only independent rooms. '
                     'Retain every required function and all geometric constraints.',
}


def policy_comparison(rows):
    result={}
    for policy in sorted({r['policy'] for r in rows}):
        subset=[r for r in rows if r['policy']==policy]
        result[policy]={'trials':len(subset),'hard_accepted':sum(r['accepted'] for r in subset),
            'source_unchanged':sum(r['source_unchanged'] for r in subset),
            'organization':{preference:{'trials':len(group:=[r for r in subset if r['preference']==preference]),
                'met_and_accepted':sum(r['accepted'] and r.get('requested_organization_met') is True for r in group)}
                for preference in ('independent','private_groups')},
            'cost':{key:sum(r['cost'].get(key,0) for r in subset)
                    for key in ('model_calls','prompt_tokens','completion_tokens','attempt_elapsed_s')}}
    return {'policies':result,'scope':'paired development floor programs, not full cities',
            'same_max_calls_per_task':3,'equal_realized_cost':False}


def profile_metrics(profile, building, base):
    requirements=required_functions_by_level(building,base)
    zones=[]
    semantic_ok=True
    for z in profile.vertical_zones:
        spaces=z.spatial_program.spaces
        functions={s.function for s in spaces}
        for level in range(z.start_level,z.end_level+1):
            semantic_ok &= set(requirements[str(level)])<=functions
        roots=[s for s in spaces if s.access_via=='circulation']
        zones.append({'levels':[z.start_level,z.end_level], 'room_count':len(spaces),
            'circulation_roots':len(roots),'private_children':len(spaces)-len(roots),
            'functions':sorted(functions),
            'area_distribution_m2':sorted(round(s.target_area_m2,2) for s in spaces)})
    return {'required_functions_preserved':semantic_ok,'zones':zones,
        'topology_signature':digest([{k:v for k,v in z.items() if k not in ('functions','area_distribution_m2')}
                                     for z in zones]),
        'metric_signature':digest(zones),
        'private_child_total':sum(z['private_children'] for z in zones)}


def run(config, fixtures, output, seeds, goal_channel='shared_design_goals', policies=('verified',)):
    cases=json.loads(fixtures.read_text())['cases']
    output.mkdir(parents=True,exist_ok=False)
    save_json(source_snapshot(),output/'source_provenance.json')
    save_json({'cases':cases},output/'frozen_contracts.json')
    endpoint=replace(ModelEndpoint(**config['endpoint']),max_tokens=6144)
    save_json({'endpoint':asdict(endpoint),'seeds':seeds,'max_calls':3,'preferences':PREFERENCES,
               'goal_channel':goal_channel,'policies':list(policies),'goal_extraction_tested':False},
              output/'config.json')
    rows=[]
    def publish():
        save_json({'evidence_type':'development_realized_floor_contract_steerability',
            'completed':len(rows),'expected_trials':len(cases)*len(seeds)*len(PREFERENCES)*len(policies),
            'accepted':sum(r.get('accepted',False) for r in rows),
            'first_attempt_accepted':sum(r.get('accepted',False) and len(r['attempts'])==1 for r in rows),
            'rows':[{k:v for k,v in r.items() if k!='attempts'} for r in rows],
            'limitations':['Three previously used development geometries, not held-out buildings.',
                'Geometric feasibility uses the production solver, not an independent implementation.',
                'No full city compile, render, room furniture or visual aesthetic evaluation.',
                'Requested organization is a soft preference; incompatibility is not permission to change the interface.',
                'No contract-free baseline; this measures conditional capability, not M1 causal gain.',
                'Different model seeds on the same geometry are not independent urban samples.']},
            output/'summary.json')
    publish()
    tasks=[(i,seed,pref,policy) for i in range(len(cases)) for seed in seeds
           for pref in PREFERENCES for policy in policies]
    random.Random(817).shuffle(tasks)
    for i,seed,pref,policy in tasks:
        case=cases[i];building=_building(case['building'])
        base=FloorProfile.from_dict(case['base_profile']);spec=CitySpec.from_dict(case['spec'])
        before=digest(building);key=f'plate{i}_seed{seed}_{pref}_{policy}'
        print('floor_start',key,flush=True)
        agent=BuildingFloorAgent(OpenAICompatibleService(replace(endpoint,seed=seed)),
                                 model_id=endpoint.model,max_calls=3)
        agent.semantic_objective_policy=policy
        context={}
        if goal_channel=='shared_design_goals':
            quote=PREFERENCES[pref]
            agent.design_goals=validate_goals({'goals':[{
                'source_quote':quote,'preference':quote,'levels':['floor']}]},quote)
        else:
            context={'soft_layout_preference':PREFERENCES[pref],
                'preference_priority':'Only among feasible choices; never remove global functions or change plate/core/entry.'}
        attempts=();start=time.perf_counter()
        row={'id':key,'plate':i,'seed':seed,'preference':pref,'policy':policy,'accepted':False}
        try:
            result=agent.plan(building,base,spec,prototype_context=context)
            attempts=result.attempts
            metrics=profile_metrics(result.program.profile,building,base)
            row.update(accepted=metrics['required_functions_preserved'],metrics=metrics)
            # Evaluate against the frozen request, not the model's interpretation.
            met=(all(z['private_children']>0 for z in metrics['zones']) if pref=='private_groups'
                 else all(z['private_children']==0 for z in metrics['zones']) if pref=='independent' else None)
            row.update(requested_organization_met=met,decision_receipt=result.program.decision_receipt)
            save_json(result.program,output/f'programs/{key}.json')
        except AgentGenerationError as exc:attempts=exc.attempts;row['error']=str(exc)
        except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}'
        row.update(attempts=[asdict(a) for a in attempts],cost=attempt_cost(attempts),
                   elapsed_s=time.perf_counter()-start,source_unchanged=before==digest(building))
        row['accepted'] &= row['source_unchanged']
        rows.append(row);save_json(row,output/f'trials/{key}.json');publish()
        print('floor_end',key,row['accepted'],len(attempts),row.get('error'),flush=True)
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--fixtures',type=Path,default=Path('tests/fixtures/floor_brief_contracts.json'))
    p.add_argument('--config',type=Path,default=Path('configs/model_method_pilot.json'))
    p.add_argument('--seeds',type=int,nargs='+',default=[101,202])
    p.add_argument('--goal-channel',choices=['shared_design_goals','prototype_priors'],default='shared_design_goals')
    p.add_argument('--policies',nargs='+',choices=['legacy','verified'],default=['verified'])
    p.add_argument('--summarize-only',action='store_true')
    a=p.parse_args()
    if a.summarize_only:
        summary=json.loads((a.output/'summary.json').read_text())
        if summary['completed']!=summary['expected_trials']:raise ValueError('Run is incomplete')
        comparison=policy_comparison(summary['rows'])
        save_json(comparison,a.output/'policy_comparison.json')
        print(json.dumps(comparison,indent=2))
    else:run(json.loads(a.config.read_text()),a.fixtures,a.output,a.seeds,a.goal_channel,a.policies)
