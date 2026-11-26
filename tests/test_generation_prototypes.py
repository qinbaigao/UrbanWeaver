from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cityg.agents import RequirementAgent
from cityg.agents.prototype_selection import select_reference
from cityg.assets import AssetRegistry
from cityg.geometry import GeometryCompiler
from cityg.planning.baseline import BaselineCityPlanner
from cityg.planning.generation_prototypes import GenerationPrototypes, DeferredFurniture, load_options
from cityg.planning.floor_repartition import repartition_city
from cityg.requirement_ledger import create_ledger, evaluate_ledger
from cityg.schemas import CitySpec
from cityg.ccwp import build_world_program
import test_closed_loop as closed
import test_floor_repartition as fixtures

ROOT = Path(__file__).resolve().parents[1]


def offline_responses():
    """Explicit test doubles, not recorded or live model evidence."""
    spec = json.loads(closed.responses()[0])
    spec.update(name='round1_offline_contract_test', width_m=220, depth_m=200,
                building_count=10, rooms_per_floor=2, room_count_strategy='adaptive', seed=1701,
                zones=[{'name': 'housing', 'function': 'residential', 'weight': .4},
                       {'name': 'offices', 'function': 'commercial', 'weight': .4},
                       {'name': 'civic', 'function': 'public_service', 'weight': .2}])
    functions = [('residential', 'residential_slab', ['bedroom', 'living_room']),
                 ('commercial', 'commercial_tower', ['office', 'open_office']),
                 ('public_service', 'public_civic', ['office', 'waiting_room'])]
    urban = {'district_order': ['zone_00', 'zone_01', 'zone_02'], 'road_pattern': 'connected_grid',
             'block_traversal': 'row_major', 'collector_policy': 'perimeter'}
    skyline = {'profiles': [{'function': fn, 'min_floors': 2, 'max_floors': 2,
                            'centrality_bias': 'distributed', 'height_role': 'lowrise'} for fn, _, _ in functions],
               'highrise_ratio': 0., 'landmark_count': 0, 'landmark_functions': [], 'skyline_strength': .7}
    building = {'profiles': [{'function': fn, 'floor_policy': 'midpoint', 'entrance_side': 'west',
                              'prototype_id': proto} for fn, proto, _ in functions]}
    from cityg.buildings import DEFAULT_BUILDING_CATALOG
    for profile in building['profiles']:
        profile['archetype_palette'] = [r.archetype_id for r in DEFAULT_BUILDING_CATALOG
                                        if r.massing_style == 'bar' and not r.highrise_only
                                        and profile['function'] in r.compatible_functions][:4]
    spaces = {'profiles': [{'function': fn, 'archetypes': [
        {'role': role, 'preferred_room_count': 3, 'min_room_count': 2, 'max_room_count': 5,
         'target_room_area_m2': 50, 'min_room_width_m': 3, 'unit_group_size': 1,
         'max_room_depth_m': 30, 'max_room_aspect_ratio': 8, 'layout_template': 'auto',
         'room_function_cycle': cycle} for role in ('ground', 'typical')]} for fn, _, cycle in functions]}
    floors = {'profiles': [{'function': fn, 'layout': 'double_loaded_corridor', 'corridor_ratio': .18,
                            'room_function_cycle': cycle} for fn, _, cycle in functions]}
    return [{'prototype_id': 'urban_residential_v1', 'reason': 'Offline fixture only'}, json.dumps(spec),
            *[closed.final(value) for value in (urban, skyline, building, spaces, floors)]]


class GenerationPrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.options = load_options(ROOT/'configs/generation_prototypes.json')
        cls.runtime = GenerationPrototypes(cls.options)
        fixtures.FloorRepartitionTests.setUpClass()

    def test_options_are_strict_and_config_relative(self):
        self.assertEqual(Path(self.options['library_root']), ROOT/'configs/layout_prototypes/v1')
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'config.json'
            p.write_text(json.dumps({'unknown': True}))
            with self.assertRaises(ValueError): load_options(p)

    def test_detached_resources_rebind_facade_runtime_too(self):
        from cityg.facade_runtime import FacadeAssetRuntime
        from cityg.facade_assets import FacadeAssetIndex
        registry=AssetRegistry()
        facade=FacadeAssetRuntime(FacadeAssetIndex({'schema_version':'cityg.facade_asset_annotations.v1','assets':[]}),registry,project_root=ROOT)
        compiler=GeometryCompiler(asset_registry=registry,facade_asset_runtime=facade)
        detached=self.runtime.prepare_resources(registry,compiler)
        self.assertIs(compiler.asset_registry,detached)
        self.assertIs(compiler.streetscape_compiler.asset_registry,detached)
        self.assertIs(facade.asset_registry,detached)

    def test_deferred_planning_keeps_empty_inventory(self):
        spec = CitySpec.from_dict(json.loads(closed.responses()[0]))
        city = BaselineCityPlanner(floor_detail_agent=DeferredFurniture()).plan(spec)
        self.assertFalse(list(city.iter_objects()))
        self.assertTrue(list(city.iter_rooms()))
        self.assertEqual(city.metadata['interior_detail']['planner'], 'deferred_until_partition')

    def test_reference_does_not_supply_sample_count(self):
        context = self.runtime.context({'prototype_id': 'urban_center_v1'})
        self.assertNotIn('building_count', context['reference_defaults'])
        self.assertNotIn('room_count_strategy', context['reference_defaults'])
        svc = closed.FakeService([closed.responses()[0]])
        parsed = RequirementAgent(svc).parse('building_count=2', reference_context=context)
        self.assertEqual(parsed.spec.building_count, 2)
        self.assertIn('urban_center_v1', svc.calls[0][0][0].content)

    def test_selection_retries_unknown_ids_and_records_attempts(self):
        service = closed.FakeService([{'prototype_id': 'bad', 'reason': 'x'},
                                     {'prototype_id': 'urban_center_v1', 'reason': 'business core'}])
        result, attempts = select_reference(RequirementAgent(service), '商务区', self.runtime.urban)
        self.assertEqual(result['prototype_id'], 'urban_center_v1')
        self.assertEqual(len(attempts), 2)
        self.assertTrue(attempts[0].error)

    def test_empty_scope_never_means_all_floors(self):
        city, _, _ = fixtures.FloorRepartitionTests().fixture()
        result, report = repartition_city(city, self.runtime.floors, GeometryCompiler(),
                                         {'enabled': True}, target_levels={})
        self.assertEqual(result, city)
        self.assertEqual(report['attempts'], [])

    def test_occupied_city_is_not_cleared(self):
        spec = CitySpec.from_dict(json.loads(closed.responses()[0]))
        city = BaselineCityPlanner().plan(spec)
        before = deepcopy(city)
        with self.assertRaisesRegex(ValueError, 'inventory cannot be cleared'):
            self.runtime.populate(city, None, GeometryCompiler())
        self.assertEqual(city, before)

    def test_ledger_never_claims_semantic_verification(self):
        spec = CitySpec.from_dict(json.loads(closed.responses()[0]))
        city = BaselineCityPlanner(floor_detail_agent=DeferredFurniture()).plan(spec)
        ledger = evaluate_ledger(create_ledger('温馨社区', spec), city)
        self.assertEqual(ledger['status'], 'checked_with_unverified_semantics')
        city.districts[0].parcels[0].buildings.clear()
        self.assertEqual(evaluate_ledger(ledger, city)['status'], 'violated')

    def test_main_coordinator_consumes_reference_and_reports_exterior_skip(self):
        service = closed.FakeService([{'prototype_id': 'urban_center_v1', 'reason': 'reference'}, *closed.responses()])
        with tempfile.TemporaryDirectory() as folder:
            result = closed.coordinator(service, prototype_options=self.options).run('building_count=2', folder)
            self.assertEqual(result.run.status, 'success', result.run)
            self.assertFalse(list(result.city.iter_objects()))
            self.assertTrue((Path(folder)/'programs/prototype_selection.json').is_file())
            report = json.loads((Path(folder)/'programs/prototype_adaptation.json').read_text())
            self.assertEqual(report['status'], 'interiors_skipped')
            self.assertEqual(result.city.metadata['urban_layout_prototype']['mode'], 'reference_conditioned_planning')

    def test_scope_and_room_caps_with_real_compiler(self):
        runtime = GenerationPrototypes(self.options)
        city, b, f = fixtures.FloorRepartitionTests().fixture()
        for floor in city.iter_floors():
            floor.objects.clear()
            for room in floor.rooms: room.object_ids.clear()
        city.world_program = build_world_program(city, producer='test_unfurnished', seed=None)
        before = deepcopy(city)
        runtime.options['adaptation'].update(max_rooms=2, max_attempts=8)
        compiler = GeometryCompiler(asset_registry=AssetRegistry(ROOT/'assets/asset_registry.json'))
        registry = runtime.prepare_resources(compiler.asset_registry, compiler)
        from cityg.memory import MemoryStore, MemoryQuery
        with tempfile.TemporaryDirectory() as folder, MemoryStore(Path(folder)/'memory.sqlite') as store:
            result, report = runtime.populate(city, registry, compiler, building_limit=1, floor_limit=1,
                                              memory_store=store)
            for row in report['rooms']:
                version=next(n.version for n in result.world_program.nodes if n.entity_id==row['room_id'])
                records=store.query(MemoryQuery(scope_id=row['room_id'],world_version=version,
                                               kinds=('room_reference_execution',)))
                self.assertEqual(len(records),1)
                self.assertEqual(records[0].content['prototype_id'],row['prototype_id'])
                self.assertTrue(records[0].content['compiled_verified'])
        self.assertEqual(city, before)
        self.assertTrue(report['floor_repartition']['accepted'], report)
        self.assertTrue(report['rooms'], report['attempts'])
        self.assertLessEqual(len(report['rooms']), 2)
        self.assertEqual(report['authorized_levels'], {b.id: [0]})
        self.assertEqual(next(result.iter_buildings()).floors[1], b.floors[1])

    def test_default_coordinator_openusd_integration(self):
        from cityg.agents import HierarchicalPlanningAgent, RepairAgent
        from cityg.closed_loop import ClosedLoopCoordinator
        from cityg.services import OpenUSDBackend
        from cityg.serialization import save_json
        registry = AssetRegistry(ROOT/'assets/asset_registry.json')
        service = closed.FakeService(offline_responses())
        opt = deepcopy(self.options)
        opt['adaptation']['max_rooms'] = 4
        backend = OpenUSDBackend(GeometryCompiler(asset_registry=registry))
        # Avoid a second gigabyte asset export in unit tests; compile the same
        # real geometry and verify its serialized final inventory in production.
        def compile_manifest(city, output):
            return [save_json(backend.geometry_compiler.compile(city), output/'geometry_manifest.json')]
        runner = ClosedLoopCoordinator(RequirementAgent(service), HierarchicalPlanningAgent(service),
            RepairAgent(service), asset_registry=registry, simulation_backend=backend,
            prototype_options=opt, export_viewer=False)
        with tempfile.TemporaryDirectory() as folder, patch.object(backend, 'compile', side_effect=compile_manifest):
            result = runner.run('10 buildings with up to 4 detailed rooms', folder)
            self.assertEqual(result.run.status, 'success', result.run.error)
            report = json.loads((Path(folder)/'final/reports/prototype_compiled_acceptance.json').read_text())
            self.assertEqual(len(report['rooms']), 4)
            self.assertTrue(report['ok'])

    def test_no_supported_interior_scope_stops_before_export(self):
        from cityg.agents import HierarchicalPlanningAgent, RepairAgent
        from cityg.closed_loop import ClosedLoopCoordinator
        from cityg.services import OpenUSDBackend
        registry=AssetRegistry(ROOT/'assets/asset_registry.json')
        service=closed.FakeService(offline_responses())
        backend=OpenUSDBackend(GeometryCompiler(asset_registry=registry))
        runner=ClosedLoopCoordinator(RequirementAgent(service),HierarchicalPlanningAgent(service),
            RepairAgent(service),asset_registry=registry,simulation_backend=backend,
            prototype_options=self.options,export_viewer=False)
        def unsupported(city,**kwargs):
            return {},{}, {'target_buildings':{},'rejected':[{'building_id':b.id,
                'reason':'no_street_frontage_for_supported_circulation_axis'} for b in city.iter_buildings()]}
        with tempfile.TemporaryDirectory() as folder, patch(
                'cityg.planning.interior_capability.reserve_interiors',side_effect=unsupported), patch.object(backend,'compile') as compile:
            result=runner.run('10 buildings and detailed interiors',folder)
            self.assertEqual(result.run.status,'replan_required')
            self.assertEqual(result.run.stage,'interior_capability')
            self.assertFalse((Path(folder)/'final').exists());compile.assert_not_called()
            conflicts=json.loads((Path(folder)/'programs/planning_conflicts.json').read_text())
            self.assertEqual(len(conflicts),10)
            self.assertTrue(all(c['entity_binding_verified'] and not c['automatic_scope_expansion'] for c in conflicts))

    def test_fixed_partition_preserves_room_counts(self):
        city, b, _ = fixtures.FloorRepartitionTests().fixture()
        for floor in city.iter_floors():
            floor.objects.clear()
            for room in floor.rooms: room.object_ids.clear()
        city.world_program = build_world_program(city, producer='test_unfurnished', seed=None)
        with patch('cityg.planning.generation_prototypes.adapt_city_rooms', return_value=(city, {
                'summary': {}, 'rooms': []})):
            result, report = self.runtime.populate(city, None, GeometryCompiler(), preserve_partition=True)
        self.assertFalse(report['floor_repartition']['enabled'])
        self.assertEqual([len(f.rooms) for f in result.iter_floors()], [len(f.rooms) for f in city.iter_floors()])

    def test_explicit_scope_targets_are_not_lost_to_default_selection(self):
        rt = GenerationPrototypes(self.options)
        spec = CitySpec.from_dict(json.loads(closed.responses()[0]))
        city = BaselineCityPlanner(floor_detail_agent=DeferredFurniture()).plan(spec)
        target = list(city.iter_buildings())[-1].id
        rt.options['adaptation']['floor_repartition'].update(target_building_ids=[target], levels=[1])
        scope = rt.select_scope(city, building_limit=1, floor_limit=1)
        self.assertEqual(scope['building_levels'], {target: [1]})
        rt.options['adaptation']['floor_repartition']['target_building_ids'] = ['missing']
        with self.assertRaises(ValueError): rt.select_scope(city)

    def test_main_coordinator_marks_partial_instead_of_success(self):
        from types import SimpleNamespace
        options = deepcopy(self.options)
        service = closed.FakeService([{'prototype_id': 'none', 'reason': 'no reference'}, *closed.responses()])
        from cityg.services import OpenUSDBackend
        runtime_report = {'status': 'no_compatible_rooms', 'summary': {'accepted_rooms': 0}, 'rooms': []}
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(GenerationPrototypes, 'prepare_resources', return_value=AssetRegistry()), \
             patch.object(GenerationPrototypes, 'populate', side_effect=lambda city, *a, **kw: (city, runtime_report)):
            runner = closed.coordinator(service, prototype_options=options)
            runner.simulation_backend = OpenUSDBackend(GeometryCompiler())
            with patch.object(runner.simulation_backend, 'compile', return_value=[]):
                result = runner.run('small city', folder)
            self.assertEqual(result.run.status, 'partial_success')
            self.assertFalse(result.ok)


if __name__ == '__main__': unittest.main()
