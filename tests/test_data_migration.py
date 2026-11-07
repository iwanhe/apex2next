import json
import sqlite3
from pathlib import Path

import pytest

from apex2next_schema_analyzer.data_migration import (
    ChunkCheckpointStore,
    build_chunk_manifest,
    load_manifest,
    run_migration,
)


class FakeSink:
    def __init__(self, fail_first: int = 0) -> None:
        self.applied: dict[tuple[str, str], str] = {}
        self.rows: list[dict] = []
        self.calls = 0
        self.fail_first = fail_first

    def load_chunk(self, migration_id, chunk_id, checksum, rows):
        self.calls += 1
        if self.calls <= self.fail_first:
            raise RuntimeError("simulated target outage")
        key = (migration_id, chunk_id)
        if key in self.applied:
            assert self.applied[key] == checksum
            return 0
        self.applied[key] = checksum
        self.rows.extend(rows)
        return len(rows)


def make_manifest(tmp_path: Path):
    return build_chunk_manifest(
        ({"ID": i, "VALUE": f"row-{i}"} for i in range(1, 8)),
        tmp_path / "export", migration_id="mig-001", source_owner="APP",
        source_table="T_ORDERS", key_fields=["ID"], chunk_size=3,
        created_at="2026-11-07T10:00:00+07:00",
    )


def test_chunk_manifest_is_deterministic_and_chunked(tmp_path: Path) -> None:
    first = make_manifest(tmp_path)
    second = build_chunk_manifest(
        ({"ID": i, "VALUE": f"row-{i}"} for i in range(1, 8)),
        tmp_path / "export-2", migration_id="mig-001", source_owner="APP",
        source_table="T_ORDERS", key_fields=["ID"], chunk_size=3,
        created_at="2026-11-07T10:00:00+07:00",
    )
    assert first.total_rows == 7
    assert [x.row_count for x in first.chunks] == [3, 3, 1]
    assert [x.checksum for x in first.chunks] == [x.checksum for x in second.chunks]
    assert load_manifest(tmp_path / "export" / "manifest.json") == first


def test_chunk_builder_requires_unique_ordered_keys(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="strictly ordered"):
        build_chunk_manifest([{"ID": 2}, {"ID": 2}], tmp_path / "bad",
            migration_id="m", source_owner="A", source_table="T", key_fields=["ID"],
            chunk_size=2, created_at="now")


def test_checkpoint_restart_skips_already_loaded_chunks(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    store = ChunkCheckpointStore(tmp_path / "checkpoint.sqlite")
    sink = FakeSink()
    first = run_migration(manifest, tmp_path / "export", store, sink)
    calls = sink.calls
    second = run_migration(manifest, tmp_path / "export", store, sink)
    assert first["status"] == second["status"] == "COMPLETED"
    assert sink.calls == calls
    assert len(sink.rows) == 7
    store.close()


def test_retry_recovers_transient_failure(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    store = ChunkCheckpointStore(tmp_path / "checkpoint.sqlite")
    sink = FakeSink(fail_first=1)
    result = run_migration(manifest, tmp_path / "export", store, sink, max_retries=2)
    assert result["status"] == "COMPLETED"
    assert sink.calls == 4
    assert len(sink.rows) == 7
    store.close()


def test_failed_chunk_can_resume_after_target_recovers(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    store = ChunkCheckpointStore(tmp_path / "checkpoint.sqlite")
    broken = FakeSink(fail_first=99)
    with pytest.raises(RuntimeError, match="failed after"):
        run_migration(manifest, tmp_path / "export", store, broken, max_retries=2)
    assert store.summary("mig-001")["FAILED"] == 1
    recovered = FakeSink()
    result = run_migration(manifest, tmp_path / "export", store, recovered)
    assert result["status"] == "COMPLETED"
    assert len(recovered.rows) == 7
    store.close()


def test_modified_chunk_is_rejected_before_target_load(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    file = tmp_path / "export" / manifest.chunks[0].file
    file.write_text('{"ID":1,"VALUE":"tampered"}\n', encoding="utf-8")
    store = ChunkCheckpointStore(tmp_path / "checkpoint.sqlite")
    sink = FakeSink()
    with pytest.raises(ValueError, match="checksum mismatch"):
        run_migration(manifest, tmp_path / "export", store, sink)
    assert sink.calls == 0
    store.close()


def test_partial_target_result_is_not_marked_loaded(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    class PartialSink:
        def load_chunk(self, migration_id, chunk_id, checksum, rows):
            return 1
    store = ChunkCheckpointStore(tmp_path / "checkpoint.sqlite")
    with pytest.raises(RuntimeError, match="failed after"):
        run_migration(manifest, tmp_path / "export", store, PartialSink(), max_retries=1)
    assert store.summary("mig-001")["FAILED"] == 1
    store.close()
