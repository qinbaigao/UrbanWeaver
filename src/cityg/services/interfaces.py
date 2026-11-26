"""Process-safe service contracts for optional heavyweight systems."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, Sequence

from cityg.schemas import City, Floor


@dataclass(frozen=True)
class ModelEndpoint:
    """Configuration for an OpenAI-compatible endpoint such as vLLM."""

    base_url: str
    model: str
    api_key_env: str = "CITYG_MODEL_API_KEY"
    timeout_s: float = 120.0
    temperature: float = 0.7
    top_p: float = 0.8
    max_tokens: int = 2048
    seed: int | None = None
    enable_thinking: bool = False


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str
    image_paths: tuple[Path, ...] = ()


@dataclass(frozen=True)
class AssetReference:
    id: str
    source: str
    uri: str
    metadata: dict[str, Any] = field(default_factory=dict)


class TextReasoningService(Protocol):
    """LLM reasoning through a local vLLM or hosted compatible endpoint."""

    def complete(
        self, messages: Sequence[ChatMessage], response_schema: dict[str, Any] | None = None
    ) -> str:
        ...


class VisionReviewService(Protocol):
    """VLM review of renders produced by a geometry or simulation backend."""

    def review(self, prompt: str, image_paths: Sequence[Path]) -> str:
        ...


class IndoorGenerationService(Protocol):
    """Refine a single floor while preserving CityG IDs and boundaries."""

    def refine_floor(self, city_id: str, building_id: str, floor: Floor) -> Floor:
        ...


class AssetGenerationService(Protocol):
    """Retrieve or generate one reusable simulation asset."""

    def resolve(self, description: str, category: str) -> AssetReference:
        ...


class TrafficBackend(Protocol):
    """Compile the road graph and optionally synchronize a traffic runtime."""

    def compile(self, city: City, output_dir: Path) -> list[Path]:
        ...


class SimulationBackend(Protocol):
    """Compile a canonical city into a simulator-specific representation."""

    def compile(self, city: City, output_dir: Path) -> list[Path]:
        ...
