import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_interface_binding_pilot import fixture, violations, execute, SCENARIOS


class InterfaceBindingTests(unittest.TestCase):
    def test_satisfiable_and_infeasible_cases_have_geometric_oracles(self):
        for scenario in SCENARIOS:
            city,b,f,contract,candidates=fixture(scenario,101)
            good=[c for c in candidates if not violations(contract,c['shared_boundary_x'])]
            self.assertEqual(bool(good),scenario in {'left_capacity','right_capacity','door_limited'},scenario)
            if good:
                _,receipt=execute(city,b,f,contract,good[0])
                self.assertEqual(receipt['status'],'resolved',receipt)

    def test_door_corner_and_capacity_are_independent_constraints(self):
        _,_,_,contract,_=fixture('door_limited',101)
        edge=contract['shared_boundary_before']+.72
        self.assertEqual(violations(contract,edge),['door_corner'])

