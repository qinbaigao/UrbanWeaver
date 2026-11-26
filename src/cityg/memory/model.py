"""Typed memory records kept separate from authoritative CCWP world state."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any


MEMORY_STATUSES = frozenset({"candidate", "accepted", "rejected", "stale"})


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    kind: str
    scope_type: str
    scope_id: str
    content: dict[str, Any]
    world_version: int | None = None
    tags: tuple[str, ...] = ()
    producer: str = "unknown"
    validation_status: str = "candidate"
    confidence: float = 1.0
    run_id: str | None = None
    provenance_ids: tuple[str, ...] = ()
    cross_run: bool = False
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    invalidated_by: str | None = None

    def __post_init__(self) -> None:
        if not self.memory_id.strip() or not self.kind.strip() or not self.scope_id.strip():
            raise ValueError("memory_id, kind and scope_id must not be empty")
        if self.validation_status not in MEMORY_STATUSES:
            raise ValueError(f"unsupported memory status: {self.validation_status}")
        if self.world_version is not None and self.world_version < 1:
            raise ValueError("world_version must be positive or None")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("memory confidence must be within [0, 1]")

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(
            json.dumps(self.content, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

    def with_status(
        self, status: str, *, invalidated_by: str | None = None
    ) -> "MemoryRecord":
        return replace(
            self,
            validation_status=status,
            invalidated_by=invalidated_by,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "kind": self.kind,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "content": self.content,
            "world_version": self.world_version,
            "tags": list(self.tags),
            "producer": self.producer,
            "validation_status": self.validation_status,
            "confidence": self.confidence,
            "run_id": self.run_id,
            "provenance_ids": list(self.provenance_ids),
            "cross_run": self.cross_run,
            "created_at": self.created_at,
            "invalidated_by": self.invalidated_by,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryRecord":
        return cls(
            memory_id=str(data["memory_id"]),
            kind=str(data["kind"]),
            scope_type=str(data["scope_type"]),
            scope_id=str(data["scope_id"]),
            content=dict(data.get("content", {})),
            world_version=(
                int(data["world_version"])
                if data.get("world_version") is not None
                else None
            ),
            tags=tuple(str(item) for item in data.get("tags", ())),
            producer=str(data.get("producer", "unknown")),
            validation_status=str(data.get("validation_status", "candidate")),
            confidence=float(data.get("confidence", 1.0)),
            run_id=data.get("run_id"),
            provenance_ids=tuple(str(item) for item in data.get("provenance_ids", ())),
            cross_run=bool(data.get("cross_run", False)),
            created_at=str(
                data.get("created_at") or datetime.now(timezone.utc).isoformat()
            ),
            invalidated_by=data.get("invalidated_by"),
        )


@dataclass(frozen=True)
class MemoryQuery:
    scope_id: str | None = None
    scope_type: str | None = None
    kinds: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ("accepted",)
    world_version: int | None = None
    run_id: str | None = None
    allow_cross_run: bool = False
    limit: int = 8

    def __post_init__(self) -> None:
        if self.limit < 1 or self.limit > 100:
            raise ValueError("memory query limit must be within [1, 100]")
        if any(status not in MEMORY_STATUSES for status in self.statuses):
            raise ValueError("memory query contains an unsupported status")


__all__ = ["MEMORY_STATUSES", "MemoryQuery", "MemoryRecord"]
