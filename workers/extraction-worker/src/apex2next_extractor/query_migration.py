"""Conservative Oracle SQL-to-PostgreSQL query planning for generated APEX metadata."""
from __future__ import annotations

import hashlib
from typing import Any


def _walk(properties: Any, prefix: str = ""):
    if not isinstance(properties, dict):
        return
    for name, prop in sorted(properties.items()):
        if not isinstance(prop, dict):
            continue
        path = f"{prefix}.{name}" if prefix else str(name)
        yield path, prop
        if prop.get("valueType") == "OBJECT":
            yield from _walk(prop.get("value"), path)


def build_query_migration_plan(document: dict[str, Any]) -> dict[str, Any]:
    """Translate only explicitly classified SQL expressions; never execute a query."""
    from apex2next_schema_analyzer.sql_expression import convert_expression
    from apex2next_schema_analyzer.sql_tokens import tokenize

    objects = document.get("objects", [])
    known_objects = frozenset(
        str(obj.get("name", "")).upper()
        for obj in objects
        if str(obj.get("type", "")).upper() in {"TABLE", "VIEW"} and obj.get("name")
    )
    entries = []
    for obj in sorted(objects, key=lambda item: str(item.get("id", ""))):
        for property_path, prop in _walk(obj.get("properties", {})):
            language = str(prop.get("expressionLanguage", "")).upper()
            value_type = str(prop.get("valueType", "")).upper()
            if language != "SQL" and value_type != "SQL_EXPRESSION":
                continue
            source_sql = str(prop.get("rawExpression") or "")
            if not source_sql:
                entries.append({
                    "objectId": str(obj.get("id", "")), "objectType": str(obj.get("type", "")),
                    "propertyPath": property_path, "disposition": "MANUAL",
                    "targetSql": None, "findings": [{"code": "R3Q001",
                    "message": "SQL expression has no preserved raw source."}],
                    "executionEnabled": False,
                })
                continue
            try:
                result = convert_expression(tokenize(source_sql), known_objects=known_objects)
                entries.append({
                    "objectId": str(obj.get("id", "")), "objectType": str(obj.get("type", "")),
                    "objectName": str(obj.get("name") or ""), "propertyPath": property_path,
                    "disposition": result.disposition, "targetSql": result.sql,
                    "targetSqlSha256": "sha256:" + hashlib.sha256(result.sql.encode()).hexdigest(),
                    "findings": result.findings, "objectReferences": sorted(result.object_refs),
                    "unresolvedReferences": sorted(result.unresolved_refs),
                    "executionEnabled": False,
                })
            except (ValueError, TypeError) as exc:
                entries.append({
                    "objectId": str(obj.get("id", "")), "objectType": str(obj.get("type", "")),
                    "objectName": str(obj.get("name") or ""), "propertyPath": property_path,
                    "disposition": "UNSUPPORTED", "targetSql": None,
                    "findings": [{"code": "R3Q002", "message": f"SQL tokenization/conversion failed: {exc}"}],
                    "executionEnabled": False,
                })
    return {
        "format": "apex2next.query-migration-plan.v1",
        "converter": "schema-analyzer.sql-expression",
        "queryCount": len(entries),
        "automaticCount": sum(item["disposition"] == "AUTOMATIC" for item in entries),
        "assistedCount": sum(item["disposition"] == "ASSISTED" for item in entries),
        "manualCount": sum(item["disposition"] == "MANUAL" for item in entries),
        "unsupportedCount": sum(item["disposition"] == "UNSUPPORTED" for item in entries),
        "queries": entries,
        "safety": {"executed": False, "executionEnabled": False,
                   "manualReviewRequired": any(item["disposition"] != "AUTOMATIC" for item in entries)},
    }


def build_query_migration_files(document: dict[str, Any]) -> dict[str, str]:
    import json

    plan = build_query_migration_plan(document)
    return {
        "migration-report/query-migration-plan.json": json.dumps(
            plan, ensure_ascii=False, sort_keys=True, indent=2
        ) + "\\n",
    }