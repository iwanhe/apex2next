"""Validation helpers for the versioned APEX2NEXT application IR contract."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

DEFAULT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[4]
    / "packages"
    / "ir-schema"
    / "schema"
    / "apex2next.application-ir.v1.schema.json"
)


@lru_cache(maxsize=4)
def load_ir_schema(schema_path: str | Path | None = None) -> dict[str, Any]:
    """Load and meta-validate the IR JSON Schema."""
    path = Path(schema_path) if schema_path is not None else DEFAULT_SCHEMA_PATH
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def validate_ir_document(
    document: dict[str, Any], schema_path: str | Path | None = None
) -> list[dict[str, Any]]:
    """Return deterministic, machine-readable diagnostics for an IR document."""
    validator = Draft202012Validator(
        load_ir_schema(str(schema_path) if schema_path is not None else None),
        format_checker=FormatChecker(),
    )
    errors = sorted(
        validator.iter_errors(document),
        key=lambda error: (tuple(str(part) for part in error.absolute_path), error.message),
    )
    return [
        {
            "code": "IR001",
            "severity": "ERROR",
            "category": "IR_SCHEMA",
            "path": "/" + "/".join(str(part) for part in error.absolute_path),
            "message": error.message,
        }
        for error in errors
    ]
