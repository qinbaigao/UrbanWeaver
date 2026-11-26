import tempfile
import unittest
from pathlib import Path

from cityg.services.interfaces import ChatMessage, ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService


class ModelServiceTests(unittest.TestCase):
    def test_text_payload(self):
        payload = OpenAICompatibleService._message_payload(
            ChatMessage(role="user", content="plan a district")
        )
        self.assertEqual(payload, {"role": "user", "content": "plan a district"})

    def test_image_payload_uses_data_url(self):
        with tempfile.TemporaryDirectory() as temporary:
            image = Path(temporary) / "preview.png"
            image.write_bytes(b"not-a-real-png")
            payload = OpenAICompatibleService._message_payload(
                ChatMessage(role="user", content="review", image_paths=(image,))
            )
        self.assertEqual(payload["content"][0], {"type": "text", "text": "review"})
        self.assertTrue(payload["content"][1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_endpoint_configuration_does_not_store_secret(self):
        endpoint = ModelEndpoint("http://127.0.0.1:8000/v1", "local-model")
        service = OpenAICompatibleService(endpoint)
        self.assertIsNone(service.api_key)
        self.assertEqual(endpoint.api_key_env, "CITYG_MODEL_API_KEY")

    def test_endpoint_has_bounded_non_thinking_defaults(self):
        endpoint = ModelEndpoint("http://127.0.0.1:8000/v1", "local-model")
        self.assertEqual(endpoint.max_tokens, 2048)
        self.assertFalse(endpoint.enable_thinking)


if __name__ == "__main__":
    unittest.main()
