"""Small live §4.4 development diagnostic, not a held-out paper benchmark.

Production agent-build, fixed local assets, serial executions, every failure kept.
The low/standard contrast changes progressive CALL caps, not pure retry counts.
No VLM, rendering or mesh-generation cost is included in generation measurements.
Separate observation/edit diagnostics consume the preserved standard source.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
from unittest.mock import patch

from cityg.serialization import load_city, save_json
from cityg.run_provenance import source_snapshot

ROOT = Path(__file__).resolve().parents[1]


def bounded_execute(command, log, env, timeout=3900):
    """A process-group deadline also stops the child behind /usr/bin/time."""
    process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,
                             stderr=subprocess.STDOUT,start_new_session=True)
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait(timeout=10)
        return 124


def read(path, default=None):
    if path.is_file():
        return json.loads(path.read_text())
    compressed = Path(str(path)+'.gz')
    if compressed.is_file():
        with gzip.open(compressed,'rt') as stream:return json.load(stream)
    return default


def matrix():
    rows = []
    for seed in (611, 612, 613):
        for cap in ((2, 4) if seed % 2 else (4, 2)):
            rows.append(dict(id=f'n10_r4_s{seed}_c{cap}', buildings=10, rooms=4, seed=seed, calls=cap))
    rows += [dict(id=f'n{n}_r4_s611_c4', buildings=n, rooms=4, seed=611, calls=4) for n in (30, 60, 100)]
    rows += [dict(id='n10_r10_s611_c4', buildings=10, rooms=10, seed=611, calls=4)]
    return rows


def repair_matrix():
    """Targeted post-repair cases, not a replacement for the original cohort."""
    return [dict(id=f'n{n}_r{rooms}_s611_c{cap}', buildings=n, rooms=rooms,
                 seed=611, calls=cap)
            for n, rooms, cap in ((10,4,2),(10,4,4),(10,10,4),(30,4,4))]


def child(case_path):
    from cityg import cli
    from cityg.services.openai_compatible import OpenAICompatibleService
    from run_edit_method_pilot import RecordedService
    case = read(case_path)
    save_json(source_snapshot(),case_path.parent/'execution_source.json')
    out = Path(case['generation'])
    # Record every actual model request, including prototype selection/objectives
    # that are not necessarily all represented in the coordinator's counters.
    def factory(endpoint):
        return RecordedService(OpenAICompatibleService(endpoint), case_path.parent/'all_model_calls.json')
    options = [
        'agent-build', '--requirement-file', str(case_path.parent/'instruction.txt'),
        '--base-url', case.get('base_url','http://127.0.0.1:8000/v1'),
        '--model', case.get('model','cityg-llm'),
        '--output', str(out), '--prototype-config', str(case_path.parent/'prototypes.json'),
        '--backend', 'openusd', '--no-viewer', '--max-tokens', '6144',
        '--max-attempts', '3', '--max-calls-per-agent', str(case['calls']),
        '--max-total-tokens', '0', '--max-total-model-calls', str(case.get('total_call_cap',160)),
        '--max-wall-time', '3600', '--max-touched-entities', '80',
        '--model-seed', str(case['seed']), '--timeout', '180',
        '--asset-registry', str(ROOT/'assets/asset_registry.json'),
        '--material-library', str(ROOT/'assets/material_library.json'),
        '--facade-asset-index', str(ROOT/'assets/facades/asset_annotations_reviewed.json'),
        '--memory-store', str(case_path.parent/'memory.sqlite'),
    ]
    with patch.object(cli, 'OpenAICompatibleService', side_effect=factory):
        return cli._agent_build(cli._parser().parse_args(options))


def attempt_rows(value):
    if isinstance(value, dict):
        if 'prompt_hash' in value and 'raw_output' in value and 'error' in value:
            yield value
        else:
            for item in value.values():
                yield from attempt_rows(item)
    elif isinstance(value, list):
        for item in value:
            yield from attempt_rows(item)


def rejection_rows(runroot):
    paths = set((runroot/'programs').glob('*trace.json'))
    paths.update(Path(str(p)[:-3]) for p in (runroot/'programs').glob('*trace.json.gz'))
    paths.update((runroot/'failures').glob('*.json'))
    paths.update(Path(str(p)[:-3]) for p in (runroot/'failures').glob('*.json.gz'))
    paths.add(runroot/'requirement/trace.json')
    seen = set(); rows = []
    for path in sorted(paths):
        for attempt in attempt_rows(read(path,{})):
            if not attempt['error']:continue
            key=(attempt['prompt_hash'],attempt['error'],attempt['raw_output'])
            if key in seen:continue
            seen.add(key)
            rows.append({'file':str(path.relative_to(runroot)),'error':attempt['error']})
    return rows


def audit(case, folder, execution):
    runroot = folder/'generation'
    run = read(runroot/'run.json', {})
    proto = read(runroot/'programs/prototype_adaptation.json', {})
    row = {**case, **execution, 'status': run.get('status', 'missing_result'),
           'error': run.get('error'), 'stage': run.get('stage'),
           'coordinator_metrics': run.get('metrics', {}), 'checks': {}}
    checks = row['checks']
    city_path = runroot/'final/city.json'
    compiled = runroot/'final/openusd'
    row['flow_complete'] = city_path.is_file() and (compiled/'usd/city.usda').is_file()
    checks['flow_complete'] = row['flow_complete']
    checks['generation_status'] = row['status'] == 'success'
    for name in ('geometry_validation_report', 'usd_validation_report', 'interaction_smoke_report'):
        report = read(compiled/(name+'.json'), {})
        checks[name] = report.get('ok') is True
    if city_path.is_file():
        from cityg.validation import CityValidator
        city = load_city(city_path)
        buildings = list(city.iter_buildings())
        row['actual'] = dict(buildings=len(buildings), floors=sum(1 for _ in city.iter_floors()),
                             rooms=sum(1 for _ in city.iter_rooms()), objects=sum(1 for _ in city.iter_objects()))
        functions = Counter(b.function for b in buildings)
        row['actual']['functions'] = dict(functions)
        checks['building_count'] = len(buildings) == case['buildings']
        checks['required_functions'] = {'residential','commercial','public_service'} <= functions.keys()
        checks['semantic_validation'] = CityValidator().validate(city).ok
        row['actual']['fine_rooms'] = proto.get('summary', {}).get('accepted_rooms', 0)
        checks['fine_rooms'] = row['actual']['fine_rooms'] == case['rooms']
        detailed_buildings = [b for b in buildings if any(f.objects for f in b.floors)]
        checks['detail_building_limit'] = len(detailed_buildings) <= case.get('detail_building_limit',(3 if case['rooms'] == 10 else 2))
        checks['floor_range'] = all(2 <= len(b.floors) <= 3 for b in buildings)
        row['city_sha256'] = hashlib.sha256(city_path.read_bytes()).hexdigest()
    row['machine_complete'] = all(checks.values())
    calls = read(folder/'all_model_calls.json', [])
    usages = [c.get('completion', {}).get('usage', {}) for c in calls]
    row['actual_model_calls'] = len(calls)
    row['usage_complete'] = all('prompt_tokens' in u and 'completion_tokens' in u for u in usages)
    row['usage'] = {k:sum(u.get(k,0) for u in usages) for k in ('prompt_tokens','completion_tokens')}
    row['model_request_s'] = sum(c.get('elapsed_s',0) for c in calls)
    row['request_errors'] = sum('error' in c for c in calls)
    row['truncated_responses'] = sum(c.get('completion',{}).get('finish_reason')=='length' for c in calls)
    rejected = rejection_rows(runroot)
    row['rejections'] = rejected
    row['planning_conflicts'] = read(runroot/'programs/planning_conflicts.json', [])
    row['fallback_buildings'] = len(row['planning_conflicts'])
    row['first_candidate_success_proxy'] = (row['machine_complete'] and not rejected and
        not row['fallback_buildings'] and not run.get('metrics',{}).get('repair_rounds',0))
    row['stage_times_s'] = {}
    events = [json.loads(s) for s in (runroot/'events.jsonl').read_text().splitlines()] if (runroot/'events.jsonl').is_file() else []
    previous = 0
    for event in events:
        elapsed = event.get('elapsed_s',0)
        key = event.get('stage','unknown')
        row['stage_times_s'][key] = row['stage_times_s'].get(key,0) + max(0,elapsed-previous)
        previous = elapsed
    return row


def compress_and_prune(folder, keep_scene=False):
    """Only this suite's already-audited case: retain JSON/log evidence, not binaries."""
    assert folder.parent.name == 'runs' and folder.parent.parent.name.startswith('analysis44_')
    if not keep_scene:
        final = folder/'generation/final'
        if final.is_dir():
            evidence = folder/'final_evidence'
            evidence.mkdir(exist_ok=True)
            for name in ('geometry_validation_report.json', 'usd_validation_report.json',
                         'interaction_smoke_report.json', 'compile_metrics.json'):
                path = final/'openusd'/name
                if path.is_file(): shutil.copy2(path,evidence/name)
            for path in (final/'reports').glob('*.json'):
                shutil.copy2(path,evidence/path.name)
            if (final/'city.json').is_file():
                with (final/'city.json').open('rb') as source, gzip.open(evidence/'city.json.gz','wb') as target:
                    shutil.copyfileobj(source,target)
            shutil.rmtree(final)
    for name in ('facade_cache', 'viewer'):
        for path in list(folder.rglob(name)):
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
    # Lossless text compression of expensive diagnostics, without losing failures.
    if not keep_scene:
        for path in folder.rglob('*.json'):
            if path.stat().st_size > 100_000:
                with path.open('rb') as source, gzip.open(str(path)+'.gz', 'wb') as target:
                    shutil.copyfileobj(source,target)
                path.unlink()


def run(output, fine_extension=False, *, repair_regression=False,
        base_url='http://127.0.0.1:8000/v1', model='cityg-llm'):
    from cityg.planning.generation_prototypes import load_options, GenerationPrototypes
    source_options = load_options(ROOT/'configs/generation_prototypes.json')
    GenerationPrototypes(source_options)  # preflight before creating any trial
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    save_json(source_snapshot(), output/'source_provenance.json')
    cases = matrix()
    if fine_extension:
        cases = [dict(id=f'n10_r10_s{seed}_c4',buildings=10,rooms=10,seed=seed,calls=4)
                 for seed in (612,613)]
    if repair_regression:
        cases = repair_matrix()
    protocol = {'kind':'live_development_diagnostic', 'cases':cases, 'serial':True,
        'endpoint':base_url, 'model':model, 'total_token_cap':0,
        'frozen_assets':True, 'mesh_generation':False, 'generation_includes_visual_review':False,
        'supplement_after_initial_batch':fine_extension,
        'repair_regression':repair_regression,
        'comparison':'2 vs 4 proposal/invalid-action attempts per hierarchy agent; successful disclosure separately bounded',
        'limitations':['Small development sample, not independent held-out tasks.',
            'Post-repair disclosure semantics differ from the original cohort; not a pure retry ablation.',
            'Machine-complete is limited to the explicitly reported checks, not all aesthetic/physical claims.',
            'First-candidate success is a trace-based proxy; prototype search can reject untraced candidates.',
            'Existing asset warm caches and service contention are not controlled.']}
    save_json(protocol, output/'protocol.json')
    from urllib.parse import urlparse
    bypass=','.join(filter(None,[os.environ.get('NO_PROXY',''),'127.0.0.1','localhost',urlparse(base_url).hostname]))
    env = {**os.environ, 'PYTHONPATH':str(ROOT/'src'), 'NO_PROXY':bypass,
           'no_proxy':bypass, 'CITYG_PROGRESS':'true', 'CITYG_PROGRESS_INTERVAL':'30'}
    rows = []
    for case in cases:
        folder = output/'runs'/case['id']
        folder.mkdir(parents=True)
        if shutil.disk_usage(output).free < 12*1024**3:
            rows.append({**case,'status':'not_run_disk','machine_complete':False})
            save_json({'rows':rows},output/'summary.json')
            break
        n, rooms = case['buildings'], case['rooms']
        width = round(max(240, 74*math.sqrt(n)))
        limit = 3 if rooms == 10 else 2
        instruction = (f'生成严格{n}栋建筑的混合社区，包含住宅、办公商业与社区公共服务建筑，'
            '道路连通，各建筑入口连接道路。建筑采用常规矩形形态，每栋2至3层，高度有所变化。'
            f'仅在最多{limit}栋建筑、每栋最多2层中选择总共{rooms}个房间精细陈设，其余保留外壳或粗布局。'
            '保留入口、核心筒和通行，不得缩小家具或删除必要陈设掩盖空间不足。'
            '允许未陈设的相邻房间在上述约束下有限调整共享边界。\n'
            f'building_count={n}\nwidth_m={width}\ndepth_m={width}\nmin_floors=2\nmax_floors=3\nseed={case["seed"]}')
        (folder/'instruction.txt').write_text(instruction,encoding='utf-8')
        prototype = read(ROOT/'configs/generation_prototypes.json')
        prototype['library_root'] = source_options['library_root']
        prototype['adaptation'].update(max_buildings=limit,max_rooms=rooms,max_attempts=30)
        prototype['adaptation']['floor_repartition']['max_floors'] = limit*2
        save_json(prototype,folder/'prototypes.json')
        save_json({**case,'generation':str(folder/'generation'),
                   'base_url':base_url,'model':model},folder/'case.json')
        print('CASE_START',case['id'],flush=True)
        start = time.perf_counter()
        with (folder/'execution.log').open('w') as log:
            code = bounded_execute(['/usr/bin/time','-v','-o',str(folder/'resources.txt'),sys.executable,
                    str(Path(__file__).resolve()),'--child',str(folder/'case.json')],
                    log,env)
        execution = {'exit_code':code,'elapsed_s':round(time.perf_counter()-start,3)}
        resource = (folder/'resources.txt').read_text() if (folder/'resources.txt').exists() else ''
        match = re.search(r'Maximum resident set size \(kbytes\): (\d+)',resource)
        execution['peak_rss_kb'] = int(match[1]) if match else None
        try:
            row = audit(case,folder,execution)
        except Exception as exc:
            row = {**case,**execution,'status':'audit_error','machine_complete':False,'error':str(exc)}
        rows.append(row)
        save_json(row,folder/'audit.json')
        save_json({'protocol':protocol, 'rows':rows,'completed':len(rows),
                   'machine_complete':sum(r['machine_complete'] for r in rows)},output/'summary.json')
        # Two fixed sources for later observations/edits; no best-run selection.
        keep = case['id'] in {'n10_r4_s611_c4','n10_r10_s611_c4'}
        compress_and_prune(folder,keep_scene=keep)
        print('CASE_END',case['id'],row['status'],row['machine_complete'],execution['elapsed_s'],flush=True)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--child',type=Path)
    parser.add_argument('--fine-extension',action='store_true',
                        help='Separate supplementary cohort: 10 fine rooms with seeds 612/613; never replaces failures')
    parser.add_argument('--repair-regression',action='store_true')
    parser.add_argument('--base-url',default='http://127.0.0.1:8000/v1')
    parser.add_argument('--model',default='cityg-llm')
    args = parser.parse_args()
    if not args.child and not args.output: parser.error('--output or --child required')
    if args.fine_extension and args.repair_regression: parser.error('Choose one cohort')
    raise SystemExit(child(args.child) if args.child else run(args.output,args.fine_extension,
        repair_regression=args.repair_regression,base_url=args.base_url,model=args.model))
