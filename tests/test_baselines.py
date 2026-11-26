import json
import tempfile
import unittest
from pathlib import Path

from cityg.baselines import freeze_baseline, verify_baseline


class BaselineTests(unittest.TestCase):
    def test_freeze_and_verify_detects_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = root / "scene"
            scene.mkdir()
            (scene / "city.json").write_text('{"id":"city_demo"}\n')
            (scene / "compile_metrics.json").write_text('{"primitive_count":3}\n')
            manifest = freeze_baseline(scene, root / "baseline", name="demo")
            payload = json.loads(manifest.read_text())
            self.assertEqual(payload["protocol_version"], "cityg.baseline.v1")
            self.assertTrue(verify_baseline(manifest)["ok"])
            (scene / "city.json").write_text('{"id":"changed"}\n')
            report = verify_baseline(manifest)
            self.assertFalse(report["ok"])
            self.assertIn(report["issues"][0]["code"], {"size_mismatch", "hash_mismatch"})


if __name__ == "__main__":
    unittest.main()
