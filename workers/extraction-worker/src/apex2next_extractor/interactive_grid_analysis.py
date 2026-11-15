"""Fail-closed eligibility analysis for editable APEX Interactive Grids.

This module deliberately does not generate DML. It separates facts that can be
proven from the export from security/parity gates that still require review.
"""
from __future__ import annotations

import re
from typing import Any

_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]*$")
_TABLE = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]*(?:\.[A-Za-z][A-Za-z0-9_$#]*)?$")
_ALLOWED_OPERATIONS = {"i", "u", "d"}


def _explicit_bool(value: Any) -> bool | None:
    if value is True or (isinstance(value, str) and value.strip().upper() in {"Y", "YES", "TRUE"}):
        return True
    if value is False or (isinstance(value, str) and value.strip().upper() in {"N", "NO", "FALSE"}):
        return False
    return None


def _operations(value: Any) -> set[str] | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw_parts = [part.strip().lower() for part in re.split(r"[,;:]", value)]
    if not raw_parts or any(not part for part in raw_parts):
        return None
    parts = set(raw_parts)
    if not parts <= _ALLOWED_OPERATIONS:
        return None
    return parts


def _finding(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def analyze_editable_interactive_grids(inventory: dict[str, Any]) -> dict[str, Any]:
    """Classify editable IGs without ever granting write permission.

    A candidate can reach REVIEW_REQUIRED only when export metadata proves a
    table-backed grid, associated native DML process, explicit single key,
    safe identifiers, explicit visibility/writeability, and known operations.
    Authorization, row scope, validation parity and concurrency implementation
    remain mandatory human/runtime gates, so auto_generate is always False.
    """
    results: list[dict[str, Any]] = []
    for page in inventory.get("pages", []):
        components = page.get("components", [])
        regions = [c for c in components if c.get("kind") == "REGION"
                   and c.get("props", {}).get("plug_source_type") == "NATIVE_IG"]
        processes = [c for c in components if c.get("kind") == "PROCESS"]
        columns = [c for c in components if c.get("kind") == "REGION_COLUMN"]
        for region in regions:
            props = region.get("props", {})
            editable = _explicit_bool(props.get("is_editable"))
            if editable is False:
                continue  # explicitly read-only grids use the existing read-only path

            findings: list[dict[str, str]] = []
            if editable is None:
                findings.append(_finding("IG000", "Editability is not explicit; the grid cannot be treated as writable."))
            table = props.get("query_table")
            if props.get("query_type") != "TABLE" or not isinstance(table, str) or not _TABLE.fullmatch(table):
                findings.append(_finding("IG001", "Grid source must be an explicitly table-backed query with a simple table identifier."))

            region_name = region.get("name")
            region_id = props.get("source_id")
            if not isinstance(region_id, str) or not region_id.strip():
                findings.append(_finding("IG015", "The region's immutable export ID is missing; component ownership cannot be proven."))
                region_columns = []
            else:
                region_columns = [c for c in columns if c.get("props", {}).get("region_id") == region_id]
            if not region_columns:
                findings.append(_finding("IG002", "No region-column metadata is explicitly associated with this region ID."))

            keys: list[str] = []
            writable: list[str] = []
            for col in region_columns:
                cp = col.get("props", {})
                visible = _explicit_bool(cp.get("is_visible"))
                if visible is None:
                    findings.append(_finding("IG003", f"Column {col.get('name')} has no explicit visibility metadata."))
                expr = cp.get("source_expression")
                if not isinstance(expr, str) or not _IDENTIFIER.fullmatch(expr.strip()):
                    findings.append(_finding("IG004", f"Column {col.get('name')} is not a simple identifier projection."))
                if _explicit_bool(cp.get("is_primary_key")) is True:
                    if isinstance(expr, str) and _IDENTIFIER.fullmatch(expr.strip()):
                        keys.append(expr.strip().lower())
                    else:
                        findings.append(_finding("IG005", f"Primary-key column {col.get('name')} has an unsupported source expression."))
                query_only = _explicit_bool(cp.get("is_query_only"))
                read_only = _explicit_bool(cp.get("is_readonly"))
                required = _explicit_bool(cp.get("is_required"))
                if query_only is None or read_only is None:
                    findings.append(_finding("IG006", f"Column {col.get('name')} lacks explicit query-only/read-only metadata."))
                if required is None:
                    findings.append(_finding("IG014", f"Column {col.get('name')} lacks explicit required metadata."))
                elif required is True:
                    # Required/default and validation semantics are recorded for review, never inferred here.
                    pass
                if query_only is False and read_only is False and visible is True:
                    if isinstance(expr, str) and _IDENTIFIER.fullmatch(expr.strip()) and expr.strip().lower() not in keys:
                        writable.append(expr.strip().lower())

            if len(keys) != 1:
                findings.append(_finding("IG007", "Exactly one explicitly identified simple primary-key column is required."))
            if not writable:
                findings.append(_finding("IG008", "No explicitly visible, writable column is available."))

            operations = _operations(props.get("edit_operations"))
            if operations is None:
                findings.append(_finding("IG009", "Allowed insert/update/delete operations are missing or unsupported."))

            dml = [p for p in processes if p.get("props", {}).get("native_ig_dml_candidate") is True
                   and isinstance(region_id, str)
                   and p.get("props", {}).get("region_id") == region_id]
            if len(dml) != 1:
                findings.append(_finding("IG010", "Exactly one native IG DML process explicitly associated with this editable region is required."))

            # Keep structural eligibility separate from the mandatory security/parity review gates.
            # This avoids a fragile "number of findings" heuristic when new gates are added later.
            structural_blocked = bool(findings)

            # These are deliberately unconditional blockers until dedicated translators and
            # runtime enforcement are implemented and parity-tested.
            findings.extend([
                _finding("IG011", "Page/process authorization and row-level authorization are not yet proven for generated row DML."),
                _finding("IG012", "APEX validations, server-side conditions and per-operation behavior need explicit mapping."),
                _finding("IG013", "Lost-update metadata is preserved but its source semantics are not yet proven equivalent to runtime checks."),
            ])

            results.append({
                "pageId": page.get("id"),
                "region": region_name,
                "region_id": region_id if isinstance(region_id, str) else None,
                "table": table if isinstance(table, str) else None,
                "classification": "MANUAL" if structural_blocked else "REVIEW_REQUIRED",
                "auto_generate": False,
                "primary_key": keys[0] if len(keys) == 1 else None,
                "writable_columns": sorted(set(writable)),
                "required_columns": sorted({c.get("props", {}).get("source_expression", "").strip().lower() for c in region_columns if _explicit_bool(c.get("props", {}).get("is_required")) is True and isinstance(c.get("props", {}).get("source_expression"), str)}),
                "column_metadata": [{
                    "column": c.get("props", {}).get("source_expression"),
                    "is_required": _explicit_bool(c.get("props", {}).get("is_required")),
                    "default_type": c.get("props", {}).get("default_type"),
                    "default_expression": c.get("props", {}).get("default_expression"),
                    "is_visible": _explicit_bool(c.get("props", {}).get("is_visible")),
                    "is_query_only": _explicit_bool(c.get("props", {}).get("is_query_only")),
                    "is_readonly": _explicit_bool(c.get("props", {}).get("is_readonly")),
                } for c in region_columns],
                "operations": sorted(operations) if operations else [],
                "native_dml_processes": [p.get("name") for p in dml],
                "security_evidence": {
                    "page_scheme": page.get("scheme"),
                    "region_scheme": props.get("security_scheme"),
                    "process_schemes": [p.get("props", {}).get("security_scheme") for p in dml],
                    "row_scope_proven": False,
                },
                "validation_evidence": [
                    {"name": c.get("name"), "type": c.get("props", {}).get("validation_type"),
                     "associated_item": c.get("props", {}).get("associated_item")}
                    for c in components if c.get("kind") == "VALIDATION"
                ],
                "lost_update_check_type": props.get("lost_update_check_type"),
                "findings": findings,
            })

    return {
        "format": "apex2next.editable-ig-analysis.v1",
        "summary": {
            "editable_grids": len(results),
            "review_required": sum(r["classification"] == "REVIEW_REQUIRED" for r in results),
            "manual": sum(r["classification"] == "MANUAL" for r in results),
            "auto_generate": 0,
        },
        "grids": results,
    }


def main() -> int:
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Fail-closed eligibility analysis for editable APEX Interactive Grids")
    parser.add_argument("inventory", type=Path, help="apex-page-inventory.json produced by apex2next inventory")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    result = analyze_editable_interactive_grids(inventory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = result["summary"]
    print(f"Editable grids: {summary['editable_grids']}; review required: {summary['review_required']}; "
          f"manual: {summary['manual']}; auto-generate: 0")
    print(f"Written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
