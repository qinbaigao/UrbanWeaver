import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from cityg.viewer_lod import collect_viewer_lods


class ViewerLodTests(unittest.TestCase):
    def test_hash_gated_derivatives_leave_original_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source, derivative = b'original', b'lower resolution'
            (root/'low.glb').write_bytes(derivative)
            v = {'file':'low.glb', 'asset_id':'tree_low', 'max_pixels':48, 'triangles':10,
                 'relative_error_limit':0.01, 'sha256':hashlib.sha256(derivative).hexdigest()}
            record = {'source_sha256':hashlib.sha256(source).hexdigest(), 'original_triangles':100, 'variants':[v]}
            (root/'manifest.json').write_text(json.dumps({'assets':{'tree':record}}))
            assets = {'tree':source}
            mapping = collect_viewer_lods(assets, root)
            self.assertEqual(assets['tree'],source)
            self.assertEqual(assets['tree_low'],derivative)
            self.assertEqual(mapping['tree'][0]['max_pixels'],48)
            self.assertEqual(collect_viewer_lods({'tree':b'changed'},root),{})
            (root/'low.glb').write_bytes(b'corrupt')
            self.assertEqual(collect_viewer_lods({'tree':source},root),{})

    def test_missing_cache_is_optional(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(collect_viewer_lods({'tree':b'source'},d),{})
