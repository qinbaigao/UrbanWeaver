import unittest
from types import SimpleNamespace

from scripts.city_render.background import configure_background


class BackgroundTests(unittest.TestCase):
    def scene(self):
        return SimpleNamespace(render=SimpleNamespace(image_settings=SimpleNamespace()),
                               objects={name: SimpleNamespace(hide_render=False)
                                        for name in ('distant_land_backdrop',
                                                     'asset_instances_distant_land', 'city_ground')})

    def test_transparent_preserves_city(self):
        scene = self.scene()
        report = configure_background(scene, True)
        self.assertEqual(scene.render.image_settings.color_mode, 'RGBA')
        self.assertTrue(scene.render.film_transparent)
        self.assertEqual(len(report['hidden_display_backdrops']), 2)
        self.assertFalse(scene.objects['city_ground'].hide_render)

    def test_cached_scene_can_return_to_opaque(self):
        scene = self.scene()
        configure_background(scene, True)
        configure_background(scene, False)
        self.assertFalse(scene.render.film_transparent)
        self.assertEqual(scene.render.image_settings.color_mode, 'RGB')
        self.assertFalse(scene.objects['distant_land_backdrop'].hide_render)

    def test_scene_without_decorative_backdrop(self):
        scene = self.scene()
        scene.objects = {}
        self.assertEqual(configure_background(scene, True)['hidden_display_backdrops'], [])
