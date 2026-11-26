import unittest
from copy import deepcopy

from cityg.buildings import DEFAULT_BUILDING_CATALOG, BuildingSelector
from cityg.buildings.selector import BuildingSelectionContext
from cityg.geometry.compiler import GeometryCompiler
from cityg.planning.baseline import BaselineCityPlanner
from cityg.schemas import Bounds2D, CitySpec, ZoneSpec


class BuildingCatalogTests(unittest.TestCase):
    def test_catalog_has_distinct_signatures_and_valid_entries(self):
        self.assertGreaterEqual(len(DEFAULT_BUILDING_CATALOG), 88)
        self.assertGreaterEqual(
            len({item.massing_signature for item in DEFAULT_BUILDING_CATALOG}), 72
        )
        self.assertEqual(
            len({item.archetype_id for item in DEFAULT_BUILDING_CATALOG}),
            len(DEFAULT_BUILDING_CATALOG),
        )

    def test_selector_keeps_hard_constraints_and_is_reproducible(self):
        context = BuildingSelectionContext(
            building_id="building_007",
            function="commercial",
            floor_count=18,
            width_m=24.0,
            depth_m=32.0,
            highrise=True,
        )
        selector = BuildingSelector()
        first = selector.select(context)
        second = selector.select(context)
        self.assertEqual(first.archetype.archetype_id, second.archetype.archetype_id)
        self.assertIn("commercial", first.archetype.compatible_functions)
        self.assertTrue(first.archetype.min_floors <= context.floor_count <= first.archetype.max_floors)

    def test_planner_records_per_building_archetype_selection(self):
        spec = CitySpec(
            name="catalog_test",
            width_m=220.0,
            depth_m=220.0,
            building_count=12,
            rooms_per_floor=5,
            min_floors=2,
            max_floors=14,
            zones=(ZoneSpec("mixed", "mixed_use", 1.0),),
            seed=41,
        )
        city = BaselineCityPlanner().plan(spec)
        buildings = list(city.iter_buildings())
        self.assertTrue(all(item.metadata.get("archetype_id") for item in buildings))
        self.assertTrue(all(item.metadata.get("massing_signature") for item in buildings))
        self.assertTrue(all(item.metadata.get("facade_style_override") for item in buildings))

    def test_new_massing_grammar_compiles(self):
        spec = CitySpec(
            name="massing_test",
            width_m=160.0,
            depth_m=160.0,
            building_count=4,
            rooms_per_floor=4,
            min_floors=2,
            max_floors=3,
            zones=(ZoneSpec("mixed", "mixed_use", 1.0),),
            seed=3,
        )
        city = BaselineCityPlanner().plan(spec)
        first = next(city.iter_buildings())
        first.metadata["massing_style"] = "courtyard"
        scene = GeometryCompiler().compile(city)
        self.assertTrue(scene.primitives)
        self.assertTrue(any(item.metadata.get("massing_style") == "courtyard" for item in scene.primitives))

    def test_signature_variants_produce_distinct_normalized_massing(self):
        spec = CitySpec(
            name="signature_geometry",
            width_m=160.0,
            depth_m=160.0,
            building_count=1,
            rooms_per_floor=3,
            min_floors=2,
            max_floors=2,
            zones=(ZoneSpec("res", "residential", 1.0),),
            seed=5,
        )
        building = next(BaselineCityPlanner().plan(spec).iter_buildings())
        variants = [
            item for item in DEFAULT_BUILDING_CATALOG
            if item.massing_signature.startswith("bar_compact_")
        ]
        self.assertEqual(len(variants), 5)
        geometries = set()
        for archetype in variants:
            candidate = deepcopy(building)
            candidate.metadata["massing_style"] = archetype.massing_style
            candidate.metadata["massing_parameters"] = dict(archetype.massing_parameters)
            parts = GeometryCompiler._massing_parts(candidate)
            geometries.add(tuple(
                (
                    round(part["center_x"] - candidate.footprint.center.x, 3),
                    round(part["center_y"] - candidate.footprint.center.y, 3),
                    round(part["width"], 3),
                    round(part["depth"], 3),
                )
                for part in parts
            ))
        self.assertEqual(len(geometries), len(variants))


if __name__ == "__main__":
    unittest.main()
