"""WP9.3 APEX consumer references for schema dependency validation.

Input is the list of import-API calls produced by
``apex2next_extractor.apex_export.extract_export`` per export file (the export
is never executed). Output is a list of reference groups that
``schema_plan.build_schema_plan(apex_references=...)`` validates:

- FORM_TABLE: table-backed regions and the columns their items/IG columns use;
- SQL: objects after FROM/JOIN in region/chart/LOV/IR queries, plus directly
  selected source columns of single-object queries;
- PLSQL_CALL: ``package.member`` calls in processes, authorizations, etc.
"""
from __future__ import annotations

import re
from typing import Any

from .sql_tokens import TokenizeError, identifier_name, significant, split_top_level, string_value, tokenize

SQL_ARGS = ("p_plug_source", "p_data_source", "p_lov_query", "p_source", "p_query_where",
            "p_list_query")
PLSQL_ARGS = ("p_process_sql_clob", "p_attribute_01", "p_plug_source", "p_validation",
              "p_validation2", "p_source", "p_function_body", "p_plsql_code",
              "p_condition_expression1", "p_authorization_scheme_body", "p_attributes")
IGNORED_PREFIXES = ("APEX_", "WWV_", "DBMS_", "UTL_", "SYS", "HTP", "HTF", "OWA")


def _text(value: Any, raw: str | None) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and raw and any(k in raw.lower() for k in (
            "wwv_flow_string.join", "wwv_flow_t_varchar2", "wwv_flow_t_plugin_attributes")):
        try:
            return "\n".join(string_value(t) for t in tokenize(raw) if t.kind == "STRING")
        except TokenizeError:
            return None
    return None


def _sql_objects(sql: str) -> tuple[list[str], list[str] | None]:
    """Objects after FROM/JOIN and source columns of a single-object select list."""
    try:
        tokens = tokenize(sql)
    except TokenizeError:
        return [], None
    sig = significant(tokens)
    objects: list[str] = []
    for i, t in enumerate(sig[:-1]):
        if t.kind == "IDENT" and t.upper in {"FROM", "JOIN"} and sig[i + 1].kind in {"IDENT", "QIDENT"}:
            name = identifier_name(sig[i + 1])
            if i + 3 < len(sig) and sig[i + 2].text == ".":
                name = identifier_name(sig[i + 3])
            if name.upper() not in {"DUAL", "TABLE", "LATERAL"}:
                objects.append(name.upper())
    columns: list[str] | None = None
    if len(set(objects)) == 1 and sig and sig[0].upper == "SELECT":
        start = tokens.index(sig[0]) + 1
        depth = 0
        end = len(tokens)
        for idx in range(start, len(tokens)):
            tk = tokens[idx]
            if tk.kind == "OP" and tk.text == "(":
                depth += 1
            elif tk.kind == "OP" and tk.text == ")":
                depth -= 1
            elif depth == 0 and tk.kind == "IDENT" and tk.upper == "FROM":
                end = idx
                break
        columns = []
        for item in split_top_level(tokens[start:end]):
            s = significant(item)
            if len(s) == 1 and s[0].kind in {"IDENT", "QIDENT"}:
                columns.append(identifier_name(s[0]).upper())
            elif len(s) == 3 and s[1].text == "." and s[2].kind in {"IDENT", "QIDENT"}:
                columns.append(identifier_name(s[2]).upper())
    return sorted(set(objects)), columns


def _plsql_calls(text: str) -> list[tuple[str, str]]:
    try:
        sig = significant(tokenize(text))
    except TokenizeError:
        return []
    calls = []
    for i in range(len(sig) - 2):
        a, dot, b = sig[i], sig[i + 1], sig[i + 2]
        if a.kind in {"IDENT", "QIDENT"} and dot.text == "." and b.kind in {"IDENT", "QIDENT"} \
                and not (i > 0 and sig[i - 1].text == "."):
            pkg = identifier_name(a).upper()
            if re.search(r"_PKG$", pkg) and not pkg.startswith(IGNORED_PREFIXES):
                calls.append((pkg, identifier_name(b).upper()))
    return calls


def collect_apex_references(calls_by_file: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for path in sorted(calls_by_file):
        calls = calls_by_file[path]
        page = next((c["arguments"].get("p_id") for c in calls if c["routine"] == "create_page"), None)
        where = f"page {page}" if page is not None else path
        plugs = {}
        for c in calls:
            if c["routine"] == "create_page_plug":
                pid = c["raw_arguments"].get("p_id")
                plugs[pid] = c
        # form/table regions and their item columns
        for pid, plug in plugs.items():
            args = plug["arguments"]
            if str(args.get("p_query_type", "")).upper() == "TABLE" and args.get("p_query_table"):
                cols = sorted({str(c["arguments"]["p_source"]).upper() for c in calls
                               if c["routine"] == "create_page_item"
                               and c["raw_arguments"].get("p_item_source_plug_id") == pid
                               and c["arguments"].get("p_source_type") in (None, "REGION_SOURCE_COLUMN")
                               and isinstance(c["arguments"].get("p_source"), str)}
                              | {str(c["arguments"]["p_source_expression"]).upper() for c in calls
                                 if c["routine"] == "create_region_column"
                                 and c["raw_arguments"].get("p_region_id") == pid
                                 and c["arguments"].get("p_source_type") == "DB_COLUMN"
                                 and isinstance(c["arguments"].get("p_source_expression"), str)})
                refs.append({"kind": "FORM_TABLE", "source": f"{where} region {args.get('p_plug_name')}",
                             "object": str(args["p_query_table"]).upper(), "columns": cols})
        # SQL sources and PL/SQL calls
        for c in calls:
            label = f"{where} {c['routine']} {c['arguments'].get('p_plug_name') or c['arguments'].get('p_name') or c['arguments'].get('p_process_name') or c['arguments'].get('p_lov_name') or ''}".strip()
            for arg in SQL_ARGS:
                text = _text(c["arguments"].get(arg), c["raw_arguments"].get(arg))
                if not text or not re.search(r"\bselect\b[\s\S]*\bfrom\b", text, re.I):
                    continue
                objects, columns = _sql_objects(text)
                for i, obj in enumerate(objects):
                    refs.append({"kind": "SQL", "source": f"{label} [{arg}]", "object": obj,
                                 "columns": columns if (columns and len(objects) == 1) else []})
            seen = set()
            for arg in PLSQL_ARGS:
                text = _text(c["arguments"].get(arg), c["raw_arguments"].get(arg))
                if not text:
                    continue
                for pkg, member in _plsql_calls(text):
                    if (pkg, member) in seen:
                        continue
                    seen.add((pkg, member))
                    refs.append({"kind": "PLSQL_CALL", "source": f"{label} [{arg}]", "object": pkg,
                                 "member": member})
    return refs
