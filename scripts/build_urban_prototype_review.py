"""Build opt-in urban prototype review scenes with local assets, never model calls.

Use --resume to continue this script's completed preparation checkpoints.
Partial compilation directories are not overwritten. Rendering is headless.
"""
import argparse
import asyncio
from functools import partial
import html
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
import shutil
from pathlib import Path
from threading import Thread
from zipfile import ZipFile,ZIP_DEFLATED

from cityg.assets import AssetRegistry,MaterialLibrary
from cityg.geometry import GeometryCompiler,GeometryValidator
from cityg.planning.urban_prototypes import UrbanPrototypeLibrary,realization,topology_snapshot
from cityg.planning.urban_prototype_review import plan_svg,review_views
from cityg.serialization import save_json,load_city
from cityg.services import OpenUSDBackend
from cityg.validation import CityValidator
from cityg.viewer import export_portable_viewer
from cityg.viewer import viewer_static_dir


def gallery(output,rows,library):
    cards=[]
    for row in rows:
        key=row['prototype_id'];r=library.records[key];m=row['realization']
        images=f'<figure><a href="{key}/layout.svg"><img src="{key}/layout.svg"></a><figcaption>规划图：建筑包络 / 道路 / 地块 / 空地</figcaption></figure>'
        for suffix,title in [('bird','斜向鸟瞰'),('street_1','街景 A'),('street_2','街景 B'),('feature','滨水 / 公共空间')]:
            if (output/key/'screenshots'/f'{suffix}.png').is_file():
                images+=f'<figure><a href="{key}/screenshots/{suffix}.png"><img loading="lazy" src="{key}/screenshots/{suffix}.png"></a><figcaption>{title}</figcaption></figure>'
        cards.append(f'<article data-id="{key}"><h2>{html.escape(r["display_name"])}</h2><p>{html.escape(r["intent"])}</p>'
            f'<p>{m["building_count"]} 栋 · {m["multi_building_block_count"]} 个多楼组团 · {m["public_space_count"]} 处公共空地 · '
            f'{m["morphology"]["straight_road_length_ratio"]:.1%} 直线路长 · '
            f'{m["morphology"]["expressive_building_count"]} 栋异形建筑 · {m["bridge_count"]} 座桥</p><div class="images">{images}</div>'
            f'<p>交互查看：下载 <code>{key}/viewer</code>，运行 <code>python serve.py</code>。</p>'
            f'<details><summary>实际统计与验证</summary><pre>{html.escape(json.dumps(row,ensure_ascii=False,indent=2))}</pre></details>'
            '<select><option value="pending">待审核</option><option value="approve">认可</option><option value="revise">修改</option></select>'
            '<textarea placeholder="例如：调整街区尺度、建筑疏密、高层比例或公共空间位置。"></textarea></article>')
    seed=json.dumps({'prototypes':[{k:r[k] for k in ('prototype_id','content_fingerprint')} for r in rows]},ensure_ascii=False).replace('<','\\u003c')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>CityG 城市原型审核</title>
<style>body{margin:0;background:#edf1f4;color:#24313b;font:16px/1.6 system-ui}main{max-width:1500px;padding:24px;margin:auto}header,article{background:white;padding:24px;border-radius:12px;margin:18px 0}.images{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}figure{margin:0}img{width:100%}pre{white-space:pre-wrap;font-size:12px}textarea{width:95%;min-height:75px;display:block;margin-top:12px}button,select{padding:10px}@media(max-width:800px){.images{grid-template-columns:1fr}}</style>
<main><header><h1>CityG · 城市 / 街区原型审核</h1><p>本批只审核室外布局、道路、组团、公共空间和天际线，不包含精细室内。使用现有本地资产，无 LLM/VLM、下载或生成模型调用。</p>
<p>规划图矩形是建筑规划包络，不是最终外轮廓；实际体量、材质与资产见 Viewer 截图。
这是现有路网语法上的可调整配方，不是任意路网或历史城区复原。公共空间锚点从现有合法空地选取，不保证位于城市几何中心；商住沿街后排关系、园区专属步行网/集中停车尚未硬约束。</p>
<p>截图保留真实 GLB / 纹理，关闭阴影、HDR 和玻璃透射；每视图最多抽取 64 个户外资产实例（鸟瞰按区域、近景按类型与距离），不使用几何树替代。
因此截图用于布局审核，不代表全量景观密度。完整资产仍保存在各 Viewer，正常 Presentation 模式不采样；不修改界面默认设置。
城市、几何、USD 和浏览器检查不等于真实物理运行或视觉审核通过。楼层原型只保留引用提示，未接入生成。反馈只下载到本机，不会自动提交或批准。</p>
<button id="download">下载审核意见</button></header>'''+''.join(cards)+'''</main><script>
const seed=SEED;document.querySelector('#download').onclick=()=>{const data={...seed,reviewed_at:new Date().toISOString(),prototypes:seed.prototypes.map(r=>{const e=document.querySelector(`[data-id="${r.prototype_id}"]`);return {...r,decision:e.querySelector('select').value,notes:e.querySelector('textarea').value}})};const u=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='urban_prototype_feedback.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);};</script></html>'''.replace('SEED',seed)
    (output/'review_index.html').write_text(page)
    save_json({'schema_version':1,'status':'pending_human_review','production_enabled':False,'prototypes':rows},output/'review_manifest.json')
    with ZipFile(output/'review_images.zip','w',ZIP_DEFLATED) as z:
        for p in (output/'review_index.html',output/'review_manifest.json'):z.write(p,p.name)
        for row in rows:
            base=output/row['prototype_id']
            files=[base/'layout.svg',base/'recipe.json',base/'realization.json',base/'topology.json',base/'validation.json',base/'observation.json']
            files.extend(sorted((base/'screenshots').glob('*.png')))
            for p in files:
                if p.is_file() and p.name!='navigation.png':z.write(p,str(p.relative_to(output)))
        z.writestr('HOW_TO_REVIEW.txt','解压后打开 review_index.html；交互 Viewer 需另行下载每个原型的 viewer 文件夹。\n')


def prepare(key,library,output,resume):
    dest=output/key;stamp=library.content_fingerprint(key)
    if (dest/'prepared.json').exists():
        row=json.loads((dest/'prepared.json').read_text())
        if not resume or row['content_fingerprint']!=stamp:raise ValueError('Existing checkpoint does not match current recipe; use a fresh output')
        for name in ('validation.json','scene/city.json','viewer/index.html'):
            if not (dest/name).is_file():raise ValueError('Incomplete checkpoint: '+name)
        # Refresh only frontend code for this builder-owned portable export;
        # leave the compiled scene and copied asset payloads untouched.
        shutil.copytree(viewer_static_dir(),dest/'viewer',dirs_exist_ok=True)
        return row,load_city(dest/'scene/city.json')
    if dest.exists() and any(dest.iterdir()):raise ValueError('Partial output exists; use a fresh output directory')
    dest.mkdir(parents=True,exist_ok=True)
    save_json(library.records[key],dest/'recipe.json')
    city=library.plan(key);measure=realization(city,library.spec(key));semantic=CityValidator().validate(city)
    save_json(measure,dest/'realization.json');save_json(semantic.to_dict(),dest/'validation.json')
    if not measure['ok'] or not semantic.ok:raise ValueError('Urban reference planning failed; inspect validation/realization')
    save_json(topology_snapshot(city),dest/'topology.json')
    print('compile_start',key,flush=True)
    root=Path(__file__).resolve().parents[1]
    registry=AssetRegistry(root/'assets/asset_registry.json');materials=MaterialLibrary(root/'assets/material_library.json')
    compiler=GeometryCompiler(asset_registry=registry,material_library=materials,include_interiors=False,
        facade_asset_index_path=str(root/'assets/facades/asset_annotations_reviewed.json'),
        facade_asset_cache_root=str(dest/'facade_cache'))
    scene=compiler.compile(city);geometry=GeometryValidator().validate(city,scene)
    save_json(geometry.to_dict(),dest/'geometry_validation.json')
    if not geometry.ok:raise ValueError('Compiled urban geometry failed validation')
    if scene.metadata.get('interiors_compiled'):raise ValueError('Urban review must not compile interiors')
    OpenUSDBackend(compiler).compile(city,dest/'scene',_scene_override=scene)
    save_json(semantic.to_dict(),dest/'scene/validation_report.json')
    export_portable_viewer(dest/'scene',dest/'viewer')
    (dest/'layout.svg').write_text(plan_svg(city))
    views=review_views(city);save_json({'selected_views':views},dest/'observation.json')
    row={'prototype_id':key,'content_fingerprint':stamp,'realization':measure,'render_status':'not_requested',
        'city_validation_ok':semantic.ok,'geometry_validation_ok':geometry.ok,
        'interiors_compiled':False,'physics_runtime':'not_executed','llm_used':False,'vlm_used':False,
        'primitive_count':len(scene.primitives),'resolved_asset_primitives':scene.metadata.get('resolved_asset_primitive_count',0)}
    save_json(row,dest/'prepared.json')
    print('compile_end',key,len(scene.primitives),flush=True)
    return row,city


def captures_complete(dest,views):
    """Reuse successful, identical views only; failed/partial captures retry."""
    try:
        report=json.loads((dest/'screenshots/viewer_smoke.json').read_text())
        if not report.get('exercise_ok') or not report.get('canvas_only'):return False
        if [v['spec'] for v in report['views']]!=views:return False
        return all((dest/'screenshots'/f"{v['view_id']}.png").is_file() for v in views)
    except (OSError,ValueError,KeyError,TypeError):
        return False


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,default=Path('configs/layout_prototypes/v1'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--prototypes',nargs='+')
    parser.add_argument('--render',action='store_true');parser.add_argument('--resume',action='store_true')
    parser.add_argument('--force-render',action='store_true',help='Refresh even successful captures after renderer changes')
    args=parser.parse_args();lib=UrbanPrototypeLibrary(args.library);keys=args.prototypes or list(lib.records)
    if args.force_render and not args.render:parser.error('--force-render requires --render')
    if len(keys)!=len(set(keys)) or not 1<=len(keys)<=12 or any(k not in lib.records for k in keys):parser.error('Select 1..12 unique existing prototypes')
    if args.output.exists() and any(args.output.iterdir()) and not args.resume:parser.error('Use a fresh output or --resume')
    args.output.mkdir(parents=True,exist_ok=True);rows=[]
    for key in keys:
        row,city=prepare(key,lib,args.output,args.resume);dest=args.output/key
        if args.render:
            views=review_views(city)
            save_json({'selected_views':views},dest/'observation.json')
            row['capture_profile']='textured_no_shadow_no_hdr_no_transmission'
            row['capture_outdoor_asset_budget']=64
            if args.resume and not args.force_render and captures_complete(dest,views):
                row['render_status']='passed'
                rows.append(row);gallery(args.output,rows,lib)
                print('capture_reused',key,flush=True)
                continue
            from scripts.check_portable_viewer import check
            class QuietHandler(SimpleHTTPRequestHandler):
                def log_message(self,*args):pass
            server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str((dest/'viewer').resolve())))
            Thread(target=server.serve_forever,daemon=True).start();(dest/'screenshots').mkdir(exist_ok=True)
            try:
                result=asyncio.run(check(f'http://127.0.0.1:{server.server_port}/',dest/'screenshots',240,
                    views,require_assets=True,canvas_only=True))
                row['render_status']='passed' if result.get('exercise_ok') else 'failed'
            finally:server.shutdown();server.server_close()
        rows.append(row);gallery(args.output,rows,lib)
        if row['render_status']=='failed':raise RuntimeError('Headless capture failed; prepared scene is resumable')
    print('Review gallery:',args.output/'review_index.html',flush=True)


if __name__=='__main__':main()
