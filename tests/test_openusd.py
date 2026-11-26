import json
import tempfile
import unittest
from pathlib import Path

from cityg.geometry import GeometryCompiler
from cityg.pipeline import GenerationPipeline
from cityg.planning import BaselineCityPlanner
from cityg.schemas import CitySpec
from cityg.services import OpenUSDBackend
from cityg.usd import UsdaPackageValidator, UsdaWriter


class OpenUSDBackendTests(unittest.TestCase):
    def test_incremental_repartition_replaces_edges_even_for_stable_room_ids(self):
        from cityg.subtree_transactions import FloorSubtreePlanner
        from cityg.geometry.incremental import merge_building_scene
        city = BaselineCityPlanner().plan(CitySpec(building_count=2, min_floors=2,
            max_floors=2, rooms_per_floor=4, seed=19))
        building = next(city.iter_buildings()); floor = building.floors[0]
        before = GeometryCompiler().compile(city)
        changed = FloorSubtreePlanner().replace(city, floor.id,
            {'room_count': 8, 'room_functions': ['office']}).city
        compiler = GeometryCompiler()
        subset = compiler.compile(changed, building_ids={building.id})
        merged, _ = merge_building_scene(changed, before, subset, {building.id}, previous_city=city)
        full = compiler.compile(changed)
        self.assertEqual(sorted(merged.navigation.edges, key=lambda x:x.id),
                         sorted(full.navigation.edges, key=lambda x:x.id))
        machines = {m.id for m in merged.state_machines}
        self.assertTrue(all(not e.condition_state_machine_id or e.condition_state_machine_id in machines
                            for e in merged.navigation.edges))

    def test_backend_writes_relocatable_layered_package(self):
        spec = CitySpec(
            name="usd_test",
            width_m=180,
            depth_m=160,
            building_count=2,
            min_floors=2,
            max_floors=2,
            rooms_per_floor=2,
            seed=6,
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            result = GenerationPipeline(simulation_backend=OpenUSDBackend()).run(spec, output)
            self.assertTrue(result.ok)
            root = output / "usd" / "city.usda"
            self.assertTrue(root.is_file())
            report = UsdaPackageValidator().validate(root)
            self.assertTrue(report.ok, report.to_dict())
            self.assertGreater(report.metrics["payload_arc_count"], 0)
            self.assertGreater(report.metrics["reference_arc_count"], 0)
            self.assertGreater(report.metrics["instanceable_prim_count"], 0)
            self.assertEqual(report.metrics["physics_scene_count"], 1)
            self.assertNotIn("@/", root.read_text(encoding="utf-8"))
            self.assertIn('def PhysicsScene "PhysicsScene"', root.read_text(encoding="utf-8"))
            roads = (output / "usd" / "layers" / "roads.usda").read_text(encoding="utf-8")
            self.assertIn('prepend apiSchemas = ["PhysicsCollisionAPI"]', roads)
            self.assertIn('token visibility = "invisible"', roads)
            metrics = json.loads((output / "compile_metrics.json").read_text())
            self.assertEqual(metrics["outdoor_to_room_path_ratio"], 1.0)
            self.assertEqual(metrics["structural_physics_errors"], 0)

    def test_active_floor_package_keeps_city_shells_and_one_interior(self):
        spec = CitySpec(
            name="active_floor_test",
            width_m=220,
            depth_m=180,
            building_count=3,
            min_floors=2,
            max_floors=2,
            rooms_per_floor=3,
            seed=12,
        )
        city = BaselineCityPlanner().plan(spec)
        scene = GeometryCompiler().compile(city)
        active_floor = next(city.iter_buildings()).floors[0]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            UsdaWriter().write(city, scene, output, active_floor_id=active_floor.id)
            report = UsdaPackageValidator().validate(output / "city.usda")
            self.assertTrue(report.ok, report.to_dict())
            self.assertEqual(len(list((output / "layers" / "floors").glob("*.usda"))), 1)
            self.assertEqual(
                len(list((output / "layers" / "buildings").glob("*_interior.usda"))),
                1,
            )
            district_text = "".join(
                path.read_text(encoding="utf-8")
                for path in (output / "layers" / "districts").glob("*.usda")
            )
            self.assertEqual(district_text.count("prepend payload"), 1)
            self.assertEqual(district_text.count('def Xform "Shell"'), 3)

    def test_incremental_room_change_reuses_other_buildings_and_matches_full_geometry(self):
        spec = CitySpec(
            name="incremental_test",
            width_m=220,
            depth_m=180,
            building_count=3,
            min_floors=2,
            max_floors=2,
            rooms_per_floor=3,
            seed=19,
        )
        city = BaselineCityPlanner().plan(spec)
        backend = OpenUSDBackend()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base_dir = root / "base"
            incremental_dir = root / "incremental"
            full_dir = root / "full_after"
            backend.compile(city, base_dir)
            target_building = next(city.iter_buildings())
            target_room = target_building.floors[0].rooms[0]
            target_room.metadata["incremental_test_revision"] = 1
            backend.compile_incremental(
                city,
                incremental_dir,
                base_dir,
                [target_room.id],
            )
            backend.compile(city, full_dir)
            inc_manifest = json.loads(
                (incremental_dir / "geometry_manifest.json").read_text()
            )
            full_manifest = json.loads(
                (full_dir / "geometry_manifest.json").read_text()
            )
            self.assertEqual(
                sorted(inc_manifest["primitives"], key=lambda item: item["id"]),
                sorted(full_manifest["primitives"], key=lambda item: item["id"]),
            )
            incremental = json.loads(
                (incremental_dir / "incremental_manifest.json").read_text()
            )
            self.assertEqual(incremental["affected_buildings"], [target_building.id])
            self.assertEqual(incremental["recompiled_building_count"], 1)
            self.assertEqual(incremental["reused_building_count"], 2)
            self.assertGreater(incremental["reused_primitive_count"], 0)


if __name__ == "__main__":
    unittest.main()
