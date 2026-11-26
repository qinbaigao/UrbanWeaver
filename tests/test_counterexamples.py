import unittest

from cityg.evaluation import ERROR_CASES, error_regression_suite, inject_error
from cityg.planning import BaselineCityPlanner
from cityg.schemas import CitySpec
from cityg.validation import CityValidator


class CounterexampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.city = BaselineCityPlanner().plan(
            CitySpec(
                name="error_regression",
                width_m=180,
                depth_m=160,
                building_count=2,
                min_floors=2,
                max_floors=2,
                rooms_per_floor=3,
                seed=8,
            )
        )

    def test_injected_errors_are_detected_and_localized(self):
        validator = CityValidator()
        for case, expected_codes in ERROR_CASES.items():
            with self.subTest(case=case):
                report = validator.validate(inject_error(self.city, case))
                actual_codes = {issue.code for issue in report.errors}
                self.assertFalse(report.ok)
                self.assertTrue(expected_codes.issubset(actual_codes), actual_codes)
                counterexamples = [
                    issue for issue in report.errors if issue.code in expected_codes
                ]
                self.assertTrue(any(issue.constraint_id for issue in counterexamples))
                rich = next(issue for issue in counterexamples if issue.constraint_id)
                self.assertTrue(rich.violating_entities)
                self.assertIsNotNone(rich.responsible_ancestor)
                self.assertTrue(rich.dependency_path)
                self.assertIsNotNone(rich.allowed_patch_scope)
                self.assertTrue(rich.suggested_operations)

    def test_thirty_case_regression_suite(self):
        validator = CityValidator()
        cases = list(error_regression_suite(self.city))
        self.assertEqual(len(cases), 30)
        for name, expected_codes, invalid_city in cases:
            with self.subTest(case=name):
                actual = {issue.code for issue in validator.validate(invalid_city).errors}
                self.assertTrue(expected_codes.issubset(actual), actual)


if __name__ == "__main__":
    unittest.main()
