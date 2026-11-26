import unittest
from scripts.city_render.facade_variation import facade_seeds, stable_fraction


class FacadeVariationTest(unittest.TestCase):
    def test_same_window_glass_backing_and_frame_share_seed(self):
        p = {'id': 'building_004_floor_03_north_bay_06', 'layer_id': 'shell:building_004'}
        expected = facade_seeds(p)
        for suffix in ('_frame', '_backing'):
            self.assertEqual(expected, facade_seeds({**p, 'id': p['id'] + suffix}))

    def test_building_age_is_shared_but_windows_vary(self):
        a = facade_seeds({'id': 'window_a', 'layer_id': 'shell:building_001'})
        b = facade_seeds({'id': 'window_b', 'layer_id': 'shell:building_001'})
        c = facade_seeds({'id': 'window_b', 'layer_id': 'shell:building_002'})
        self.assertEqual(a[1], b[1]); self.assertNotEqual(a[0], b[0])
        self.assertNotEqual(b[1], c[1])
        self.assertTrue(all(0 <= v < 1 for v in a + b + c))

    def test_seed_is_stable(self):
        self.assertEqual(stable_fraction('building_001'), stable_fraction('building_001'))
