"""Development scaling with an invariant local repair task and growing distractors.

The 100-building master site's roads/parcels stay fixed; smaller scenes remove
only non-target buildings. This is NOT a growing-area or urban quality study.
Both arms use strong local retrieval; only explicit contract records differ.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import random
import time

from cityg.agents import AgentGenerationError, RepairAgent
from cityg.ccwp import build_world_program
from cityg.evaluation.error_injection import inject_error
from cityg.evaluation.model_repair_pilot import LocalSummaryRepairAgent, attempt_cost, judge, summary
from cityg.planning.baseline import BaselineCityPlanner
from cityg.planning.generation_prototypes import DeferredFurniture
from cityg.run_provenance import source_snapshot
from cityg.schemas import CitySpec
from cityg.serialization import save_json, to_primitive
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from cityg.transactions import fingerprint
from cityg.validation import CityValidator
from profile_method_scaling import digest


def master_fixture(seed, count=100):
    spec = CitySpec(building_count=count, width_m=1000, depth_m=1000,
        min_floors=2, max_floors=2, layout_style='regular_grid',
        road_pattern='connected_grid', buildings_per_block=1,
        branch_road_ratio=0, layout_irregularity=0, seed=seed)
    city = BaselineCityPlanner(floor_detail_agent=DeferredFurniture()).plan(spec)
    if not CityValidator().validate(city).ok:
        raise ValueError('Invalid master fixture; do not adapt dimensions after failure')
    return city, spec


def nested_fixture(master, count):
    buildings = list(master.iter_buildings())
    if not 1 <= count <= len(buildings):
        raise ValueError('Requested size exceeds frozen master')
    selected = {b.id for b in buildings[:count]}
    city = deepcopy(master)
    for parcel in city.iter_parcels():
        parcel.buildings[:] = [b for b in parcel.buildings if b.id in selected]
    city.world_program = build_world_program(city, producer='fixed_local_scaling', seed=None)
    if not CityValidator().validate(city).ok:
        raise ValueError('Invalid nested fixture')
    # Entity identity and geometry must not drift after rebuilding the overlay.
    if any(digest(a) != digest(b) for a, b in zip(buildings[:count], city.iter_buildings())):
        raise ValueError('Subset construction changed retained building geometry or identity')
    return city


def run(config, output, sizes, seeds, families):
    output.mkdir(parents=True, exist_ok=False)
    frozen = source_snapshot()
    save_json(frozen, output/'source_provenance.json')
    endpoint = ModelEndpoint(**config['endpoint'])
    save_json({'split':'development', 'sizes':sizes, 'seeds':seeds, 'families':families,
        'endpoint':asdict(endpoint), 'max_attempts':config['max_attempts'],
        'protocol':'fixed_100_building_site_nested_population_v1'}, output/'config.json')
    rows, fixtures, failures = [], [], []
    context_hashes, target_hashes = {}, {}

    def publish(status):
        grouped = {str(n):summary([r for r in rows if r['buildings']==n]) for n in sizes}
        save_json({'run_status':status, 'evidence_type':'development_fixed_local_real_model_scaling',
            'rows':[{k:v for k,v in r.items() if k!='attempts'} for r in rows],
            'by_size':grouped, 'fixtures':fixtures, 'failures':failures,
            'expected_trials':len(sizes)*len(seeds)*len(families)*2,
            'limitations':['Same site/roads/parcels at all sizes; buildings alone are distractors.',
                'Unfurnished procedural two-floor scenes; not general city quality.',
                'Two local-retrieval methods, not a monolithic or M2 joint-acquisition comparison.',
                'Repeated identical local tasks across sizes are paired, not independent samples.',
                'Wall times may include contention with the concurrent end-to-end suite.',
                'Geometry judging compiles the full scene; its cost is outside the model/repair timer.']},
            output/'summary.json')

    publish('running')
    try:
        for seed in seeds:
            master, spec = master_fixture(seed, max(sizes))
            save_json(master, output/f'fixtures/{seed}_master.json')
            save_json(spec, output/f'fixtures/{seed}_spec.json')
            # Permute scale order to reduce systematic endpoint warmup effects.
            order = list(sizes)
            random.Random(seed).shuffle(order)
            for n in order:
                clean = nested_fixture(master, n)
                target = next(clean.iter_buildings())
                target_hashes.setdefault(seed, digest(target))
                assert target_hashes[seed] == digest(target), 'Local task geometry drift'
                fixtures.append({'seed':seed,'buildings':n,'city_sha256':digest(clean),
                    'target_sha256':digest(target), 'roads_sha256':digest(clean.road_network),
                    'full_scene_json_bytes':len(json.dumps(to_primitive(clean),ensure_ascii=False).encode())})
                for family in families:
                    broken = inject_error(clean, family)
                    before = fingerprint(broken)
                    report = CityValidator().validate(broken)
                    methods = [('local_summary',LocalSummaryRepairAgent),('explicit_contracts',RepairAgent)]
                    random.Random(f'{seed}:{n}:{family}').shuffle(methods)
                    for method, agent_type in methods:
                        key = f'{seed}_{n}_{family}_{method}'
                        print('trial_start',key,flush=True)
                        agent = agent_type(OpenAICompatibleService(replace(endpoint,seed=seed)),
                            model_id=endpoint.model,max_attempts=config['max_attempts'])
                        # Both faults lie inside target; production selects the actual
                        # narrow permission scope itself, independently of this audit.
                        context = agent._context(broken,report,target.id)
                        invariant_key = (seed,family,method)
                        context_hashes.setdefault(invariant_key,digest(context))
                        if context_hashes[invariant_key] != digest(context):
                            raise ValueError('Measured target context changes with distractor population')
                        attempts, candidate, status, error = (), deepcopy(broken), 'failed', None
                        start = time.perf_counter()
                        try:
                            result = agent.repair(broken)
                            candidate, attempts, status = result.city,result.attempts,'accepted'
                        except AgentGenerationError as exc:
                            attempts,error = exc.attempts,str(exc)
                        except Exception as exc:
                            error = f'{type(exc).__name__}: {exc}'
                        elapsed = time.perf_counter()-start
                        evaluation_start = time.perf_counter()
                        evaluation = judge(clean,broken,candidate)
                        row = {'trial_id':key,'buildings':n,'seed':seed,'family':family,'method':method,
                            'status':status,'error':error,'elapsed_s':elapsed,
                            'evaluation_elapsed_s':time.perf_counter()-evaluation_start,
                            'evaluation':evaluation,'source_unchanged':fingerprint(broken)==before,
                            'context_sha256':digest(context),'target_sha256':digest(target),
                            'attempts':[asdict(a) for a in attempts],'cost':attempt_cost(attempts)}
                        rows.append(row)
                        save_json(row,output/f'trials/{key}.json')
                        publish('running')
                        print('trial_end',key,status,evaluation['verified_restoration'],flush=True)
        publish('completed')
    except BaseException as exc:
        failures.append({'error':f'{type(exc).__name__}: {exc}'})
        publish('interrupted_or_failed')
        raise
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--config',type=Path,default=Path('configs/model_method_pilot.json'))
    parser.add_argument('--sizes',type=int,nargs='+',default=[10,30,60,100])
    parser.add_argument('--seeds',type=int,nargs='+',default=[101,202])
    parser.add_argument('--families',nargs='+',choices=['disconnected_entrance','disconnected_room'],
                        default=['disconnected_entrance','disconnected_room'])
    args = parser.parse_args()
    if len(set(args.sizes)) != len(args.sizes) or min(args.sizes)<2:
        parser.error('Use unique sizes of at least two buildings')
    run(json.loads(args.config.read_text()),args.output,args.sizes,args.seeds,args.families)
