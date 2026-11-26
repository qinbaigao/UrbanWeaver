"""Production edits on a real generated scene; preserve all failures and sources.

This is development regression, not a benchmark or automatic-repair evaluation.
Model outputs never determine the expected result. Successful edits feed the next
step; rejected steps do not replace the current scene. No browser is opened.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

from cityg.editing import resolve_scene, rollback_scene, run_batch_edit, run_edit
from cityg.naming import identity_for
from cityg.run_provenance import record_stage_start
from cityg.serialization import load_city, save_json
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from cityg.transactions import descendants, fingerprint, snapshots
from cityg.validation import CityValidator
from run_edit_method_pilot import RecordedService


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def visual_signature(manifest):
    """Compare rendered geometry/bindings, independent of exported file paths."""
    fields=('id','owner_id','primitive_type','center','size','rotation_z_deg',
            'semantic_class','material_id','layer_id','collision_enabled','body_type')
    return {p['id']:{**{k:p.get(k) for k in fields},
                     'asset_id':p.get('metadata',{}).get('asset_id')}
            for p in manifest['primitives']}


def run(scene, output, kinds=None, *, base_url='http://127.0.0.1:8000/v1', seed=521):
    output.mkdir(parents=True, exist_ok=False)
    record_stage_start(output)
    source = resolve_scene(scene)
    initial = load_city(source.canonical_path)
    buildings = list(initial.iter_buildings())
    # Structural tests explicitly replace an unfurnished subtree, not an
    # approved showcase or the carefully furnished rooms of the test city.
    building = next(b for b in buildings if len(b.floors) >= 2
                    and not any(f.objects for f in b.floors))
    a, b = building.floors[:2]
    detailed = next(r for f in initial.iter_floors() for r in f.rooms if r.object_ids)
    uid = identity_for(initial, building.id)['uid']
    common = '保留建筑外轮廓、入口和核心筒，只修改明确指定的实体，其它建筑与楼层不变。'
    new_count = len(building.floors) + 1
    cases = [
        ('rename_uid', f'仅将 uid={uid} 的建筑显示名称改为“联调服务楼”。'+common,
         'name', '联调服务楼'),
        ('floor_layout', f'将 id={a.id} 重新分区为严格4个非走廊房间。'+common,
         'floor_counts', {a.id: 4}),
        ('two_floors', f'将 id={a.id} 改为5个非走廊房间；将 id={b.id} 改为4个非走廊房间。'+common,
         'floor_counts', {a.id: 5, b.id: 4}),
        ('building_stack', f'将 id={building.id} 整栋楼重建为严格{new_count}层，每层4个非走廊房间。'
         '允许重建该建筑的楼层、房间和垂直交通，保留建筑外轮廓、位置、入口与显示名称，其它建筑不变。',
         'building_floors', new_count),
        ('room_furnishing', f'仅重新布置 id={detailed.id} 的家具，保持房间功能和门窗位置，'
         '保留必要陈设、家具尺度与已有高质量资产，改善贴墙摆放与进门通行，其它房间不变。',
         'room', detailed.id),
        ('ambiguous', '把这栋楼变得高一些。', 'refuse', None),
        ('ambiguous_count', f'把 {a.id} 和 {b.id} 两个楼层合计改为8间房间，保留两层。', 'refuse', None),
        ('impossible_floor', f'将 id={a.id} 改为10000个独立办公室，不允许减少数量。', 'refuse', None),
    ]
    rows = []
    current = scene
    endpoint = ModelEndpoint(base_url=base_url, model='cityg-llm',
                             max_tokens=6144, timeout_s=180, seed=seed)

    def publish():
        save_json({'evidence_type':'live_generated_scene_multiturn_development',
                   'initial_scene':str(scene), 'latest_scene':str(current),
                   'paper_benchmark':False, 'mesh_generation_tested':False,
                   'rows':rows, 'completed':len(rows), 'passed':sum(r['ok'] for r in rows)},
                  output/'summary.json')

    for kind, instruction, check_kind, expected in cases:
        if kinds and kind not in kinds:
            continue
        before_ref = resolve_scene(current)
        before_hash = digest(before_ref.canonical_path)
        before = load_city(before_ref.canonical_path)
        destination = output/kind
        service = RecordedService(OpenAICompatibleService(endpoint), output/'traces'/f'{kind}.json')
        row = {'kind':kind, 'instruction':instruction, 'source':str(current),
               'expected':expected, 'status':'error', 'ok':False}
        start = time.monotonic()
        print('START', kind, flush=True)
        try:
            result = run_edit(current, instruction, destination, service,
                              model_id=endpoint.model, backend='openusd', no_viewer=True,
                              max_attempts=3)
            row['status'] = result.status
            row['error'] = result.error
            if result.status == 'applied':
                after = load_city(result.output_city)
                changed_building = next(x for x in after.iter_buildings() if x.id == building.id)
                left, right = snapshots(before), snapshots(after)
                changed = {table[k][0] for k in left.keys() | right.keys()
                           if k.startswith('entity:') and left.get(k) != right.get(k)
                           for table in (left, right) if k in table}
                plan = json.loads((destination/'edit_plan_effective.json').read_text())
                scope = [key for target in plan['targets'] for key in target['resolved_ids']]
                allowed = descendants(before, scope) | descendants(after, scope)
                row['outside_scope'] = sorted(changed-allowed)
                row['semantic_ok'] = CityValidator().validate(after).ok
                row['geometry_ok'] = json.loads((result.output_compiled/'geometry_validation_report.json').read_text())['ok']
                if check_kind == 'name':
                    goal = changed_building.name == expected
                elif check_kind == 'floor_counts':
                    counts = {f.id:sum(r.function != 'corridor' for r in f.rooms) for f in after.iter_floors()}
                    row['actual'] = {key:counts.get(key) for key in expected}
                    goal = row['actual'] == expected
                elif check_kind == 'building_floors':
                    row['actual'] = len(changed_building.floors)
                    goal = row['actual'] == expected and all(
                        sum(r.function != 'corridor' for r in f.rooms) == 4 for f in changed_building.floors)
                elif check_kind == 'room':
                    old_objects = [o for o in before.iter_objects() if o.room_id == expected]
                    objects = [o for o in after.iter_objects() if o.room_id == expected]
                    row['inventory_before_after'] = [len(old_objects), len(objects)]
                    old_manifest=json.loads((before_ref.compiled_path/'geometry_manifest.json').read_text())
                    new_manifest=json.loads((result.output_compiled/'geometry_manifest.json').read_text())
                    from cityg.geometry.incremental import scene_from_manifest
                    from cityg.validation.local_room import room_mesh_retention
                    row['major_mesh_retention']=room_mesh_retention(old_objects,objects,
                        scene_from_manifest(old_manifest),scene_from_manifest(new_manifest))
                    # This verifies the preservation gate, not visual preference fulfillment.
                    goal = bool(objects) and row['major_mesh_retention']['ok'] and (destination/'rendered_inventory_acceptance.json').is_file()
                else:
                    goal = False
                row['goal_met'] = goal
                row['ok'] = goal and not row['outside_scope'] and row['semantic_ok'] and row['geometry_ok']
                if row['ok']:
                    current = destination
            else:
                row['ok'] = check_kind == 'refuse' and result.status in {'needs_clarification','rejected','replan_required'}
                row['ok'] &= not (destination/'final').exists()
        except Exception as error:
            row['error'] = f'{type(error).__name__}: {error}'
            # A crash is never counted as a correct refusal.
        row['source_unchanged'] = digest(before_ref.canonical_path) == before_hash
        row['ok'] &= row['source_unchanged']
        row['actual_model_calls'] = len(service.calls)
        row['elapsed_s'] = round(time.monotonic()-start, 3)
        rows.append(row)
        publish()
        print('END', kind, row['status'], row['ok'], row.get('error'), flush=True)

    if not kinds or 'batch_pause' in kinds:
        base_ref = resolve_scene(current)
        before_hash = digest(base_ref.canonical_path)
        row = {'kind':'batch_pause','ok':False}
        service = RecordedService(OpenAICompatibleService(endpoint), output/'traces/batch_pause.json')
        try:
            result = run_batch_edit(current, [
                f'仅将 id={building.id} 的显示名称改为“批量暂停验收楼”。',
                '把这栋楼改漂亮一点。',
                f'仅将 id={building.id} 的显示名称改为“不应执行”。'], output/'batch_pause',
                service, model_id=endpoint.model, backend='openusd', no_viewer=True)
            row.update(status=result.status, steps=len(result.steps))
            row['ok'] = result.status == 'paused' and len(result.steps) == 2 and not (output/'batch_pause/steps/step_03').exists()
        except Exception as error:
            row['error'] = f'{type(error).__name__}: {error}'
        row['source_unchanged'] = digest(base_ref.canonical_path) == before_hash
        row['ok'] &= row['source_unchanged']
        rows.append(row);publish();print('END batch_pause',row,flush=True)

    if not kinds or 'rollback' in kinds:
        base_ref = resolve_scene(current)
        before_hash = digest(base_ref.canonical_path)
        row = {'kind':'rollback','ok':False}
        try:
            rollback_scene(current, output/'rollback', target_scene=scene, backend='openusd', no_viewer=True)
            restored = load_city(output/'rollback/final/city.json')
            row['canonical_equal'] = fingerprint(restored) == fingerprint(initial)
            row['geometry_ok'] = json.loads((output/'rollback/final/openusd/geometry_validation_report.json').read_text())['ok']
            restored_manifest=json.loads((output/'rollback/final/openusd/geometry_manifest.json').read_text())
            original_manifest=json.loads((source.compiled_path/'geometry_manifest.json').read_text())
            row['visual_geometry_equal'] = visual_signature(restored_manifest)==visual_signature(original_manifest)
            keys=('interiors_compiled','facade_asset_system_enabled')
            row['compiler_contract_equal']=all(restored_manifest['metadata'].get(k)==original_manifest['metadata'].get(k) for k in keys)
            row['ok'] = all(row[k] for k in ('canonical_equal','geometry_ok','visual_geometry_equal','compiler_contract_equal'))
        except Exception as error:
            row['error'] = f'{type(error).__name__}: {error}'
        row['source_unchanged'] = digest(base_ref.canonical_path) == before_hash
        row['ok'] &= row['source_unchanged']
        rows.append(row);publish();print('END rollback',row,flush=True)
    return 0 if all(r['ok'] for r in rows) else 3


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--kinds', nargs='+')
    args = parser.parse_args()
    raise SystemExit(run(args.scene.resolve(), args.output.resolve(), args.kinds))
