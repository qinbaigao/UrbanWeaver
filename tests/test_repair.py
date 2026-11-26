import json
import tempfile
import unittest
from pathlib import Path

from cityg.cli import main
from cityg.evaluation import inject_error
from cityg.planning import BaselineCityPlanner
from cityg.repair import (
    PatchEngine,
    PatchOperation,
    PatchRejected,
    WorldPatch,
    lock_outside_scope,
)
from cityg.schemas import CitySpec
from cityg.serialization import load_city, save_json, to_primitive


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.valid_city = BaselineCityPlanner().plan(
            CitySpec(
                name="repair_test",
                width_m=180,
                depth_m=160,
                building_count=2,
                min_floors=2,
                max_floors=2,
                rooms_per_floor=3,
                seed=5,
            )
        )

    def test_missing_access_relation_can_be_repaired_locally(self):
        invalid = inject_error(self.valid_city, "disconnected_entrance")
        building = next(invalid.iter_buildings())
        original = next(
            relation
            for relation in self.valid_city.world_program.relations
            if relation.relation_type == "accessible_from"
            and relation.source_id == building.id
        )
        node = next(
            item for item in invalid.world_program.nodes if item.entity_id == building.id
        )
        lock_outside_scope(invalid, building.id)
        result = PatchEngine().apply(
            invalid,
            WorldPatch(
                id="restore_access",
                scope_entity_id=building.id,
                operations=(
                    PatchOperation(
                        op="add_relation",
                        target_id=building.id,
                        value=to_primitive(original),
                    ),
                ),
                expected_versions={building.id: node.version},
                reason="restore injected pedestrian access relation",
            ),
        )
        self.assertTrue(result.validation.ok)
        self.assertEqual(result.touched_entity_ids, (building.id,))
        repaired_node = next(
            item for item in result.city.world_program.nodes if item.entity_id == building.id
        )
        self.assertEqual(repaired_node.version, node.version + 1)
        self.assertTrue(result.provenance_ids)

    def test_scope_violation_does_not_mutate_original(self):
        before = to_primitive(self.valid_city)
        buildings = list(self.valid_city.iter_buildings())
        target = buildings[1]
        target_node = next(
            node
            for node in self.valid_city.world_program.nodes
            if node.entity_id == target.id
        )
        with self.assertRaises(PatchRejected) as context:
            PatchEngine().apply(
                self.valid_city,
                WorldPatch(
                    id="escape_scope",
                    scope_entity_id=buildings[0].id,
                    operations=(
                        PatchOperation(
                            op="replace_entity",
                            target_id=target.id,
                            path="name",
                            value="Forbidden change",
                        ),
                    ),
                    expected_versions={target.id: target_node.version},
                ),
            )
        self.assertEqual(context.exception.code, "scope_violation")
        self.assertEqual(to_primitive(self.valid_city), before)

    def test_version_conflict_is_rejected(self):
        building = next(self.valid_city.iter_buildings())
        with self.assertRaises(PatchRejected) as context:
            PatchEngine().apply(
                self.valid_city,
                WorldPatch(
                    id="stale_patch",
                    scope_entity_id=building.id,
                    operations=(
                        PatchOperation(
                            op="replace_entity",
                            target_id=building.id,
                            path="name",
                            value="New name",
                        ),
                    ),
                    expected_versions={building.id: 0},
                ),
            )
        self.assertEqual(context.exception.code, "version_conflict")

    def test_cli_applies_json_patch(self):
        invalid = inject_error(self.valid_city, "disconnected_entrance")
        building = next(invalid.iter_buildings())
        relation = next(
            item
            for item in self.valid_city.world_program.relations
            if item.relation_type == "accessible_from" and item.source_id == building.id
        )
        node = next(
            item for item in invalid.world_program.nodes if item.entity_id == building.id
        )
        patch = WorldPatch(
            id="cli_restore_access",
            scope_entity_id=building.id,
            operations=(
                PatchOperation("add_relation", building.id, value=to_primitive(relation)),
            ),
            expected_versions={building.id: node.version},
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = save_json(invalid, root / "invalid.json")
            patch_path = root / "patch.json"
            patch_path.write_text(json.dumps(to_primitive(patch)), encoding="utf-8")
            output_path = root / "repaired.json"
            report_path = root / "report.json"
            self.assertEqual(
                main(
                    [
                        "patch",
                        str(manifest_path),
                        "--patch",
                        str(patch_path),
                        "--output",
                        str(output_path),
                        "--report",
                        str(report_path),
                    ]
                ),
                0,
            )
            self.assertTrue(output_path.is_file())
            self.assertTrue(report_path.is_file())
            self.assertEqual(load_city(output_path).schema_version, "0.2.0")


if __name__ == "__main__":
    unittest.main()
