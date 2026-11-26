"""Registry membership checks retain dangling-reference diagnostics."""
import unittest

from cityg.planning import BaselineCityPlanner
from cityg.schemas import CitySpec
from cityg.validation.ccwp import CCWPValidator
from cityg.validation.model import ValidationReport


class RegistryValidationTests(unittest.TestCase):
    def setUp(self):
        self.city = BaselineCityPlanner().plan(CitySpec(
            name="registry_membership", width_m=180, depth_m=160,
            building_count=2, min_floors=2, max_floors=2,
            rooms_per_floor=2, seed=4))

    def test_missing_reference_in_each_registry_is_reported(self):
        for field in ("contract_ids", "relation_ids", "artifact_ids", "provenance_ids"):
            with self.subTest(field=field):
                node = self.city.world_program.nodes[0]
                values = getattr(node, field)
                values.append("missing_registry_entry")
                try:
                    report = ValidationReport()
                    CCWPValidator().validate_into(self.city, report)
                    self.assertTrue(any(i.code == "invalid_node_reference" for i in report.errors))
                finally:
                    values.pop()

    def test_missing_provenance_parent_is_reported(self):
        self.city.world_program.provenance[0].parent_record_ids.append("missing_parent")
        report = ValidationReport()
        CCWPValidator().validate_into(self.city, report)
        self.assertTrue(any(i.code == "invalid_provenance_reference" for i in report.errors))


if __name__ == "__main__":
    unittest.main()
