import unittest

from cityg.facade_assets import FacadeAssetIndex, classify_facade_asset


def _classify(name: str, *, source_asset_id: str = "test") -> dict:
    return classify_facade_asset(
        name,
        source_asset_id=source_asset_id,
        source_id="test_pack",
        style="photoreal_weathered_pbr",
        realism_level="photoreal_pbr",
        source_front_axis="+Z",
        front_axis_confidence="medium",
        extent_xyz=(1.0, 2.0, 0.2),
        selector={"kind": "whole_asset"},
        geometry_path="assets/incoming/test.glb",
        license_id="CC0-1.0",
        source_url="https://example.com",
        quality_score=0.9,
        technical={"texture_count": 3, "triangle_count": 100},
    )


class FacadeAssetClassificationTest(unittest.TestCase):
    def test_balcony_is_repeatable_residential_facade_bay(self):
        record = _classify("building-window-balcony")
        self.assertEqual(record["semantic_type"], "balcony_bay")
        self.assertEqual(record["placement"]["mount_surface"], "wall")
        self.assertTrue(record["repeatability"]["repeatable"])
        self.assertIn("residential", record["compatible_building_functions"])

        awning = _classify("building-window-awnings")
        self.assertEqual(awning["semantic_type"], "awning_module")

    def test_factory_shutter_is_ground_level_industrial_service_bay(self):
        record = _classify(
            "dado_garage_door_01", source_asset_id="modular_factory_facade"
        )
        self.assertEqual(record["semantic_type"], "service_door_bay")
        self.assertEqual(record["compatible_facade_zones"], ["ground", "podium"])
        self.assertIn("industrial", record["compatible_building_functions"])

    def test_roof_and_fire_escape_use_distinct_mount_contracts(self):
        roof = _classify("roof-flat-awning-a")
        escape = _classify("modular_fire_escape_stairs")
        self.assertEqual(roof["semantic_type"], "awning_module")
        self.assertEqual(roof["placement"]["mount_surface"], "wall")
        self.assertEqual(escape["repeatability"]["mode"], "vertical_stack")
        self.assertEqual(escape["placement"]["frontage_roles"], ["rear", "service"])

    def test_reference_building_is_not_a_placement_candidate(self):
        record = _classify("building-sample-tower-a")
        self.assertEqual(record["semantic_type"], "reference_building")
        self.assertEqual(record["selection_status"], "reference_only")

    def test_compound_roof_and_barricade_names_keep_primary_semantics(self):
        self.assertEqual(_classify("roof-slanted-window")["semantic_type"], "roof_module")
        self.assertEqual(
            _classify("barricade-doorway-a")["semantic_type"],
            "opening_security_panel",
        )
        self.assertEqual(_classify("border-high")["semantic_type"], "facade_band")

    def test_index_filters_before_progressive_agent_disclosure(self):
        balcony = _classify("building-window-balcony")
        shutter = _classify(
            "dado_garage_door_01", source_asset_id="modular_factory_facade"
        )
        index = FacadeAssetIndex(
            {
                "schema_version": "cityg.facade_asset_annotations.v1",
                "summary": {"asset_count": 2},
                "assets": [balcony, shutter],
            }
        )
        result = index.candidates(
            "garage door",
            building_function="industrial",
            facade_zone="ground",
            realism_level="photoreal_pbr",
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["semantic_type"], "service_door_bay")
        self.assertNotIn("technical", result[0])


if __name__ == "__main__":
    unittest.main()
