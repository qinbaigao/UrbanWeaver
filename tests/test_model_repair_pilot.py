import json
import unittest
from types import SimpleNamespace
from cityg.agents import RepairAgent
from cityg.evaluation.error_injection import inject_error
from cityg.evaluation.model_repair_pilot import LocalSummaryRepairAgent, judge, attempt_cost
from cityg.planning.baseline import BaselineCityPlanner
from cityg.planning.generation_prototypes import DeferredFurniture
from cityg.schemas import CitySpec
from cityg.serialization import to_primitive
from cityg.validation import CityValidator


class FakeService:
    def __init__(self, text): self.text = text
    def complete(self, messages, response_schema=None): return self.text


class ModelRepairPilotTests(unittest.TestCase):
    def setUp(self):
        self.city = BaselineCityPlanner(floor_detail_agent=DeferredFurniture()).plan(
            CitySpec(building_count=2,min_floors=2,max_floors=2,width_m=180,depth_m=140))
        self.broken = inject_error(self.city, 'disconnected_entrance')

    def test_ablation_only_removes_contract_records(self):
        report = CityValidator().validate(self.broken)
        scope = next(self.city.iter_buildings()).id
        service = FakeService('')
        full = RepairAgent(service)._context(self.broken, report, scope)
        reduced = LocalSummaryRepairAgent(service)._context(self.broken, report, scope)
        self.assertTrue(full['contracts'])
        full['contracts'] = []
        self.assertEqual(full, reduced)

    def test_known_restore_is_scored_and_noop_is_not(self):
        building = next(self.city.iter_buildings())
        relation = next(r for r in self.city.world_program.relations
                        if r.id == f'rel_building_access__{building.id}')
        proposal = json.dumps({'reason':'restore', 'operations':[{'op':'add_relation',
            'target_id':building.id, 'path':'', 'value_json':json.dumps(to_primitive(relation))}]})
        result = RepairAgent(FakeService(proposal)).repair(self.broken)
        evaluation = judge(self.city, self.broken, result.city)
        self.assertTrue(evaluation['verified_restoration'], evaluation)
        self.assertFalse(judge(self.city, self.broken, self.broken)['verified_restoration'])

    def test_missing_usage_is_unknown_not_zero(self):
        self.assertEqual(attempt_cost([])['prompt_tokens'], 0)
        self.assertIsNone(attempt_cost([SimpleNamespace(usage={},elapsed_s=1,messages=[])])['prompt_tokens'])
