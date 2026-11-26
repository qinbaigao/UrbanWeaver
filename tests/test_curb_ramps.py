import math
import unittest

from cityg.geometry.crossings import connect_crossings
from cityg.geometry.geography import primitive_footprint
from cityg.geometry.model import GeometryPrimitive, Vec3
from cityg.polygons import geos


def block(name, x, y, length, width, kind, height):
    return GeometryPrimitive(
        name,
        "road",
        "box",
        Vec3(x, y, height / 2),
        Vec3(length, width, height),
        0,
        kind,
        "concrete",
        "roads",
    )


def crossing():
    stripes = []
    for i in range(6):
        p = block(f"stripe_{i}", (i - 2.5) * 0.72, 0, 0.48, 9.1, "crosswalk", 0.025)
        p.metadata["junction_side"] = "start"
        stripes.append(p)
    return stripes + [
        block("left", 0, 6.5, 30, 3, "sidewalk", 0.15),
        block("right", 0, -6.5, 30, 3, "sidewalk", 0.15),
        block("raised_median", 0, 0, 30, 1, "road_median", 0.12),
        block("curb", 0, 5.1, 30, 0.2, "curb", 0.18),
    ]


class CrossingTests(unittest.TestCase):
    def test_bilateral_slopes_and_median_opening(self):
        pieces = crossing()
        self.assertEqual(connect_crossings(pieces)["curb_ramp_pairs"], 1)
        ramps = [p for p in pieces if p.semantic_class == "curb_ramp"]
        self.assertEqual(len(ramps), 2)
        passage = next(
            geos().Polygon(p.metadata["crossing_passage_xy"])
            for p in pieces
            if "crossing_passage_xy" in p.metadata
        )
        for p in ramps:
            self.assertTrue(p.collision_enabled)
            self.assertEqual(p.primitive_type, "path_mesh")
            self.assertAlmostEqual(p.size.y, 1.8)
            top = [p.center.z + v[2] * p.size.z for v in p.metadata["mesh_vertices"]]
            self.assertAlmostEqual(max(top), 0.15)
            self.assertGreater(passage.intersection(primitive_footprint(p)).area, 0)
            for slab in pieces:
                if slab.semantic_class in ("curb", "sidewalk"):
                    self.assertLess(
                        primitive_footprint(p).intersection(primitive_footprint(slab)).area, 1e-8
                    )
        median = next(p for p in pieces if p.semantic_class == "road_median")
        self.assertLess(primitive_footprint(median).intersection(passage).area, 1e-8)
        domain = (
            geos()
            .union_all(
                [passage]
                + [
                    primitive_footprint(p)
                    for p in pieces
                    if p.semantic_class in ("curb_ramp", "sidewalk")
                ]
            )
            .buffer(-0.3)
        )
        self.assertTrue(domain.covers(geos().LineString([(-0.36, -7), (-0.36, 7)])))

    def test_oblique_road_keeps_both_slopes_aligned(self):
        pieces = crossing()
        az = math.radians(31)
        for p in pieces:
            x, y = p.center.x, p.center.y
            p.center = Vec3(92 + x * math.cos(az) - y * math.sin(az),
                            44 + x * math.sin(az) + y * math.cos(az), p.center.z)
            p.rotation_z_deg = 31
        self.assertEqual(connect_crossings(pieces)["curb_ramp_pairs"], 1)
        passage = next(geos().Polygon(p.metadata["crossing_passage_xy"])
                       for p in pieces if "crossing_passage_xy" in p.metadata)
        for p in pieces:
            if p.semantic_class == "curb_ramp":
                self.assertGreater(passage.intersection(primitive_footprint(p)).area, 0.01)

    def test_missing_landing_creates_no_dead_end(self):
        pieces = [p for p in crossing() if p.id != "right"]
        self.assertEqual(connect_crossings(pieces)["crossings_omitted_no_landing"], 1)
        self.assertEqual({p.id for p in pieces}, {"left", "curb", "raised_median"})
