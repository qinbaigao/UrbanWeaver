"""Controlled offline development probes, not model or paper efficacy results."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import resource
import time

from cityg.ccwp import entity_index
from cityg.evaluation.error_injection import ERROR_CASES, inject_error
from cityg.geometry import GeometryCompiler
from cityg.geometry.validation import GeometryValidator
from cityg.planning.baseline import BaselineCityPlanner
from cityg.planning.generation_prototypes import DeferredFurniture
from cityg.planning.negotiation import negotiate
from cityg.run_provenance import source_snapshot
from cityg.schemas import CitySpec
from cityg.serialization import save_json
from cityg.subtree_transactions import FloorSubtreePlanner
from cityg.transactions import fingerprint
from cityg.validation import CityValidator

METHODS = ('room_only', 'fixed_floor', 'bounded_hierarchy')
SCENARIOS = ('single_floor', 'two_floors', 'locked_parent', 'unsupported_count',
             'one_attempt', 'stale_conflict')


def room_count(floor):
    return sum(r.function != 'corridor' for r in floor.rooms)


def make_case(city, scenario):
    if scenario not in SCENARIOS:
        raise ValueError(f'Unknown scenario: {scenario}')
    building = next(city.iter_buildings())
    floor = building.floors[0]
    room = next(r for r in floor.rooms if r.function != 'corridor')
    targets = building.floors[:2] if scenario == 'two_floors' else [floor]
    count = 6 if all(room_count(f) != 6 for f in targets) else 7
    if scenario == 'unsupported_count':
        count = 65  # Explicit planner capability limit, not claimed physical impossibility.
    return {
        'scenario': scenario, 'conflict_id': scenario, 'entity_id': room.id,
        'building_id': building.id, 'floor_id': floor.id,
        'target_floor_ids': [f.id for f in targets], 'requested_floor_room_count': count,
        'authorized_roots': [room.id if scenario == 'locked_parent' else
                             building.id if scenario == 'two_floors' else floor.id],
        'base_fingerprint': 'stale-controlled-request' if scenario == 'stale_conflict' else fingerprint(city),
        'task_class': 'repair' if scenario in ('single_floor', 'two_floors', 'one_attempt') else 'safe_nonexecution',
    }


def objective_met(city, case):
    entities = entity_index(city)
    return all(key in entities and room_count(entities[key]) == case['requested_floor_room_count']
               for key in case['target_floor_ids'])


def evaluate_result(before, after, case, geometry_ok, source_unchanged):
    """Read-only task oracle separate from the strategy and its acceptance receipt.

    Structural/geometry validators are shared production implementations, not
    a second independently implemented geometry engine. Counts/protection are
    recomputed here; a reported 'resolved' status never suffices.
    """
    old_buildings = {b.id: b for b in before.iter_buildings()}
    new_buildings = {b.id: b for b in after.iter_buildings()}
    protected = old_buildings.keys() == new_buildings.keys() and all(
        (b.footprint, b.entrance, b.vertical_connectors) ==
        (new_buildings[k].footprint, new_buildings[k].entrance, new_buildings[k].vertical_connectors)
        for k, b in old_buildings.items())
    outside = all(new_buildings.get(k) == b for k, b in old_buildings.items() if k != case['building_id'])
    old_floors = {f.id: f for f in before.iter_floors()}
    new_floors = {f.id: f for f in after.iter_floors()}
    outside = outside and all(new_floors.get(k) == f for k, f in old_floors.items()
                              if k not in case['target_floor_ids'])
    changed = sorted(k for k in old_floors.keys() | new_floors.keys()
                     if old_floors.get(k) != new_floors.get(k))
    structure = CityValidator().validate(deepcopy(after))
    goal = objective_met(after, case)
    unchanged = fingerprint(before) == fingerprint(after)
    safety = bool(protected and outside and geometry_ok and structure.ok and source_unchanged
                  and (case['task_class'] != 'safe_nonexecution' or unchanged))
    return {'objective_met': goal, 'protected_geometry_preserved': protected,
            'outside_target_floors_preserved': outside, 'source_unchanged': source_unchanged,
            'structural_ok': structure.ok, 'geometry_ok': geometry_ok,
            'structural_error_codes': sorted({i.code for i in structure.errors}),
            'changed_floor_ids': changed, 'changed_floor_count': len(changed),
            'safety_ok': safety, 'unchanged': unchanged,
            'verified_repair': case['task_class'] == 'repair' and goal and safety,
            'safe_nonexecution': case['task_class'] == 'safe_nonexecution' and unchanged and safety}


def run_comparison(city, case, method, max_attempts=3):
    if method not in METHODS:
        raise ValueError(f'Unknown method: {method}')
    before = deepcopy(city)
    started = time.perf_counter()
    compilation = {'calls': 0, 'elapsed_s': 0.0, 'primitive_counts': []}

    def compile_check(candidate):
        start = time.perf_counter()
        geometry = GeometryCompiler().compile(candidate)
        report = GeometryValidator().validate(candidate, geometry).to_dict()
        compilation['calls'] += 1
        compilation['elapsed_s'] += time.perf_counter() - start
        compilation['primitive_counts'].append(len(geometry.primitives))
        return report

    def room_strategy(*_):
        raise ValueError('Room-local edits cannot change a floor partition count')

    def floor_strategy(draft, scope, conflict):
        return FloorSubtreePlanner().replace(draft, scope,
            {'room_count': conflict['requested_floor_room_count']}).city

    def building_strategy(draft, scope, conflict):
        for key in conflict['target_floor_ids']:
            if not any(f.id == key for f in entity_index(draft)[scope].floors):
                raise ValueError('Requested floor not inside authorized building')
            draft = floor_strategy(draft, key, conflict)
        return draft

    strategies = ({'room': room_strategy} if method == 'room_only' else
                  {'floor': floor_strategy} if method == 'fixed_floor' else
                  {'room': room_strategy, 'floor': floor_strategy, 'building': building_strategy})
    result, receipt = negotiate(city, case, authorized_roots=case['authorized_roots'],
        strategies=strategies, compiled_gate=compile_check,
        resolution_gate=lambda candidate, conflict: objective_met(candidate, conflict),
        source='user_edit', max_attempts=1 if case['scenario'] == 'one_attempt' else max_attempts)
    method_elapsed = time.perf_counter() - started
    compile_during_method = deepcopy(compilation)
    # Always recompile the final state, including a refusal. This is evaluation
    # overhead, not an algorithm runtime or extra free attempt.
    final_report = compile_check(deepcopy(result))
    check = evaluate_result(before, result, case, final_report['ok'], city == before)
    expected_stop = {'locked_parent': 'needs_authorization', 'unsupported_count': 'unresolved',
                     'stale_conflict': 'stale_conflict'}.get(case['scenario'])
    check['appropriate_stop_reason'] = receipt['status'] == expected_stop if expected_stop else None
    return {'method': method, 'case': case, 'receipt': receipt, 'evaluation': check,
            'before_sha256': fingerprint(before), 'after_sha256': fingerprint(result),
            'cost': {'method_elapsed_s': method_elapsed,
                     'evaluation_elapsed_s': time.perf_counter() - started - method_elapsed,
                     'compilation': compile_during_method, 'compile_unit': 'full_city',
                     'model_calls': 0, 'prompt_tokens': 0, 'completion_tokens': 0,
                     'images': 0, 'gpu_memory_mb': None},
            'evidence_type': 'controlled_offline', 'provider': 'deterministic_shared_subtree_planner'}


def summarize(rows):
    summary = {}
    for method in sorted({r['method'] for r in rows}):
        subset = [r for r in rows if r['method'] == method]
        repairs = [r for r in subset if r['case']['task_class'] == 'repair']
        guards = [r for r in subset if r['case']['task_class'] == 'safe_nonexecution']
        completed = [r for r in subset if 'evaluation' in r]
        summary[method] = {
            'trials': len(subset), 'errors': len(subset) - len(completed),
            'repair_tasks': len(repairs),
            'verified_repairs': sum(r.get('evaluation', {}).get('verified_repair', False) for r in repairs),
            'guard_tasks': len(guards),
            'safe_nonexecutions': sum(r.get('evaluation', {}).get('safe_nonexecution', False) for r in guards),
            'appropriate_stop_reasons': sum(r.get('evaluation', {}).get('appropriate_stop_reason') is True for r in guards),
            'safety_failures': sum(not r['evaluation']['safety_ok'] for r in completed),
            'method_elapsed_s_total': sum(r['cost']['method_elapsed_s'] for r in completed),
            'timing_complete': len(completed) == len(subset),
            'by_scenario': {scenario: {
                'trials': sum(r['case']['scenario'] == scenario for r in subset),
                'verified_repairs': sum(r.get('evaluation', {}).get('verified_repair', False)
                    for r in subset if r['case']['scenario'] == scenario),
                'statuses': [r.get('receipt', {}).get('status', 'error')
                    for r in subset if r['case']['scenario'] == scenario],
            } for scenario in sorted({r['case']['scenario'] for r in subset})},
        }
    return summary


def run(config, output):
    if config.get('split') != 'development' or config.get('schema_version') != 1:
        raise ValueError('This runner only supports schema 1 development probes')
    if set(config['methods']) - set(METHODS) or set(config['scenarios']) - set(SCENARIOS):
        raise ValueError('Unsupported method/scenario')
    if (not config['seeds'] or not config['methods'] or not config['scenarios']
        or len(config['seeds']) != len(set(config['seeds']))
        or len(config['methods']) != len(set(config['methods']))
        or len(config['scenarios']) != len(set(config['scenarios']))
        or type(config['error_variants']) is not int or not 1 <= config['error_variants'] <= 6
        or type(config['max_attempts']) is not int or not 1 <= config['max_attempts'] <= 6):
        raise ValueError('Nonempty unique cases/seeds/methods and valid budgets required')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    save_json(config, output/'config.json')
    save_json(source_snapshot(), output/'source_provenance.json')
    rows, calibration, fixtures = [], [], []
    started = time.perf_counter()
    status = {'schema_version': 1, 'split': 'development', 'evidence_type': 'controlled_offline',
              'run_status': 'running',
              'model_calls': 0, 'M1_model_efficacy': 'not_measured', 'M2': 'not_measured',
              'M3': 'deterministic_scope_scheduling_only',
              'limitations': ['Unfurnished regular two-building fixtures; no furniture preservation evidence.',
                  'Full-city compilation; no incremental speedup measured.',
                  'Shared production validators, independently recomputed task/protection checks.',
                  'Known injected errors; no natural repair success or model quality measured.',
                  'Local-only is capability-limited; fixed-floor is the meaningful direct-scope control.',
                  'Timings are single-process development measurements, not randomized performance estimates.']}

    def publish():
        save_json({**status, 'fixtures': fixtures, 'calibration': calibration,
                   'comparisons': summarize(rows), 'completed_trials': len(rows),
                   'elapsed_s': time.perf_counter() - started,
                   'process_peak_rss_mb_linux': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                   'memory_scope': 'cumulative_runner_peak_not_per_method'}, output/'summary.json')

    try:
        for seed in config['seeds']:
            city = BaselineCityPlanner(floor_detail_agent=DeferredFurniture()).plan(
                replace(CitySpec(**config['city_spec']), seed=seed))
            clean = CityValidator().validate(city)
            save_json(city, output/f'fixtures/seed_{seed}.json')
            fixtures.append({'seed': seed, 'sha256': fingerprint(city), 'structure_ok': clean.ok,
                             'buildings': len(list(city.iter_buildings())),
                             'floors': len(list(city.iter_floors())),
                             'rooms': sum(len(f.rooms) for f in city.iter_floors()),
                             'objects': sum(len(f.objects) for f in city.iter_floors())})
            calibration.append({'seed': seed, 'case': 'clean', 'clean': True,
                                'correct': clean.ok, 'error_codes': sorted({i.code for i in clean.errors})})
            for family, expected in ERROR_CASES.items():
                for variant in range(config['error_variants']):
                    report = CityValidator().validate(inject_error(city, family, variant))
                    codes = {i.code for i in report.errors}
                    calibration.append({'seed': seed, 'case': family, 'variant': variant, 'clean': False,
                        'correct': bool(codes & expected) and clean.ok,
                        'expected_codes_any': sorted(expected), 'error_codes': sorted(codes)})
            publish()
            if not clean.ok:
                raise ValueError(f'Invalid clean fixture {seed}; do not run invalid paired comparisons')
            for scenario in config['scenarios']:
                case = make_case(city, scenario)
                for method in config['methods']:
                    key = f'{seed}_{scenario}_{method}'
                    print('trial_start', key, flush=True)
                    try:
                        row = run_comparison(city, case, method, config['max_attempts'])
                    except Exception as exc:
                        row = {'method': method, 'case': case, 'error': f'{type(exc).__name__}: {exc}'}
                    row.update(seed=seed, trial_id=key)
                    rows.append(row)
                    save_json(row, output/f'trials/{key}.json')
                    publish()
                    print('trial_end', key, row.get('receipt', {}).get('status', row.get('error')), flush=True)
        status['run_status'] = 'completed'
        status['runner_ok'] = (all('error' not in r and r['evaluation']['safety_ok'] for r in rows)
                               and all(c['correct'] for c in calibration))
    except BaseException:
        status['run_status'] = 'interrupted_or_failed'
        raise
    finally:
        publish()
    return json.loads((output/'summary.json').read_text())
