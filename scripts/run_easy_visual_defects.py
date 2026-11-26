"""Small blinded VLM diagnostic, deliberately NOT a production success-rate benchmark.

prepare/render work offline; review requires a vision endpoint. Private truth is
never included in a review call. Intentionally invalid geometry is exported as
an isolated rendering fixture, without relaxing any production validator.
"""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import html
import json
from pathlib import Path
import random

from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler
from cityg.observation import AdaptiveObservationPlanner
from cityg.planning.prototype_decor_assets import add_review_decorations
from cityg.planning.prototype_lab import detached_registry, make_lab, populate_reference
from cityg.planning.prototypes import LayoutPrototypeLibrary
from cityg.planning.room_envelope import metric_envelope
from cityg.planning.room_metric_frame import restore_metric_object
from cityg.schemas import Point2D
from cityg.serialization import load_city, save_json, to_primitive
from cityg.validation.visual_grounding import ground_review, room_facts

PROTOTYPE = 'office_focus_compact_v1'
PROMPT = (
    'Inspect these two views of the SAME furnished office. Report only clearly visible '
    'physical layout problems, their affected furniture groups, and concrete feasible '
    'corrections. A scene may be fine: return no issues when there is no convincing '
    'problem. Do not demand more decoration or infer invisible requirements. '
    'The roof is intentionally removed for inspection; this is not a defect. '
    'Use the supplied identity inventory only for binding, not as evidence of a problem.'
)


def resources():
    root = Path('configs/layout_prototypes/v1')
    library = LayoutPrototypeLibrary(root)
    registry = detached_registry(AssetRegistry('assets/asset_registry.json'))
    for path in sorted(root.glob('reference_assets_*.json')):
        add_review_decorations(registry, path, project_root=Path.cwd(),
            asset_ids=set(library.materialize(PROTOTYPE).asset_bindings.values()))
    return library, registry


def move_metric(obj, x, y):
    """Update both representations, preserving the compiler's metric certificate."""
    pose = obj.metadata['metric_room_placement']
    dx, dy = x-pose['center'][0], y-pose['center'][1]
    sx, sy = pose['canonical_scale']
    obj.position = Point2D(obj.position.x+dx/sx, obj.position.y+dy/sy)
    pose['center'] = [x, y]
    pose['canonical_binding'][:2] = [obj.position.x, obj.position.y]


def turn_metric(obj, degrees):
    pose=obj.metadata['metric_room_placement']
    obj.rotation_deg=(obj.rotation_deg+degrees)%360
    sx,sy=pose['canonical_scale']; width,depth,_=pose['dimensions_m']
    swapped=round(obj.rotation_deg/90)%2
    obj.width_m=width/(sy if swapped else sx)
    obj.depth_m=depth/(sx if swapped else sy)
    pose['canonical_binding']=[obj.position.x,obj.position.y,obj.width_m,obj.depth_m,
                               obj.height_m,obj.rotation_deg,obj.asset_id]


def public_context(floor, room):
    # Explicit whitelist: NO poses, validators, intended wall policies, condition
    # labels, risk scores, ground truth, or precomputed observations in VLM input.
    groups = {}
    for obj in floor.objects:
        if obj.room_id == room.id:
            key = obj.metadata['group_key']
            groups.setdefault(key, []).append({'object_id': obj.id, 'category': obj.category})
    return {'allowed_entity_ids': [room.id], 'room_function': room.function,
            'cutaway_entity_ids': [room.id],
            'room_group_bindings': {room.id: [
                {'group_id': key, 'objects': objects} for key, objects in sorted(groups.items())]},
            'views': [{'view_id': 'view_01', 'entity_id': room.id, 'kind': 'top_down'},
                      {'view_id': 'view_02', 'entity_id': room.id, 'kind': 'oblique_cutaway'}]}


def export_fixture(city, compiler, destination):
    """Reference shared assets; avoid copying hundreds of MB per small case."""
    scene = compiler.compile(city)
    for index, material in enumerate(scene.materials):
        paths = {}
        for channel in ('base_color','normal','roughness','ambient_occlusion'):
            key=channel+'_path'; raw=getattr(material,key,None)
            if raw:
                source=compiler.material_library.resolve_path(raw)
                if source.is_file(): paths[key]=str(source.resolve())
        if paths: scene.materials[index]=replace(material,**paths)
    save_json(city, destination/'city.json')
    save_json(scene, destination/'geometry_manifest.json')
    save_json(scene.navigation, destination/'navigation.json')
    save_json({'state_machines': scene.state_machines}, destination/'interactions.json')
    save_json({'layers': scene.layers, 'activation_tiers': scene.activation_tiers,
               'building_prototypes': scene.building_prototypes}, destination/'activation_manifest.json')
    used = {p.metadata.get('asset_id') for p in scene.primitives}
    subset = AssetRegistry()
    for record in compiler.asset_registry.list_all():
        if record.asset_id in used:
            subset.register(record)
    subset.save(destination/'assets/asset_registry.json')
    # These tiny packages can also serve as inputs to the real review CLI.
    # Preserve recompile dependencies, not just already compiled RGB materials.
    if compiler.material_library is not None:
        materials=MaterialLibrary()
        for material in compiler.material_library.list_all():
            paths={key:str(compiler.material_library.resolve_path(getattr(material,key)).resolve())
                   for key in ('base_color_path','normal_path','roughness_path','ambient_occlusion_path')
                   if getattr(material,key,None)}
            materials.register(replace(material,**paths))
        materials.save(destination/'assets/material_library.json')
    return scene


def prepare(output):
    output.mkdir(parents=True, exist_ok=False)
    library, registry = resources()
    clean, targets = make_lab(library, [PROTOTYPE])
    populate_reference(clean, targets[0], library, registry)
    _, b, f, r = targets[0]
    clean.world_program = build_world_program(clean, producer='visual_fixture', seed=17)
    facts = room_facts(clean, r.id)
    if not facts['supported'] or any(c['ok'] is False for c in facts['checks']):
        raise ValueError('Clean fixture is not clean under supported independent checks')
    compiler = GeometryCompiler(asset_registry=registry, material_library=MaterialLibrary(
        'assets/incoming/interior_materials/material_library.json'))
    conditions = ['clean', 'outside', 'blocked_entry', 'overlap']
    random.Random(7321).shuffle(conditions)
    records = []
    for index, condition in enumerate(conditions, 1):
        case_id = f'case_{index:02d}'
        city = deepcopy(clean)
        b = next(city.iter_buildings()); f = b.floors[0]
        r = next(room for room in f.rooms if room.id == targets[0][3].id)
        env = metric_envelope(b, f, r); bounds = env['bounds']
        objects = [o for o in f.objects if o.room_id == r.id]
        shelf = next(o for o in objects if o.category == 'bookcase')
        desk = next(o for o in objects if o.category == 'desk')
        if condition == 'outside':
            move_metric(shelf, bounds.max_x+.65, bounds.center.y)
        elif condition == 'blocked_entry':
            turn_metric(shelf,90)
            move_metric(shelf, bounds.center.x, bounds.min_y+.3)
        elif condition == 'overlap':
            move_metric(shelf, *desk.metadata['metric_room_placement']['center'])
        city.world_program = build_world_program(city, producer='visual_fixture', seed=17)
        actual = [restore_metric_object(o,b,f,r,env) for o in objects]
        metric_shelf = next(o for o in actual if o.id == shelf.id)
        metric_desk = next(o for o in actual if o.id == desk.id)
        a, d = metric_shelf.bounds, metric_desk.bounds
        overlap = max(0, min(a.max_x,d.max_x)-max(a.min_x,d.min_x))*max(
            0, min(a.max_y,d.max_y)-max(a.min_y,d.min_y))
        private = {'condition': condition, 'target_group_ids': [] if condition=='clean' else ['storage'],
                   'room_id': r.id, 'independent_facts': room_facts(city,r.id),
                   'shelf_desk_footprint_intersection_m2': overlap,
                   'scope': 'controlled_single_room_easy_diagnostic_not_natural_defect_rate'}
        if condition == 'outside':
            assert any(c['kind']=='containment' and c['ok'] is False
                       for c in private['independent_facts']['checks'])
        if condition == 'blocked_entry':
            assert any(c['kind']=='access' and c['ok'] is False
                       for c in private['independent_facts']['checks'])
            assert all(c['ok'] for c in private['independent_facts']['checks']
                       if c['kind']=='containment')
        if condition == 'overlap':
            assert overlap > .15
        root = output/case_id
        scene = export_fixture(city, compiler, root/'scene')
        plan = AdaptiveObservationPlanner(max_views=12).plan(city,
            geometry_manifest=to_primitive(scene)).to_dict()
        view = next(v for v in plan['candidates'] if v['kind']=='room_interior'
                    and r.id in v['target_entity_ids'] and '_top_' in v['view_id'])
        # Freeze identical cameras across ALL conditions; include an outer margin
        # so outside furniture remains in view. The second view exposes height.
        cx, cy = bounds.center.x+.4, bounds.center.y
        top = {**view, 'view_id':'view_01', 'camera_position':[cx,cy,13.5],
               'look_at':[cx,cy,.05], 'semantic_context':{}, 'fov_deg':48}
        oblique = {**top, 'view_id':'view_02', 'camera_position':[cx+5,cy-7,10],
                   'up':[0,0,1], 'auto_cutaway':True}
        save_json({'selected_views':[top,oblique]}, root/'render_plan.json')
        save_json(public_context(f,r), root/'public_context.json')
        save_json(private, root/'private_truth.json')
        records.append({'case_id':case_id})
        print(case_id, condition, 'prepared', flush=True)
    save_json({'protocol':'blinded_easy_visual_defects_v1','prompt':PROMPT,'cases':records,
               'notes':'No checker results or private_truth are passed to the VLM.'},output/'protocol.json')
    gallery(output)


def gallery(output):
    cards=[]
    for row in json.loads((output/'protocol.json').read_text())['cases']:
        key=row['case_id']; truth=json.loads((output/key/'private_truth.json').read_text())
        review_path=output/key/'review.json'
        summary=''
        if review_path.exists():
            review=json.loads(review_path.read_text())
            summary='<p>生产提示 VLM：'+html.escape(review['summary'])+'</p>'
        after=output/key/'repair/images/view_01.png'
        repaired=(f'<h3>局部修复后</h3><img src="{key}/repair/images/view_01.png">'
                  f'<img src="{key}/repair/images/view_02.png">') if after.exists() else ''
        cards.append(f'<section><h2>{key}</h2><div>'+''.join(
            f'<img src="{key}/images/view_{i:02d}.png">' for i in (1,2))+
            f'</div><details><summary>人工审核用真值（不提供给 VLM）</summary>{html.escape(truth["condition"])}</details>'
            +summary+repaired+'</section>')
    (output/'gallery.html').write_text('<!doctype html><meta charset="utf-8"><title>VLM controlled diagnostic</title>'
        '<style>body{font:16px sans-serif;margin:24px;background:#eee}section{background:white;padding:16px;margin:16px}'
        'img{width:46%;max-width:700px}details{margin:12px}</style><h1>盲测场景：同一房间，两个视点</h1>'+''.join(cards))


def render(output, repaired=False):
    from cityg.adaptive_review import _render_plan, _start_server
    for row in json.loads((output/'protocol.json').read_text())['cases']:
        root=output/row['case_id']
        if repaired:
            root=root/'repair'
            if not (root/'scene/city.json').exists():continue
        if (root/'images/view_02.png').is_file():
            continue
        plan=json.loads((root/'render_plan.json').read_text())
        server,thread,url=_start_server(root/'scene',0)
        try:
            asyncio.run(_render_plan(url,plan,root/'images',asset_timeout_ms=180000))
        finally:
            server.shutdown();server.server_close();thread.join(timeout=10)
    gallery(output)


def review_one(output, row, base_url, model, observation_first=False):
    from cityg.services.interfaces import ModelEndpoint
    from cityg.services.openai_compatible import OpenAICompatibleService
    from cityg.visual_review import VisualReviewAgent
    from run_edit_method_pilot import RecordedService
    root=output/row['case_id']
    evidence=root/'observation_first' if observation_first else root
    if (evidence/'review.json').exists():
        raise ValueError(f'Refusing to overwrite existing model evidence: {root}')
    context=json.loads((root/'public_context.json').read_text())
    images=[root/f'images/view_{i:02d}.png' for i in (1,2)]
    if not all(p.is_file() for p in images): raise ValueError('Render both images first')
    service=RecordedService(OpenAICompatibleService(ModelEndpoint(base_url=base_url,
        model=model,timeout_s=240,max_tokens=4096,seed=7321,enable_thinking=False)),evidence/'model_calls.json')
    # Exploratory comparison, retained separately from the production-prompt arm.
    # Identical images, identity inventory, seed and decoding settings. The proxy
    # removes production-specific design-contract prose absent from this blind test.
    active=service
    if observation_first:
        from cityg.services.interfaces import ChatMessage
        class ObservationFirstService:
            def complete_with_metadata(self,messages,response_schema=None):
                schema=deepcopy(response_schema)
                schema['properties']['observations']={'type':'array','items':{
                    'type':'object','additionalProperties':False,
                    'properties':{'object_id':{'type':'string'},'visible_relationships':{'type':'string'}},
                    'required':['object_id','visible_relationships']}}
                schema['required'].append('observations')
                prompt=(
                    'You are checking a 3D office using a top view and an oblique view of the SAME room. '
                    'First describe where each visible furniture item is relative to the room boundary, '
                    'the door opening and other furniture in observations. Then list physically implausible '
                    'placements, if any, in issues and give concrete corrections. A normal scene is possible. '
                    'Do not invent required wall placements: desks need not touch a wall. Do not invent '
                    'objects behind an occluding wall. Roof removal is intentional. No text labels were '
                    'drawn on these images: identity comes from the following inventory (view_context), '
                    'not visible_label. Classify a boundary violation as room_object_outside, a blocked '
                    'door as room_access_blocked, and furniture interpenetration as unspecified. '
                    'Name affected group IDs even for non-alignment issues. Provide a JSON response.\n'
                    +json.dumps(context,ensure_ascii=False))
                return service.complete_with_metadata([ChatMessage(role='user',content=prompt,
                    image_paths=messages[0].image_paths)],schema)
        active=ObservationFirstService()
    result=VisualReviewAgent(active,max_images=2,max_attempts=2).review(PROMPT,images,context=context)
    report=result.to_dict()
    save_json(report,evidence/'review.json')
    # Only AFTER the blind call, compare its claims with independent geometry.
    city=load_city(root/'scene/city.json')
    grounded=ground_review(city,{'aggregated_issues':report['issues']})
    save_json(grounded,evidence/'grounded_review.json')
    print(row['case_id'],'available=',result.available,'issues=',len(result.issues),flush=True)
    return {'case_id':row['case_id'],'available':result.available,'issues':report['issues'],
            'model_calls':len(service.calls),'elapsed_s':sum(c['elapsed_s'] for c in service.calls),
            'independent_verification':grounded['aggregated_issues']}


def repair_one(output,row,base_url,model):
    """Run real Room Agent transactions using ONLY detected, verified issues."""
    from cityg.assets import AssetResolver
    from cityg.planning.prototypes import reference_registry
    from cityg.refinement.room import RoomProgramAgent
    from cityg.refinement.room_preflight import prepare_preflight
    from cityg.refinement.room_commit import commit_room_program
    from cityg.validation.visual_grounding import resolution_proofs
    from cityg.transactions import fingerprint
    from cityg.services.interfaces import ModelEndpoint
    from cityg.services.openai_compatible import OpenAICompatibleService
    from run_edit_method_pilot import RecordedService
    root=output/row['case_id'];destination=root/'repair'
    if destination.exists():raise ValueError('Refusing to overwrite repair evidence')
    review=json.loads((root/'grounded_review.json').read_text())
    candidates=[i for i in review['aggregated_issues'] if i.get('automatic_repair_allowed')
                and i.get('target_group_ids')]
    if not candidates:return {'case_id':row['case_id'],'status':'not_eligible'}
    issue=candidates[0];city=load_city(root/'scene/city.json');original=fingerprint(city)
    b,f,r=next((b,f,r) for b in city.iter_buildings() for f in b.floors for r in f.rooms
               if r.id==issue['entity_id'])
    library,registry=resources();pinned=reference_registry(registry,library.materialize(PROTOTYPE))
    resolver=AssetResolver(pinned,(),max_provider_calls=0)
    compiler=GeometryCompiler(asset_registry=registry,material_library=MaterialLibrary(
        'assets/incoming/interior_materials/material_library.json'))
    service=RecordedService(OpenAICompatibleService(ModelEndpoint(base_url=base_url,model=model,
        timeout_s=240,max_tokens=4096,seed=7321,enable_thinking=False)),destination/'model_calls.json')
    report={'case_id':row['case_id'],'input_issue':issue,'ok':False}
    try:
        support,preflight,gate=prepare_preflight(city,r.id,compiler,pinned,seed=17)
        proposal=RoomProgramAgent(service,asset_resolver=resolver,max_attempts=3,
            review_sufficiency=False).propose(city,b,f,r,use_cache=False,
                visual_feedback={**issue,'compiled_support_context':support},compiled_preflight=preflight)
        save_json(proposal.program,destination/'proposed_program.json')
        committed,stats=commit_room_program(city,r.id,proposal.program,asset_resolver=resolver,
            seed=17,compiled_gate=gate,source='visual_repair')
        proofs=resolution_proofs(city,committed.city,{'aggregated_issues':[issue]})
        after=room_facts(committed.city,r.id,reference=room_facts(city,r.id))
        untouched=lambda c: [o for bb in c.iter_buildings() for ff in bb.floors for o in ff.objects
            if o.room_id==r.id and o.metadata.get('group_key') not in issue['target_group_ids']]
        report.update(transaction=committed.report,proofs=proofs,after_facts=after,
            unedited_groups_unchanged=untouched(city)==untouched(committed.city),
            source_unchanged=fingerprint(city)==original)
        report['ok']=(committed.report['status']=='accepted' and bool(proofs)
            and all(p['ok'] for p in proofs.values()) and report['source_unchanged']
            and report['unedited_groups_unchanged'] and after['supported']
            and not any(c['ok'] is False for c in after['checks']))
        export_fixture(committed.city,compiler,destination/'scene')
        save_json(json.loads((root/'render_plan.json').read_text()),destination/'render_plan.json')
    except Exception as error:
        report['error']=f'{type(error).__name__}: {error}'
    report['model_calls']=len(service.calls)
    save_json(report,destination/'result.json')
    print(row['case_id'],'repair=',report['ok'],report.get('error',''),flush=True)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=['prepare','render','review','repair'])
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--base-url',default='http://127.0.0.1:8000/v1')
    p.add_argument('--model',default='cityg-llm')
    p.add_argument('--jobs',type=int,choices=[1,2],default=2)
    p.add_argument('--observation-first',action='store_true')
    p.add_argument('--repaired',action='store_true',help='Render accepted repairs only')
    args=p.parse_args()
    if args.stage=='prepare':prepare(args.output)
    elif args.stage=='render':render(args.output,args.repaired)
    else:
        rows=json.loads((args.output/'protocol.json').read_text())['cases']
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            if args.stage=='repair':
                futures=[pool.submit(repair_one,args.output,row,args.base_url,args.model) for row in rows]
            else:
                futures=[pool.submit(review_one,args.output,row,args.base_url,args.model,args.observation_first) for row in rows]
            results=[f.result() for f in futures]
        name=('repair_results.json' if args.stage=='repair' else
              'observation_first_results.json' if args.observation_first else 'results.json')
        save_json({'endpoint':args.base_url,'model':args.model,'cases':results,
            'caution':'Controlled defects, not natural end-to-end success rate. Semantic scoring requires inspecting descriptions.'},
            args.output/name)


if __name__=='__main__':main()
