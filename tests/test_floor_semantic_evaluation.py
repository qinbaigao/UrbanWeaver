from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from run_semantic_transfer import fixture, cost_total, validate_manifest
from cityg.evaluation.floor_baselines import simple_plan
from cityg.evaluation.floor_semantics import evaluate_floor_requirements, inspect_floor
from cityg.geometry import GeometryCompiler
from cityg.serialization import to_primitive
from verify_floor_briefs import realize_profile


class FloorSemanticEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        row=json.loads((ROOT/'configs/semantic_transfer_cases.json').read_text())['fixtures'][0]
        cls.city,cls.bid,cls.base,cls.spec=fixture(row,431)
        cls.manifest=to_primitive(GeometryCompiler().compile(cls.city,building_ids={cls.bid}))
        cls.contract={'levels':[0,1],'required_functions':row['functions'],'organization':'independent'}

    def evaluate(self,city=None,manifest=None,contract=None):
        return evaluate_floor_requirements(self.city,city or self.city,self.bid,
            manifest or self.manifest,contract or self.contract)

    def test_realized_compiled_floor_passes_without_reading_planner_receipts(self):
        self.assertTrue(self.evaluate()['passed'],self.evaluate())
        city=deepcopy(self.city)
        for f in next(city.iter_buildings()).floors:f.metadata['spatial_layout']={'status':'failed'}
        self.assertTrue(self.evaluate(city=city)['passed'])

    def test_missing_or_displaced_compiled_panel_fails(self):
        for mode in ('missing','displaced'):
            manifest=deepcopy(self.manifest)
            panel=next(p for p in manifest['primitives'] if p['semantic_class']=='door')
            if mode=='missing':manifest['primitives'].remove(panel)
            else:panel['center']['x']+=100
            self.assertFalse(self.evaluate(manifest=manifest)['passed'])

    def test_missing_function_and_unrelated_modification_fail(self):
        city=deepcopy(self.city)
        for f in next(city.iter_buildings()).floors:
            for r in f.rooms:
                if r.function=='bathroom':r.function='bedroom'
        self.assertFalse(self.evaluate(city=city)['passed'])
        city=deepcopy(self.city);list(city.iter_buildings())[1].name='Unauthorized'
        self.assertFalse(self.evaluate(city=city)['passed'])

    def test_nontarget_floor_is_protected(self):
        city=deepcopy(self.city)
        next(city.iter_buildings()).floors[1].metadata['unauthorized']=True
        self.assertFalse(self.evaluate(city=city,contract={**self.contract,'levels':[0]})['passed'])

    def test_empty_scope_cannot_pass(self):
        with self.assertRaises(ValueError):self.evaluate(contract={**self.contract,'levels':[]})

    def test_malformed_contracts_fail_closed(self):
        for change in ({'levels':[[0]]},{'levels':[True]},{'levels':[0,0]},
                       {'required_functions':[]},{'no_transit_functions':'bathroom'}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.evaluate(contract={**self.contract,**change})

    def test_duplicate_floor_and_changed_entry_fail(self):
        city=deepcopy(self.city)
        next(city.iter_buildings()).floors.append(deepcopy(next(city.iter_buildings()).floors[0]))
        self.assertFalse(self.evaluate(city=city)['passed'])
        city=deepcopy(self.city)
        from cityg.schemas import Point2D
        b=next(city.iter_buildings());b.entrance=Point2D(b.entrance.x+1,b.entrance.y)
        self.assertFalse(self.evaluate(city=city)['passed'])

    def test_unconnected_extra_corridor_is_not_an_implicit_access_root(self):
        floor=deepcopy(next(self.city.iter_buildings()).floors[0])
        extra=deepcopy(next(r for r in floor.rooms if r.function=='corridor'))
        extra.id+='__isolated';floor.rooms.append(extra)
        report=inspect_floor(floor,self.manifest)
        self.assertFalse(report['valid'])
        self.assertIn('unsupported_corridor_count',report['errors'])

    def test_baseline_failed_search_preserves_model_cost(self):
        from unittest.mock import patch
        from cityg.agents.requirement import AgentGenerationError
        with patch('cityg.evaluation.floor_baselines.interpret_organization',return_value=(
                {'organization':'independent'},('trace',))),patch(
                'cityg.evaluation.floor_baselines.topology_catalog',return_value=[]):
            with self.assertRaises(AgentGenerationError) as raised:
                simple_plan(None,next(self.city.iter_buildings()),self.base,self.spec)
        self.assertEqual(raised.exception.attempts,('trace',))

    def test_missing_usage_is_unknown_not_zero(self):
        self.assertIsNone(cost_total([{'cost':{'prompt_tokens':None}}],'prompt_tokens'))
        self.assertEqual(cost_total([{'cost':{'prompt_tokens':3}}],'prompt_tokens'),3)

    def test_frozen_manifest_rejects_empty_duplicate_and_unsafe_tasks(self):
        source=json.loads((ROOT/'configs/semantic_transfer_cases.json').read_text())
        validate_manifest(source,['deterministic'])
        for mode in ('empty','duplicate','unsafe','unknown_fixture'):
            manifest=deepcopy(source)
            if mode=='empty':manifest['tasks']=[]
            elif mode=='duplicate':manifest['tasks'].append(manifest['tasks'][0])
            elif mode=='unsafe':manifest['tasks'][0]['id']='../escape'
            else:manifest['tasks'][0]['fixture']='not_found'
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                validate_manifest(manifest,['deterministic'])

    def test_private_anchor_cannot_be_forbidden_transit_function(self):
        from unittest.mock import patch
        with patch('cityg.evaluation.floor_baselines.interpret_organization',return_value=(
                {'organization':'private_groups','supporting_goal_ids':['test']},())):
            program,_,_=simple_plan(None,next(self.city.iter_buildings()),self.base,self.spec)
        result=realize_profile(self.city,self.bid,program.profile,self.spec)
        manifest=to_primitive(GeometryCompiler().compile(result,building_ids={self.bid}))
        contract={**self.contract,'organization':'private_groups','no_transit_functions':['living_room']}
        report=self.evaluate(city=result,manifest=manifest,contract=contract)
        self.assertFalse(report['passed'])
        self.assertTrue(any(not c['ok'] and 'no_transit_living_room' in c['id'] for c in report['checks']))
        for floor in report['floors']:
            for rid,witness in floor['transit_witnesses'].items():
                self.assertIn(rid,witness['access_path'][1:-1])
                self.assertEqual(witness['access_path'][-1],witness['disconnected_room_id'])

    def test_private_groups_require_real_access_edges(self):
        from unittest.mock import patch
        b=next(self.city.iter_buildings())
        with patch('cityg.evaluation.floor_baselines.interpret_organization',return_value=(
                {'organization':'private_groups','supporting_goal_ids':['test']},())):
            program,_,_=simple_plan(None,b,self.base,self.spec)
        result=realize_profile(self.city,self.bid,program.profile,self.spec)
        manifest=to_primitive(GeometryCompiler().compile(result,building_ids={self.bid}))
        report=self.evaluate(city=result,manifest=manifest,contract={**self.contract,'organization':'private_groups'})
        self.assertTrue(report['passed'],report)
