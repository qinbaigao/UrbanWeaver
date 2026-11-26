"""Optional asset providers for local or remote acquisition services.

The core registry intentionally has no heavyweight dependencies.  This module
keeps the same property: it only speaks JSON over HTTP, while model inference
runs in an isolated process and Python environment.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from cityg.assets import AssetRecord


class AssetProviderError(RuntimeError):
    """An explicitly configured asset provider could not satisfy a request."""


@dataclass(frozen=True)
class HunyuanAssetEndpoint:
    """Connection and generation policy for the local Hunyuan asset worker."""

    base_url: str = "http://127.0.0.1:8091"
    timeout_s: float = 1800.0
    request_texture: bool = True
    seed_salt: str = "cityg-hunyuan-v1"
    require_localhost: bool = True

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Hunyuan asset endpoint must be an HTTP(S) URL")
        if self.timeout_s <= 0:
            raise ValueError("Hunyuan asset timeout must be positive")
        if self.require_localhost and parsed.hostname not in {
            "127.0.0.1",
            "localhost",
            "::1",
        }:
            raise ValueError(
                "Refusing a non-local Hunyuan endpoint; set require_localhost=False "
                "only for an explicitly trusted worker"
            )


class HunyuanAssetProvider:
    """Generate a registry-ready GLB through a local Hunyuan3D worker."""

    name = "hunyuan3d2_local"

    def __init__(self, endpoint: HunyuanAssetEndpoint | None = None) -> None:
        self.endpoint = endpoint or HunyuanAssetEndpoint()

    def health(self) -> dict[str, Any]:
        return self._request_json("GET", "/health")

    def acquire(
        self,
        query: str,
        *,
        category: str | None = None,
        dimensions_m: tuple[float, float, float] | None = None,
    ) -> AssetRecord | None:
        if not query.strip():
            raise ValueError("Asset query must not be empty")
        if dimensions_m is not None and (
            len(dimensions_m) != 3 or any(value <= 0 for value in dimensions_m)
        ):
            raise ValueError("dimensions_m must contain three positive values")
        seed_material = json.dumps(
            {
                "query": query,
                "category": category,
                "dimensions_m": dimensions_m,
                "salt": self.endpoint.seed_salt,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
        seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:4], "big")
        payload = {
            "description": query,
            "category": category or "generic_object",
            "dimensions_m": list(dimensions_m) if dimensions_m else None,
            "seed": seed,
            "texture": self.endpoint.request_texture,
        }
        response = self._request_json("POST", "/v1/assets/generate", payload)
        record_payload = response.get("asset_record")
        if not isinstance(record_payload, dict):
            raise AssetProviderError("Hunyuan worker response has no asset_record")
        record = AssetRecord.from_dict(record_payload)
        if not record.geometry_path:
            raise AssetProviderError("Hunyuan worker returned an asset without geometry")
        geometry_path = Path(record.geometry_path)
        if not geometry_path.is_file() or geometry_path.stat().st_size == 0:
            raise AssetProviderError(
                f"Generated geometry is unavailable on the shared filesystem: {geometry_path}"
            )
        return record

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.endpoint.base_url.rstrip('/')}{path}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=body,
            method=method,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.endpoint.timeout_s) as response:
                raw = response.read()
        except HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            raise AssetProviderError(
                f"Hunyuan worker returned HTTP {error.code}: {details[:500]}"
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise AssetProviderError(f"Hunyuan worker is unavailable at {url}: {error}") from error
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AssetProviderError("Hunyuan worker returned invalid JSON") from error
        if not isinstance(value, dict):
            raise AssetProviderError("Hunyuan worker response must be a JSON object")
        return value
