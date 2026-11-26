"""Three-building floor/room adapter regression fixture, NOT city generation.

Explicit boundary-map proposals exercise the adapter; they are not an Agent.
No downloads, model calls, original library writes, or production approvals.
"""
import argparse
import asyncio
from copy import deepcopy
from functools import partial
import html
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from zipfile import ZipFile, ZIP_DEFLATED

from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.planning.floor_prototypes import FloorPrototypeLibrary
from cityg.planning.floor_prototype_lab import make_floor_lab, compiled_floor_checks
from cityg.planning.prototype_adaptation import adapt_floor_reference, room_candidates, populate_adapted_room
from cityg.planning.prototype_lab import detached_registry, compiled_containment_checks, compiled_open_plan_checks
from cityg.planning.prototype_decor_assets import add_review_decorations
from cityg.serialization import save_json
from cityg.services import OpenUSDBackend
from cityg.validation import CityValidator
from cityg.viewer import export_portable_viewer
from scripts.build_layout_prototype_review import inventory_checks
from scripts.run_interior_asset_smoke import check_placements


PROPOSALS={
    'residential_spine_v1':{
        'x_knots':[[0,0],[5,4.2],[8,7.6],[13,11.8],[16,15.2],[21,19.4],[24,22.8]],
        'y_knots':[[0,0],[3.5,4.1],[4.8,5.4],[9,9.6],[17,17.6],[21.2,21.8],[22.5,23.1],[26,27.2]],
        'door_fractions':[{'a':f'{side}{n}_bed_a','b':f'{side}{n}_hall','fraction':.3 if side=='s' else .7}
                          for side in ('s','n') for n in (1,2,3)]},
    'office_mixed_v1':{
        'x_knots':[[0,0],[12,11.8],[20,19.8],[28,26.6],[36,34.6]],
        'y_knots':[[0,0],[8,6.4],[16,14.4],[24,22.4]]},
    'community_library_v1':{
        'x_knots':[[0,0],[10,11.2],[18,18],[40,40]],
        'y_knots':[[0,0],[8,8],[24,24.4],[26,25.2],[32,32]]},
}
TARGETS={
    'residential_spine_v1':[(0,'s1_bed_a'),(0,'n1_bed_a'),(0,'s2_bed_a'),(0,'n2_bed_a')],
    'office_mixed_v1':[(0,'office'),(0,'pantry'),(1,'office'),(1,'pantry')],
    'community_library_v1':[(0,'discussion'),(0,'staff')],
}


def gallery(out,manifest):
    cards=[]
    for view in manifest['views']:
        name=view['view_id'];path=f'screenshots/{name}.png'
        if (out/path).is_file():cards.append(f'<figure><a href="{path}"><img loading="lazy" src="{path}"></a><figcaption>{html.escape(name)}</figcaption></figure>')
    (out/'review_index.html').write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>CityG 跨层级适配联调</title><style>body{font:16px/1.6 system-ui;background:#eef1f4;color:#24313b;margin:24px}main{max-width:1400px;margin:auto}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0;background:white;padding:12px}img{width:100%}pre{white-space:pre-wrap}</style><main>
<h1>楼层—房间原型适配联调</h1><p>三栋建筑、每栋两层，最多十个精细房间；其它家具为轻量示意。
这是手工边界提案驱动的受控样例，不是城市原型自动选型或 LLM/VLM 全流程。
家具不缩放；门向通过旋转设计约束后重新求解。楼梯、电梯保持物理尺寸和上下层对齐。
未获批准的组合不写回正式库；失败候选不删减必需家具来强行通过。</p>
<p>下载同目录 viewer 文件夹，在本机运行 python serve.py 可交互查看。图片可以直接打开。</p><pre>'''+html.escape(json.dumps(manifest['summary'],ensure_ascii=False,indent=2))+ '</pre><div class="grid">'+''.join(cards)+'</div></main>')
    with ZipFile(out/'review_images.zip','w',ZIP_DEFLATED) as z:
        for p in [out/'review_index.html',out/'review_manifest.json',out/'validation.json',out/'placement_trace.json',
                  *sorted((out/'screenshots').glob('*.png')),*sorted((out/'library_snapshot').glob('*.json'))]:
            if p.is_file() and p.name!='navigation.png':z.write(p,str(p.relative_to(out)))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,type=Path);p.add_argument('--render',action='store_true')
    args=p.parse_args();out=args.output
    if out.exists() and any(out.iterdir()):p.error('Use a fresh output directory')
    out.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[1];lib=FloorPrototypeLibrary(root/'configs/layout_prototypes/v1')
    adapted=deepcopy(lib);floor_rows=[]
    for key,proposal in PROPOSALS.items():
        record,checks=adapt_floor_reference(lib,key,**proposal)
        adapted.floors[key]=record;floor_rows.append({'prototype_id':key,'adaptation':record['adaptation'],**checks})
    save_json({'schema_version':1,'prototypes':[adapted.floors[k] for k in PROPOSALS]},out/'library_snapshot/adapted_floors.json')
    save_json({'schema_version':1,'prototypes':list(lib.room_library.rooms.values())},out/'library_snapshot/rooms.json')
    save_json({'schema_version':1,'prototypes':list(lib.room_library.combinations.values())},out/'library_snapshot/combinations.json')
    city,fixtures=make_floor_lab(adapted,list(PROPOSALS))
    city.id='city_prototype_integration_lab';city.name='CityG floor-room integration review'
    city.metadata['prototype_integration']={'stage':'controlled_floor_room_adapter_fixture','production_enabled':False}
    registry=detached_registry(AssetRegistry(root/'assets/asset_registry.json'))
    for file in [lib.root/'decoration_assets.json',*sorted(lib.root.glob('reference_assets_*.json'))]:
        add_review_decorations(registry,file,project_root=root)
        save_json(json.loads(file.read_text()),out/'library_snapshot'/file.name)
    compiler=GeometryCompiler(asset_registry=registry,
        material_library=MaterialLibrary(root/'assets/incoming/interior_materials/material_library.json'))
    rows=[];attempts=[];targets=[]
    for b in city.iter_buildings():
        key=b.metadata['floor_layout_prototype_id']
        for level,space in TARGETS[key]:
            f=next(f for f in b.floors if f.level==level)
            r=next(r for r in f.rooms if r.metadata['floor_prototype_space']==space)
            cs=room_candidates(lib.room_library,b,f,r)
            if not cs:attempts.append({'room_id':r.id,'status':'no_compatible_reference'})
            for c in cs:
                old_metadata=deepcopy(r.metadata);old_objects=deepcopy(f.objects);old_ids=list(r.object_ids)
                try:
                    print('room_start',space,level,c,flush=True)
                    row=populate_adapted_room(city,b,f,r,lib.room_library,registry,c,review_only=True)
                    city.world_program=build_world_program(city,producer='prototype_integration_review',seed=17)
                    scene=compiler.compile(city)
                    target=(c['prototype_id'],b,f,r)
                    checks=[*inventory_checks(scene,[row]),*compiled_containment_checks(scene,[target]),
                            *compiled_open_plan_checks(scene,[target]),*check_placements(scene,[r.id])]
                    if not all(v['ok'] for v in checks):raise ValueError('Compiled inventory/placement checks failed: '+str([v for v in checks if not v['ok']]))
                    row['compiled_verified']=True;rows.append(row);targets.append(target)
                    attempts.append({'room_id':r.id,**c,'status':'accepted','major_count':row['major_count']})
                    print('room_accepted',space,row['major_count'],flush=True);break
                except ValueError as exc:
                    r.metadata=old_metadata;f.objects[:]=old_objects;r.object_ids[:]=old_ids
                    attempts.append({'room_id':r.id,**c,'status':'rejected','reason':str(exc)})
                    print('room_rejected',space,str(exc)[:220],flush=True)
                finally:save_json(attempts,out/'placement_trace.json')
    city.world_program=build_world_program(city,producer='prototype_integration_review',seed=17)
    scene=compiler.compile(city);semantic=CityValidator().validate(city);geometry=GeometryValidator().validate(city,scene)
    checks=[*compiled_floor_checks(city,scene),*compiled_containment_checks(scene,targets),
            *compiled_open_plan_checks(scene,targets),*inventory_checks(scene,rows),
            *check_placements(scene,[r['room_id'] for r in rows])]
    save_json({'city':semantic.to_dict(),'geometry':geometry.to_dict(),'checks':checks,'floor_adaptations':floor_rows},out/'validation.json')
    if not semantic.ok or not geometry.ok or not all(c['ok'] for c in checks):raise RuntimeError('Integrated compile failed validation')
    OpenUSDBackend(compiler).compile(city,out/'scene',_scene_override=scene)
    save_json(semantic.to_dict(),out/'scene/validation_report.json')
    export_portable_viewer(out/'scene',out/'viewer')
    views=[]
    for b in city.iter_buildings():
        views.append({'view_id':b.id+'_floor','kind':'floor_plan','mode':'floor_plan',
            'target_entity_ids':[b.id,b.floors[0].id],'floor_camera_preset':'top',
            'render_profile':'presentation','appearance':'presentation','auto_cutaway':True})
    for row in rows:
        for preset in ('top','cutaway'):
            views.append({'view_id':row['room_id']+'_'+preset,'kind':'room_interior','mode':'room',
                'target_entity_ids':[row['room_id']],'room_camera_preset':preset,
                'render_profile':'presentation','appearance':'presentation','auto_cutaway':True})
        row['surface_report']=scene.metadata.get('room_surface_items',{}).get(row['room_id'],{})
        row['decoration_report']=scene.metadata.get('room_decorations',{}).get(row['room_id'],{})
    manifest={'schema_version':1,'production_enabled':False,'llm_used':False,'vlm_used':False,
        'stage':'controlled_floor_room_adapter_fixture','status':'pending_human_review','views':views,'rooms':rows,
        'summary':{'building_count':3,'floor_count':6,'requested_detailed_rooms':10,'accepted_rooms':len(rows),
            'major_objects':sum(r['major_count'] for r in rows),'rejected_attempts':sum(a['status']=='rejected' for a in attempts)},
        'render_status':'not_requested'}
    save_json({'selected_views':views},out/'observation.json');save_json(manifest,out/'review_manifest.json')
    if args.render:
        from scripts.check_portable_viewer import check
        class Quiet(SimpleHTTPRequestHandler):
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str((out/'viewer').resolve())))
        Thread(target=server.serve_forever,daemon=True).start();(out/'screenshots').mkdir()
        try:
            result=asyncio.run(check(f'http://127.0.0.1:{server.server_port}/',out/'screenshots',180,
                views,require_assets=True,canvas_only=True))
            manifest['render_status']='passed' if result.get('exercise_ok') else 'failed'
        finally:server.shutdown();server.server_close()
        save_json(manifest,out/'review_manifest.json')
    gallery(out,manifest)
    if args.render and manifest['render_status']!='passed':raise RuntimeError('Headless render failed')
    print(manifest['summary'],flush=True);print('Review:',out/'review_index.html',flush=True)


if __name__=='__main__':main()
