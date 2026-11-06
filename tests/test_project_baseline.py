"""Smoke tests for the repository's initial Python worker baseline."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_worker_boundaries_are_documented() -> None:
    worker_readme = ROOT / "workers" / "README.md"
    content = worker_readme.read_text(encoding="utf-8")
    for name in ("extraction-worker", "conversion-worker", "data-worker", "validation-worker"):
        assert name in content


def test_migration_status_contract_is_documented() -> None:
    rules = ROOT / "docs" / "architecture" / "blueprint.md"
    content = rules.read_text(encoding="utf-8")
    for status in ("AUTO", "AUTO_TEST", "REVIEW", "BLOCKED", "ERROR"):
        assert status in content
