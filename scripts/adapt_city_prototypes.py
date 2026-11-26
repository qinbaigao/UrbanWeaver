"""Adapt compatible rooms in a saved generated city; never overwrite input.

Requires a canonical OpenUSD export (city.json and geometry_manifest.json).
No LLM/VLM or asset generation. Optional locked-skeleton floor repartitioning.
"""
import argparse
import asyncio
from dataclasses import replace
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
from pathlib import Path
import hashlib
import html
import json
from zipfile import ZipFile,ZIP_DEFLATED

from cityg.assets import AssetRegistry,MaterialLibrary
from cityg.geometry import GeometryCompiler,GeometryValidator
from cityg.geometry.incremental import scene_from_manifest,merge_building_scene,entity_building_index
from cityg.planning.floor_prototypes import FloorPrototypeLibrary
from cityg.planning.prototype_lab import detached_registry
from cityg.planning.prototype_decor_assets import add_review_decorations
from cityg.planning.city_prototype_adapter import adapt_city_rooms,verify_room,validate_options
from cityg.planning.floor_repartition import repartition_city
from cityg.serialization import load_city,save_json
from cityg.services import OpenUSDBackend
from cityg.viewer import export_portable_viewer
from cityg.validation import CityValidator


def resolve_input(path):
    if path.is_file():path=path.parent
    if (path/'city.json').is_file() and (path/'geometry_manifest.json').is_file():return path.resolve()
    candidates=[path/name for name in ('final','openusd','scene')
        if (path/name/'city.json').is_file() and (path/name/'geometry_manifest.json').is_file()]
    if len(candidates)!=1:raise ValueError('Input must identify one canonical city/geometry export')
    return candidates[0].resolve()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--config',type=Path,default=Path('configs/city_prototype_adaptation.json'))
    p.add_argument('--render',action='store_true')
    a=p.parse_args();source=resolve_input(a.input);out=a.output.resolve()
    if source==out or source in out.parents or out in source.parents:p.error('Output must be independent of input')
    if out.exists() and any(out.iterdir()):p.error('Use a fresh output directory')
    out.mkdir(parents=True,exist_ok=True);root=Path(__file__).resolve().parents[1]
    original_hash=hashlib.sha256((source/'city.json').read_bytes()).hexdigest()
    city=load_city(source/'city.json');lib=FloorPrototypeLibrary(root/'configs/layout_prototypes/v1')
    registry=detached_registry(AssetRegistry(root/'assets/asset_registry.json'))
    if (source/'assets/asset_registry.json').is_file():
        for record in detached_registry(AssetRegistry(source/'assets/asset_registry.json')).list_all():
            if registry.get(record.asset_id) is None:registry.register(record)
    for file in [lib.root/'decoration_assets.json',*sorted(lib.root.glob('reference_assets_*.json'))]:
        add_review_decorations(registry,file,project_root=root)
    materials=MaterialLibrary()
    for path in (source/'assets/material_library.json',root/'assets/incoming/interior_materials/material_library.json'):
        material_source=MaterialLibrary(path)
        if material_source.environment_path and materials.environment_path is None:
            materials.set_environment(material_source.resolve_path(material_source.environment_path))
        for record in material_source.list_all():
            if materials.get(record.material_id) is not None:continue
            paths={k:str(material_source.resolve_path(getattr(record,k))) for k in
                ('base_color_path','normal_path','roughness_path','ambient_occlusion_path') if getattr(record,k)}
            materials.register(replace(record,**paths))
    compiler=GeometryCompiler(asset_registry=registry,material_library=materials,
        facade_asset_index_path=str(root/'assets/facades/asset_annotations_reviewed.json'),
        facade_asset_cache_root=str(out/'facade_cache'))
    config=validate_options(json.loads(a.config.read_text()))
    progress=lambda *args:print(*args,flush=True)
    partitioned,floor_report=repartition_city(city,lib,compiler,config.get('floor_repartition',{}),
        variation=config['variation_limit'],progress=progress)
    result,report=adapt_city_rooms(partitioned,lib,registry,compiler,config,progress=progress,
        target_levels=floor_report['selected_levels'] if floor_report['enabled'] else None)
    report['floor_repartition']=floor_report
    report['summary']['repartitioned_floors']=len(floor_report['accepted'])
    if floor_report['accepted']:
        report['mode']='existing_city_locked_floor_and_room_adaptation'
        report['architecture_preserved']=False
        report['entrance_core_and_circulation_preserved']=True
        for bid,levels in floor_report['selected_levels'].items():
            report['selected_levels'][bid]=sorted(set(report['selected_levels'].get(bid,[]))|set(levels))
        report['summary']['selected_buildings']=len(report['selected_levels'])
    result.metadata['city_prototype_adaptation']={k:report[k] for k in ('mode','architecture_preserved','selected_levels','summary')}
    report.update(source_path=str(source),source_city_sha256=original_hash)
    save_json(report,out/'adaptation_report.json')
    if not report['rooms'] and not floor_report['accepted']:
        print('No compatible proposal passed. Source retained; inspect adaptation_report.json.',flush=True);return
    previous=scene_from_manifest(json.loads((source/'geometry_manifest.json').read_text()))
    affected=set(report['selected_levels'])
    subset=compiler.compile(result,building_ids=affected)
    scene,merge_stats=merge_building_scene(result,previous,subset,affected,previous_city=city)
    report['incremental_compile']=merge_stats
    old_index=entity_building_index(city);current={p.id:p for p in scene.primitives}
    retained=[p for p in previous.primitives if old_index.get(p.owner_id) not in affected]
    if any(current.get(p.id)!=p for p in retained):raise ValueError('Unrelated compiled geometry changed')
    # Shared material IDs affect retained geometry too. Keep their original PBR
    # records, not only primitive poses; preserve the existing environment.
    used_materials={p.material_id for p in retained}
    merged_materials={m.id:m for m in scene.materials}
    merged_materials.update({m.id:m for m in previous.materials if m.id in used_materials})
    scene.materials=list(merged_materials.values())
    scene.metadata['environment_path']=previous.metadata.get('environment_path')
    report['unrelated_geometry_preserved']=True
    report['retained_materials_preserved']=True
    checks=[]
    for row in report['rooms']:
        b=next(b for b in result.iter_buildings() if b.id==row['building_id'])
        f=next(f for f in b.floors if f.id==row['floor_id']);r=next(r for r in f.rooms if r.id==row['room_id'])
        checks.extend(verify_room(scene,b,f,r,row))
        for key in ('room_surface_items','room_decorations'):row[key]=scene.metadata.get(key,{}).get(r.id,{})
    semantic=CityValidator().validate(result);geometry=GeometryValidator().validate(result,scene)
    save_json({'city':semantic.to_dict(),'geometry':geometry.to_dict(),'room_checks':checks},out/'validation.json')
    if not semantic.ok or not geometry.ok:raise ValueError('Merged scene failed validation; no final scene exported')
    OpenUSDBackend(compiler).compile(result,out/'scene',_scene_override=scene)
    save_json(semantic.to_dict(),out/'scene/validation_report.json')
    export_portable_viewer(out/'scene',out/'viewer')
    views=[]
    for bid,levels in report['selected_levels'].items():
        b=next(b for b in result.iter_buildings() if b.id==bid)
        for level in levels:
            f=next(f for f in b.floors if f.level==level)
            views.append({'view_id':f.id+'_top','kind':'floor_plan','mode':'floor_plan',
                'target_entity_ids':[b.id,f.id],'floor_camera_preset':'top','render_profile':'presentation',
                'appearance':'presentation','auto_cutaway':True})
    for row in report['rooms']:
        for preset in ('top','cutaway'):
            views.append({'view_id':row['room_id']+'_'+preset,'kind':'room_interior','mode':'room',
                'target_entity_ids':[row['room_id']],'room_camera_preset':preset,'render_profile':'presentation',
                'appearance':'presentation','auto_cutaway':True})
    save_json({'selected_views':views},out/'observation.json')
    report['render_status']='not_requested'
    if a.render:
        from scripts.check_portable_viewer import check
        class Quiet(SimpleHTTPRequestHandler):
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(out/'viewer')))
        Thread(target=server.serve_forever,daemon=True).start();(out/'screenshots').mkdir()
        try:
            capture=asyncio.run(check(f'http://127.0.0.1:{server.server_port}/',out/'screenshots',240,
                views,require_assets=True,canvas_only=True))
            report['render_status']='passed' if capture.get('exercise_ok') else 'failed'
        finally:server.shutdown();server.server_close()
    assert hashlib.sha256((source/'city.json').read_bytes()).hexdigest()==original_hash
    save_json(report,out/'adaptation_report.json')
    cards=''.join(f'<figure><a href="screenshots/{v["view_id"]}.png"><img loading="lazy" src="screenshots/{v["view_id"]}.png"></a><figcaption>{html.escape(v["view_id"])}</figcaption></figure>'
        for v in views if (out/'screenshots'/f'{v["view_id"]}.png').is_file())
    (out/'review_index.html').write_text('<!doctype html><meta charset="utf-8"><title>真实城市原型适配</title><style>body{font:16px system-ui;background:#eef1f4;margin:24px}main{max-width:1400px;margin:auto}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}img{width:100%}figure{margin:0;background:white;padding:12px}pre{white-space:pre-wrap}</style><main><h1>真实城市 · 楼层与房间原型适配</h1><p>读取已生成城市，保留道路、建筑外壳、既有门、交通空间和核心筒。可按配置拆分相邻空房间，使用楼层原型的同功能开间参考；不是完整原型替换。仅提交通过编译校验的方案，失败原因见 adaptation_report.json。本轮不调用 LLM/VLM，不生成资产。</p><pre>'+html.escape(json.dumps(report['summary'],ensure_ascii=False,indent=2))+'</pre><div class="grid">'+cards+'</div></main>')
    with ZipFile(out/'review_images.zip','w',ZIP_DEFLATED) as z:
        for file in [out/'review_index.html',out/'adaptation_report.json',out/'validation.json',*sorted((out/'screenshots').glob('*.png'))]:
            if file.is_file() and file.name!='navigation.png':z.write(file,str(file.relative_to(out)))
    if report['render_status']=='failed':raise RuntimeError('Viewer capture failed')
    print(report['summary']);print('Viewer:',out/'viewer')


if __name__=='__main__':main()
