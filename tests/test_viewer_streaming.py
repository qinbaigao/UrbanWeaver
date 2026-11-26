import copy
import json
import unittest
from unittest.mock import patch

from cityg.viewer_streaming import partition_viewer_files


def fixture(interiors=False):
    city = {'id': 'city', 'world_program': {'large': 'simulation-only'}, 'districts': [
        {'id': 'd', 'parcels': [{'id': 'parcel', 'buildings': [
            {'id': 'b', 'floors': [{'id': 'f', 'level': 0, 'rooms': [{'id': 'r'}],
                                    'objects': [{'id': 'o', 'room_id': 'r'}], 'doors': []}]}]}]}]}
    primitives = []
    for i, (owner, layer, semantic) in enumerate([
        ('b', 'shell', 'exterior_wall'), ('b', 'shell', 'facade_asset_window'),
        ('f', 'floor', 'floor_slab'), ('r', 'floor', 'interior_wall'),
        ('o', 'floor', 'furniture_table'), ('road', 'roads', 'road_surface'),
    ]):
        primitives.append({'id': f'p{i}', 'owner_id': owner, 'layer_id': layer,
                           'semantic_class': semantic, 'primitive_type': 'box',
                           'center': {'x': -50+i*3, 'y': 10, 'z': 1},
                           'size': {'x': 3, 'y': 4, 'z': 2}, 'rotation_z_deg': 45,
                           'metadata': {}})
    geometry = {'primitives': primitives, 'metadata': {'interiors_compiled': interiors},
                'materials': [{'id': 'color', 'display_color': [1, .5, 0]}],
                'layers': [{'id': 'shell', 'layer_type': 'building_shell'},
                           {'id': 'floor', 'layer_type': 'floor'}, {'id': 'roads', 'layer_type': 'roads'}]}
    files = {'geometry_manifest.json': json.dumps(geometry).encode(), 'city.json': json.dumps(city).encode()}
    return files, geometry, city


class StreamingViewerTests(unittest.TestCase):
    def test_small_scene_unchanged(self):
        files, _, _ = fixture()
        self.assertIs(partition_viewer_files(files), files)

    def test_detail_partition_is_lossless_unique_and_bounded(self):
        files, original, _ = fixture()
        before = copy.deepcopy(files)
        with patch('cityg.viewer_streaming.CHUNK_ITEMS', 2):
            result = partition_viewer_files(files, force=True)
        header = json.loads(result['geometry_manifest.json'])
        chunks = header['streaming']['chunks']
        reconstructed = [p for c in chunks for p in json.loads(result[c['file']])['primitives']]
        self.assertEqual(sorted(reconstructed, key=lambda p: p['id']), original['primitives'])
        self.assertEqual(len({p['id'] for p in reconstructed}), len(reconstructed))
        self.assertTrue(all(c['count'] <= 2 for c in chunks))
        self.assertEqual(files, before)
        self.assertEqual(header['materials'], original['materials'])
        for c in chunks:
            self.assertEqual(c['bytes'], len(result[c['file']]))
            self.assertEqual(c['bounds3d'], [*c['bounds'][:2], 0, *c['bounds'][2:], 2])
            if any(owner in c['owner_ids'] for owner in ['b', 'f', 'r', 'o']):
                self.assertEqual((c['scope'], c['scope_id']), ('building', 'b'))

    def test_city_projection_keeps_bindings_without_fake_interiors(self):
        files, _, _ = fixture()
        result = partition_viewer_files(files, force=True)
        city = json.loads(result['city.json'])
        self.assertNotIn('world_program', city)
        floor = city['districts'][0]['parcels'][0]['buildings'][0]['floors'][0]
        self.assertEqual(floor['id'], 'f')
        self.assertNotIn('rooms', floor)
        files, _, _ = fixture(interiors=True)
        result = partition_viewer_files(files, force=True)
        floor = json.loads(result['city.json'])['districts'][0]['parcels'][0]['buildings'][0]['floors'][0]
        self.assertEqual(floor['rooms'], [{'id': 'r'}])

    def test_overview_is_labelled_subset_and_packaging_is_idempotent(self):
        files, original, _ = fixture()
        result = partition_viewer_files(files, force=True)
        header = json.loads(result['geometry_manifest.json'])
        previews = [p for c in header['streaming']['overview'] for p in json.loads(result[c['file']])['primitives']]
        self.assertTrue(previews)
        self.assertLess(len(previews), len(original['primitives']))
        self.assertTrue(all(p in original['primitives'] for p in previews))
        self.assertEqual(partition_viewer_files(result, force=True), result)


if __name__ == '__main__':
    unittest.main()
