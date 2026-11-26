from copy import deepcopy
from dataclasses import replace
import unittest

from cityg.evaluation.method_pilot import evaluate_result, make_case, summarize
from cityg.planning.baseline import BaselineCityPlanner
from cityg.planning.generation_prototypes import DeferredFurniture
from cityg.schemas import CitySpec
from cityg.subtree_transactions import FloorSubtreePlanner


class MethodPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.city = BaselineCityPlanner(floor_detail_agent=DeferredFurniture()).plan(
            CitySpec(building_count=2, min_floors=2, max_floors=2, width_m=180, depth_m=140))

    def test_noop_is_not_repair(self):
        case = make_case(self.city, 'single_floor')
        result = evaluate_result(self.city, self.city, case, True, True)
        self.assertFalse(result['objective_met'])
        self.assertFalse(result['verified_repair'])

    def test_external_oracle_rejects_protected_and_outside_changes(self):
        case = make_case(self.city, 'single_floor')
        candidate = deepcopy(self.city)
        list(candidate.iter_buildings())[1].name = 'Unrelated edit'
        report = evaluate_result(self.city, candidate, case, True, True)
        self.assertFalse(report['outside_target_floors_preserved'])
        self.assertFalse(report['safety_ok'])
        candidate = deepcopy(self.city)
        building = next(candidate.iter_buildings())
        building.entrance = replace(building.entrance, x=building.entrance.x+1)
        report = evaluate_result(self.city, candidate, case, True, True)
        self.assertFalse(report['protected_geometry_preserved'])

    def test_guard_is_separate_from_task_success(self):
        case = make_case(self.city, 'locked_parent')
        report = evaluate_result(self.city, self.city, case, True, True)
        self.assertTrue(report['safe_nonexecution'])
        self.assertFalse(report['verified_repair'])

    def test_matching_count_still_requires_geometry_and_unchanged_source(self):
        case = make_case(self.city, 'single_floor')
        candidate = FloorSubtreePlanner().replace(self.city, case['floor_id'],
            {'room_count': case['requested_floor_room_count']}).city
        self.assertTrue(evaluate_result(self.city, candidate, case, True, True)['verified_repair'])
        self.assertFalse(evaluate_result(self.city, candidate, case, False, True)['verified_repair'])
        self.assertFalse(evaluate_result(self.city, candidate, case, True, False)['verified_repair'])

    def test_one_attempt_remains_a_repair_task_not_mandatory_refusal(self):
        self.assertEqual(make_case(self.city, 'one_attempt')['task_class'], 'repair')

    def test_failures_stay_in_denominator(self):
        case = make_case(self.city, 'single_floor')
        report = summarize([{'method': 'fixed_floor', 'case': case, 'error': 'offline'}])['fixed_floor']
        self.assertEqual(report['repair_tasks'], 1)
        self.assertEqual(report['verified_repairs'], 0)
        self.assertEqual(report['errors'], 1)
