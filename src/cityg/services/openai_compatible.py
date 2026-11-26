"""Minimal OpenAI-compatible client suitable for local vLLM endpoints.

This module deliberately uses urllib so the core environment remains dependency
free. It supports text messages and local images encoded as data URLs.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cityg.services.interfaces import ChatMessage, ModelEndpoint


@dataclass(frozen=True)
class ModelCompletion:
    """Normalized completion plus the serving metadata needed for traces."""

    content: str
    finish_reason: str | None
    usage: dict[str, Any]
    reasoning: str | None = None


class OpenAICompatibleService:
    def __init__(self, endpoint: ModelEndpoint, api_key: str | None = None) -> None:
        self.endpoint = endpoint
        self.api_key = api_key

    def complete(
        self, messages: Sequence[ChatMessage], response_schema: dict[str, Any] | None = None
    ) -> str:
        return self.complete_with_metadata(messages, response_schema).content

    def complete_with_metadata(
        self, messages: Sequence[ChatMessage], response_schema: dict[str, Any] | None = None
    ) -> ModelCompletion:
        payload: dict[str, Any] = {
            "model": self.endpoint.model,
            "messages": [self._message_payload(message) for message in messages],
            "temperature": self.endpoint.temperature,
            "top_p": self.endpoint.top_p,
            "max_tokens": self.endpoint.max_tokens,
            "chat_template_kwargs": {
                "enable_thinking": self.endpoint.enable_thinking,
            },
        }
        if self.endpoint.seed is not None:
            payload["seed"] = self.endpoint.seed
        if response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "cityg_response",
                    "strict": True,
                    "schema": response_schema,
                },
            }
        response = self._post(payload)
        try:
            choice = response["choices"][0]
            message = choice["message"]
            content = message["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError("Model endpoint returned an invalid chat completion") from error
        if not isinstance(content, str):
            raise RuntimeError("Model endpoint returned non-text completion content")
        usage = response.get("usage", {})
        return ModelCompletion(
            content=content,
            finish_reason=choice.get("finish_reason"),
            usage=dict(usage) if isinstance(usage, dict) else {},
            reasoning=message.get("reasoning"),
        )

    def review(self, prompt: str, image_paths: Sequence[Path]) -> str:
        return self.complete(
            [ChatMessage(role="user", content=prompt, image_paths=tuple(image_paths))]
        )

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = self.endpoint.base_url.rstrip("/") + "/chat/completions"
        api_key = self.api_key or os.environ.get(self.endpoint.api_key_env, "EMPTY")
        request = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.endpoint.timeout_s) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Model endpoint returned HTTP {error.code}: {detail}") from error
        except URLError as error:
            raise RuntimeError(f"Unable to reach model endpoint: {error.reason}") from error

    @classmethod
    def _message_payload(cls, message: ChatMessage) -> dict[str, Any]:
        if not message.image_paths:
            return {"role": message.role, "content": message.content}
        content: list[dict[str, Any]] = [{"type": "text", "text": message.content}]
        for image_path in message.image_paths:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": cls._image_data_url(image_path)},
                }
            )
        return {"role": message.role, "content": content}

    @staticmethod
    def _image_data_url(path: Path) -> str:
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{media_type};base64,{encoded}"
