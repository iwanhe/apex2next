"""Conservative object inventory from Oracle DDL scripts.

This module inventories CREATE headers and high-confidence REFERENCES edges.
It does not claim to fully parse SQL/PLSQL or resolve dynamic dependencies.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


TOKEN_PATTERN = re.compile(
    r'"(?:[^"]|"")*"|[A-Za-z_][A-Za-z0-9_$#]*|\d+(?:\.\d+)?|\S',
    re.MULTILINE,
)


@dataclass(frozen=True)
class Token:
    value: str
    offset: int


@dataclass(frozen=True)
class SchemaObject:
    object_type: str
    object_name: str
    line: int
    column: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _mask_comments_and_strings(source: str) -> str:
    """Replace comments/string bodies with spaces while preserving offsets/newlines."""
    chars = list(source)
    index = 0
    while index < len(source):
        if source.startswith("--", index):
            end = source.find("\n", index + 2)
            end = len(source) if end < 0 else end
            for pos in range(index, end):
                chars[pos] = " "
            index = end
        elif source.startswith("/*", index):
            end = source.find("*/", index + 2)
            end = len(source) if end < 0 else end + 2
            for pos in range(index, end):
                if chars[pos] != "\n":
                    chars[pos] = " "
            index = end
        elif source[index] == "'":
            end = index + 1
            while end < len(source):
                if source[end] == "'":
                    if end + 1 < len(source) and source[end + 1] == "'":
                        end += 2
                        continue
                    end += 1
                    break
                end += 1
            for pos in range(index, min(end, len(source))):
                if chars[pos] != "\n":
                    chars[pos] = " "
            index = end
        else:
            index += 1
    return "".join(chars)


def _tokens(source: str) -> list[Token]:
    return [Token(match.group(0), match.start()) for match in TOKEN_PATTERN.finditer(source)]


def _qualified_name(tokens: list[Token], index: int) -> tuple[str, int]:
    if index >= len(tokens):
        return "", index
    parts = [tokens[index].value]
    cursor = index + 1
    while cursor + 1 < len(tokens) and tokens[cursor].value == ".":
        parts.extend((".", tokens[cursor + 1].value))
        cursor += 2
    return "".join(parts), cursor


def _normalize_name(name: str) -> str:
    return name.strip().strip('"')


def analyze_ddl(source: str) -> dict[str, Any]:
    """Inventory Oracle CREATE objects and FK REFERENCES dependencies."""
    masked = _mask_comments_and_strings(source)
    tokens = _tokens(masked)
    objects: list[SchemaObject] = []
    dependencies: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    index = 0

    while index < len(tokens):
        if tokens[index].value.upper() != "CREATE":
            index += 1
            continue
        cursor = index + 1
        if cursor + 1 < len(tokens) and tokens[cursor].value.upper() == "OR" and tokens[cursor + 1].value.upper() == "REPLACE":
            cursor += 2
        while cursor < len(tokens) and tokens[cursor].value.upper() in {
            "FORCE", "EDITIONABLE", "NONEDITIONABLE", "PUBLIC", "UNIQUE", "BITMAP",
        }:
            cursor += 1
        if cursor + 1 < len(tokens) and tokens[cursor].value.upper() in {"GLOBAL", "PRIVATE"} and tokens[cursor + 1].value.upper() == "TEMPORARY":
            cursor += 2
        if cursor < len(tokens) and tokens[cursor].value.upper() == "MATERIALIZED":
            cursor += 1
            kind = "MATERIALIZED VIEW"
            if cursor < len(tokens) and tokens[cursor].value.upper() == "VIEW":
                cursor += 1
            else:
                index += 1
                continue
        elif cursor < len(tokens) and tokens[cursor].value.upper() in {"PACKAGE", "TYPE"} and cursor + 1 < len(tokens) and tokens[cursor + 1].value.upper() == "BODY":
            kind = tokens[cursor].value.upper() + " BODY"
            cursor += 2
        elif cursor < len(tokens) and tokens[cursor].value.upper() == "DATABASE" and cursor + 1 < len(tokens) and tokens[cursor + 1].value.upper() == "LINK":
            kind = "DATABASE LINK"
            cursor += 2
        elif cursor < len(tokens) and tokens[cursor].value.upper() == "SYNONYM" and cursor + 1 < len(tokens) and tokens[cursor + 1].value.upper() == "PUBLIC":
            kind = "PUBLIC SYNONYM"
            cursor += 2
        elif cursor < len(tokens) and tokens[cursor].value.upper() == "INDEX" and cursor + 1 < len(tokens):
            kind = "INDEX"
            cursor += 1
        elif cursor < len(tokens) and tokens[cursor].value.upper() in {
            "TABLE", "VIEW", "SEQUENCE", "SYNONYM", "PROCEDURE", "FUNCTION",
            "PACKAGE", "TYPE", "TRIGGER", "CONTEXT", "JOB", "USER",
        }:
            kind = tokens[cursor].value.upper()
            cursor += 1
        else:
            index += 1
            continue

        name, after_name = _qualified_name(tokens, cursor)
        if name:
            line = masked.count("\n", 0, tokens[index].offset) + 1
            last_newline = masked.rfind("\n", 0, tokens[index].offset)
            column = tokens[index].offset - last_newline
            key = (kind, name.upper(), tokens[index].offset)
            if key not in seen:
                objects.append(SchemaObject(kind, _normalize_name(name), line, column))
                seen.add(key)
            index = max(index + 1, after_name)
        else:
            diagnostics.append({
                "code": "ORADDL001",
                "severity": "WARNING",
                "message": f"Could not read object name after CREATE {kind}",
                "line": line,
            })
            index += 1

    # Foreign-key REFERENCES is a higher-confidence dependency than heuristic FROM/JOIN scans.
    for token_index, token in enumerate(tokens[:-1]):
        if token.value.upper() == "REFERENCES":
            target, _ = _qualified_name(tokens, token_index + 1)
            if target:
                dependencies.append({
                    "dependency_type": "REFERENCES",
                    "target_object": _normalize_name(target),
                    "line": masked.count("\n", 0, token.offset) + 1,
                    "confidence": 1.0,
                })

    counts: dict[str, int] = {}
    for item in objects:
        counts[item.object_type] = counts.get(item.object_type, 0) + 1
    return {
        "format": "apex2next.oracle-ddl-inventory.v1",
        "objects": [item.to_dict() for item in objects],
        "dependencies": dependencies,
        "summary": {"total_objects": len(objects), "object_counts": counts, "total_dependencies": len(dependencies)},
        "diagnostics": diagnostics,
        "limitations": [
            "Static CREATE-header inventory only; not a complete Oracle SQL/PLSQL parser.",
            "Dynamic SQL and dependencies hidden in PL/SQL bodies are not resolved.",
            "Run against a complete, privilege-appropriate DBMS_METADATA export for a more complete inventory.",
        ],
    }
