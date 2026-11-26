import unittest
from scripts.city_render.landscape_math import backdrop_height, outside_distance, top_ray_vertical


class LandscapeMathTests(unittest.TestCase):
    def test_city_and_river_bed_are_not_covered(self):
        bounds=(-300,1700,-500,1500)
        for x,y in ((-300,-500),(1700,1500),(600,500),(1750,1500)):
            self.assertEqual(backdrop_height(x,y,bounds),-8)

    def test_distant_height_is_bounded_and_continuous(self):
        bounds=(0,100,0,100)
        self.assertEqual(outside_distance(50,50,bounds),0)
        self.assertEqual(outside_distance(150,100,bounds),50)
        self.assertAlmostEqual(backdrop_height(220,50,bounds),backdrop_height(220.001,50,bounds),places=6)
        self.assertLess(backdrop_height(2000,2000,bounds),40)

    def test_approved_camera_points_below_horizon(self):
        m=[0.0]*16;m[6]=.8509977017896591;m[10]=.525169412236393
        self.assertLess(top_ray_vertical({'matrix_world':m,'vertical_fov_deg':46}),-.1)
