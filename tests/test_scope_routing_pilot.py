import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_scope_routing_pilot import dependency_scope, make_task, strategy, task_met
from cityg.planning.baseline import BaselineCityPlanner
from cityg.planning.generation_prototypes import DeferredFurniture
from cityg.schemas import CitySpec
from cityg.transactions import fingerprint
from copy import deepcopy


class ScopeRoutingTests(unittest.TestCase):
    def setUp(self):
        self.city=BaselineCityPlanner(floor_detail_agent=DeferredFurniture()).plan(
            CitySpec(building_count=2,min_floors=2,max_floors=2,width_m=180,depth_m=140,seed=101))

    def test_dependency_routing_uses_operations_not_scenario_label(self):
        for scenario,expected in [('room_name','room'),('single_floor','floor'),('two_floors','building')]:
            task=make_task(self.city,scenario);task['scenario']='hidden'
            self.assertEqual(dependency_scope(task),expected)

    def test_room_scope_has_a_real_implementable_task(self):
        task=make_task(self.city,'room_name');before=fingerprint(self.city)
        candidate=strategy(deepcopy(self.city),task['entity_id'],task)
        self.assertTrue(task_met(candidate,task))
        self.assertFalse(task_met(self.city,task))
        self.assertEqual(before,fingerprint(self.city))

    def test_partial_floor_change_cannot_satisfy_two_floor_request(self):
        task=make_task(self.city,'two_floors')
        candidate=strategy(deepcopy(self.city),task['floor_id'],task)
        self.assertFalse(task_met(candidate,task))
