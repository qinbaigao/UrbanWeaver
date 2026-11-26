"""Ground-floor regression cases with explicit compiled slab and portal coordinates."""

import unittest
from types import SimpleNamespace

from cityg.schemas import Bounds2D, Door, Floor, Point2D, Room
from cityg.validation.walking_geometry import PedestrianScene


def box(id, owner, kind, x, y, width, depth):
    return dict(
        id=id,
        owner_id=owner,
        semantic_class=kind,
        primitive_type="box",
        layer_id="floor:F0",
        center=dict(x=x, y=y, z=0.8 if kind != "floor_slab" else 0),
        size=dict(x=width, y=depth, z=1.6 if kind != "floor_slab" else 0.12),
    )


def fixture(gap=False, extra_door=False, obstruction=False, misplaced_exit=False, private=False):
    # Concave L, inside a much larger rectangular planned corridor. The route
    # from (2,5) to (8,1) must turn south before heading east.
    room = Room("R", "Office", "office", Bounds2D(0, 2, 2, 6))
    corridor = Room("C", "Circulation", "office" if private else "corridor", Bounds2D(2, 0, 8, 6))
    floor = Floor("F0", 0, 0, 3, [room, corridor])
    building = SimpleNamespace(id="B", metadata={}, footprint=Bounds2D(0, 0, 8, 6))
    items = [
        box("wing", "F0", "floor_slab", 2, 4, 4, 4),
        box("base", "F0", "floor_slab", 5, 0.9 if gap else 1, 6, 1.8 if gap else 2),
    ]
    nodes = [{"id": "nav_R", "position": dict(x=1, y=5)}, {"id": "nav_C"}, {"id": "nav_entrance_B"}]
    edges = []

    def door(id, a, b, x, y):
        floor.doors.append(Door(id, a, b, Point2D(x, y), 1.0))
        items.append(box(id, id, "open_passage", x, y, 0.1, 1.0))
        edges.append(
            dict(
                id="nav_door_" + id,
                traversal="door",
                width_m=1.0,
                start_node_id="nav_" + a,
                end_node_id="nav_" + b if b else "nav_entrance_B",
            )
        )

    if extra_door:
        door("bad", "R", "C", 2, 7)
    door("from_room", "R", "C", 2, 5)
    door("exit", "C", None, 7 if misplaced_exit else 8, 1)
    if obstruction:
        items.append(box("wall", "F0", "interior_wall", 5.5, 1, 0.2, 2))
    scene = PedestrianScene(dict(primitives=items, navigation=dict(nodes=nodes, edges=edges)))
    return scene.realized_floor(building, floor), room


class FloorAccessTests(unittest.TestCase):
    def test_concave_path_bends_inside_the_realized_corridor(self):
        audit, room = fixture()
        row = audit.audit(room)["doors"][0]
        self.assertEqual(row["status"], "verified")
        self.assertEqual(row["door_ids"], ["from_room", "exit"])
        points = row["polyline_xy_m"]
        _, corridor = audit.space(audit.rooms["C"])
        self.assertFalse(corridor.covers(audit.s.LineString([points[0], points[-1]])))
        self.assertTrue(corridor.covers(audit.s.LineString(points)))
        self.assertEqual(audit.approach(room)[1], row["door_ids"])

    def test_every_door_checked_even_when_an_alternative_works(self):
        audit, room = fixture(extra_door=True)
        report = audit.audit(room)
        self.assertEqual(report["status"], "unverified")
        self.assertEqual([r["status"] for r in report["doors"]], ["unverified", "verified"])
        self.assertEqual(audit.approach(room)[1][0], "from_room")

    def test_reason_distinguishes_topology_clearance_and_nonpublic_routes(self):
        for args, code in [
            ({"gap": True}, "floor_plate_disconnected"),
            ({"obstruction": True}, "walkable_corridor_disconnected"),
            ({"misplaced_exit": True}, "exit_inside_floor_plate"),
            ({"private": True}, "no_public_circulation"),
        ]:
            with self.subTest(code=code):
                audit, room = fixture(**args)
                result = audit.audit(room)["doors"][0]
                self.assertEqual(result["failures"][0]["code"], code)
                with self.assertRaises(ValueError):
                    audit.approach(room)

    def test_room_view_cap_is_not_a_floor_wall(self):
        audit, room = fixture(obstruction=True)
        wall = next(p for p in audit.scene.primitives if p["id"] == "wall")
        wall.update(collision_enabled=False, metadata={"viewer_room_only": True})
        self.assertEqual(audit.audit(room)["status"], "verified")

    def test_shell_opens_only_at_each_actual_ground_entrance(self):
        from cityg.geometry.compiler import GeometryCompiler
        from cityg.geometry.model import GeometryScene
        from cityg.validation.walking_geometry import footprint
        from cityg.serialization import to_primitive
        from cityg.polygons import geos

        compiler = GeometryCompiler()
        bounds = Bounds2D(2, 4, 12, 19)
        room = Room("C", "Corridor", "corridor", bounds)
        building = SimpleNamespace(id="B", footprint=bounds)
        prototype = SimpleNamespace(wall_thickness_m=0.24, facade_material="brick")
        centers = [(2, 10), (12, 10), (7, 4), (7, 19)]
        for index, center in enumerate(centers):
            with self.subTest(side=index):
                floor = Floor("F", 0, 0, 3, [room], [Door("entry", "C", None, Point2D(*center), 1.2)])
                scene = GeometryScene("test", "z_up")
                compiler._add_exterior_walls(building, floor, prototype, scene)

                def cut(height):
                    return geos().union_all(
                        [
                            footprint(to_primitive(p))
                            for p in scene.primitives
                            if abs(p.center.z - height) < p.size.z / 2
                        ]
                    )

                low, high = cut(1), cut(2.7)
                # Probe half a wall thickness inward, avoiding numeric error on the outer boundary.
                for i, (x, y) in enumerate(centers):
                    point = geos().Point(
                        x + (0.1 if i == 0 else -0.1 if i == 1 else 0),
                        y + (0.1 if i == 2 else -0.1 if i == 3 else 0),
                    )
                    self.assertEqual(low.covers(point), i != index)
                    self.assertTrue(high.covers(point))
