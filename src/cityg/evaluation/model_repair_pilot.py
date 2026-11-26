"""Real-model contract exposure ablation within the existing RepairAgent.

Both methods retain local geometry, version/permission information, error text,
relation protocol, tools and final gates. Only explicit contract records differ.
This is a controlled repair study, not the full hierarchical synthesis claim.
"""
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import random
import time

from cityg.agents import AgentGenerationError, RepairAgent
from cityg.evaluation.error_injection import inject_error
from cityg.geometry import GeometryCompiler
from cityg.geometry.validation import GeometryValidator
from cityg.planning.baseline import BaselineCityPlanner
from cityg.planning.generation_prototypes import DeferredFurniture
from cityg.run_provenance import source_snapshot
from cityg.schemas import CitySpec
from cityg.serialization import save_json, to_primitive
from cityg.services.interfaces import ChatMessage, ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from cityg.transactions import fingerprint
from cityg.validation import CityValidator


class LocalSummaryRepairAgent(RepairAgent):
    def _context(self, city, report, scope_id):
        context = super()._context(city, report, scope_id)
        context['contracts'] = []
        return context


def judge(clean, broken, candidate):
    """Count a repair only if shared validation passes AND original geometry,
    contracts and graph relations are restored (ordering/version independent).

    Exact restoration is intentionally stricter than general valid redesign;
    valid alternatives are reported separately, not called verified restorations.
    """
    structural = CityValidator().validate(deepcopy(candidate))
    geometry_ok, geometry_errors, geometry_status = None, [], 'not_run_invalid_structure'
    if structural.ok:
        geometry_city = deepcopy(candidate)
        try:
            geometry = GeometryCompiler().compile(geometry_city)
            compiled = GeometryValidator().validate(geometry_city, geometry)
            geometry_ok = compiled.ok
            geometry_errors = [i.code for i in compiled.errors]
            geometry_status = 'passed' if compiled.ok else 'failed'
        except Exception as exc:
            geometry_ok, geometry_status = False, 'compile_error'
            geometry_errors = [f'{type(exc).__name__}: {exc}']
    def canonical(city):
        raw = to_primitive(city)
        raw.pop('world_program', None)
        return raw
    original = canonical(clean) == canonical(candidate)
    def records(city, field):
        return {item.id: to_primitive(item) for item in getattr(city.world_program, field)}
    contracts = records(clean, 'contracts') == records(candidate, 'contracts')
    relations = records(clean, 'relations') == records(candidate, 'relations')
    return {'structural_ok': structural.ok, 'geometry_ok': geometry_ok, 'geometry_status': geometry_status,
            'original_canonical_restored': original, 'original_contracts_preserved': contracts,
            'original_relations_restored': relations,
            'verified_restoration': structural.ok and geometry_ok and original and contracts and relations,
            'structurally_valid_alternative': structural.ok and geometry_ok and not (original and contracts and relations),
            'no_change': fingerprint(broken) == fingerprint(candidate),
            'structural_errors': [i.code for i in structural.errors],
            'geometry_errors': geometry_errors}


def attempt_cost(attempts):
    usage = [a.usage for a in attempts]
    return {'model_calls': len(attempts),
            'prompt_tokens': sum(u['prompt_tokens'] for u in usage) if all('prompt_tokens' in u for u in usage) else None,
            'completion_tokens': sum(u['completion_tokens'] for u in usage) if all('completion_tokens' in u for u in usage) else None,
            'attempt_elapsed_s': sum(a.elapsed_s for a in attempts),
            'input_characters': [sum(len(m['content']) for m in a.messages) for a in attempts],
            'images': 0}


def summary(rows):
    result = {}
    for method in sorted({r['method'] for r in rows}):
        group = [r for r in rows if r['method'] == method]
        result[method] = {'trials': len(group),
            'verified_restorations': sum(r.get('evaluation', {}).get('verified_restoration', False) for r in group),
            'structurally_valid_alternatives': sum(r.get('evaluation', {}).get('structurally_valid_alternative', False) for r in group),
            'first_attempt_restorations': sum(r.get('evaluation', {}).get('verified_restoration', False) and len(r['attempts']) == 1 for r in group),
            'failed_trials': sum(r['status'] != 'accepted' for r in group),
            'model_calls': sum(r['cost']['model_calls'] for r in group),
            'prompt_tokens': sum(r['cost']['prompt_tokens'] for r in group) if all(r['cost']['prompt_tokens'] is not None for r in group) else None,
            'completion_tokens': sum(r['cost']['completion_tokens'] for r in group) if all(r['cost']['completion_tokens'] is not None for r in group) else None,
            'trial_elapsed_s': sum(r['elapsed_s'] for r in group)}
    return result


def run(config, output):
    if config['split'] != 'development' or config['schema_version'] != 1:
        raise ValueError('Only schema 1 development experiments supported')
    if set(config['methods']) != {'local_summary', 'explicit_contracts'}:
        raise ValueError('This ablation requires both paired methods')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    save_json(config, output/'config.json')
    save_json(source_snapshot(), output/'source_provenance.json')
    endpoint = ModelEndpoint(**config['endpoint'])
    rows = []
    report = {'split': 'development', 'evidence_type': 'real_model_controlled_repair',
              'run_status': 'preflight', 'M1': 'explicit_contract_records_ablation_not_full_synthesis',
              'M2': 'not_evaluated', 'M3': 'existing_patch_agent_not_scope_selection',
              'limitations': ['Known injected faults on unfurnished two-building scenes.',
                  'Exact restoration evaluator; valid alternatives reported separately.',
                  'Both arms keep error text, geometry, tools, protocol and identical safety gates.',
                  'No claims of significant differences from this small development sample.']}
    def publish():
        save_json({**report, 'completed_trials': len(rows), 'summary': summary(rows)}, output/'summary.json')
    publish()
    try:
        service = OpenAICompatibleService(replace(endpoint, max_tokens=32))
        ready = service.complete_with_metadata([ChatMessage(role='user', content='Reply with the single word READY.')])
        save_json(asdict(ready), output/'preflight.json')
        if 'READY' not in ready.content.upper():
            raise RuntimeError('Readiness completion did not produce READY')
        report['run_status'] = 'running'
        for seed in config['seeds']:
            clean = BaselineCityPlanner(floor_detail_agent=DeferredFurniture()).plan(
                CitySpec(**config['city_spec'], seed=seed))
            if not CityValidator().validate(clean).ok:
                raise ValueError('Clean fixture is invalid')
            save_json(clean, output/f'fixtures/{seed}_clean.json')
            for family in config['families']:
                broken = inject_error(clean, family)
                source_sha = fingerprint(broken)
                save_json(broken, output/f'fixtures/{seed}_{family}.json')
                order = list(config['methods'])
                random.Random(f'{seed}:{family}').shuffle(order)
                for method in order:
                    key = f'{seed}_{family}_{method}'
                    print('trial_start', key, flush=True)
                    started = time.perf_counter()
                    agent_type = RepairAgent if method == 'explicit_contracts' else LocalSummaryRepairAgent
                    service = OpenAICompatibleService(replace(endpoint, seed=seed))
                    agent = agent_type(service, model_id=endpoint.model, max_attempts=config['max_attempts'])
                    attempts, candidate, error, status = (), deepcopy(broken), None, 'failed'
                    try:
                        result = agent.repair(broken)
                        candidate, attempts, status = result.city, result.attempts, 'accepted'
                    except AgentGenerationError as exc:
                        attempts, error = exc.attempts, str(exc)
                    except Exception as exc:
                        error = f'{type(exc).__name__}: {exc}'
                    row = {'trial_id': key, 'seed': seed, 'family': family, 'method': method,
                           'status': status, 'error': error, 'attempts': [asdict(a) for a in attempts],
                           'cost': attempt_cost(attempts), 'elapsed_s': time.perf_counter()-started,
                           'source_sha256': source_sha, 'after_sha256': fingerprint(candidate)}
                    try:
                        row['evaluation'] = judge(clean, broken, candidate)
                        row['source_unchanged'] = fingerprint(broken) == source_sha
                        if not row['source_unchanged']:
                            row['evaluation']['verified_restoration'] = False
                    except Exception as exc:
                        row['evaluation_error'] = f'{type(exc).__name__}: {exc}'
                    rows.append(row)
                    save_json(row, output/f'trials/{key}.json')
                    if status == 'accepted': save_json(candidate, output/f'accepted/{key}.json')
                    publish()
                    print('trial_end', key, status, row.get('evaluation'), flush=True)
        report['run_status'] = 'completed'
    except BaseException as exc:
        report.update(run_status='interrupted_or_failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        publish()
    return {**report, 'summary': summary(rows)}
