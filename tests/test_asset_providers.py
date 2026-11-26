import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cityg.asset_providers import HunyuanAssetEndpoint, HunyuanAssetProvider
from cityg.hunyuan_asset_service import (
    HunyuanWorkerConfig,
    generation_identity,
    validate_generation_request,
)


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class HunyuanAssetProviderTests(unittest.TestCase):
    def test_provider_health_and_registry_ready_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            geometry = Path(temporary) / "chair.glb"
            geometry.write_bytes(b"glTF-test")
            requests = []

            def fake_urlopen(request, timeout):
                requests.append(request)
                if request.method == "GET":
                    return _FakeResponse({"status": "ready", "texture_available": True})
                payload = json.loads(request.data)
                return _FakeResponse({
                    "asset_record": {
                        "asset_id": "hunyuan_office_chair_test",
                        "category": payload["category"],
                        "tags": ["generated", payload["category"]],
                        "dimensions_m": payload["dimensions_m"],
                        "geometry_path": str(geometry),
                        "source": "hunyuan3d2_local",
                        "license_id": "Tencent-Hunyuan-3D-2.0-Community-License",
                        "metadata": {"texture_status": "generated"},
                    }
                })

            provider = HunyuanAssetProvider(
                HunyuanAssetEndpoint(timeout_s=2)
            )
            with patch("cityg.asset_providers.urlopen", side_effect=fake_urlopen):
                self.assertEqual(provider.health()["status"], "ready")
                record = provider.acquire(
                    "modern ergonomic office chair",
                    category="office_chair",
                    dimensions_m=(0.58, 0.58, 1.0),
                )
                self.assertEqual(record.source, "hunyuan3d2_local")
                self.assertEqual(record.geometry_path, str(geometry))
                payload = json.loads(requests[1].data)
                self.assertTrue(payload["texture"])
                self.assertIsInstance(payload["seed"], int)

    def test_request_validation_and_identity_are_deterministic(self):
        request = validate_generation_request(
            {
                "description": "a chair",
                "category": "office_chair",
                "dimensions_m": [0.6, 0.6, 1.0],
                "seed": 12,
                "texture": True,
            }
        )
        config = HunyuanWorkerConfig(
            repo_path=Path("/repo"),
            shape_model_root=Path("/models"),
            text_to_image_model=Path("/t2i"),
            output_root=Path("/assets"),
        )
        first = generation_identity(request, config)
        second = generation_identity(request, config)
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("hunyuan_office_chair_"))

    def test_remote_endpoint_is_rejected_by_default(self):
        with self.assertRaises(ValueError):
            HunyuanAssetEndpoint(base_url="http://example.com:8091")


if __name__ == "__main__":
    unittest.main()
