"""Offline, restartable chunk migration primitives.

The engine accepts already-extracted JSONL chunks and an idempotent target sink.
It deliberately contains no Oracle/PostgreSQL driver and executes no SQL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Protocol, Sequence

MANIFEST_FORMAT = "apex2next.data-migration.chunk-manifest.v1"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    ordinal: int
    file: str
    row_count: int
    checksum: str
    first_key: list[Any]
    last_key: list[Any]


@dataclass(frozen=True)
class ChunkManifest:
    format: str
    migration_id: str
    source_owner: str
    source_table: str
    key_fields: list[str]
    created_at: str
    chunks: list[Chunk]
    total_rows: int

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        return result


def _key(row: dict[str, Any], fields: Sequence[str]) -> tuple[Any, ...]:
    values = tuple(row.get(field) for field in fields)
    if any(value is None for value in values):
        raise ValueError(f"Chunk key fields must be present and non-null: {fields}")
    if any(not isinstance(value, (str, int, float)) or isinstance(value, bool) for value in values):
        raise ValueError("Chunk key values must be JSON scalar strings or numbers")
    return values


def build_chunk_manifest(
    rows: Iterable[dict[str, Any]],
    output_dir: Path,
    *,
    migration_id: str,
    source_owner: str,
    source_table: str,
    key_fields: Sequence[str],
    chunk_size: int = 1000,
    created_at: str,
) -> ChunkManifest:
    """Write deterministic JSONL chunks from a key-ordered, consistent source snapshot."""
    if not migration_id.strip() or not source_owner.strip() or not source_table.strip():
        raise ValueError("migration_id, source_owner, and source_table are required")
    if not key_fields or len(set(key_fields)) != len(key_fields):
        raise ValueError("key_fields must be a non-empty unique sequence")
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")
    if not created_at.strip():
        raise ValueError("created_at must be supplied explicitly")
    chunks_dir = output_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunks: list[Chunk] = []
    buffer: list[dict[str, Any]] = []
    previous_key: tuple[Any, ...] | None = None
    total = 0

    def flush() -> None:
        nonlocal buffer
        if not buffer:
            return
        ordinal = len(chunks) + 1
        filename = f"chunks/chunk-{ordinal:06d}.jsonl"
        content = "".join(canonical_json(row) + "\n" for row in buffer)
        checksum = sha256_text(content)
        first_key = list(_key(buffer[0], key_fields))
        last_key = list(_key(buffer[-1], key_fields))
        chunk_id = f"chunk-{ordinal:06d}-{checksum.split(':', 1)[1][:16]}"
        (output_dir / filename).write_text(content, encoding="utf-8")
        chunks.append(Chunk(chunk_id, ordinal, filename, len(buffer), checksum, first_key, last_key))
        buffer = []

    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Every source row must be a JSON object")
        current_key = _key(row, key_fields)
        if previous_key is not None:
            try:
                if current_key <= previous_key:
                    raise ValueError("Source rows must be strictly ordered by unique key fields")
            except TypeError as exc:
                raise ValueError("Chunk key values must have mutually comparable types") from exc
        previous_key = current_key
        # Validate canonical JSON before writing any chunk.
        canonical_json(row)
        buffer.append(row)
        total += 1
        if len(buffer) >= chunk_size:
            flush()
    flush()
    manifest = ChunkManifest(MANIFEST_FORMAT, migration_id, source_owner.upper(),
                             source_table.upper(), list(key_fields), created_at,
                             chunks, total)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


class IdempotentTargetSink(Protocol):
    """Target adapter contract: same migration/chunk/checksum must be a no-op on retry."""

    def load_chunk(self, migration_id: str, chunk_id: str, checksum: str,
                   rows: list[dict[str, Any]]) -> int:
        """Load a chunk atomically; return rows accepted, or 0 for an already-applied chunk."""
        ...


class ChunkCheckpointStore:
    """SQLite-backed local checkpoint ledger; suitable for a single migration worker."""

    def __init__(self, database: Path) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(database)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS migration_chunks (
                migration_id TEXT NOT NULL,
                chunk_id TEXT NOT NULL,
                checksum TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                PRIMARY KEY (migration_id, chunk_id)
            )
        """)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def prepare(self, migration_id: str, chunk: Chunk) -> str:
        row = self.connection.execute(
            "SELECT checksum, row_count, status FROM migration_chunks WHERE migration_id=? AND chunk_id=?",
            (migration_id, chunk.chunk_id),
        ).fetchone()
        if row is None:
            self.connection.execute(
                "INSERT INTO migration_chunks(migration_id,chunk_id,checksum,row_count,status) VALUES(?,?,?,?,?)",
                (migration_id, chunk.chunk_id, chunk.checksum, chunk.row_count, "PENDING"),
            )
            self.connection.commit()
            return "PENDING"
        if row[0] != chunk.checksum or row[1] != chunk.row_count:
            raise ValueError(f"Checkpoint identity conflict for {chunk.chunk_id}")
        return str(row[2])

    def mark_attempt(self, migration_id: str, chunk: Chunk) -> None:
        self.connection.execute(
            "UPDATE migration_chunks SET status='RUNNING', attempts=attempts+1, error=NULL "
            "WHERE migration_id=? AND chunk_id=?",
            (migration_id, chunk.chunk_id),
        )
        self.connection.commit()

    def mark_loaded(self, migration_id: str, chunk: Chunk) -> None:
        self.connection.execute(
            "UPDATE migration_chunks SET status='LOADED', error=NULL WHERE migration_id=? AND chunk_id=?",
            (migration_id, chunk.chunk_id),
        )
        self.connection.commit()

    def mark_failed(self, migration_id: str, chunk: Chunk, error: str) -> None:
        self.connection.execute(
            "UPDATE migration_chunks SET status='FAILED', error=? WHERE migration_id=? AND chunk_id=?",
            (error[:2000], migration_id, chunk.chunk_id),
        )
        self.connection.commit()

    def summary(self, migration_id: str) -> dict[str, int]:
        rows = self.connection.execute(
            "SELECT status, COUNT(*) FROM migration_chunks WHERE migration_id=? GROUP BY status",
            (migration_id,),
        ).fetchall()
        result = {"PENDING": 0, "RUNNING": 0, "LOADED": 0, "FAILED": 0}
        result.update({status: count for status, count in rows})
        return result

    def chunk_status(self, migration_id: str, chunk_id: str) -> str | None:
        row = self.connection.execute(
            "SELECT status FROM migration_chunks WHERE migration_id=? AND chunk_id=?",
            (migration_id, chunk_id),
        ).fetchone()
        return str(row[0]) if row else None


def _load_chunk_file(path: Path, chunk: Chunk) -> list[dict[str, Any]]:
    content = path.read_text(encoding="utf-8")
    if sha256_text(content) != chunk.checksum:
        raise ValueError(f"Chunk checksum mismatch: {chunk.file}")
    rows = [json.loads(line) for line in content.splitlines() if line.strip()]
    if len(rows) != chunk.row_count:
        raise ValueError(f"Chunk row count mismatch: {chunk.file}")
    return rows


def run_migration(manifest: ChunkManifest, chunk_root: Path, checkpoint: ChunkCheckpointStore,
                  sink: IdempotentTargetSink, *, max_retries: int = 3) -> dict[str, Any]:
    """Load chunks in order, skipping durable successes and retrying failed chunks."""
    if max_retries < 1:
        raise ValueError("max_retries must be at least 1")
    for chunk in manifest.chunks:
        status = checkpoint.prepare(manifest.migration_id, chunk)
        if status == "LOADED":
            continue
        path = (chunk_root / chunk.file).resolve()
        root = chunk_root.resolve()
        if root not in path.parents:
            raise ValueError(f"Chunk path escapes manifest directory: {chunk.file}")
        rows = _load_chunk_file(path, chunk)
        last_error: Exception | None = None
        for _ in range(max_retries):
            checkpoint.mark_attempt(manifest.migration_id, chunk)
            try:
                accepted = sink.load_chunk(manifest.migration_id, chunk.chunk_id, chunk.checksum, rows)
                if accepted not in {0, chunk.row_count}:
                    raise ValueError("Target sink returned a partial chunk result; atomic load is required")
                checkpoint.mark_loaded(manifest.migration_id, chunk)
                last_error = None
                break
            except Exception as exc:  # adapter failures are retried; checkpoint retains the final error
                last_error = exc
        if last_error is not None:
            checkpoint.mark_failed(manifest.migration_id, chunk, str(last_error))
            raise RuntimeError(f"Chunk {chunk.chunk_id} failed after {max_retries} attempts") from last_error
    summary = checkpoint.summary(manifest.migration_id)
    return {"migrationId": manifest.migration_id, "status": "COMPLETED" if summary["LOADED"] == len(manifest.chunks)
            else "INCOMPLETE", "totalChunks": len(manifest.chunks), "totalRows": manifest.total_rows,
            "checkpoint": summary}


def load_manifest(path: Path) -> ChunkManifest:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != MANIFEST_FORMAT:
        raise ValueError(f"Unsupported chunk manifest format: {data.get('format')!r}")
    return ChunkManifest(
        data["format"], data["migration_id"], data["source_owner"], data["source_table"],
        data["key_fields"], data["created_at"],
        [Chunk(**item) for item in data["chunks"]], data["total_rows"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a WP8.3 chunk manifest")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    print(json.dumps({"migrationId": manifest.migration_id, "source": f"{manifest.source_owner}.{manifest.source_table}",
                      "chunks": len(manifest.chunks), "rows": manifest.total_rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
