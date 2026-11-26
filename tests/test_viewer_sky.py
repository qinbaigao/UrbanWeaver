import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from cityg.viewer_sky import collect_viewer_skies, default_environment_file


class ViewerSkyTests(unittest.TestCase):
    def test_optional_hash_verified_pack_preserves_original_environment(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);environments={'urban.hdr':b'original'}
            self.assertEqual(collect_viewer_skies(environments,root),{})
            data=b'hdr';(root/'clear.hdr').write_bytes(data)
            record={'file':'clear.hdr','label':'Clear','sha256':hashlib.sha256(data).hexdigest()}
            (root/'manifest.json').write_text(json.dumps({'presets':{'clear':record}}))
            presets=collect_viewer_skies(environments,root)
            self.assertEqual(environments['clear.hdr'],data)
            self.assertEqual(default_environment_file(environments,presets),'urban.hdr')
            (root/'clear.hdr').write_bytes(b'corrupt')
            self.assertEqual(collect_viewer_skies({},root),{})
            self.assertEqual(default_environment_file({'clear.hdr':data},presets),None)
