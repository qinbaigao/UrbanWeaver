import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cityg.geometry.vegetation_clearance import tree_bounds
from cityg.validation.walking_geometry import footprint, pedestrian_obstacle
from cityg.walking_requirements import assess
from test_walking_requirements import crossing_fixture


class EntranceClearanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.city, cls.bindings, cls.req, cls.scene = crossing_fixture()
        cls.connector = next(p for p in cls.scene["primitives"] if p["semantic_class"] == "frontage_connector")

    def barrier(self, kind, z, height):
        c = self.connector
        return dict(c, id="obstacle", semantic_class=kind, metadata={},
                    center=dict(c["center"], z=z), size={"x": .35, "y": c["size"]["y"] + 1, "z": height})

    def route_with(self, obstacle):
        scene = dict(self.scene, primitives=[*self.scene["primitives"], obstacle])
        return assess(self.city, self.bindings, [self.req], scene)[0]["status"]

    def test_overhanging_crown_and_low_physical_barriers(self):
        self.assertEqual(self.route_with(self.barrier("street_tree_canopy", 4, 2)), "satisfied")
        for kind in ("frontage_planter", "parcel_shrub_asset", "street_tree_trunk",
                     "street_tree_canopy", "street_light", "street_tree_asset"):
            with self.subTest(kind=kind):
                self.assertEqual(self.route_with(self.barrier(kind, .6, 1.2)), "unverified")

    def test_compiler_keeps_furniture_clear_of_the_frontage(self):
        from shapely.geometry import LineString
        from cityg.geometry.vegetation_clearance import PEDESTRIAN_RADIUS

        scene = self.scene
        self.assertGreater(scene["metadata"]["streetscape_stats"]["sidewalk_assets_relocated"], 0)
        # The fixture road runs east-west; the curb is four metres inward
        # from the sidewalk end of each north-side connector.
        for connector in (p for p in scene["primitives"] if p["semantic_class"] == "frontage_connector"):
            x = connector["center"]["x"]
            _, edge, _, door = footprint(connector).bounds
            strip = LineString([(x, edge - 4), (x, door)]).buffer(connector["size"]["y"] / 2, cap_style="flat")
            for p in scene["primitives"]:
                if p["semantic_class"] in {"street_light", "frontage_planter", "frontage_vegetation",
                                           "frontage_sign", "bench", "street_bin", "street_tree_trunk",
                                           "street_tree_canopy"}:
                    with self.subTest(connector=connector["id"], item=p["id"]):
                        self.assertTrue(pedestrian_obstacle(p).buffer(PEDESTRIAN_RADIUS).disjoint(strip))

    def test_profile_height_rotation_and_content_identity(self):
        tree = self.barrier("street_tree_asset", 2, 4)
        tree.update(center={"x": 10, "y": 20, "z": 2}, size={"x": 4, "y": 2, "z": 4}, rotation_z_deg=90)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.glb"
            path.write_bytes(b"original")
            data = {path.name: {"sha256": hashlib.sha256(b"original").hexdigest(),
                                "bounds": [[.1, -.1, .2, .1]] * 3 + [[-.5, -.5, .5, .5]]}}
            tree["metadata"]["asset_geometry_path"] = str(path)
            with patch("cityg.geometry.vegetation_clearance._profiles", return_value=data):
                self.assertEqual(pedestrian_obstacle(tree).bounds, (9.8, 20.4, 10.2, 20.8))
                self.assertEqual(tree_bounds(path, .5, 1), [-.5, -.5, .5, .5])
                path.write_bytes(b"different mesh")
                self.assertTrue(pedestrian_obstacle(tree).equals(footprint(tree)))
                path.unlink()
                self.assertTrue(pedestrian_obstacle(tree).equals(footprint(tree)))
