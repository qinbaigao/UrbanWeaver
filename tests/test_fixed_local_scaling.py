import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_fixed_local_scaling import master_fixture, nested_fixture, digest
from cityg.agents import RepairAgent
from cityg.evaluation.error_injection import inject_error
from cityg.validation import CityValidator


class FixedLocalScalingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.master,_ = master_fixture(101,10)

    def test_nested_population_preserves_site_and_target(self):
        before = digest(self.master)
        small = nested_fixture(self.master,2)
        large = nested_fixture(self.master,10)
        self.assertEqual(len(list(small.iter_buildings())),2)
        self.assertEqual(len(list(large.iter_buildings())),10)
        self.assertEqual(small.road_network,large.road_network)
        self.assertEqual(next(small.iter_buildings()),next(large.iter_buildings()))
        self.assertEqual(before,digest(self.master))
        self.assertTrue(CityValidator().validate(small).ok)

    def test_fault_context_is_identical_at_both_sizes(self):
        for family in ('disconnected_entrance','disconnected_room'):
            contexts=[]
            for n in (2,10):
                city=inject_error(nested_fixture(self.master,n),family)
                contexts.append(RepairAgent(None)._context(city,CityValidator().validate(city),
                    next(city.iter_buildings()).id))
            self.assertEqual(contexts[0],contexts[1])

    def test_rejects_population_outside_master(self):
        for n in (0,11):
            with self.assertRaises(ValueError):nested_fixture(self.master,n)
