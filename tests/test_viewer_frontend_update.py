import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from update_viewer_render_bundle import update


class FrontendUpdateTests(unittest.TestCase):
    def test_frontend_only_preserves_scene_configuration_and_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'portable';static=Path(tmp)/'static'
            (root/'scene').mkdir(parents=True);(root/'assets').mkdir()
            (static/'assets').mkdir(parents=True)
            originals={
                'viewer-config.json':json.dumps({'source':'portable_export','camera':{'fov':62}}).encode(),
                'scene/geometry_manifest.json':b'{"primitives":[]}',
                'assets/tree.glb':b'glTF', 'assets/old.js':b'old bundle',
                'serve.py':b'# retained launcher', 'review.html':b'gallery'}
            for name,data in originals.items():(root/name).write_bytes(data)
            (static/'index.html').write_text('<button id="export-render-view-button">Export render view</button>')
            (static/'assets/new.js').write_text('new bundle')
            with patch('update_viewer_render_bundle.viewer_static_dir',return_value=static), \
                 patch('update_viewer_render_bundle.collect_viewer_lods') as lods:
                result=update(root,frontend_only=True)
            lods.assert_not_called()
            self.assertFalse(result['scene_modified'])
            for name,data in originals.items():self.assertEqual((root/name).read_bytes(),data)
            self.assertIn('Export render view',(root/'index.html').read_text())
            self.assertTrue((root/'assets/new.js').is_file())

    def test_rejects_nonportable_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'viewer-config.json').write_text('{}')
            with self.assertRaises(ValueError):update(root,frontend_only=True)
