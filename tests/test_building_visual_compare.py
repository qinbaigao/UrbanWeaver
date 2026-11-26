import json
import tempfile
import unittest
from pathlib import Path

from cityg.buildings.visual_compare import (
    BuildingVisualComparisonAgent,
    isolated_candidate_city,
    shortlist_building_candidates,
)
from cityg.planning.baseline import BaselineCityPlanner
from cityg.schemas import CitySpec, ZoneSpec


class FakeService:
    def __init__(self, payload):
        self.payload = payload

    def complete(self, messages, response_schema=None):
        return json.dumps(self.payload)


class BuildingVisualCompareTests(unittest.TestCase):
    def setUp(self):
        self.city = BaselineCityPlanner().plan(
            CitySpec(
                name="visual_compare_test",
                width_m=160,
                depth_m=160,
                building_count=2,
                rooms_per_floor=3,
                min_floors=3,
                max_floors=3,
                zones=(ZoneSpec("res", "residential", 1.0),),
                seed=19,
            )
        )
        self.building = next(self.city.iter_buildings())

    def test_shortlist_keeps_current_and_adds_distinct_compatible_signatures(self):
        candidates = shortlist_building_candidates(self.building, max_candidates=4)
        self.assertEqual(len(candidates), 4)
        self.assertEqual(candidates[0].archetype_id, self.building.metadata["archetype_id"])
        self.assertTrue(all(
            self.building.function in item.selection.archetype.compatible_functions
            for item in candidates
        ))
        self.assertEqual(
            len({item.selection.archetype.massing_signature for item in candidates}),
            len(candidates),
        )

    def test_isolated_preview_does_not_mutate_canonical_city(self):
        candidate = shortlist_building_candidates(self.building, max_candidates=2)[1]
        preview = isolated_candidate_city(self.city, self.building.id, candidate)
        self.assertEqual(len(list(preview.iter_buildings())), 1)
        self.assertEqual(
            next(preview.iter_buildings()).metadata["archetype_id"],
            candidate.archetype_id,
        )
        self.assertEqual(
            next(preview.iter_buildings()).metadata["massing_style"],
            candidate.selection.archetype.massing_style,
        )
        self.assertNotEqual(
            next(preview.iter_buildings()).metadata["archetype_id"],
            self.building.metadata["archetype_id"],
        )
        self.assertEqual(len(list(self.city.iter_buildings())), 2)

    def test_visual_agent_requires_exact_panel_bindings(self):
        candidates = shortlist_building_candidates(self.building, max_candidates=2)
        ranking = [
            {
                "panel_id": item.panel_id,
                "archetype_id": item.archetype_id,
                "rank": index + 1,
                "semantic_fit": 0.9 - index * 0.1,
                "visual_fit": 0.8,
                "context_fit": 0.75,
                "confidence": 0.86,
                "reason": "compatible and visually legible",
                "visible_risks": [],
            }
            for index, item in enumerate(candidates)
        ]
        service = FakeService({
            "building_id": self.building.id,
            "selected_archetype_id": candidates[0].archetype_id,
            "confidence": 0.86,
            "comparison_summary": "Panel A best balances the constraints.",
            "ranking": ranking,
        })
        with tempfile.TemporaryDirectory() as directory:
            sheet = Path(directory) / "sheet.png"
            sheet.write_bytes(b"test image placeholder")
            result = BuildingVisualComparisonAgent(service).compare(
                self.building, candidates, sheet
            )
        self.assertTrue(result.available)
        self.assertEqual(result.selected_archetype_id, candidates[0].archetype_id)
        self.assertEqual(len(result.ranking), 2)

    def test_visual_agent_rejects_invented_archetype(self):
        candidates = shortlist_building_candidates(self.building, max_candidates=2)
        service = FakeService({
            "building_id": self.building.id,
            "selected_archetype_id": "invented_archetype",
            "confidence": 0.99,
            "comparison_summary": "invalid",
            "ranking": [],
        })
        with tempfile.TemporaryDirectory() as directory:
            sheet = Path(directory) / "sheet.png"
            sheet.write_bytes(b"test image placeholder")
            result = BuildingVisualComparisonAgent(service).compare(
                self.building, candidates, sheet
            )
        self.assertFalse(result.available)
        self.assertIn("outside the contact sheet", result.error)


if __name__ == "__main__":
    unittest.main()
