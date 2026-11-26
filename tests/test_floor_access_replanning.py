import unittest
from dataclasses import replace

from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler
from cityg.planning import BaselineCityPlanner
from cityg.planning.floor_access_repair import repair_floor_access
from cityg.schemas import CitySpec, Point2D
from cityg.serialization import to_primitive
from cityg.transactions import fingerprint
from cityg.validation import CityValidator
from cityg.validation.walking_geometry import PedestrianScene


class FloorReplanningTests(unittest.TestCase):
    def city(self):
        return BaselineCityPlanner().plan(
            CitySpec(
                name="walk_6131",
                width_m=270,
                depth_m=255,
                building_count=6,
                rooms_per_floor=3,
                min_floors=2,
                max_floors=2,
                seed=6131,
                road_pattern="connected_grid",
            )
        )

    def exercise(self, city, building):
        f = building.floors[0]
        r = f.rooms[1]
        compiler = GeometryCompiler()
        before = fingerprint(city)

        def compile_floor(city):
            return to_primitive(compiler.compile(city, building_ids={building.id}))

        source = compile_floor(city)
        req = {
            "start": dict(building=building.id, space=r.id, level=0),
            "end": dict(building=building.id, space="entrance", level=0),
        }
        revised, trace = repair_floor_access(city, source, compiler, [], [req, req])
        self.assertEqual(fingerprint(city), before)
        self.assertEqual(len(trace), 1)
        if trace[0]["status"] == "accepted":
            b = next(b for b in revised.iter_buildings() if b.id == building.id)
            floor = b.floors[0]
            view = PedestrianScene(compile_floor(revised)).realized_floor(b, floor)
            self.assertEqual(view.audit(view.rooms[r.id])["status"], "verified")
            self.assertTrue(view.approach(view.rooms[r.id])[0])
            self.assertTrue(CityValidator().validate(revised).ok)
        return revised, trace[0]

    def test_u_shape_repair_and_access_only_scope(self):
        c = self.city()
        b = next(c.iter_buildings())
        _, row = self.exercise(c, b)
        self.assertEqual(row["choice"]["kind"], "extend_corridor_at_slab_turn")
        c.metadata["interior_scope"] = {
            "building_levels": {b.id: [0]},
            "access_dependency_levels": {b.id: [0]},
        }
        revised, row = self.exercise(c, b)
        self.assertIs(revised, c)
        self.assertEqual(row["reason"], "access_dependency_only")

    def test_create_return_corridor_with_fixed_north_entrance(self):
        c = self.city()
        b = list(c.iter_buildings())[3]
        f = b.floors[0]
        b.metadata.update(
            massing_style="bar",
            interior_layout_contract={"source": "new_scene_rectangular_interior_v1"},
        )
        corridor, left, right, _ = f.rooms
        edge = b.footprint.max_y - 10
        corridor.bounds = replace(corridor.bounds, max_y=edge)
        left.bounds = replace(left.bounds, min_y=edge, max_x=b.entrance.x + 3)
        right.bounds = replace(right.bounds, min_y=edge, min_x=left.bounds.max_x)
        for door in f.doors[:2]:
            door.position = Point2D(door.position.x, edge)
        f.objects.clear()
        for r in f.rooms:
            r.object_ids.clear()
        c.world_program = build_world_program(c, producer="return_corridor_fixture", seed=6131)
        _, row = self.exercise(c, b)
        self.assertEqual(row["choice"]["kind"], "turn_corridor_to_entrance")
        self.assertIn(row["choice"]["branch"]["passage_id"], row["witness"]["door_ids"])

    def blocked_door(self):
        from test_walking_requirements import crossing_fixture
        from cityg.schemas import InteriorObject

        city, bindings, req, _ = crossing_fixture()
        b = next(city.iter_buildings())
        f = b.floors[0]
        r = f.rooms[1]
        d = f.doors[1]
        chair = InteriorObject(
            r.id + "_blocking_chair",
            r.id,
            "office_chair",
            "office_chair",
            Point2D(d.position.x, d.position.y + 0.24),
            0.4,
            0.4,
            0.75,
        )
        f.objects.append(chair)
        r.object_ids.append(chair.id)
        city.world_program = build_world_program(city, producer="door_repair_fixture", seed=1)
        city.metadata["walking_contract"] = {"bindings": bindings, "requirements": [req]}
        return city, b

    def test_move_door_along_wall_without_moving_chair(self):
        city, b = self.blocked_door()
        revised, row = self.exercise(city, b)
        self.assertEqual(row["choice"]["kind"], "move_room_door")
        self.assertEqual(next(revised.iter_buildings()).floors[0].objects, b.floors[0].objects)

    def test_rejected_full_city_check_exports_original(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from cityg.services.openusd import OpenUSDBackend
        from cityg.serialization import load_city
        from cityg.planning.floor_access_repair import compile_with_access_replanning

        city = self.city()
        b, dest = list(city.iter_buildings())[:2]
        def end(building):
            return dict(building=building.id, space=building.floors[0].rooms[1].id, level=0)
        city.metadata["walking_contract"] = dict(bindings=[], requirements=[dict(start=end(b),
            end=end(dest), via_bridge=False, opposite_banks=False, max_distance_m=None)])

        def reject(draft, before, after):
            raise ValueError("existing design requirement lost")

        with TemporaryDirectory() as tmp:
            restored, _, trace = compile_with_access_replanning(
                city, OpenUSDBackend(), Path(tmp), select=None, preserve_requirements=reject
            )
            delivered = load_city(Path(tmp) / "city.json")
        self.assertIs(restored, city)
        self.assertEqual(trace[0]["status"], "rolled_back")
        self.assertEqual(next(delivered.iter_buildings()).floors[0].doors, b.floors[0].doors)
