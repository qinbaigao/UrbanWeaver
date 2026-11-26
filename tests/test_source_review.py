import unittest

from scripts.prepare_source_review import canonicalize_review


class SourceReviewOrientationTests(unittest.TestCase):
    def test_negative_front_rotates_geometry_and_keeps_up(self):
        document = {"asset": {"version": "2.0"}, "nodes": [{}], "scenes": [{"nodes": [0]}]}
        bounds = {"min": [-1, -2, -3], "max": [1, 2, 3], "extent": [2, 4, 6]}
        for front, sign in (("+Z", 1), ("-Z", -1)):
            result = canonicalize_review(document, bounds, "test", front)
            matrix = result["nodes"][-1]["matrix"]
            self.assertEqual(matrix[8], sign / 6)
            self.assertEqual(matrix[1], sign / 2)
            self.assertEqual(matrix[6], 1 / 4)
        self.assertEqual(len(document["nodes"]), 1)

    def test_rejects_unimplemented_axis(self):
        with self.assertRaises(ValueError):
            canonicalize_review({}, {}, "test", "+X")
