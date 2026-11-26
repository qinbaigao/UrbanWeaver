"""Build selected review-only floor references, diagrams, portable Viewer and screenshots.

No vLLM, downloads, room-prototype promotion or production planner changes.
"""
import argparse
import asyncio
from functools import partial
import html
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from zipfile import ZipFile, ZIP_DEFLATED

from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.planning.floor_prototypes import FloorPrototypeLibrary, box, connection_segment
from cityg.planning.floor_prototype_lab import make_floor_lab, compiled_floor_checks, furnish_reference, door_point
from cityg.planning.prototypes import fingerprint
from cityg.serialization import save_json
from cityg.services import OpenUSDBackend
from cityg.validation import CityValidator
from cityg.viewer import export_portable_viewer


COLORS={'corridor':'#e4dfcf','living_room':'#f2d6a2','bedroom':'#c0d7ef','kitchen':'#d8e8bb',
    'bathroom':'#bde3e1','open_office':'#c6dbed','office':'#d5c9e5','meeting_room':'#e9d0bc',
    'break_room':'#dbe7ba','shop':'#e8d0b7','waiting_room':'#cce0c0','storage':'#d4d4d4'}


def diagram(r):
    """Geometry-derived SVG, not a generated illustration or alternate plan."""
    w,d=(r['reference'][k] for k in ('width_m','depth_m'));scale=24;padding=44
    def xy(x,y):return padding+x*scale,padding+(d-y)*scale
    def rect(b,attrs):
        x,y=xy(b.min_x,b.max_y)
        return f'<rect x="{x}" y="{y}" width="{b.width*scale}" height="{b.depth*scale}" {attrs}/>'
    def line(x0,y0,x1,y1,attrs):
        a,b=xy(x0,y0);c,e=xy(x1,y1)
        return f'<line x1="{a}" y1="{b}" x2="{c}" y2="{e}" {attrs}/>'
    width=w*scale+padding*2;height=d*scale+padding*2+72
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
         '<rect width="100%" height="100%" fill="#f7f8fa"/>',
         f'<text x="44" y="24" font-family="sans-serif" font-size="16">{r["id"]} · {w} x {d} m · north ↑</text>']
    for s in r['spaces']:
        b=box(s['bounds_m']);svg.append(rect(b,f'fill="{COLORS.get(s["function"],"#eee")}" stroke="#48525b" stroke-width="2"'))
        for uv in s.get('clear_aisles_uv',[]):
            from cityg.planning.room_regions import region_bounds
            svg.append(rect(region_bounds(b,uv),'fill="#fff" opacity=".65"'))
    for item in furnish_reference(r)[0]:svg.append(rect(item['bounds'],'fill="#727c87" fill-opacity=".35" stroke="#727c87" stroke-width=".6"'))
    for c in r['connections']:
        axis,edge,lo,hi=connection_segment(r,c)
        if c['kind']=='open':
            from cityg.planning.spatial_layout import shared_boundary
            spaces={s['id']:box(s['bounds_m']) for s in r['spaces']}
            axis,edge,lo,hi=shared_boundary(spaces[c['a']],spaces[c['b']])
        coords=(lo,edge,hi,edge) if axis=='x' else (edge,lo,edge,hi)
        svg.append(line(*coords,'stroke="#f7f8fa" stroke-width="5"'))
        svg.append(line(*coords,'stroke="#198d75" stroke-width="2"'))
    for s in r['spaces']:
        b=box(s['bounds_m']);x,y=xy(b.center.x,b.center.y)
        # Labels are identifiers: the gallery maps them to Chinese room names.
        svg.append(f'<text x="{x}" y="{y}" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#1e3543" stroke="#fff" stroke-width="2.5" paint-order="stroke">{html.escape(s["id"])} · {b.area:.0f}m²</text>')
    for core in r['cores']:
        b=box(core['bounds_m']);svg.append(rect(b,'fill="#a7b9c3" stroke="#304959" stroke-width="2"'))
        if core['kind']=='stairs':
            for i in range(1,15):svg.append(line(b.min_x,b.min_y+b.depth*i/15,b.max_x,b.min_y+b.depth*i/15,'stroke="#526f7a" stroke-width="1"'))
        x,y=xy(b.center.x,b.center.y)
        svg.append(f'<text x="{x}" y="{y}" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#152f3b">{core["kind"]}</text>')
    entry=door_point(r);x,y=xy(entry.x,entry.y)
    svg.append(f'<circle cx="{x}" cy="{y}" r="7" fill="#dd8130"/><text x="{x+10}" y="{y-10}" font-size="12" font-family="sans-serif">ENTRY</text>')
    svg.append(f'<text x="44" y="{height-40}" font-size="13" font-family="sans-serif">Green: door / open connection · gray: preview furniture · stairs/lift: fixed vertical stack</text>')
    svg.append(f'<text x="44" y="{height-20}" font-size="13" font-family="sans-serif">Concept reference only. Doors assumed open for access checks. No fire-code certification.</text></svg>')
    return ''.join(svg)


def gallery(output,manifest,library):
    cards=[]
    for row in manifest['floors']:
        key=row['prototype_id'];r=library.floors[key]
        figures=f'<figure><a href="diagrams/{key}.svg"><img src="diagrams/{key}.svg"></a><figcaption>标注平面图 · 与场景共用几何定义</figcaption></figure>'
        for suffix,label in [('top','实际俯视'),('perspective','三维剖切'),('core','楼梯 / 电梯')]:
            if (output/'screenshots'/f'{key}_{suffix}.png').exists():
                figures+=f'<figure><a href="screenshots/{key}_{suffix}.png"><img loading="lazy" src="screenshots/{key}_{suffix}.png"></a><figcaption>{label}</figcaption></figure>'
        names='；'.join(f'{s["id"]}：{s["display_name"]}' for s in r['spaces'])
        cards.append(f'<article data-id="{key}"><h2>{html.escape(row["display_name"])}</h2><p>{html.escape(row["intent"])}</p>'
            f'<p>{r["reference"]["width_m"]} × {r["reference"]["depth_m"]} m · {row["unit_count"]} 个住宅单元 · '
            f'{row["space_count"]} 个空间（含走道） · {row["preview_furniture_count"]} 件简化陈设 / 层</p>'
            f'<div class="images">{figures}</div><details><summary>空间名称与检查记录</summary><p>{html.escape(names)}</p>'
            f'<pre>{html.escape(json.dumps(row,ensure_ascii=False,indent=2))}</pre></details>'
            '<select><option value="pending">待审核</option><option value="approve">认可</option><option value="revise">修改</option></select>'
            '<textarea placeholder="例如：缩小公共交通厅、增加某个单元面积、调整商铺入口。"></textarea></article>')
    seed=json.dumps({'batch_fingerprint':manifest['batch_fingerprint'],'floors':[
        {k:r[k] for k in ('prototype_id','content_fingerprint')} for r in manifest['floors']]},ensure_ascii=False).replace('<','\\u003c')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>CityG 楼层原型审核</title><style>body{background:#edf1f4;color:#24313b;font:16px/1.6 system-ui;margin:0}main{max-width:1600px;margin:auto;padding:24px}header,article{background:white;padding:24px;border-radius:12px;margin:18px 0}.images{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}figure{margin:0}img{width:100%}pre{white-space:pre-wrap;font-size:12px}textarea{display:block;width:95%;min-height:70px;margin-top:12px}button,select{padding:10px}@media(max-width:800px){.images{grid-template-columns:1fr}}</style>
<main><header><h1>CityG · 楼层原型审核</h1><p>只审核楼层空间组织。家具是轻量程序化示意，不代表精细房间原型已接入或高质量资产已加载。</p>
<p>每栋样例重复上下两层以检查核心对齐，图片展示下层。绿色线为门洞或无门公共通道；住宅 unit_id 记录户内层级。
当前不含窗户、采光分析、结构柱、合规疏散设计、跨层中庭或扶梯。图上面积是分区面积，未扣墙厚。</p>
<p>房间原型仅存为参考提示，尚未证明所有尺寸和门向兼容；本批不会改变正式生成流程。下载意见后再关闭页面。</p>
<button id="download">下载审核意见</button></header>'''+''.join(cards)+'''</main><script>
const seed=SEED;document.querySelector('#download').onclick=()=>{const data={...seed,reviewed_at:new Date().toISOString(),floors:seed.floors.map(r=>{const e=document.querySelector(`[data-id="${r.prototype_id}"]`);return {...r,decision:e.querySelector('select').value,notes:e.querySelector('textarea').value}})};const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='floor_prototype_feedback.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};</script></html>'''.replace('SEED',seed)
    (output/'review_index.html').write_text(page)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,default=Path('configs/layout_prototypes/v1'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--prototypes',nargs='+')
    parser.add_argument('--render',action='store_true')
    args=parser.parse_args();out=args.output
    if out.exists() and any(out.iterdir()):parser.error('Use a fresh output directory')
    lib=FloorPrototypeLibrary(args.library);keys=args.prototypes or list(lib.floors)
    city,rows=make_floor_lab(lib,keys);out.mkdir(parents=True,exist_ok=True)
    save_json({'schema_version':1,'prototypes':[lib.floors[k] for k in keys]},out/'library_snapshot/floors.json')
    save_json({'schema_version':1,'prototypes':list(lib.room_library.rooms.values())},out/'library_snapshot/room_references.json')
    city.world_program=build_world_program(city,producer='floor_prototype_lab',seed=17)
    compiler=GeometryCompiler();scene=compiler.compile(city)
    semantic=CityValidator().validate(city);geometry=GeometryValidator().validate(city,scene)
    compiled=compiled_floor_checks(city,scene)
    report={'city':semantic.to_dict(),'geometry':geometry.to_dict(),'compiled_checks':compiled,
            'layout_checks':[{k:r[k] for k in ('prototype_id','layout_validation','circulation_check')} for r in rows]}
    save_json(report,out/'validation.json')
    if not semantic.ok or not geometry.ok or not all(c['ok'] for c in compiled):
        raise RuntimeError('Floor review validation failed; inspect validation.json')
    OpenUSDBackend(compiler).compile(city,out/'scene',_scene_override=scene)
    save_json(semantic.to_dict(),out/'scene/validation_report.json')
    export_portable_viewer(out/'scene',out/'viewer')
    views=[]
    for r in rows:
        for preset in ('top','perspective','core'):
            views.append({'view_id':r['prototype_id']+'_'+preset,'kind':'floor_plan','mode':'floor_plan' if preset=='top' else 'floor',
                'target_entity_ids':[r['building_id'],r['floor_id']],'floor_camera_preset':preset,
                'render_profile':'review','appearance':'semantic','auto_cutaway':True})
    save_json({'selected_views':views},out/'observation.json')
    manifest={'schema_version':1,'status':'pending_human_review','floors':rows,'production_enabled':False,
        'llm_used':False,'asset_generation_used':False,'render_status':'not_requested',
        'batch_fingerprint':fingerprint([r['content_fingerprint'] for r in rows])}
    if args.render:
        from scripts.check_portable_viewer import check
        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str((out/'viewer').resolve())))
        Thread(target=server.serve_forever,daemon=True).start();(out/'screenshots').mkdir()
        try:
            result=asyncio.run(check(f'http://127.0.0.1:{server.server_port}/',out/'screenshots',180,views,canvas_only=True))
            manifest['render_status']='passed' if result.get('exercise_ok') else 'failed'
        finally:server.shutdown();server.server_close()
    save_json(manifest,out/'review_manifest.json');(out/'diagrams').mkdir()
    for key in keys:(out/'diagrams'/f'{key}.svg').write_text(diagram(lib.floors[key]))
    gallery(out,manifest,lib)
    if args.render and manifest['render_status']!='passed':raise RuntimeError('Headless screenshots failed')
    with ZipFile(out/'review_images.zip','w',ZIP_DEFLATED) as archive:
        for p in [out/'review_index.html',out/'review_manifest.json',out/'validation.json',*sorted((out/'diagrams').glob('*.svg')),
                  *sorted((out/'screenshots').glob('*.png')),*sorted((out/'library_snapshot').glob('*.json'))]:
            if p.exists() and p.name!='navigation.png':archive.write(p,str(p.relative_to(out)))
        archive.writestr('HOW_TO_REVIEW.txt','解压后打开 review_index.html；图片是实际 Viewer 截图，SVG 是同一布局的标注平面图。\n交互查看需另下载 viewer 文件夹，运行 python serve.py。\n')
    print('Review gallery:',out/'review_index.html',flush=True)
    print('Portable Viewer:',out/'viewer',flush=True)


if __name__=='__main__':main()
