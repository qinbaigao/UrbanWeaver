import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cityg.geometry.geography import primitive_footprint
from cityg.geometry.model import GeometryPrimitive, Vec3
from cityg.geometry.pedestrian_network import connect_actual_doors
from cityg.geometry.vegetation_clearance import tree_bounds
from test_walking_requirements import crossing_fixture


class WalkNetworkTests(unittest.TestCase):
    def test_portable_alias_still_checks_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "portable_renamed_mesh.glb"
            path.write_bytes(b"sample")
            bounds = [-0.1, -0.1, 0.1, 0.1]
            profile = {"bounds": [bounds], "sha256": hashlib.sha256(b"sample").hexdigest()}
            with patch(
                "cityg.geometry.vegetation_clearance._profiles",
                return_value={"sample.glb": profile},
            ):
                self.assertEqual(tree_bounds(path, 1, 2), bounds)
                path.write_bytes(b"replacement")
                self.assertIsNone(tree_bounds(path, 1, 2))

    def test_frontage_only_opens_at_real_door_on_perimeter(self):
        city, _, _, _ = crossing_fixture()
        building = next(city.iter_buildings())
        floor = building.floors[0]
        door = next(d for d in floor.doors if d.room_b_id is None)

        def box(owner, name, x, y, dx, dy, kind):
            return GeometryPrimitive(
                name, owner, "box", Vec3(x, y, 0), Vec3(dx, dy, 0.1), 0, kind, "concrete", "roads"
            )

        for x, expected in (
            (29.93, "connected_to_compiled_entrance"),
            (28, "no_clear_frontage_strip"),
        ):
            with self.subTest(x=x):
                slab = box(floor.id, "plate", 25, 25, 10, 10, "floor_slab")
                portal = box(door.id, "door", x, 25, 0.14, 1.2, "door")
                path = box("road", "path", 34, 25, 3, 1.4, "frontage_connector")
                path.metadata["building_id"] = building.id
                items = [slab, portal, path]
                result = connect_actual_doors(city, items)
                self.assertEqual(result[building.id], expected)
                thresholds = [p for p in items if p.semantic_class == "entrance_threshold"]
                if x == 28:
                    self.assertFalse(thresholds)
                else:
                    self.assertEqual(len(thresholds), 1)
                    self.assertLess(primitive_footprint(thresholds[0]).area, 0.3)
                    self.assertTrue(thresholds[0].collision_enabled)
