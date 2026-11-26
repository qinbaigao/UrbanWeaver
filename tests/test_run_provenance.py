import tempfile
from pathlib import Path
import unittest

from cityg.run_provenance import source_snapshot


class SourceProvenanceTests(unittest.TestCase):
    def test_changed_untracked_code_and_config_are_fingerprinted_without_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'src').mkdir(); (root/'configs').mkdir()
            source = root/'src/example.py'; source.write_text('value = 1')
            (root/'configs/test.env').write_text('SECRET_TOKEN=do-not-persist')
            first = source_snapshot(root)
            self.assertIn('src/example.py', first['file_sha256'])
            self.assertNotIn('do-not-persist', str(first))
            source.write_text('value = 2')
            self.assertNotEqual(first['tree_sha256'], source_snapshot(root)['tree_sha256'])
            self.assertFalse(first['asset_binary_hashes_included'])
