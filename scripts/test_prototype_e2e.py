"""Opt-in real-model prototype integration tests, not the default Agent runner.

LLM recipe selection -> bounded generation -> locked floor/room adaptation ->
validated USD/portable Viewer -> headless multiscale captures -> VLM audit.
Never approves or edits the source library. No downloads or asset generation.
"""
import argparse
import asyncio
from collections import Counter
from dataclasses import replace
from functools import partial
import hashlib
import html
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
from threading import Thread

from cityg.agents.requirement import _parse_json_object
from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.planning.city_prototype_adapter import adapt_city_rooms, verify_room
from cityg.planning.floor_prototypes import FloorPrototypeLibrary
from cityg.planning.floor_repartition import repartition_city, propose_floor, options
from cityg.planning.prototype_lab import detached_registry
from cityg.planning.prototype_decor_assets import add_review_decorations
from cityg.planning.urban_prototypes import UrbanPrototypeLibrary, realization
from cityg.planning.urban_prototype_review import review_views, plan_svg
from cityg.serialization import load_city, save_json, to_primitive
from cityg.services import OpenUSDBackend
from cityg.services.interfaces import ChatMessage, ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from cityg.validation import CityValidator
from cityg.viewer import export_portable_viewer
from cityg.visual_review import VisualReviewAgent
from cityg.visual_evidence import prototype_review_context


CASES = {
    '01_neighborhood': {'seed': 1701, 'variation': 0.0,
        'instruction': '生成20栋建筑的生活社区，以住宅为主，配有日常商铺和社区公共服务，公园与邻里活动空间。以现有城市原型为基底，保留其结构。只选少数楼层与房间做精细原型适配。'},
    '02_business': {'seed': 1702, 'variation': 0.15,
        'instruction': '生成20栋建筑的办公商业混合片区，沿城市交通轴分布，建筑高低错落，有办公、商铺与公共空间。选择最适合的原型并在允许范围内调整，检查少数办公或零售楼层和房间。'},
    '03_waterfront': {'seed': 1703, 'variation': 0.3,
        'instruction': '生成20栋建筑的滨水混合城区，有弯曲河流、桥梁、滨水休闲空间，主要道路保持直线，住宅商业并存。基于合适原型做受约束变化，只精细设计少量楼层和房间。'},
}


def validate_selection(data, library, case):
    if set(data) != {'prototype_id', 'overrides', 'reason'}:
        raise ValueError('Unexpected selection fields')
    if data['prototype_id'] not in library.records:
        raise ValueError('Unknown urban prototype')
    if data['overrides'] != {'building_count': 20, 'seed': case['seed']}:
        raise ValueError('Test requires exactly 20 buildings and the configured seed')
    library.spec(data['prototype_id'], data['overrides'])
    if not isinstance(data['reason'], str) or not data['reason'].strip():
        raise ValueError('Missing selection explanation')
    if '河流' in case['instruction'] and library.spec(data['prototype_id']).river_mode == 'none':
        raise ValueError('Selected recipe cannot meet the explicit river requirement')
    return data


def select_recipe(service, library, case, out):
    candidates = [{k: record[k] for k in ('id', 'display_name', 'intent', 'adjustable_parameters', 'limits')}
                  | {'spec': record['spec']} for record in library.records.values()]
    schema = {'type': 'object', 'additionalProperties': False, 'properties': {
        'prototype_id': {'type': 'string', 'enum': list(library.records)},
        'reason': {'type': 'string'}, 'overrides': {'type': 'object', 'additionalProperties': False,
            'properties': {'building_count': {'type': 'integer', 'enum': [20]},
                           'seed': {'type': 'integer', 'enum': [case['seed']]}},
            'required': ['building_count', 'seed']}},
        'required': ['prototype_id', 'overrides', 'reason']}
    prompt = (case['instruction'] + '\n从给定目录选择一个最匹配的城市原型。只允许目录开放的调整，不编造能力。'
              '楼层、房间适配由后续约束检查决定，不能保证全部成功。\n'
              + json.dumps({'required_seed': case['seed'], 'catalog': candidates}, ensure_ascii=False))
    messages = [ChatMessage('user', prompt)]; traces = []
    for _ in range(3):
        completion = service.complete_with_metadata(messages, schema)
        row = {'content': completion.content, 'usage': completion.usage, 'finish_reason': completion.finish_reason}
        traces.append(row)
        try:
            choice = validate_selection(_parse_json_object(completion.content), library, case)
            row['accepted'] = True
            save_json(traces, out/'llm_selection_trace.json')
            return choice
        except (ValueError, TypeError, KeyError) as exc:
            row.update(accepted=False, error=str(exc))
            save_json(traces, out/'llm_selection_trace.json')
            messages.extend([ChatMessage('assistant', completion.content), ChatMessage('user', str(exc))])
    raise ValueError('No valid LLM recipe selection after three attempts')


def resources(root, out, library):
    registry = detached_registry(AssetRegistry(root/'assets/asset_registry.json'))
    for file in [library.root/'decoration_assets.json', *sorted(library.root.glob('reference_assets_*.json'))]:
        add_review_decorations(registry, file, project_root=root)
    materials = MaterialLibrary()
    for path in (root/'assets/material_library.json', root/'assets/incoming/interior_materials/material_library.json'):
        source = MaterialLibrary(path)
        if source.environment_path and not materials.environment_path:
            materials.set_environment(source.resolve_path(source.environment_path))
        for record in source.list_all():
            if materials.get(record.material_id):
                continue
            paths = {k: str(source.resolve_path(getattr(record, k))) for k in
                     ('base_color_path', 'normal_path', 'roughness_path', 'ambient_occlusion_path') if getattr(record, k)}
            materials.register(replace(record, **paths))
    return registry, GeometryCompiler(asset_registry=registry, material_library=materials,
        facade_asset_index_path=str(root/'assets/facades/asset_annotations_reviewed.json'),
        facade_asset_cache_root=str(out/'facade_cache'))


def variation_audit(source, library, floor_report):
    """Paired same-floor diagnostic; never confound different cities with a knob effect."""
    rows = []
    for accepted in floor_report['accepted']:
        b = next(b for b in source.iter_buildings() if b.id == accepted['building_id'])
        f = next(f for f in b.floors if f.id == accepted['floor_id'])
        row = {'floor_id': f.id, 'proposals': []}
        for v in (0.0, 0.15, 0.3):
            try:
                proposal, evidence = propose_floor(b, f, library, options({'enabled': True,'joint_room_planning':True}), v)
                shape = [{'id': r.id, 'bounds': to_primitive(r.bounds)} for r in proposal.rooms]
                row['proposals'].append({'variation': v, 'status': 'feasible_precompile',
                    'geometry_sha256': hashlib.sha256(json.dumps(shape, sort_keys=True).encode()).hexdigest(),
                    'after_rooms': evidence['after_rooms']})
            except ValueError as exc:
                row['proposals'].append({'variation': v, 'status': 'rejected', 'reason': str(exc)})
        rows.append(row)
    return rows


def prepare(case, service, urban, floors, root, out):
    if (out/'prepared.json').is_file():
        return json.loads((out/'prepared.json').read_text()), load_city(out/'scene/city.json')
    if shutil.disk_usage(out).free < 6*1024**3:
        raise RuntimeError('Less than 6 GiB free; stop without deleting user outputs')
    selection_path = out/'selection.json'
    choice = json.loads(selection_path.read_text()) if selection_path.is_file() else select_recipe(service, urban, case, out)
    validate_selection(choice, urban, case); save_json(choice, selection_path)
    print('selected', choice['prototype_id'], choice['overrides'], flush=True)
    source = urban.plan(choice['prototype_id'], choice['overrides'])
    measured = realization(source, urban.spec(choice['prototype_id'], choice['overrides']))
    save_json(measured, out/'urban_realization.json'); save_json(source, out/'city_before_adaptation.json')
    if not measured['ok']:
        raise ValueError('Urban realization failed')
    registry, compiler = resources(root, out, floors)
    city, floor_report = repartition_city(source, floors, compiler,
        {'enabled': True, 'max_floors': 2, 'levels': [0, 1], 'joint_room_planning':True},
        variation=case['variation'], progress=lambda *a: print(*a, flush=True))
    save_json(floor_report, out/'floor_adaptation.json')
    save_json(variation_audit(source, floors, floor_report), out/'paired_variation_audit.json')
    # Independent room search includes compatible unchanged floors, rather than
    # claiming an empty repartitioned office must fit an unrelated room template.
    city, room_report = adapt_city_rooms(city, floors, registry, compiler,
        {'max_buildings': 2, 'max_floors_per_building': 2, 'max_rooms': 4,
         'max_attempts': 12, 'variation_limit': case['variation']},
        progress=lambda *a: print(*a, flush=True))
    save_json(room_report, out/'room_adaptation.json')
    # Selected upper rooms need their unchanged ground-to-floor access chain.
    for b in city.iter_buildings():
        selected = city.metadata['interior_scope']['building_levels'].get(b.id, [])
        if selected:
            city.metadata['interior_scope']['building_levels'][b.id] = [f.level for f in b.floors if f.level <= max(selected)]
    city.world_program = build_world_program(city, producer='prototype_e2e_review', seed=case['seed'])
    print('compile_final', flush=True)
    scene = compiler.compile(city)
    checks = []
    for row in room_report['rooms']:
        b = next(b for b in city.iter_buildings() if b.id == row['building_id'])
        f = next(f for f in b.floors if f.id == row['floor_id'])
        r = next(r for r in f.rooms if r.id == row['room_id'])
        checks.extend(verify_room(scene, b, f, r, row))
    semantic = CityValidator().validate(city); geometry = GeometryValidator().validate(city, scene)
    save_json({'city': semantic.to_dict(), 'geometry': geometry.to_dict(), 'room_checks': checks}, out/'validation.json')
    if not semantic.ok or not geometry.ok:
        raise ValueError('Final city/geometry validation failed')
    OpenUSDBackend(compiler).compile(city, out/'scene', _scene_override=scene)
    save_json(semantic.to_dict(), out/'scene/validation_report.json')
    export_portable_viewer(out/'scene', out/'viewer')
    (out/'layout.svg').write_text(plan_svg(city))
    views = review_views(city)[:2]
    targets = {(a['building_id'], a['floor_id']) for a in floor_report['accepted']}
    targets.update((a['building_id'], a['floor_id']) for a in room_report['rooms'])
    for bid, fid in sorted(targets)[:3]:
        views.append({'view_id': fid+'_top', 'kind': 'floor_plan', 'mode': 'floor_plan',
            'target_entity_ids': [bid, fid], 'floor_camera_preset': 'top',
            'render_profile': 'presentation', 'appearance': 'presentation', 'auto_cutaway': True})
    for row in room_report['rooms'][:2]:
        views.append({'view_id': row['room_id']+'_cutaway', 'kind': 'room_interior', 'mode': 'room',
            'target_entity_ids': [row['room_id']], 'room_camera_preset': 'cutaway',
            'render_profile': 'presentation', 'appearance': 'presentation', 'auto_cutaway': True})
    save_json({'selected_views': views}, out/'observation.json')
    report = {'mode': 'opt_in_prototype_e2e_test_not_default_agent_pipeline',
        'selection': choice, 'case': case, 'building_count': len(list(city.iter_buildings())),
        'floor_references': [a['reference_id'] for a in floor_report['accepted']],
        'repartitioned_floors': len(floor_report['accepted']), 'room_summary': room_report['summary'],
        'room_references': dict(Counter(a['prototype_id'] for a in room_report['rooms'])),
        'floor_rejection_reasons': dict(Counter(a['reason'] for a in floor_report['attempts'] if a['status'] == 'rejected')),
        'city_validation_ok': semantic.ok, 'geometry_validation_ok': geometry.ok,
        'primitive_count': len(scene.primitives), 'llm_used': True, 'asset_generation_used': False,
        'automatic_vlm_repairs': False, 'physics_runtime': 'not_executed', 'production_approved': False}
    save_json(report, out/'prepared.json')
    return report, city


def capture_and_review(service, out, report):
    views = json.loads((out/'observation.json').read_text())['selected_views']
    city=load_city(out/'scene/city.json')
    manifest=json.loads((out/'scene/geometry_manifest.json').read_text())
    capture_path = out/'screenshots/viewer_smoke.json'
    captured = json.loads(capture_path.read_text()) if capture_path.is_file() else {}
    if not captured.get('exercise_ok'):
        from scripts.check_portable_viewer import check
        class Quiet(SimpleHTTPRequestHandler):
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Quiet, directory=str(out/'viewer')))
        Thread(target=server.serve_forever, daemon=True).start()
        (out/'screenshots').mkdir(exist_ok=True)
        try:
            captured = asyncio.run(check(f'http://127.0.0.1:{server.server_port}/', out/'screenshots', 240,
                views, require_assets=True, canvas_only=True))
        finally:
            server.shutdown(); server.server_close()
    report['render_ok'] = bool(captured.get('exercise_ok'))
    if not report['render_ok']:
        raise ValueError('Headless capture failed')
    reviews = []
    # Serial, two images per request: avoid concurrent multimodal cache pressure.
    for start in range(0, len(views), 2):
        batch = views[start:start+2]; path = out/f'vlm_review_{start//2:02d}.json'
        context=prototype_review_context(city,manifest,batch)
        context_hash=hashlib.sha256(json.dumps(context,sort_keys=True).encode()).hexdigest()
        previous = json.loads(path.read_text()) if path.is_file() else {}
        if previous.get('available') and previous.get('evidence_sha256')==context_hash:
            reviews.append(previous); continue
        if path.is_file():
            history=out/'review_history'; history.mkdir(exist_ok=True); revision=1
            while (history/f'{path.stem}_{revision:03d}.json').exists():revision+=1
            path.rename(history/f'{path.stem}_{revision:03d}.json')
            evidence_path=out/f'vlm_evidence_{start//2:02d}.json'
            if evidence_path.is_file():
                evidence_path.rename(history/f'{evidence_path.stem}_{revision:03d}.json')
        result = VisualReviewAgent(service, max_images=2).review(
            '核对原型嵌入后的实际可见效果：布局、墙门、家具、越界与拥堵。仅报告图像能支持的问题。'
            '未精装房间为空是本测试的已知范围，不是家具缺失错误。不要从单幅图断言城市其他位置不存在设施。'
            '只绑定上下文中的实体ID；不确定时用null并降低置信度。本轮只审核，不执行修改。',
            [out/'screenshots'/f"{v['view_id']}.png" for v in batch],
            context=context)
        data = {**result.to_dict(),'evidence_sha256':context_hash,'raw_response':result.raw}
        save_json(context,out/f'vlm_evidence_{start//2:02d}.json')
        save_json(data, path); reviews.append(data)
        print('vlm_review', start//2, result.available, len(result.issues), result.error, flush=True)
    report['vlm_available'] = all(r['available'] for r in reviews)
    report['vlm_issue_count'] = sum(len(r['issues']) for r in reviews)
    report['vlm_deferred_count'] = sum(len(r.get('deferred_issues',[])) for r in reviews)
    report['joint_furnished_room_ids']=[r.id for r in city.iter_rooms()
        if r.metadata.get('layout_prototype_id') and
        r.metadata['layout_prototype_id']==r.metadata.get('joint_room_plan',{}).get('prototype_id')]
    report['all_three_levels_used'] = bool(report['repartitioned_floors'] and report['joint_furnished_room_ids'])
    report['integration_status'] = 'complete_three_level_reuse' if report['all_three_levels_used'] else 'partial_reuse'
    report['execution_status'] = 'completed' if report['vlm_available'] else 'vlm_unavailable'
    save_json(report, out/'result.json')
    if (out/'failure.json').is_file():
        history = out/'recovered_failures'; history.mkdir(exist_ok=True)
        index = 1
        while (history/f'attempt_{index:04d}.json').exists():
            index += 1
        (out/'failure.json').rename(history/f'attempt_{index:04d}.json')
    return report


def gallery(out, rows):
    cards = []
    for key, row in rows.items():
        images = ''.join(f'<figure><a href="{key}/screenshots/{p.name}"><img loading="lazy" src="{key}/screenshots/{p.name}"></a><figcaption>{html.escape(p.stem)}</figcaption></figure>'
                         for p in sorted((out/key/'screenshots').glob('*.png')) if p.name != 'navigation.png')
        cards.append(f'<section><h2>{key}</h2><pre>{html.escape(json.dumps(row, ensure_ascii=False, indent=2))}</pre><div class="grid">{images}</div></section>')
    (out/'review_index.html').write_text('<!doctype html><meta charset="utf-8"><title>CityG 原型端到端实测</title>'
        '<style>body{font:16px system-ui;margin:24px;background:#edf1f4}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}img{width:100%}pre{white-space:pre-wrap}section{background:white;padding:20px;margin:20px 0}</style>'
        '<h1>三次原型端到端集成测试</h1><p>可选测试入口，不是默认主脚本。LLM选城市原型，规则适配楼层/房间，VLM只审核。失败与回退单独记录，不自动批准原型。户外截图采用限量真实资产的轻量截图模式，Viewer保留完整资产。</p>' + ''.join(cards))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cases', nargs='+', choices=list(CASES), default=list(CASES))
    parser.add_argument('--base-url', default='http://127.0.0.1:8000/v1')
    parser.add_argument('--model', default='cityg-llm')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args(); root = Path(__file__).resolve().parents[1]; out = args.output.resolve()
    if out.exists() and any(out.iterdir()) and not args.resume:
        parser.error('Use a fresh output or --resume')
    out.mkdir(parents=True, exist_ok=True)
    urban = UrbanPrototypeLibrary(root/'configs/layout_prototypes/v1'); floors = FloorPrototypeLibrary(urban.root)
    snapshot = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(urban.root.glob('*.json'))}
    previous = out/'library_hashes.json'
    if previous.is_file() and json.loads(previous.read_text()) != snapshot:
        parser.error('Prototype library changed since checkpoint')
    save_json(snapshot, previous); rows = {}
    for key in args.cases:
        dest = out/key; dest.mkdir(exist_ok=True); print('case_start', key, flush=True)
        service = OpenAICompatibleService(ModelEndpoint(args.base_url, args.model,
            timeout_s=240, max_tokens=4096, temperature=.2, seed=CASES[key]['seed']))
        try:
            report, city = prepare(CASES[key], service, urban, floors, root, dest)
            rows[key] = capture_and_review(service, dest, report)
        except Exception as exc:
            rows[key] = {'failed': True, 'error': f'{type(exc).__name__}: {exc}'}
            save_json(rows[key], dest/'failure.json')
            print('case_failed', key, rows[key]['error'], flush=True)
        save_json(rows, out/'summary.json'); gallery(out, rows)
    assert snapshot == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(urban.root.glob('*.json'))}
    print('review_gallery', out/'review_index.html', flush=True)
    if any(r.get('failed') or not r.get('vlm_available') for r in rows.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
