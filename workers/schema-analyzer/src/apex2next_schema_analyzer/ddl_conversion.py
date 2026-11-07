"""Conservative Oracle CREATE TABLE DDL conversion to PostgreSQL.

Only a deliberately small, auditable SQL subset is emitted. Source DDL is never executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

CONVERTER_VERSION = "0.1.0"
IDENT = r'(?:"(?:[^"]|"")*"|[A-Za-z_][A-Za-z0-9_$#]*)'
QUALIFIED = rf"{IDENT}(?:\s*\.\s*{IDENT})?"
TYPE_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_$#]*)(?:\s*\((.*?)\))?", re.S)


def _diag(code: str, severity: str, message: str, *, object_name: str | None = None,
          line: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"code": code, "severity": severity, "message": message}
    if object_name is not None:
        result["objectName"] = object_name
    if line is not None:
        result["line"] = line
    return result


def _mask(source: str) -> str:
    """Mask comments and quoted literals while preserving positions and newlines."""
    out = list(source)
    i = 0
    while i < len(source):
        if source.startswith("--", i):
            end = source.find("\n", i + 2)
            end = len(source) if end < 0 else end
            for p in range(i, end):
                out[p] = " "
            i = end
        elif source.startswith("/*", i):
            end = source.find("*/", i + 2)
            end = len(source) if end < 0 else end + 2
            for p in range(i, end):
                if out[p] != "\n":
                    out[p] = " "
            i = end
        elif source[i] == "'":
            end = i + 1
            while end < len(source):
                if source[end] == "'":
                    if end + 1 < len(source) and source[end + 1] == "'":
                        end += 2
                        continue
                    end += 1
                    break
                end += 1
            for p in range(i, min(end, len(source))):
                if out[p] != "\n":
                    out[p] = " "
            i = end
        elif source[i] == '"':
            # Preserve quoted identifiers, including doubled quote escapes.
            i += 1
            while i < len(source):
                if source[i] == '"':
                    if i + 1 < len(source) and source[i + 1] == '"':
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
        else:
            i += 1
    return "".join(out)


def _split_top_level(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote:
                if i + 1 < len(text) and text[i + 1] == quote:
                    i += 2
                    continue
                quote = None
        elif ch in {"'", '"'}:
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(text[start:i].strip())
            start = i + 1
        i += 1
    parts.append(text[start:].strip())
    return [part for part in parts if part]


def _find_matching_paren(text: str, opening: int) -> int | None:
    depth = 0
    quote: str | None = None
    i = opening
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote:
                if i + 1 < len(text) and text[i + 1] == quote:
                    i += 2
                    continue
                quote = None
        elif ch in {"'", '"'}:
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def _unquote_identifier(value: str) -> str:
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1].replace('""', '"')
    return value.upper()


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _split_qualified(value: str) -> list[str]:
    return [_unquote_identifier(p.strip()) for p in re.split(r"\s*\.\s*", value.strip())]


def _type_mapping(raw: str) -> tuple[str | None, str | None]:
    match = TYPE_RE.match(raw)
    if not match:
        return None, "Unrecognized column datatype."
    name = match.group(1).upper()
    args = (match.group(2) or "").strip()
    if name == "NUMBER":
        if not args:
            return "NUMERIC", None
        try:
            values = [int(x.strip()) for x in args.split(",")]
        except ValueError:
            return None, "NUMBER precision/scale is not a simple integer pair."
        if len(values) not in {1, 2} or values[0] < 1 or values[0] > 38:
            return None, "NUMBER precision/scale is outside the supported subset."
        precision = values[0]
        scale = values[1] if len(values) == 2 else 0
        if scale < -84 or scale > 127:
            return None, "NUMBER scale is outside the supported PostgreSQL mapping."
        if scale == 0:
            target = "SMALLINT" if precision <= 4 else "INTEGER" if precision <= 9 else "BIGINT" if precision <= 18 else f"NUMERIC({precision},0)"
            return target, None
        return f"NUMERIC({precision},{scale})", None
    if name in {"VARCHAR2", "NVARCHAR2", "VARCHAR"}:
        if not args or not re.fullmatch(r"\s*\d+\s*(?:BYTE|CHAR)?\s*", args, re.I):
            return None, f"{name} length/semantics require manual review."
        length = int(re.match(r"\s*(\d+)", args).group(1))
        if length < 1 or length > 10_485_760:
            return None, "Character length is outside the configured safe range."
        return f"VARCHAR({length})", None
    if name in {"CHAR", "NCHAR"}:
        if not args or not re.fullmatch(r"\s*\d+\s*(?:BYTE|CHAR)?\s*", args, re.I):
            return None, f"{name} length/semantics require manual review."
        length = int(re.match(r"\s*(\d+)", args).group(1))
        if length < 1 or length > 10_000:
            return None, "CHAR length is outside the configured safe range."
        return f"CHAR({length})", None
    if name in {"CLOB", "NCLOB"}:
        return "TEXT", None
    if name == "BLOB":
        return "BYTEA", None
    if name == "RAW":
        if not args or not re.fullmatch(r"\s*\d+\s*", args):
            return None, "RAW length must be explicit for this conversion subset."
        length = int(args)
        if length < 1 or length > 2000:
            return None, "RAW length is outside Oracle RAW limits."
        return "BYTEA", None
    if name == "DATE":
        return "TIMESTAMP(0) WITHOUT TIME ZONE", None
    if name == "TIMESTAMP":
        if args and not re.fullmatch(r"\s*\d+\s*", args):
            return None, "TIMESTAMP precision is not a simple integer."
        precision = int(args) if args else 6
        if precision > 6:
            return None, "PostgreSQL timestamp precision is at most 6."
        return f"TIMESTAMP({precision}) WITHOUT TIME ZONE", None
    if name == "BINARY_FLOAT":
        return "REAL", None
    if name == "BINARY_DOUBLE":
        return "DOUBLE PRECISION", None
    if name == "FLOAT":
        return "DOUBLE PRECISION", None
    if name == "BOOLEAN":
        return "BOOLEAN", None
    return None, f"Datatype {name} is not in the automatic mapping allowlist."


def _parse_table_body(body: str, table_name: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    columns: list[dict[str, Any]] = []
    constraints: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for fragment in _split_top_level(body):
        constraint_match = re.match(
            r"^\s*(?:CONSTRAINT\s+(?P<name>" + IDENT + r")\s+)?(?P<kind>PRIMARY\s+KEY|UNIQUE|FOREIGN\s+KEY|CHECK)\b(?P<rest>.*)$",
            fragment, re.I | re.S,
        )
        if constraint_match:
            kind = re.sub(r"\s+", " ", constraint_match.group("kind").upper())
            name = constraint_match.group("name")
            rest = constraint_match.group("rest").strip()
            if kind == "CHECK":
                diagnostics.append(_diag("ORAMAP004", "WARNING",
                    "CHECK constraint expression is preserved for manual review and is not emitted.",
                    object_name=table_name))
                continue
            local_match = re.match(r"^\s*\((.*?)\)", rest, re.S)
            if not local_match:
                diagnostics.append(_diag("ORAMAP003", "ERROR",
                    f"Could not parse {kind} column list.", object_name=table_name))
                continue
            local_columns = [_unquote_identifier(x) for x in _split_top_level(local_match.group(1))]
            item: dict[str, Any] = {"kind": kind, "name": _unquote_identifier(name) if name else None,
                                    "columns": local_columns}
            if kind == "FOREIGN KEY":
                ref = re.search(r"\bREFERENCES\s+(" + QUALIFIED + r")\s*\((.*?)\)", rest[local_match.end():], re.I | re.S)
                if not ref:
                    diagnostics.append(_diag("ORAMAP005", "WARNING",
                        "Foreign key target could not be parsed; constraint omitted.", object_name=table_name))
                    continue
                item["target"] = ref.group(1)
                item["targetColumns"] = [_unquote_identifier(x) for x in _split_top_level(ref.group(2))]
                if re.search(r"\bON\s+DELETE\s+CASCADE\b", rest, re.I):
                    item["onDelete"] = "CASCADE"
                elif re.search(r"\bON\s+DELETE\s+SET\s+NULL\b", rest, re.I):
                    item["onDelete"] = "SET NULL"
                elif re.search(r"\bON\s+DELETE\s+SET\s+DEFAULT\b", rest, re.I):
                    item["onDelete"] = "SET DEFAULT"
                elif re.search(r"\bON\s+DELETE\s+RESTRICT\b", rest, re.I):
                    item["onDelete"] = "RESTRICT"
            constraints.append(item)
            continue

        col_match = re.match(r"^\s*(" + IDENT + r")\s+(.+)$", fragment, re.I | re.S)
        if not col_match:
            diagnostics.append(_diag("ORAMAP001", "WARNING",
                "Unrecognized table element; retained in report, not emitted.", object_name=table_name))
            continue
        col_name, remainder = col_match.group(1), col_match.group(2).strip()
        type_match = TYPE_RE.match(remainder)
        if not type_match:
            diagnostics.append(_diag("ORAMAP002", "ERROR",
                f"Could not parse datatype for column {_unquote_identifier(col_name)}.",
                object_name=table_name))
            continue
        type_end = type_match.end()
        target_type, reason = _type_mapping(type_match.group(0))
        column = {"name": _unquote_identifier(col_name), "sourceType": type_match.group(0).strip(),
                  "targetType": target_type, "nullable": not bool(re.search(r"\bNOT\s+NULL\b", remainder[type_end:], re.I))}
        if reason:
            column["blockedReason"] = reason
            diagnostics.append(_diag("ORAMAP006", "ERROR",
                f"Column {column['name']}: {reason}", object_name=table_name))
        default_match = re.search(r"\bDEFAULT\s+(.+?)(?=\s+NOT\s+NULL\b|\s+CONSTRAINT\b|$)", remainder[type_end:], re.I | re.S)
        if default_match:
            default = default_match.group(1).strip()
            if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", default) or re.fullmatch(r"'(?:[^']|'')*'", default):
                column["default"] = default
            elif re.fullmatch(r"NULL", default, re.I):
                column["default"] = "NULL"
            elif re.fullmatch(r"(?:SYSTIMESTAMP|CURRENT_TIMESTAMP)", default, re.I):
                column["default"] = "CURRENT_TIMESTAMP"
            else:
                diagnostics.append(_diag("ORAMAP007", "WARNING",
                    f"Default expression for {column['name']} requires manual conversion.",
                    object_name=table_name))
        if re.search(r"\bPRIMARY\s+KEY\b", remainder[type_end:], re.I):
            constraints.append({"kind": "PRIMARY KEY", "name": None, "columns": [column["name"]]})
        if re.search(r"\bUNIQUE\b", remainder[type_end:], re.I):
            constraints.append({"kind": "UNIQUE", "name": None, "columns": [column["name"]]})
        columns.append(column)
    return columns, constraints, diagnostics


def _create_table_statements(source: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    masked = _mask(source)
    pattern = re.compile(r"\bCREATE\s+(?:GLOBAL\s+TEMPORARY\s+)?TABLE\s+(" + QUALIFIED + r")\s*\(", re.I)
    tables: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for match in pattern.finditer(masked):
        opening = masked.find("(", match.start())
        closing = _find_matching_paren(source, opening)
        if closing is None:
            diagnostics.append(_diag("ORAMAP000", "ERROR", "Unterminated CREATE TABLE definition.",
                object_name=match.group(1), line=source.count("\n", 0, match.start()) + 1))
            continue
        raw_name = match.group(1)
        name_parts = _split_qualified(raw_name)
        table_name = name_parts[-1]
        schema_name = name_parts[-2] if len(name_parts) > 1 else None
        cols, constraints, table_diags = _parse_table_body(source[opening + 1:closing], table_name)
        line = source.count("\n", 0, match.start()) + 1
        tables.append({"sourceName": raw_name, "sourceSchema": schema_name, "name": table_name,
                       "line": line, "columns": cols, "constraints": constraints,
                       "temporary": bool(re.search(r"\bGLOBAL\s+TEMPORARY\b", match.group(0), re.I))})
        diagnostics.extend({**d, "line": line} for d in table_diags)
    return tables, diagnostics


def convert_oracle_ddl(source: str, *, target_schema: str = "app") -> dict[str, Any]:
    """Convert safe CREATE TABLE subset to PostgreSQL SQL; unsafe tables are not emitted."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", target_schema):
        raise ValueError("target_schema must be a simple unquoted PostgreSQL identifier (1-63 chars).")
    tables, diagnostics = _create_table_statements(source)
    statements: list[str] = []
    converted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    source_names = {table["name"].upper(): table for table in tables}
    for table in tables:
        reasons = [c.get("blockedReason") for c in table["columns"] if c.get("blockedReason")]
        if not table["columns"]:
            reasons.append("No convertible columns were parsed.")
        if reasons:
            blocked.append({"table": table["sourceName"], "reasons": reasons})
            continue
        qtable = _quote_identifier(table["name"])
        column_sql = []
        for col in table["columns"]:
            item = f"  {_quote_identifier(col['name'])} {col['targetType']}"
            if not col["nullable"]:
                item += " NOT NULL"
            if "default" in col:
                item += " DEFAULT " + col["default"]
            column_sql.append(item)
        for constraint in table["constraints"]:
            kind = constraint["kind"]
            if kind not in {"PRIMARY KEY", "UNIQUE"}:
                continue
            cols = ", ".join(_quote_identifier(c) for c in constraint["columns"])
            cname = f" CONSTRAINT {_quote_identifier(constraint['name'])}" if constraint.get("name") else ""
            column_sql.append(f"  {cname} {kind} ({cols})")
        statements.append(f"CREATE TABLE {_quote_identifier(target_schema)}.{qtable} (\n" + ",\n".join(column_sql) + "\n);")
        converted.append({"table": table["sourceName"], "columnCount": len(table["columns"])})
    for table in tables:
        if table in blocked:
            continue
        for constraint in table["constraints"]:
            if constraint["kind"] != "FOREIGN KEY":
                continue
            target_parts = _split_qualified(constraint["target"])
            target = target_parts[-1]
            if target.upper() not in source_names:
                diagnostics.append(_diag("ORAMAP008", "WARNING",
                    f"Foreign key target {constraint['target']} is not in this DDL input; constraint omitted.",
                    object_name=table["name"]))
                continue
            if source_names[target.upper()] in [next((t for t in tables if t["sourceName"] == b["table"]), None) for b in blocked]:
                diagnostics.append(_diag("ORAMAP009", "WARNING",
                    f"Foreign key target {constraint['target']} is blocked; constraint omitted.",
                    object_name=table["name"]))
                continue
            cols = ", ".join(_quote_identifier(c) for c in constraint["columns"])
            target_cols = ", ".join(_quote_identifier(c) for c in constraint["targetColumns"])
            cname = f" CONSTRAINT {_quote_identifier(constraint['name'])}" if constraint.get("name") else ""
            action = f" ON DELETE {constraint['onDelete']}" if constraint.get("onDelete") else ""
            statements.append(f"ALTER TABLE {_quote_identifier(target_schema)}.{_quote_identifier(table['name'])}"
                f" ADD{cname} FOREIGN KEY ({cols}) REFERENCES {_quote_identifier(target_schema)}."
                f"{_quote_identifier(target)} ({target_cols}){action};")
    sql = "CREATE SCHEMA IF NOT EXISTS " + _quote_identifier(target_schema) + ";\n\n"
    sql += "\n\n".join(statements)
    if statements:
        sql += "\n"
    return {
        "format": "apex2next.oracle-to-postgresql.ddl.v1",
        "converterVersion": CONVERTER_VERSION,
        "targetSchema": target_schema,
        "sourceHash": "sha256:" + hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "tables": tables,
        "convertedTables": converted,
        "blockedTables": blocked,
        "diagnostics": sorted(diagnostics, key=lambda d: (d.get("line", 0), d["code"], d["message"])),
        "sql": sql,
        "summary": {"sourceTables": len(tables), "convertedTables": len(converted),
                    "blockedTables": len(blocked), "diagnostics": len(diagnostics)},
        "limitations": [
            "Only CREATE TABLE column definitions and selected PRIMARY KEY, UNIQUE, and FOREIGN KEY constraints are converted.",
            "CHECK constraints, indexes, triggers, views, sequences, identity semantics, partitions, grants, and PL/SQL are not converted.",
            "Oracle DATE maps to TIMESTAMP(0) WITHOUT TIME ZONE because Oracle DATE contains time-of-day.",
            "Character byte/character semantics, collation, empty-string behavior, and application-specific defaults require review.",
            "Generated SQL is a draft artifact; inspect diagnostics and execute only in a disposable target environment after approval.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert a safe Oracle CREATE TABLE subset to PostgreSQL SQL")
    parser.add_argument("ddl_file", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="JSON conversion report output")
    parser.add_argument("--sql-output", type=Path, help="Optional generated PostgreSQL SQL output")
    parser.add_argument("--target-schema", default="app")
    args = parser.parse_args()
    result = convert_oracle_ddl(args.ddl_file.read_text(encoding="utf-8", errors="replace"),
                                target_schema=args.target_schema)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.sql_output:
        args.sql_output.parent.mkdir(parents=True, exist_ok=True)
        args.sql_output.write_text(result["sql"], encoding="utf-8")
    return 1 if result["blockedTables"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
