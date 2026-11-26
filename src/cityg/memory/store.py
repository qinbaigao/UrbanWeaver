"""SQLite-backed memory with deterministic filtering and stale-version safety."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from cityg.agents.context import ContextSection
from cityg.memory.model import MemoryQuery, MemoryRecord


SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_records (
    memory_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    scope_type TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    world_version INTEGER,
    content_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    producer TEXT NOT NULL,
    validation_status TEXT NOT NULL,
    confidence REAL NOT NULL,
    run_id TEXT,
    provenance_json TEXT NOT NULL,
    cross_run INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    invalidated_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_memory_scope
    ON memory_records(scope_id, world_version, validation_status);
CREATE INDEX IF NOT EXISTS idx_memory_kind
    ON memory_records(kind, validation_status);
CREATE INDEX IF NOT EXISTS idx_memory_run
    ON memory_records(run_id, validation_status);
"""


class MemoryStore:
    """Persistent shared memory; CCWP remains the authoritative current state."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def relocate_artifact_paths(self, previous: str, published: str) -> None:
        """Relocate staging-local evidence and rehash content before publication."""
        from dataclasses import replace
        with self.connection:
            ids = [row[0] for row in self.connection.execute('SELECT memory_id FROM memory_records')]
            for memory_id in ids:
                record = self.get(memory_id)
                payload = json.dumps(record.content, ensure_ascii=False)
                relocated = payload.replace(previous, published)
                if relocated != payload:
                    self._put(replace(record, content=json.loads(relocated)), overwrite=True)

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def put(self, record: MemoryRecord, *, overwrite: bool = False) -> MemoryRecord:
        with self.connection:
            return self._put(record, overwrite=overwrite)

    def _put(self, record: MemoryRecord, *, overwrite: bool = False) -> MemoryRecord:
        """Write without committing; callers own the SQLite transaction."""
        existing = self.get(record.memory_id)
        if existing is not None and not overwrite:
            if existing != record:
                raise ValueError(f"memory already exists: {record.memory_id}")
            return existing
        verb = "INSERT OR REPLACE" if overwrite else "INSERT"
        self.connection.execute(
            f"""{verb} INTO memory_records VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.memory_id,
                record.kind,
                record.scope_type,
                record.scope_id,
                record.world_version,
                json.dumps(record.content, ensure_ascii=False, sort_keys=True),
                record.content_hash,
                json.dumps(list(record.tags), ensure_ascii=False),
                record.producer,
                record.validation_status,
                record.confidence,
                record.run_id,
                json.dumps(list(record.provenance_ids), ensure_ascii=False),
                int(record.cross_run),
                record.created_at,
                record.invalidated_by,
            ),
        )
        return record

    def get(self, memory_id: str) -> MemoryRecord | None:
        row = self.connection.execute(
            "SELECT * FROM memory_records WHERE memory_id = ?", (memory_id,)
        ).fetchone()
        return self._record(row) if row is not None else None

    def query(self, query: MemoryQuery) -> list[MemoryRecord]:
        clauses = []
        values: list[Any] = []
        if query.scope_id is not None:
            clauses.append("scope_id = ?")
            values.append(query.scope_id)
        if query.scope_type is not None:
            clauses.append("scope_type = ?")
            values.append(query.scope_type)
        if query.kinds:
            clauses.append(f"kind IN ({','.join('?' for _ in query.kinds)})")
            values.extend(query.kinds)
        if query.statuses:
            clauses.append(
                f"validation_status IN ({','.join('?' for _ in query.statuses)})"
            )
            values.extend(query.statuses)
        if query.world_version is not None:
            # Versionless semantic records remain reusable; entity facts must
            # match the current CCWP node version exactly.
            clauses.append("(world_version IS NULL OR world_version = ?)")
            values.append(query.world_version)
        if query.run_id is not None:
            if query.allow_cross_run:
                clauses.append("(run_id = ? OR cross_run = 1)")
            else:
                clauses.append("run_id = ?")
            values.append(query.run_id)
        elif not query.allow_cross_run:
            clauses.append("cross_run = 0")
        sql = "SELECT * FROM memory_records"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY confidence DESC, created_at DESC, memory_id ASC"
        rows = self.connection.execute(sql, values).fetchall()
        result = [self._record(row) for row in rows]
        if query.tags:
            wanted = set(query.tags)
            result = [record for record in result if wanted.issubset(set(record.tags))]
        return result[: query.limit]

    def set_status(
        self,
        memory_id: str,
        status: str,
        *,
        invalidated_by: str | None = None,
    ) -> MemoryRecord:
        record = self.get(memory_id)
        if record is None:
            raise KeyError(memory_id)
        updated = record.with_status(status, invalidated_by=invalidated_by)
        return self.put(updated, overwrite=True)

    def invalidate_scope(
        self,
        scope_id: str,
        *,
        current_world_version: int,
        reason: str,
    ) -> int:
        cursor = self.connection.execute(
            """UPDATE memory_records
               SET validation_status = 'stale', invalidated_by = ?
               WHERE scope_id = ? AND world_version IS NOT NULL
                 AND world_version != ?
                 AND validation_status IN ('candidate', 'accepted')""",
            (reason, scope_id, current_world_version),
        )
        self.connection.commit()
        return int(cursor.rowcount)

    def invalidate_entities(self, entity_ids, *, reason: str) -> int:
        """Invalidate exact-scope/dependency evidence, including unversioned views.

        Only explicit dependency_entity_ids are expanded; arbitrary strings in
        historical narratives are not interpreted as live dependencies.
        """
        with self.connection:
            return self._invalidate_entities(entity_ids, reason=reason)

    def _invalidate_entities(self, entity_ids, *, reason: str) -> int:
        wanted = set(entity_ids)
        rows = self.connection.execute("SELECT * FROM memory_records WHERE validation_status IN ('candidate', 'accepted')").fetchall()
        ids = [row['memory_id'] for row in rows if row['scope_id'] in wanted or wanted.intersection(
            json.loads(row['content_json']).get('dependency_entity_ids', []))]
        self.connection.executemany("UPDATE memory_records SET validation_status='stale', invalidated_by=? WHERE memory_id=?",
                                    [(reason, key) for key in ids])
        return len(ids)

    def record_mutation(self, record: MemoryRecord, entity_ids) -> int:
        """Atomically retire dependent evidence and insert its accepted decision.

        A duplicate/conflicting decision or SQL error leaves all evidence intact.
        This is a memory transaction, not a filesystem publication guarantee.
        """
        with self.connection:
            if self.get(record.memory_id) is not None:
                raise ValueError(f"mutation already recorded: {record.memory_id}")
            count = self._invalidate_entities(entity_ids, reason=record.memory_id)
            self._put(record)
        return count

    def context_section(
        self,
        key: str,
        description: str,
        query: MemoryQuery,
    ) -> ContextSection:
        records = self.query(query)
        return ContextSection(
            key,
            description,
            [record.to_dict() for record in records],
        )

    def stats(self) -> dict[str, Any]:
        total = self.connection.execute(
            "SELECT COUNT(*) FROM memory_records"
        ).fetchone()[0]
        statuses = {
            row[0]: row[1]
            for row in self.connection.execute(
                "SELECT validation_status, COUNT(*) FROM memory_records GROUP BY validation_status"
            )
        }
        return {"path": str(self.path), "record_count": total, "statuses": statuses}

    @staticmethod
    def _record(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            memory_id=row["memory_id"],
            kind=row["kind"],
            scope_type=row["scope_type"],
            scope_id=row["scope_id"],
            content=json.loads(row["content_json"]),
            world_version=row["world_version"],
            tags=tuple(json.loads(row["tags_json"])),
            producer=row["producer"],
            validation_status=row["validation_status"],
            confidence=float(row["confidence"]),
            run_id=row["run_id"],
            provenance_ids=tuple(json.loads(row["provenance_json"])),
            cross_run=bool(row["cross_run"]),
            created_at=row["created_at"],
            invalidated_by=row["invalidated_by"],
        )


__all__ = ["MemoryStore"]
