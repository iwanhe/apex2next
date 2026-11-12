"""Offline, conservative PL/SQL conversion workbench and rule registry."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

WORKBENCH_FORMAT = "apex2next.plsql-workbench.v1"
RULE_REGISTRY_VERSION = "2026.11.1"
MAX_SOURCE_CHARS = 1_000_000

_RULES = (
    ("PLW001", r"\bNVL\s*\(", "ASSISTED", "NVL has Oracle-specific type and empty-string semantics; review before COALESCE conversion."),
    ("PLW002", r"\bDECODE\s*\(", "MANUAL", "DECODE null and type-comparison behavior needs an explicit CASE mapping."),
    ("PLW003", r"\bSYSDATE\b", "MANUAL", "Choose an explicit target clock and timezone policy."),
    ("PLW004", r"\bSYSTIMESTAMP\b", "MANUAL", "Review timestamp precision and timezone semantics."),
    ("PLW005", r"\bROWNUM\b", "MANUAL", "Review ordering and evaluation semantics before LIMIT/window rewrite."),
    ("PLW006", r"\bCONNECT\s+BY\b", "UNSUPPORTED", "Hierarchical queries require a separately reviewed recursive-query transformation."),
    ("PLW007", r"\bDBMS_[A-Z0-9_$]+\b", "UNSUPPORTED", "Oracle DBMS package calls need a target-specific replacement or service boundary."),
    ("PLW008", r"\bEXECUTE\s+IMMEDIATE\b", "MANUAL", "Review dynamic SQL binds, identifier validation, and execution semantics."),
    ("PLW009", r"%\s*(?:TYPE|ROWTYPE)\b", "MANUAL", "Anchored declarations need explicit target type and record-shape resolution."),
    ("PLW010", r"\bPRAGMA\s+AUTONOMOUS_TRANSACTION\b", "UNSUPPORTED", "Autonomous transaction boundaries have no safe direct equivalent."),
    ("PLW011", r"\bBULK\s+COLLECT\b|\bFORALL\b", "MANUAL", "Bulk SQL behavior and exception handling need explicit redesign."),
    ("PLW012", r"\bWHEN\s+OTHERS\b", "MANUAL", "Review exception scope, rethrow behavior, and transaction handling."),
    ("PLW013", r"\bUTL_(?:HTTP|FILE|SMTP|TCP)\b", "UNSUPPORTED", "UTL integrations require an external service or approved target adapter."),
    ("PLW014", r"\bDBMS_SCHEDULER\b", "UNSUPPORTED", "Move scheduling to an explicitly designed job runtime."),
    ("PLW015", r"\bPIPELINED\b", "UNSUPPORTED", "Pipelined table functions need a redesigned set-returning function or service."),
    ("PLW016", r"\bAUTHID\s+(?:CURRENT_USER|DEFINER)\b", "MANUAL", "Map invoker/definer rights to target ownership and authorization explicitly."),
    ("PLW017", r"\b(?:SAVEPOINT|ROLLBACK\s+TO)\b", "MANUAL", "Review transaction ownership and savepoint behavior in the target runtime."),
)


def rule_registry() -> dict[str, Any]:
    """Return a deterministic, JSON-serializable registry snapshot."""
    return {
        "version": RULE_REGISTRY_VERSION,
        "rules": [
            {
                "id": rule_id,
                "pattern": pattern,
                "disposition": disposition,
                "guidance": guidance,
            }
            for rule_id, pattern, disposition, guidance in _RULES
        ],
        "automaticRewriteCount": 0,
    }


def _mask_comments_and_literals(source: str) -> str:
    """Mask comments and quoted text without changing offsets or newlines."""
    chars = list(source)
    i = 0
    length = len(source)

    while i < length:
        if source.startswith("--", i):
            end = source.find("\n", i)
            if end < 0:
                end = length
            for index in range(i, end):
                chars[index] = " "
            i = end
        elif source.startswith("/*", i):
            start = i
            depth = 1
            i += 2
            while i < length and depth:
                if source.startswith("/*", i):
                    depth += 1
                    i += 2
                elif source.startswith("*/", i):
                    depth -= 1
                    i += 2
                else:
                    i += 1
            for index in range(start, i):
                if chars[index] != "\n":
                    chars[index] = " "
        elif source[i] in ("'", '"'):
            quote = source[i]
            start = i
            i += 1
            while i < length:
                if source[i] == quote and i + 1 < length and source[i + 1] == quote:
                    i += 2
                elif source[i] == quote:
                    i += 1
                    break
                else:
                    i += 1
            for index in range(start, i):
                if chars[index] != "\n":
                    chars[index] = " "
        else:
            i += 1

    return "".join(chars)


def _position(source: str, offset: int) -> tuple[int, int]:
    line = source.count("\n", 0, offset) + 1
    return line, offset - source.rfind("\n", 0, offset)


def _artifact_kind(masked: str) -> str:
    unit_pattern = (
        r"\bCREATE\s+(?:OR\s+REPLACE\s+)?"
        r"(?:(?:EDITIONABLE|NONEDITIONABLE)\s+)?"
        r"(?:PACKAGE\s+BODY|TYPE\s+BODY|PACKAGE|PROCEDURE|FUNCTION|TRIGGER|TYPE)\b"
    )
    if re.search(unit_pattern, masked, re.IGNORECASE):
        return "PLSQL_UNIT"
    if re.match(r"\s*(?:DECLARE|BEGIN)\b", masked, re.IGNORECASE):
        return "ANONYMOUS_BLOCK"
    if re.search(r"\b(?:SELECT|INSERT|UPDATE|DELETE|MERGE)\b", masked, re.IGNORECASE):
        return "SQL_FRAGMENT"
    return "UNKNOWN"


def analyze_plsql(source: str, *, source_name: str = "<memory>") -> dict[str, Any]:
    """Analyze a bounded SQL/PLSQL fragment without parsing or executing it."""
    if not isinstance(source, str):
        raise TypeError("source must be a string")
    if len(source) > MAX_SOURCE_CHARS:
        raise ValueError(f"source exceeds {MAX_SOURCE_CHARS} characters")
    if not isinstance(source_name, str) or not source_name.strip():
        raise ValueError("source_name must be a non-empty string")

    masked = _mask_comments_and_literals(source)
    diagnostics: list[dict[str, Any]] = []
    statement_counts: dict[str, int] = {}
    keywords = (
        "SELECT", "INSERT", "UPDATE", "DELETE", "MERGE", "COMMIT",
        "ROLLBACK", "SAVEPOINT", "OPEN", "FETCH", "CLOSE", "RAISE",
    )
    for keyword in keywords:
        statement_counts[keyword.lower()] = len(
            re.findall(rf"\b{keyword}\b", masked, re.IGNORECASE)
        )

    for rule_id, pattern, disposition, guidance in _RULES:
        for match in re.finditer(pattern, masked, re.IGNORECASE):
            line, column = _position(source, match.start())
            diagnostics.append(
                {
                    "code": rule_id,
                    "severity": "UNSUPPORTED" if disposition == "UNSUPPORTED" else "WARNING",
                    "disposition": disposition,
                    "message": guidance,
                    "source": {"name": source_name, "line": line, "column": column},
                    "matchedText": source[match.start():match.end()],
                }
            )

    dispositions = {item["disposition"] for item in diagnostics}
    if "UNSUPPORTED" in dispositions:
        status = "UNSUPPORTED"
    elif dispositions:
        status = "MANUAL"
    else:
        status = "REVIEW_REQUIRED"

    diagnostics.sort(
        key=lambda item: (
            item["source"]["line"],
            item["source"]["column"],
            item["code"],
        )
    )
    return {
        "format": WORKBENCH_FORMAT,
        "registryVersion": RULE_REGISTRY_VERSION,
        "source": {
            "name": source_name,
            "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "characterCount": len(source),
        },
        "artifactKind": _artifact_kind(masked),
        "status": status,
        "statementInventory": statement_counts,
        "diagnostics": diagnostics,
        "candidateSource": source,
        "rewriteCount": 0,
        "limitations": [
            "Lexical rule analysis only; not a complete Oracle PL/SQL parser.",
            "No source or generated SQL/PLSQL is executed.",
            "No rule is AUTOMATIC and no source rewrite is applied.",
            "No diagnostics does not prove syntax validity or semantic equivalence.",
            "Package state, grants, synonyms, database links, triggers, transaction boundaries, "
            "NLS, timezone, and external integrations need separate analysis.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Oracle PL/SQL for APEX2NEXT migration")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze_plsql(
        args.input.read_text(encoding="utf-8"),
        source_name=str(args.input),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return 2 if report["status"] == "UNSUPPORTED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
