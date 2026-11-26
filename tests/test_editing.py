import json
import tempfile
import unittest
from pathlib import Path

from cityg.editing import EditAgent, resolve_scene, rollback_scene, run_batch_edit, run_edit
from cityg.planning import BaselineCityPlanner
from cityg.schemas import CitySpec
from cityg.serialization import load_city, save_json
from cityg.ccwp import build_world_program
from cityg.naming import identity_for


class _FakeService:
    def __init__(self, payload):
        self.payload = payload

    def complete(self, messages, response_schema=None):
        return json.dumps(self.payload, ensure_ascii=False)


def _city():
    city = BaselineCityPlanner().plan(
        CitySpec(
            name="editing_test",
            width_m=180,
            depth_m=160,
            building_count=2,
            min_floors=1,
            max_floors=2,
            rooms_per_floor=2,
            seed=12,
        )
    )
    city.world_program = build_world_program(city, producer="test", seed=12)
    return city


class EditingTests(unittest.TestCase):
    def test_failed_model_attempts_are_saved_without_publication(self):
        from cityg.agents import AgentGenerationError
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=save_json(_city(),root/'city.json');before=source.read_bytes()
            with self.assertRaises(AgentGenerationError):
                run_edit(source,'给 building_000 改名',root/'edited',_FakeService({}),
                         backend='manifest',no_viewer=True,max_attempts=2)
            self.assertFalse((root/'edited').exists())
            self.assertEqual(source.read_bytes(),before)
            files=list(root.glob('.edited.pending-*/edit_plan_failure.json'))
            self.assertEqual(len(files),1)
            report=json.loads(files[0].read_text())
            self.assertEqual(len(report['attempts']),2)
            self.assertTrue(all(a['raw_output']=='{}' and a['error'] for a in report['attempts']))

    def test_material_alias_preserves_all_other_metadata_and_scene(self):
        from copy import deepcopy
        from cityg.editing import apply_edit_plan
        city=_city();building=next(city.iter_buildings())
        building.metadata['appearance_plan'].update(material_family='brick',custom_intent='preserve')
        city.world_program=build_world_program(city,producer='test',seed=12)
        original=deepcopy(city)
        payload={'status':'apply','reason':'material only','clarification':'',
            'targets':[{'description':building.id,'resolved_ids':[building.id],'confidence':.99}],
            'operations':[{'op':'replace_node','target_id':building.id,
                'path':'appearance_plan.material_family','value_json':'"plaster"'}], 'visual_checks':[]}
        plan=EditAgent(_FakeService(payload)).plan(city,'修改 building_000 的立面为 plaster')
        result,_=apply_edit_plan(city,plan,patch_id='test_material_alias')
        changed=next(result.city.iter_buildings())
        expected=deepcopy(building.metadata);expected['appearance_plan']['material_family']='plaster'
        # Identity annotations may be added at publication; original keys must survive.
        for k,v in expected.items(): self.assertEqual(changed.metadata[k],v)
        self.assertEqual(city,original)
        self.assertEqual(changed.floors,building.floors)
        self.assertEqual(list(result.city.iter_buildings())[1],list(city.iter_buildings())[1])

    def test_unknown_patch_path_retries_before_transaction(self):
        from copy import deepcopy
        city=_city();building=next(city.iter_buildings())
        good={'status':'apply','reason':'rename','clarification':'',
            'targets':[{'description':building.id,'resolved_ids':[building.id],'confidence':.99}],
            'operations':[{'op':'replace_entity','target_id':building.id,'path':'name','value_json':'"New name"'}],
            'visual_checks':[]}
        class Service:
            calls=0
            def complete(self,*args):
                self.calls+=1;result=deepcopy(good)
                if self.calls==1: result['operations'][0].update(op='replace_node',path='arbitrary.invalid')
                return json.dumps(result)
        service=Service();plan=EditAgent(service,max_attempts=2).plan(city,'给 building_000 改名')
        self.assertEqual(service.calls,2)
        self.assertIn('Unpatchable',plan.attempts[0].error)
        self.assertEqual(plan.operations[0]['path'],'name')

    def test_invalid_nested_json_is_corrected_during_planning(self):
        from copy import deepcopy
        city = _city(); building = next(city.iter_buildings())
        bad = {'status': 'apply', 'reason': 'rename', 'clarification': '',
            'targets': [{'description': building.id, 'resolved_ids': [building.id], 'confidence': 1}],
            'operations': [{'op': 'replace_entity', 'target_id': building.id,
                            'path': 'name', 'value_json': 'New name'}], 'visual_checks': []}
        good = deepcopy(bad); good['operations'][0]['value_json'] = json.dumps('New name')
        class SequenceService:
            def __init__(self): self.items = iter([bad, good])
            def complete(self, messages, response_schema=None):
                return json.dumps(next(self.items))
        result = EditAgent(SequenceService()).plan(city, f'Rename {building.id}')
        self.assertEqual(len(result.attempts), 2)
        self.assertIn('value_json', result.attempts[0].error)
        self.assertEqual(json.loads(result.operations[0]['value_json']), 'New name')

    def test_edit_branches_memory_without_mutating_previous_version(self):
        from cityg.memory import MemoryStore, MemoryRecord
        city = _city(); building = next(city.iter_buildings())
        payload = {'status': 'apply', 'reason': 'rename', 'clarification': '',
            'targets': [{'description': building.id, 'resolved_ids': [building.id], 'confidence': 1}],
            'operations': [{'op': 'replace_entity', 'target_id': building.id,
                            'path': 'name', 'value_json': json.dumps('New name')}], 'visual_checks': []}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root/'source'; output = root/'edited'
            save_json(city, source/'final/city.json')
            with MemoryStore(source/'memory.sqlite') as memory:
                memory.put(MemoryRecord(memory_id='old_view', kind='visual_evidence',
                    scope_type='building', scope_id=building.id, content={'image':'old.png'},
                    validation_status='accepted'))
            run_edit(source, f'Rename {building.id}', output, _FakeService(payload),
                     backend='manifest', no_viewer=True)
            with MemoryStore(source/'memory.sqlite') as memory:
                self.assertEqual(memory.get('old_view').validation_status, 'accepted')
            with MemoryStore(output/'memory.sqlite') as memory:
                self.assertEqual(memory.get('old_view').validation_status, 'stale')
                self.assertEqual(memory.connection.execute(
                    "select count(*) from memory_records where kind='mutation_decision'"
                ).fetchone()[0], 1)

    def test_pipeline_root_selects_completed_review_not_old_generation(self):
        city = _city()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); save_json(city, root/'final/city.json')
            review = root/'visual_review'; package = review/'openusd_after'
            revised = _city(); revised.name = 'reviewed city'
            save_json(revised, package/'city.json'); save_json({}, package/'geometry_manifest.json')
            # A partial render is not a published review.
            self.assertEqual(resolve_scene(root).canonical_path, root/'final/city.json')
            save_json({'rendered_inventory_acceptance':{'ok':True}}, review/'adaptive_review_report.json')
            self.assertEqual(resolve_scene(root).canonical_path, package/'city.json')
            self.assertEqual(resolve_scene(root).compiled_path, package)
            self.assertEqual(resolve_scene(review).run_root, root)

    def test_compile_failure_never_publishes_final_bundle(self):
        from unittest.mock import patch
        city = _city(); building = next(city.iter_buildings())
        payload = {'status': 'apply', 'reason': 'tag', 'clarification': '',
            'targets': [{'description': building.id, 'resolved_ids': [building.id], 'confidence': 1.0}],
            'operations': [{'op': 'replace_entity', 'target_id': building.id,
                            'path': 'metadata', 'value_json': '{"edited":true}'}],
            'visual_checks': []}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = save_json(city, root/'city.json'); before = source.read_bytes()
            with patch('cityg.editing.OpenUSDBackend.compile', side_effect=RuntimeError('injected compiler failure')):
                with self.assertRaises(RuntimeError):
                    run_edit(source, '标记 building_000', root/'edited', _FakeService(payload), no_viewer=True)
            self.assertFalse((root/'edited').exists())
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(len(list(root.glob('.edited.pending-*/publication_failure.json'))), 1)

    def test_source_change_during_model_call_rejects_publication(self):
        from cityg.repair import PatchRejected
        city = _city(); building = next(city.iter_buildings())
        payload = {'status': 'apply', 'reason': 'tag', 'clarification': '',
            'targets': [{'description': building.id, 'resolved_ids': [building.id], 'confidence': 1.0}],
            'operations': [{'op': 'replace_entity', 'target_id': building.id,
                            'path': 'metadata', 'value_json': '{"edited":true}'}],
            'visual_checks': []}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = save_json(city, root/'city.json')
            class ConcurrentService(_FakeService):
                def complete(self, *args, **kwargs):
                    city.name = 'external concurrent update'; save_json(city, source)
                    return super().complete(*args, **kwargs)
            with self.assertRaises(PatchRejected):
                run_edit(source, '标记 building_000', root/'edited', ConcurrentService(payload),
                         backend='manifest', no_viewer=True)
            self.assertFalse((root/'edited').exists())
            self.assertEqual(load_city(source).name, 'external concurrent update')

    def test_deictic_reference_is_rejected_without_model_guess(self):
        city = _city()
        result = EditAgent(_FakeService({})).plan(city, "把这栋楼改成办公楼")
        self.assertEqual(result.status, "needs_clarification")
        self.assertFalse(result.operations)

    def test_explicit_low_risk_edit_creates_new_version(self):
        city = _city()
        building = next(city.iter_buildings())
        payload = {
            "status": "apply",
            "reason": "record an edit tag",
            "clarification": "",
            "targets": [
                {"description": building.id, "resolved_ids": [building.id], "confidence": 0.99}
            ],
            "operations": [
                {
                    "op": "replace_entity",
                    "target_id": building.id,
                    "path": "metadata",
                    "value_json": json.dumps({"edited": True}),
                }
            ],
            "visual_checks": [building.id],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "city.json"
            save_json(city, source)
            output = root / "edited"
            result = run_edit(
                source,
                "修改 building_000 的元数据",
                output,
                _FakeService(payload),
                model_id="fake",
                backend="manifest",
                no_viewer=True,
            )
            self.assertEqual(result.status, "applied")
            self.assertTrue(result.output_city.is_file())
            self.assertTrue((output / "base_scene_ref.json").is_file())
            edited = load_city(result.output_city)
            self.assertTrue(next(edited.iter_buildings()).metadata["edited"])
            self.assertFalse(source.read_text(encoding="utf-8") == result.output_city.read_text(encoding="utf-8"))

    def test_uid_alias_is_canonicalized_before_patch(self):
        city = _city()
        building = next(city.iter_buildings())
        uid = identity_for(city, building.id)["uid"]
        payload = {
            "status": "apply",
            "reason": "edit through stable UID",
            "clarification": "",
            "targets": [{"description": uid, "resolved_ids": [uid], "confidence": 0.99}],
            "operations": [{
                "op": "replace_entity",
                "target_id": uid,
                "path": "metadata",
                "value_json": json.dumps({"uid_edit": True}),
            }],
            "visual_checks": [uid],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "city.json"
            save_json(city, source)
            result = run_edit(
                source,
                f"修改 {uid} 的元数据",
                root / "edited_uid",
                _FakeService(payload),
                model_id="fake",
                backend="manifest",
                no_viewer=True,
            )
            self.assertEqual(result.status, "applied")
            edited = load_city(result.output_city)
            self.assertTrue(next(edited.iter_buildings()).metadata["uid_edit"])

    def test_scene_directory_resolution_prefers_canonical_final_city(self):
        city = _city()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_json(city, root / "final" / "city.json")
            reference = resolve_scene(root)
            self.assertEqual(reference.canonical_path, (root / "final" / "city.json").resolve())
            self.assertEqual(reference.run_root, root.resolve())

    def test_batch_edit_pauses_on_ambiguous_step(self):
        city = _city()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "city.json"
            save_json(city, source)
            result = run_batch_edit(
                source,
                ["把这栋楼改成办公楼"],
                root / "batch",
                _FakeService({}),
                backend="manifest",
                no_viewer=True,
            )
            self.assertEqual(result.status, "paused")
            self.assertEqual(len(result.steps), 1)
            self.assertEqual(result.steps[-1].status, "needs_clarification")

    def test_rollback_restores_explicit_target_without_overwriting(self):
        city = _city()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            save_json(city, source / "city.json")
            output = rollback_scene(source, root / "rollback", target_scene=source, backend="manifest", no_viewer=True)
            self.assertTrue((output / "final" / "city.json").is_file())
            self.assertTrue((output / "rollback_result.json").is_file())


if __name__ == "__main__":
    unittest.main()
