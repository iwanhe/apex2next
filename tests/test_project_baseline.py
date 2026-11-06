"""Smoke tests for the repository's initial Python worker baseline."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_worker_directories_are_present() -> None:
    for name in ("extraction-worker", "conversion-worker", "data-worker", "validation-worker"):
        assert (ROOT / "workers" / name).is_dir()


def test_migration_status_contract_is_documented() -> None:
    rules = ROOT / "docs" / "architecture" / "blueprint.md"
    content = rules.read_text(encoding="utf-8")
    for status in ("AUTO", "AUTO_TEST", "REVIEW", "BLOCKED", "ERROR"):
        assert status in content
