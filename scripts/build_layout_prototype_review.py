"""Build an opt-in, offline prototype lab and a human review gallery.

No model, downloads, production registry writes, or approval are performed.
The optional headless renderer never opens a desktop browser.
"""
from __future__ import annotations

import argparse
import asyncio
from functools import partial
from dataclasses import asdict
import html
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from zipfile import ZipFile, ZIP_DEFLATED

from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.observation import AdaptiveObservationPlanner
from cityg.planning.prototype_lab import (compiled_containment_checks, detached_registry,
                                          make_lab, populate_reference, compiled_open_plan_checks)
from cityg.planning.prototypes import LayoutPrototypeLibrary, fingerprint
from cityg.serialization import save_json
from cityg.services import OpenUSDBackend
from cityg.validation import CityValidator
from cityg.viewer import export_portable_viewer


def gallery(output, manifest):
    cards = []
    for row in manifest['rooms']:
        key = row['prototype_id']
        images = ''.join((f'<figure><a href="screenshots/{key}_{preset}.png" target="_blank">'
                         f'<img loading="lazy" src="screenshots/{key}_{preset}.png" alt="{label}"></a>'
                         f'<figcaption>{label}</figcaption></figure>')
                         if (output/'screenshots'/f'{key}_{preset}.png').is_file()
                         else f'<figure><p>{label}：尚未渲染，请使用 --render 生成。</p></figure>'
                         for preset, label in [('top', '俯视 · 空间与通道'), ('cutaway', '剖切透视 · 整体关系'),
                                               ('eye', '室内透视 · 尺度与朝向')])
        ref = row['reference']
        cards.append(f'''<article data-id="{key}"><h2>{html.escape(row['display_name'])}</h2>
<code>{key}</code><p>{html.escape(row['intent'])}</p>
<p>{ref['width_m']} × {ref['depth_m']} m · {row['occupants']} 人 · 主体 {row['major_count']} 件 ·
小物件 {row['surface_placed']}/{row['surface_requested']} 件 ·
装饰 {row.get('decorations',{}).get('placed',0)}/{row.get('decorations',{}).get('requested',0)} 件 · 状态：待你审核</p>
<div class="images">{images}</div><p>适配测试：{html.escape(row['adaptation_summary'])}</p>
<details><summary>组合、资产与检查记录</summary><pre>{html.escape(json.dumps(row, ensure_ascii=False, indent=2))}</pre></details>
<label>你的意见 <select><option value="pending">待审核</option><option value="approve">认可当前版本</option>
<option value="revise">需要修改</option><option value="reject">不采用</option></select></label>
<textarea placeholder="例如：床组保留；衣柜换到西墙；书桌与椅子的间距再缩小。"></textarea></article>''')
    seed = json.dumps({'schema_version': 1, 'review_batch_fingerprint': manifest['batch_fingerprint'],
                       'rooms': [{'prototype_id': r['prototype_id'], 'content_fingerprint': r['content_fingerprint'],
                                  'snapshot_fingerprint': r['snapshot_fingerprint']} for r in manifest['rooms']]},
                      ensure_ascii=False).replace('<', '\\u003c')
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>CityG · 房间原型审核</title><style>
body{margin:0;background:#eef1f4;color:#24313b;font:16px/1.6 system-ui,sans-serif}main{max-width:1500px;margin:auto;padding:28px}
header,article{background:white;border-radius:14px;padding:24px;margin:18px 0}h1,h2{margin:0 0 12px}code{color:#526a77}
.images{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}figure{margin:0}img{width:100%;background:#dae3e5}figcaption{color:#526a77}
textarea{display:block;box-sizing:border-box;width:100%;min-height:80px;margin:12px 0;padding:12px}button,select{padding:10px;border:1px solid #b8c6ce;border-radius:6px}
button{background:#20566b;color:white;cursor:pointer}pre{white-space:pre-wrap;font-size:12px}details{margin:12px 0}
@media(max-width:850px){.images{grid-template-columns:1fr}main{padding:12px}}</style><main><header>
<h1>CityG · 房间布局原型审核</h1><p>这是待审核的参考设计，不是已批准的正式原型。点击图片可放大；下方可填写意见并下载反馈 JSON。
反馈只下载到本机，不会自动修改原型库，也不会上传。关闭页面前请下载保存。</p>
<p>小物件显示“实际放置 / 请求数量”；不能实现的物件不会隐瞒。适配范围是候选筛选条件，不代表范围内所有输入均已验证。</p>
<p>本版装饰包含真实绿植、画框、地毯和部分落地灯。窗户/窗帘尚未加入：需先建立室内墙洞与建筑立面共享的开口契约，不以贴在实墙上的假窗替代。</p>
<p>交互查看：在同目录的 <code>viewer</code> 中运行 <code>python serve.py</code>。本页面可以直接打开，不需要 vLLM。</p>
<button id="download">下载审核意见</button></header>''' + ''.join(cards) + '''</main><script>
const seed = SEED;
document.querySelector('#download').onclick=()=>{
 const result={...seed,reviewed_at:new Date().toISOString(),rooms:seed.rooms.map(r=>{
 const e=document.querySelector(`[data-id="${r.prototype_id}"]`);
 return {...r,decision:e.querySelector('select').value,notes:e.querySelector('textarea').value};})};
 const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));
 const a=document.createElement('a');a.href=url;a.download='prototype_feedback.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};</script></html>'''.replace('SEED', seed)
    (output/'review_index.html').write_text(page, encoding='utf-8')


def pack_review(output):
    """Small portable review evidence; deliberately excludes large scene GLBs."""
    with ZipFile(output/'review_images.zip', 'w', compression=ZIP_DEFLATED) as archive:
        files = [output/'review_index.html', output/'review_manifest.json', output/'validation.json',
                 *(p for p in sorted((output/'screenshots').glob('*.png')) if p.name != 'navigation.png'),
                 *sorted((output/'library_snapshot').glob('*.json'))]
        for path in files:
            if path.is_file():
                archive.write(path, str(path.relative_to(output)))
        archive.writestr('HOW_TO_REVIEW.txt',
            '解压后直接打开 review_index.html；也可逐张查看 screenshots。\n'
            '每个原型提供俯视、剖切透视、室内透视。页面意见可下载为 prototype_feedback.json。\n'
            '此轻量包不包含交互 Viewer 或 GLB；需要交互时另行下载服务器输出中的 viewer 文件夹。\n'
            '所有原型待人工审核；软件校验通过不代表视觉质量已获批准。\n')


def inventory_checks(scene, rows):
    """Never call a partial nominal inventory a completed review reference."""
    checks = []
    for row in rows:
        for name in ('room_surface_items', 'room_decorations'):
            report = scene.metadata.get(name, {}).get(row['room_id'], {})
            requested, placed = report.get('requested', 0), report.get('placed', 0)
            expected = row.get('expected_inventory', {}).get(name, requested)
            checks.append({'prototype_id':row['prototype_id'], 'kind':name,
                           'expected':expected, 'requested':requested, 'placed':placed,
                           'ok':expected == requested == placed})
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, default=Path('configs/layout_prototypes/v1'))
    parser.add_argument('--registry', type=Path, default=Path('assets/asset_registry.json'))
    parser.add_argument('--materials', type=Path, default=Path('assets/incoming/interior_materials/material_library.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--prototypes', nargs='+', help='Review these IDs (at most ten); default: base rooms.json batch')
    args = parser.parse_args()
    library = LayoutPrototypeLibrary(args.library)
    keys = args.prototypes or [r['id'] for r in json.loads((args.library/'rooms.json').read_text())['prototypes']]
    if len(keys) > 10 or len(keys) != len(set(keys)) or any(k not in library.rooms for k in keys):
        parser.error('Select 1..10 distinct existing room IDs with --prototypes')
    if args.output.exists() and any(args.output.iterdir()):
        parser.error('Use a fresh output directory; existing review evidence is never overwritten')
    args.output.mkdir(parents=True, exist_ok=True)
    source = AssetRegistry(args.registry)
    registry = detached_registry(source)
    from cityg.planning.prototype_decor_assets import add_review_decorations
    decor_annotations = args.library/'decoration_assets.json'
    if decor_annotations.is_file():
        add_review_decorations(registry, decor_annotations, project_root=Path(__file__).resolve().parents[1])
    used = {asset for key in keys for asset in library.materialize(key).asset_bindings.values()}
    used.update(d['asset_id'] for key in keys for d in library.rooms[key].get('decorations', []))
    for annotations in sorted(args.library.glob('reference_assets_*.json')):
        add_review_decorations(registry, annotations, project_root=Path(__file__).resolve().parents[1], asset_ids=used)
        save_json(json.loads(annotations.read_text()), args.output/'library_snapshot'/annotations.name)
    city, targets = make_lab(library, keys)
    rows = []
    # Snapshot the exact definitions; changing the source cannot change this review.
    for filename, records in [('rooms.json', library.rooms), ('combinations.json', library.combinations)]:
        save_json({'schema_version':1, 'prototypes':list(records.values())}, args.output/'library_snapshot'/filename)
    if decor_annotations.is_file():
        save_json(json.loads(decor_annotations.read_text()), args.output/'library_snapshot/decoration_assets.json')
    for target in targets:
        key = target[0]
        print('prototype_start', key, flush=True)
        row = populate_reference(city, target, library, registry)
        record = library.rooms[key]
        row['expected_inventory'] = {
            'room_surface_items':sum(q['count'] for q in library.materialize(key).design.surface_items),
            'room_decorations':len(record.get('decorations', []))}
        row.update({k: record[k] for k in ('display_name', 'intent', 'reference', 'occupants',
                                         'applicability', 'hard_constraints', 'editable_fields', 'group_instances')})
        row['review_status'] = 'pending_review'
        row['zones'] = record['zones']
        row['reserved_areas'] = record.get('reserved_areas', [])
        row['adaptations'] = []
        for case in record.get('adaptation_cases', []):
            try:
                trial, trials = make_lab(library, [key], {key: case})
                evidence = populate_reference(trial, trials[0], library, registry)
                # Check all variants, including rooms without decorations.
                trial.world_program = build_world_program(trial, producer='prototype_adaptation', seed=17)
                trial_scene = GeometryCompiler(asset_registry=registry,
                    material_library=MaterialLibrary(args.materials)).compile(trial)
                from scripts.run_interior_asset_smoke import check_placements
                trial_decor = trial_scene.metadata.get('room_decorations',{}).get(trials[0][3].id,{})
                trial_surface = trial_scene.metadata.get('room_surface_items',{}).get(trials[0][3].id,{})
                if (trial_decor.get('placed',0) != trial_decor.get('requested',0)
                        or trial_surface.get('placed',0) != trial_surface.get('requested',0)
                        or not all(c['ok'] for c in inventory_checks(trial_scene, [row]))
                        or not all(c['ok'] for c in [*check_placements(trial_scene,[trials[0][3].id]),
                                                   *compiled_containment_checks(trial_scene,trials),
                                                   *compiled_open_plan_checks(trial_scene,trials)])):
                    raise ValueError('Adapted decorations/props do not realize their complete inventory')
                extra = {'decorations':trial_decor, 'surface_placed':trial_surface.get('placed',0)}
                row['adaptations'].append({'case': case, 'ok': True, 'major_count': evidence['major_count'], **extra})
            except ValueError as exc:
                row['adaptations'].append({'case': case, 'ok': False, 'error': str(exc)})
        row['adaptation_summary'] = (f"{sum(c['ok'] for c in row['adaptations'])}/{len(row['adaptations'])} "
                                     '尺寸/入口变化测试通过；装饰原型另验实际支撑，不代表全部连续尺寸范围')
        # Record physical metadata AND geometry hash, not just mutable asset IDs.
        from hashlib import sha256
        row['asset_snapshot'] = [{**registry.get(asset_id).to_dict(),
                                 'geometry_sha256': sha256(registry.resolve_path(
                                     registry.get(asset_id).geometry_path).read_bytes()).hexdigest()}
                                for asset_id in sorted(set(row['asset_bindings'].values()))]
        row['snapshot_fingerprint'] = fingerprint({'prototype': row['content_fingerprint'],
                                                    'assets': row['asset_snapshot']})
        rows.append(row)
        save_json(rows, args.output/'placement_trace.json')
        print('prototype_end', key, row['major_count'], row['adaptation_summary'], flush=True)
    city.world_program = build_world_program(city, producer='layout_prototype_review', seed=17)
    compiler = GeometryCompiler(asset_registry=registry,material_library=MaterialLibrary(args.materials))
    scene = compiler.compile(city)
    validation = CityValidator().validate(city)
    geometry = GeometryValidator().validate(city, scene)
    # Shared surface-support acceptance checks, not visual certification.
    from scripts.run_interior_asset_smoke import check_placements
    support_checks = check_placements(scene, [r['room_id'] for r in rows])
    containment = compiled_containment_checks(scene, targets)
    inventory = inventory_checks(scene, rows)
    open_plan = compiled_open_plan_checks(scene, targets)
    checks = {'city': validation.to_dict(), 'geometry': geometry.to_dict(),
              'surface_checks': support_checks, 'compiled_containment': containment,
              'inventory_checks': inventory, 'open_plan_checks':open_plan}
    save_json(checks, args.output/'validation.json')
    if not validation.ok or not geometry.ok or not all(c['ok'] for c in [*support_checks, *containment, *inventory, *open_plan]):
        raise RuntimeError('Reference validation failed; inspect validation.json')
    for row in rows:
        surfaces = scene.metadata.get('room_surface_items', {}).get(row['room_id'], {})
        row.update(surface_requested=surfaces.get('requested', 0), surface_placed=surfaces.get('placed', 0),
                   surface_report=surfaces)
        row['finishes'] = scene.metadata.get('room_finishes',{}).get(row['room_id'],{})
        row['decorations'] = scene.metadata.get('room_decorations',{}).get(row['room_id'],{})
        row['finish_material_snapshot'] = []
        for material in scene.materials:
            if material.id not in row['finishes'].values():
                continue
            from hashlib import sha256
            texture_hashes = {channel: sha256(Path(path).read_bytes()).hexdigest()
                for channel in ('base_color', 'normal', 'roughness', 'ambient_occlusion')
                if (path := getattr(material, channel+'_path'))}
            row['finish_material_snapshot'].append({**asdict(material), 'texture_sha256': texture_hashes})
        # Include actual small-prop choices as well as the pinned major assets.
        from hashlib import sha256
        ids = {p.metadata['asset_id'] for p in scene.primitives
               if row['room_id'] in p.metadata.get('room_ids', []) and p.metadata.get('resolved_asset')}
        row['realized_asset_snapshot'] = [{**registry.get(asset_id).to_dict(),
            'geometry_sha256': sha256(registry.resolve_path(registry.get(asset_id).geometry_path).read_bytes()).hexdigest()}
            for asset_id in sorted(ids)]
        row['snapshot_fingerprint'] = fingerprint({'prototype': row['content_fingerprint'],
            'assets': row['asset_snapshot'], 'realized_assets': row['realized_asset_snapshot'],
            'surface_report': surfaces, 'finishes': row['finish_material_snapshot'],
            'decorations': row['decorations']})
    OpenUSDBackend(compiler).compile(city, args.output/'scene', _scene_override=scene)
    save_json(validation.to_dict(), args.output/'scene/validation_report.json')
    export_portable_viewer(args.output/'scene', args.output/'viewer')
    plan = AdaptiveObservationPlanner(max_views=24).plan(city, geometry_manifest=scene)
    views = []
    for row in rows:
        candidates = [v.to_dict() for v in plan.candidates if v.kind == 'room_interior'
                      and v.target_entity_ids[0] == row['room_id']]
        for suffix, preset in [('top_00', 'top'), ('perspective_00', 'eye')]:
            candidate = next(v for v in candidates if v['view_id'].endswith(suffix))
            views.append({**candidate, 'view_id': f"{row['prototype_id']}_{preset}",
                          'render_profile': 'presentation'})
        views.append({'view_id': f"{row['prototype_id']}_cutaway", 'kind': 'room_interior', 'mode': 'room',
                      'target_entity_ids': [row['room_id']], 'room_camera_preset': 'cutaway',
                      'render_profile': 'presentation', 'appearance': 'presentation'})
    save_json({'selected_views': views}, args.output/'observation.json')
    manifest = {'schema_version': 1, 'status': 'pending_human_review', 'rooms': rows,
                'batch_fingerprint': fingerprint([r['snapshot_fingerprint'] for r in rows]),
                'llm_used': False, 'asset_generation_used': False, 'production_enabled': False,
                'render_status': 'not_requested'}
    save_json(manifest, args.output/'review_manifest.json')
    if args.render:
        from scripts.check_portable_viewer import check
        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str((args.output/'viewer').resolve())))
        Thread(target=server.serve_forever, daemon=True).start()
        (args.output/'screenshots').mkdir()
        try:
            smoke = asyncio.run(check(f'http://127.0.0.1:{server.server_port}/', args.output/'screenshots',
                                      180, views, require_assets=True))
            manifest['render_status'] = 'passed' if smoke.get('exercise_ok') else 'failed'
            save_json(manifest, args.output/'review_manifest.json')
            if not smoke.get('exercise_ok'):
                raise RuntimeError('Headless review capture failed; inspect screenshots/viewer_smoke.json')
        finally:
            server.shutdown()
            server.server_close()
    gallery(args.output, manifest)
    if manifest['render_status'] == 'passed':
        pack_review(args.output)
    print('Review gallery:', args.output/'review_index.html', flush=True)
    print('Portable viewer:', args.output/'viewer', flush=True)


if __name__ == '__main__':
    main()
