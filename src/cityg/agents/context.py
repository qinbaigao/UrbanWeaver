"""Structured progressive disclosure for bounded model context."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContextSection:
    key: str
    description: str
    value: Any

    @property
    def serialized_chars(self) -> int:
        return len(json.dumps(self.value, ensure_ascii=False, sort_keys=True))


@dataclass(frozen=True)
class DisclosureEvent:
    round_index: int
    keys: tuple[str, ...]
    serialized_chars: int


@dataclass
class ProgressiveContext:
    """Reveal named sections only after a structured model request."""

    summary: dict[str, Any]
    sections: tuple[ContextSection, ...]
    max_rounds: int = 2
    max_sections: int = 4
    max_disclosed_chars: int = 16000
    events: list[DisclosureEvent] = field(default_factory=list, init=False)
    _disclosed: set[str] = field(default_factory=set, init=False, repr=False)

    def remaining_payload(self) -> dict[str, Any]:
        """Expose only requestable keys; rejected requests never consume disclosure."""
        return {
            "already_disclosed": sorted(self._disclosed),
            "available_keys": [s.key for s in self.sections if s.key not in self._disclosed],
            "remaining_rounds": max(0, self.max_rounds-len(self.events)),
            "remaining_characters": max(0, self.max_disclosed_chars-sum(e.serialized_chars for e in self.events)),
        }

    def initial_payload(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "available_details": [
                {
                    "key": section.key,
                    "description": section.description,
                    "estimated_chars": section.serialized_chars,
                }
                for section in self.sections
            ],
            "disclosure_budget": {
                "max_rounds": self.max_rounds,
                "max_sections": self.max_sections,
                "max_disclosed_chars": self.max_disclosed_chars,
            },
        }

    def disclose(self, keys: list[str]) -> dict[str, Any]:
        if len(self.events) >= self.max_rounds:
            raise ValueError("progressive disclosure round budget exhausted")
        if not keys:
            raise ValueError("detail request must contain at least one key")
        if len(keys) != len(set(keys)):
            raise ValueError("detail request contains duplicate keys")
        catalog = {section.key: section for section in self.sections}
        unknown = sorted(set(keys) - set(catalog))
        if unknown:
            raise ValueError(f"unknown detail keys: {', '.join(unknown)}")
        repeated = sorted(set(keys) & self._disclosed)
        if repeated:
            raise ValueError(f"detail keys already disclosed: {', '.join(repeated)}")
        if len(self._disclosed) + len(keys) > self.max_sections:
            raise ValueError("progressive disclosure section budget exceeded")
        selected = {key: catalog[key].value for key in keys}
        chars = len(json.dumps(selected, ensure_ascii=False, sort_keys=True))
        used = sum(event.serialized_chars for event in self.events)
        if used + chars > self.max_disclosed_chars:
            raise ValueError("progressive disclosure character budget exceeded")
        self._disclosed.update(keys)
        event = DisclosureEvent(len(self.events) + 1, tuple(keys), chars)
        self.events.append(event)
        return {
            "disclosure_round": event.round_index,
            "details": selected,
            "remaining": {
                "rounds": self.max_rounds - len(self.events),
                "sections": self.max_sections - len(self._disclosed),
                "characters": self.max_disclosed_chars - used - chars,
            },
        }

