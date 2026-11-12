"""WP9.3 schema plan: Oracle install script -> reviewed PostgreSQL schema draft.

Produces, deterministically and without executing anything:
- an object inventory where *every* statement receives a disposition;
- converted table/constraint/index/view DDL in dependency order;
- dependency validation checks (DEP-xxx);
- trigger and PL/SQL behavior inventories for WP9.4;
- an expected PostgreSQL catalog manifest for integration verification;
- post-load identity alignment SQL and a load-column plan for WP9.6.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .inventory import analyze_ddl
from .plsql_workbench import analyze_plsql
from .schema_conversion import (
    SCHEMA_CONVERTER_VERSION,
    SCHEMA_RULES,
    finding,
    identity_clause,
    parse_alter_table,
    parse_comment,
    parse_create_index,
    parse_create_table,
    parse_sequence,
    catalog_type,
    target_name,
    worst,
)
from .sql_expression import (
    EXPRESSION_RULES,
    IMMUTABLE_FUNCTIONS,
    PG_RESERVED,
    PORTABLE_FUNCTIONS,
    SEMANTIC_DIFF_FUNCTIONS,
    convert_expression,
    pg_ident,
)
from .source_overrides import apply_overrides, load_overrides
from .sql_tokens import Statement, identifier_name, significant, split_script
from .trigger_analysis import TRIGGER_RULES, parse_trigger
from .trigger_conversion import APP_USER_SQL, TRIGGER_CONVERSION_RULES, convert_trigger
from .view_conversion import VIEW_RULES, convert_view, parse_view, view_design, view_sql

PLAN_FORMAT = "apex2next.schema-plan.v1"
PLSQL_KINDS = {"PACKAGE", "PACKAGE_BODY", "PROCEDURE", "FUNCTION", "TYPE", "TYPE_BODY"}
PLAN_RULES: dict[str, tuple[str, str]] = {
    "PLS001": ("MANUAL", "PL/SQL unit is business logic; re-implemented as NestJS services in WP9.4."),
    "DAT001": ("MANUAL", "Configuration/seed DML is data, not schema; migrated and reconciled in WP9.6."),
    "STM001": ("AUTOMATIC", "Transaction-control or SQL*Plus statement; no target object."),
    "STM002": ("MANUAL", "Statement type is not converted by WP9.3; review manually."),
    "STM003": ("UNSUPPORTED", "Statement could not be tokenized."),
}
DISPOSITIONS = ("AUTOMATIC", "ASSISTED", "MANUAL", "UNSUPPORTED")
CONSTRAINT_CODES = {"PRIMARY KEY": "p", "UNIQUE": "u", "CHECK": "c", "FOREIGN KEY": "f"}


def rule_registry() -> dict[str, Any]:
    rules: dict[str, dict[str, str]] = {}
    for registry in (SCHEMA_RULES, EXPRESSION_RULES, VIEW_RULES, TRIGGER_RULES, TRIGGER_CONVERSION_RULES, PLAN_RULES):
        for code, (disposition, message) in registry.items():
            rules[code] = {"disposition": disposition, "message": message}
    digest = hashlib.sha256(json.dumps(rules, sort_keys=True).encode()).hexdigest()
    return {"version": SCHEMA_CONVERTER_VERSION, "sha256": digest, "rules": dict(sorted(rules.items()))}


def _plan_finding(code: str, obj: str, line: int, detail: str | None = None) -> dict[str, Any]:
    disposition, message = PLAN_RULES[code]
    return finding(code, obj=obj, line=line, detail=detail, disposition=disposition, message=message)


def _clean(obj: Any) -> Any:
    """Drop token lists and raw statements from report structures."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()
                if k not in {"bodyTokens", "expressionTokens", "tokens", "statement"}}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    return obj


def _unit_name(stmt: Statement) -> tuple[str, str]:
    sig = [t for t in significant(stmt.tokens)]
    words = [t.upper for t in sig]
    idx = next(i for i, w in enumerate(words) if w in {"PACKAGE", "PROCEDURE", "FUNCTION", "TYPE"})
    j = idx + 1
    if j < len(sig) and words[j] == "BODY":
        j += 1
    name = identifier_name(sig[j])
    if j + 2 < len(sig) and sig[j + 1].text == ".":
        name = identifier_name(sig[j + 2])
    return stmt.kind, name


def _spec_members(stmt: Statement) -> list[str]:
    sig = significant(stmt.tokens)
    members = []
    for i, t in enumerate(sig[:-1]):
        if t.upper in {"FUNCTION", "PROCEDURE"} and sig[i + 1].kind in {"IDENT", "QIDENT"}:
            members.append(identifier_name(sig[i + 1]))
    return sorted(set(members))


def _dml_target(stmt: Statement) -> str | None:
    sig = significant(stmt.tokens)
    for i, t in enumerate(sig[:-1]):
        if t.upper in {"INTO", "UPDATE"} or (t.upper == "FROM" and i > 0 and sig[i - 1].upper == "DELETE"):
            return identifier_name(sig[i + 1])
    return None


def _generated_name(table: str, kind: str, n: int, columns: list[str]) -> str:
    suffix = {"PRIMARY KEY": "pk", "UNIQUE": f"uk{n}", "CHECK": f"ck{n}", "FOREIGN KEY": f"fk{n}"}[kind]
    return target_name(f"{table}_{suffix}")


def build_schema_plan(source: str, *, source_name: str = "install.sql", target_schema: str = "app",
                      apex_references: list[dict[str, Any]] | None = None,
                      overrides: dict[str, Any] | None = None,
                      function_mappings: dict[str, Any] | None = None,
                      transaction_wrapper: bool = True,
                      convert_triggers: bool = False) -> dict[str, Any]:
    """``convert_triggers`` (R4a): emit PL/pgSQL triggers for triggers in the converted subset
    (trigger_conversion); off by default, so plans of applications whose trigger logic was rebuilt by hand
    (pilot WP9.4) stay unchanged."""
    if not target_schema.isidentifier() or target_schema.lower() != target_schema or len(target_schema) > 63:
        raise ValueError("target_schema must be a lower-case PostgreSQL identifier.")
    source_hash = "sha256:" + hashlib.sha256(source.encode("utf-8")).hexdigest()
    original_source = source
    mapping_records = _validate_function_mappings(function_mappings)
    mapping = {m["source"]: m["target"] for m in mapping_records}
    source, override_records = apply_overrides(source, overrides)
    statements = split_script(source)

    tables: dict[str, dict[str, Any]] = {}
    alters: list[dict[str, Any]] = []
    indexes: list[dict[str, Any]] = []
    views: dict[str, dict[str, Any]] = {}
    comments: list[dict[str, Any]] = []
    sequences: dict[str, dict[str, Any]] = {}
    trigger_stmts: list[Statement] = []
    plsql_units: list[dict[str, Any]] = []
    data_statements: list[dict[str, Any]] = []
    other_statements: list[dict[str, Any]] = []
    statement_log: list[dict[str, Any]] = []
    owners: set[str] = set()

    for index, stmt in enumerate(statements, start=1):
        entry = {"index": index, "kind": stmt.kind, "line": stmt.line}
        statement_log.append(entry)
        if stmt.kind == "TABLE":
            t = parse_create_table(stmt)
            tables[t["name"]] = t
            entry["object"] = f"TABLE {t['name']}"
            owners |= {t["owner"]} if t["owner"] else set()
        elif stmt.kind == "ALTER_TABLE":
            a = parse_alter_table(stmt)
            alters.append(a)
            entry["object"] = f"ALTER TABLE {a['table']}"
        elif stmt.kind == "INDEX":
            ix = parse_create_index(stmt)
            indexes.append(ix)
            entry["object"] = f"INDEX {ix['name']}"
        elif stmt.kind == "VIEW":
            v = parse_view(stmt)
            views[v["name"]] = v
            entry["object"] = f"VIEW {v['name']}"
            owners |= {v["owner"]} if v["owner"] else set()
        elif stmt.kind == "COMMENT":
            comments.append(parse_comment(stmt))
            entry["object"] = "COMMENT"
        elif stmt.kind == "SEQUENCE":
            s = parse_sequence(stmt)
            sequences[s["name"]] = s
            entry["object"] = f"SEQUENCE {s['name']}"
        elif stmt.kind == "TRIGGER":
            trigger_stmts.append(stmt)
            entry["object"] = "TRIGGER"
        elif stmt.kind in PLSQL_KINDS:
            kind, name = _unit_name(stmt)
            lexical = analyze_plsql(stmt.text, source_name=f"{source_name}:{stmt.line}")
            plsql_units.append({"kind": kind.replace("_", " "), "name": name, "line": stmt.line,
                                "statement": stmt, "lexicalStatus": lexical["status"],
                                "lexicalDiagnostics": dict(sorted(Counter(d["code"] for d in lexical["diagnostics"]).items())),
                                "members": _spec_members(stmt) if kind in {"PACKAGE", "TYPE"} else []})
            entry["object"] = f"{kind.replace('_', ' ')} {name}"
        elif stmt.kind in {"DML", "ANONYMOUS_BLOCK"}:
            data_statements.append({"kind": stmt.kind, "line": stmt.line, "target": _dml_target(stmt),
                                    "verb": significant(stmt.tokens)[0].upper,
                                    "findings": [_plan_finding("DAT001", stmt.kind, stmt.line)]})
            entry["object"] = "DATA"
        elif stmt.kind in {"TCL", "SQLPLUS", "EMPTY"}:
            entry["object"] = "NONE"
            entry["disposition"] = PLAN_RULES["STM001"][0]
            entry["code"] = "STM001"
        elif stmt.kind == "ERROR":
            other_statements.append({"kind": "ERROR", "line": stmt.line, "error": stmt.error,
                                     "findings": [_plan_finding("STM003", "STATEMENT", stmt.line, stmt.error)]})
            entry["object"] = "ERROR"
        else:
            other_statements.append({"kind": stmt.kind, "line": stmt.line,
                                     "findings": [_plan_finding("STM002", stmt.kind, stmt.line, stmt.text[:120])]})
            entry["object"] = stmt.kind

    checks: list[dict[str, Any]] = []

    def check(check_id: str, title: str, failures: list[str], *, notes: list[str] | None = None) -> None:
        checks.append({"id": check_id, "title": title, "status": "FAIL" if failures else "PASS",
                       "failures": failures, "notes": notes or []})

    # ---------------------------------------------------------------- constraints and alters
    target_failures: list[str] = []
    for a in alters:
        if a["table"] not in tables:
            target_failures.append(f"ALTER TABLE {a['table']} (line {a['line']}): table not defined in input")
            continue
        tables[a["table"]]["constraints"].extend(a["constraints"])
        tables[a["table"]]["findings"].extend(a["findings"])

    for t in tables.values():
        counters: Counter[str] = Counter()
        t["targetName"] = target_name(t["name"])
        for c in t["columns"]:
            c["targetName"] = target_name(c["name"])
        for con in t["constraints"]:
            counters[con["kind"]] += 1
            if not con.get("name"):
                con["name"] = _generated_name(t["name"], con["kind"], counters[con["kind"]], con["columns"]).upper()
                con["findings"] = [finding("SCH015", obj=t["name"], line=con["line"], detail=con["name"].lower())]
            else:
                con["findings"] = []
            con["targetName"] = target_name(con["name"])

    # ---------------------------------------------------------------- column conversion
    for t in tables.values():
        cols = {c["name"]: c for c in t["columns"]}
        obj = t["name"]
        char_cols = [c["name"] for c in t["columns"] if c.get("character")]
        if char_cols:
            t["findings"].append(finding("SCH004", obj=obj, line=t["line"], detail=", ".join(char_cols).lower()))
        for name in [t["name"]] + list(cols):
            if name.upper() in PG_RESERVED:
                t["findings"].append(finding("SCH028", obj=obj, line=t["line"], detail=name.lower()))
        for c in t["columns"]:
            cobj = f"{obj}.{c['name']}"
            if c.get("identity"):
                if c["targetType"] == "numeric" and c["sourceType"].upper() == "NUMBER":
                    c["targetType"] = "bigint"
                    c["typeFamily"] = "integer"
                    c["findings"] = [f for f in c["findings"] if f["code"] != "SCH002"]
                    c["findings"].append(finding("SCH006", obj=cobj, line=c["line"]))
                if c["targetType"] not in {"smallint", "integer", "bigint"}:
                    c["blocked"] = f"Identity column type {c['sourceType']} has no PostgreSQL identity mapping."
                    c["findings"].append(finding("SCH008", obj=cobj, line=c["line"], detail=c["sourceType"]))
                else:
                    clause, notes = identity_clause(c["identity"]["options"], c["targetType"])
                    mode = "ALWAYS" if c["identity"]["mode"] == "ALWAYS" else "BY DEFAULT"
                    c["identity"]["target"] = f"GENERATED {mode} AS IDENTITY{clause}"
                    if notes:
                        c["findings"].append(finding("SCH007", obj=cobj, line=c["line"], detail="; ".join(notes)))
            if c.get("generated"):
                gen = c["generated"]
                res = convert_expression(gen["tokens"])
                refs = res.identifiers
                bad_refs = sorted(r for r in refs if r not in cols or cols[r].get("generated"))
                bad_funcs = sorted(f for f in res.functions if f not in IMMUTABLE_FUNCTIONS and f != "NVL")
                if bad_refs or bad_funcs or res.has_subquery or res.plsql_calls or res.disposition in {"MANUAL", "UNSUPPORTED"}:
                    c["blocked"] = "Generated expression outside immutable subset."
                    c["findings"].append(finding("SCH010", obj=cobj, line=c["line"],
                                                 detail="; ".join(filter(None, [
                                                     ("references " + ", ".join(bad_refs)) if bad_refs else "",
                                                     ("functions " + ", ".join(bad_funcs)) if bad_funcs else ""])) or gen["source"]))
                else:
                    gen["target"] = res.sql.strip()
                    gen["references"] = sorted(refs)
                    c["findings"].append(finding("SCH009", obj=cobj, line=c["line"], detail=gen["source"]))
                    for f in res.findings:
                        c["findings"].append(finding(f["code"], obj=cobj, line=c["line"], detail=f.get("detail"),
                                                     disposition=f["disposition"], message=f["message"]))
                    if c["targetType"] is None:
                        fams = {cols[r]["typeFamily"] for r in refs}
                        if fams and fams <= {"numeric", "integer"}:
                            c["targetType"], c["typeFamily"] = "numeric", "numeric"
                            c["findings"].append(finding("SCH002", obj=cobj, line=c["line"], detail="type inferred"))
                        else:
                            c["blocked"] = "Generated column without datatype; type cannot be inferred."
                            c["findings"].append(finding("SCH010", obj=cobj, line=c["line"], detail="no datatype"))
        # constraint conversion
        for con in t["constraints"]:
            kind = con["kind"]
            con["emit"] = True
            missing = [col for col in con["columns"] if col and col not in cols]
            if missing:
                con["emit"] = False
                con["findings"].append(finding("SCH026", obj=obj, line=con["line"],
                                               detail=f"{con['name']}: unknown column(s) {', '.join(missing)}"))
            if not con.get("enabled", True):
                con["emit"] = False
                con["findings"].append(finding("SCH017", obj=obj, line=con["line"], detail=con["name"]))
            if con.get("manual"):
                con["emit"] = False
                con["findings"].append(finding("SCH022" if kind == "FOREIGN KEY" else "SCH026", obj=obj,
                                               line=con["line"], detail=", ".join(con["manual"])))
            if not con.get("validated", True):
                if kind in {"CHECK", "FOREIGN KEY"}:
                    con["notValid"] = True
                    con["findings"].append(finding("SCH018", obj=obj, line=con["line"], detail=con["name"]))
                else:
                    con["emit"] = False
                    con["findings"].append(finding("SCH017", obj=obj, line=con["line"],
                                                   detail=f"{con['name']} NOVALIDATE has no PostgreSQL equivalent for {kind}"))
            if con.get("deferrable"):
                con["findings"].append(finding("SCH031", obj=obj, line=con["line"], detail=con["name"]))
            if kind == "CHECK":
                res = convert_expression(con["expressionTokens"])
                refs = res.identifiers
                bad_refs = sorted(r for r in refs if r not in cols)
                reserved = sorted(r for r in refs if r in PG_RESERVED)
                allowed = PORTABLE_FUNCTIONS | SEMANTIC_DIFF_FUNCTIONS | {"NVL"}
                bad_funcs = sorted(f for f in res.functions if f not in allowed)
                if bad_refs or bad_funcs or reserved or res.has_subquery or res.plsql_calls or \
                        res.disposition in {"MANUAL", "UNSUPPORTED"}:
                    con["emit"] = False
                    con["findings"].append(finding("SCH016", obj=obj, line=con["line"],
                                                   detail=f"{con['name']}: {con['expression']}"))
                else:
                    con["targetExpression"] = res.sql.strip()
                    con["columns"] = sorted(refs)
                    for f in res.findings:
                        con["findings"].append(finding(f["code"], obj=obj, line=con["line"], detail=f.get("detail"),
                                                       disposition=f["disposition"], message=f["message"]))
        t["blockedReasons"] = sorted({c["blocked"] for c in t["columns"] if c.get("blocked")}
                                     | ({t["blocked"]} if t.get("blocked") else set()))
        if not t["columns"]:
            t["blockedReasons"].append("No columns parsed.")
        t["emit"] = not t["blockedReasons"]
        for c in t["columns"]:
            if not any(con["kind"] == "PRIMARY KEY" and c["name"] in con["columns"] and con["emit"]
                       for con in t["constraints"]):
                continue
            c["nullable"] = False

    # ---------------------------------------------------------------- foreign keys
    fk_target_failures: list[str] = []
    fk_unique_failures: list[str] = []
    fk_type_failures: list[str] = []
    fk_type_notes: list[str] = []
    for _ in range(3):  # alignment may cascade through chains of FKs
        for t in tables.values():
            for con in t["constraints"]:
                if con["kind"] != "FOREIGN KEY" or not con["emit"]:
                    continue
                parent = tables.get(con["target"])
                if parent is None:
                    continue
                if not con["targetColumns"]:
                    pk = next((p for p in parent["constraints"] if p["kind"] == "PRIMARY KEY"), None)
                    if pk:
                        con["targetColumns"] = list(pk["columns"])
                pcols = {c["name"]: c for c in parent["columns"]}
                ccols = {c["name"]: c for c in t["columns"]}
                for child_name, parent_name in zip(con["columns"], con["targetColumns"]):
                    child, par = ccols.get(child_name), pcols.get(parent_name)
                    if child is None or par is None or child["targetType"] == par["targetType"]:
                        continue
                    if (child["sourceType"] or "").upper() == "NUMBER" and par["typeFamily"] == "integer" \
                            and child["targetType"] == "numeric":
                        child["findings"] = [f for f in child["findings"] if f["code"] != "SCH002"]
                        child["targetType"], child["typeFamily"] = par["targetType"], "integer"
                        child["findings"].append(finding("SCH021", obj=f"{t['name']}.{child_name}", line=child["line"],
                                                         detail=f"{par['targetType']} via {con['name']}"))
    for t in tables.values():
        for con in t["constraints"]:
            if con["kind"] != "FOREIGN KEY":
                continue
            label = f"{t['name']}.{con['name']} -> {con['target']}"
            parent = tables.get(con["target"])
            if parent is None:
                con["emit"] = False
                fk_target_failures.append(label + ": target not defined in input")
                con["findings"].append(finding("SCH022", obj=t["name"], line=con["line"], detail=label + ": unresolved"))
                continue
            if not parent["emit"] or not t["emit"]:
                con["emit"] = False
                con["blockedBy"] = [x["name"] for x in (parent, t) if not x["emit"]]
                con["findings"].append(finding("SCH022", obj=t["name"], line=con["line"], detail=label + ": table blocked"))
                continue
            key = next((p for p in parent["constraints"] if p["kind"] in {"PRIMARY KEY", "UNIQUE"}
                        and p["emit"] and set(p["columns"]) == set(con["targetColumns"])), None)
            if key is None:
                con["emit"] = False
                fk_unique_failures.append(label + f" ({', '.join(con['targetColumns'])}): not a PRIMARY KEY/UNIQUE key")
                con["findings"].append(finding("SCH022", obj=t["name"], line=con["line"], detail=label + ": not unique"))
                continue
            if key.get("deferrable"):
                con["emit"] = False
                fk_unique_failures.append(label + f": referenced key {key['name']} is DEFERRABLE; "
                                          "PostgreSQL foreign keys require a non-deferrable key")
                con["findings"].append(finding("SCH022", obj=t["name"], line=con["line"],
                                               detail=label + ": referenced key is deferrable"))
                continue
            if len(con["columns"]) != len(con["targetColumns"]):
                con["emit"] = False
                fk_type_failures.append(label + ": column count mismatch")
                continue
            pcols = {c["name"]: c for c in parent["columns"]}
            ccols = {c["name"]: c for c in t["columns"]}
            for child_name, parent_name in zip(con["columns"], con["targetColumns"]):
                child, par = ccols[child_name], pcols.get(parent_name)
                if par is None:
                    con["emit"] = False
                    fk_type_failures.append(f"{label}: referenced column {parent_name} missing")
                elif child["typeFamily"] != par["typeFamily"] or (
                        child["typeFamily"] == "integer" and child["targetType"] != par["targetType"]) or (
                        child["typeFamily"] == "numeric" and child["targetType"] != par["targetType"]):
                    if child["typeFamily"] == par["typeFamily"] == "text":
                        continue
                    con["emit"] = False
                    fk_type_failures.append(f"{label}: {child_name} {child['targetType']} vs {parent_name} {par['targetType']}")
                elif child["typeFamily"] == "text" and child["targetType"] != par["targetType"]:
                    fk_type_notes.append(f"{label}: {child['targetType']} references {par['targetType']}")
            if con.get("onDelete") == "CASCADE":
                con["findings"].append(finding("SCH031", obj=t["name"], line=con["line"],
                                               detail=f"{con['name']} ON DELETE CASCADE; verify child trigger behavior"))
    check("DEP-001", "Foreign-key targets resolve to tables in the input", fk_target_failures)
    check("DEP-002", "Foreign keys reference a PRIMARY KEY or UNIQUE key", fk_unique_failures)
    check("DEP-003", "Foreign-key column types are compatible after alignment", fk_type_failures,
          notes=fk_type_notes)

    # ---------------------------------------------------------------- indexes
    emitted_constraint_keys = {}
    for t in tables.values():
        emitted_constraint_keys[t["name"]] = [set(con["columns"]) for con in t["constraints"]
                                              if con["kind"] in {"PRIMARY KEY", "UNIQUE"} and con["emit"]]
    for ix in indexes:
        ix["targetName"] = target_name(ix["name"])
        ix["emit"] = not ix.get("blocked")
        t = tables.get(ix.get("table"))
        if t is None:
            ix["emit"] = False
            target_failures.append(f"INDEX {ix['name']} (line {ix['line']}): table {ix.get('table')} not defined")
            continue
        if not t["emit"]:
            ix["emit"] = False
            ix["blockedBy"] = [t["name"]]
            continue
        cols = {c["name"] for c in t["columns"]}
        parts = []
        for el in ix["elements"]:
            if "column" in el:
                if el["column"] not in cols:
                    ix["emit"] = False
                    target_failures.append(f"INDEX {ix['name']}: unknown column {el['column']}")
                parts.append(pg_ident(el["column"]) + (" " + el["order"] if el["order"] else ""))
            else:
                res = convert_expression(el["expressionTokens"])
                bad = [f for f in res.functions if f not in IMMUTABLE_FUNCTIONS and f != "NVL"]
                if bad or res.plsql_calls or not res.identifiers <= cols or res.disposition in {"MANUAL", "UNSUPPORTED"}:
                    ix["emit"] = False
                    ix["findings"].append(finding("SCH023", obj=ix["name"], line=ix["line"], detail=el["expression"]))
                else:
                    ix["findings"].append(finding("SCH029", obj=ix["name"], line=ix["line"], detail=el["expression"]))
                    parts.append("(" + res.sql.strip() + ")" + (" " + el["order"] if el["order"] else ""))
        ix["targetElements"] = parts
        simple = [el["column"] for el in ix["elements"] if "column" in el]
        if ix["emit"] and ix["unique"] and len(simple) == len(ix["elements"]) and \
                set(simple) in emitted_constraint_keys[t["name"]]:
            ix["emit"] = False
            ix["coveredByConstraint"] = True
            ix["findings"].append(finding("SCH024", obj=ix["name"], line=ix["line"]))

    # ---------------------------------------------------------------- comments
    for cm in comments:
        t = tables.get(cm["table"]) or views.get(cm["table"])
        if t is None:
            target_failures.append(f"COMMENT ON {cm['targetKind']} {cm['table']}: object not defined")
            cm["emit"] = False
        else:
            cm["emit"] = bool(t.get("emit", True)) and cm["text"] is not None

    # ---------------------------------------------------------------- PL/SQL units and members
    packages = {u["name"] for u in plsql_units}
    members = {u["name"]: set(u["members"]) for u in plsql_units if u["kind"] == "PACKAGE"}

    # ---------------------------------------------------------------- views
    known_relations = set(tables) | set(views)
    for v in views.values():
        convert_view(v, known_objects=known_relations, source_schemas=owners, function_mappings=mapping)
    view_cycle: list[str] = []
    order: list[str] = []
    pending = {name: set(d for d in v["dependencies"] if d in views) for name, v in views.items()}
    source_order = list(views)
    while pending:
        ready = [n for n in source_order if n in pending and not pending[n]]
        if not ready:
            view_cycle = sorted(pending)
            for n in view_cycle:
                views[n]["findings"].append(finding("VIW006", obj=n, line=views[n]["line"],
                                                    disposition="MANUAL", message=VIEW_RULES["VIW006"][1]))
                order.append(n)
            break
        for n in ready:
            order.append(n)
            del pending[n]
            for deps in pending.values():
                deps.discard(n)
    emitted_relations = {n for n, t in tables.items() if t["emit"]}
    view_dep_failures: list[str] = []
    for name in order:
        v = views[name]
        v["ownDisposition"] = worst(v["findings"])
        blocked_by = sorted(d for d in v["dependencies"] if d not in emitted_relations)
        if v["unresolved"]:
            view_dep_failures.append(f"{name}: unresolved {', '.join(v['unresolved'])}")
        v["blockedBy"] = blocked_by
        v["emit"] = v["ownDisposition"] in {"AUTOMATIC", "ASSISTED"} and not blocked_by and name not in view_cycle
        v["phase"] = "deferred" if v["emit"] and (v["mappedCalls"] or any(
            views[d].get("phase") == "deferred" for d in v["dependencies"] if d in views)) else "schema"
        if blocked_by:
            v["findings"].append(finding("VIW005", obj=name, line=v["line"], detail=", ".join(blocked_by),
                                         disposition="MANUAL", message=VIEW_RULES["VIW005"][1]))
        if v["emit"]:
            emitted_relations.add(name)
        v["dependencyOrder"] = order.index(name) + 1
        v["design"] = view_design(v)
    missing_calls = []
    for v in views.values():
        for call in v["plsqlCalls"]:
            pkg, _, member = call.partition(".")
            if pkg not in packages:
                missing_calls.append(f"VIEW {v['name']} calls {call}: unit not defined in input")
            elif member and member not in members.get(pkg, set()):
                missing_calls.append(f"VIEW {v['name']} calls {call}: member not declared in package spec")
    check("DEP-004", "View dependencies resolve and are acyclic",
          view_dep_failures + ([f"cycle: {', '.join(view_cycle)}"] if view_cycle else []),
          notes=[f"{i + 1}. {n}" for i, n in enumerate(order)])

    # ---------------------------------------------------------------- triggers
    triggers: list[dict[str, Any]] = []
    trigger_failures: list[str] = []
    for stmt in trigger_stmts:
        trg = parse_trigger(stmt, known_tables=set(tables), known_packages=packages)
        triggers.append(trg)
        if convert_triggers:
            conv = convert_trigger(stmt, trg, schema=target_schema, table=tables.get(trg["table"] or ""),
                                   sequences={n for n, sq in sequences.items() if not sq.get("blocked")},
                                   known_objects=set(tables) | set(views))
            trg["emit"] = conv["converted"]
            if conv["converted"]:
                trg["targetSql"] = conv["sql"]
                trg["usesAppUser"] = conv["usesAppUser"]
                # converted: the TRG001 "re-implement by hand" finding is replaced by the conversion findings
                trg["findings"] = [f for f in trg["findings"] if f["code"] != "TRG001"]
            trg["findings"] = trg["findings"] + [
                {**f, "object": trg["name"], "line": trg["line"]} for f in conv["findings"]]
        t = tables.get(trg["table"] or "")
        if t is None:
            target_failures.append(f"TRIGGER {trg['name']}: table {trg['table']} not defined")
            continue
        cols = {c["name"] for c in t["columns"]}
        referenced = {r.split(".", 1)[1] for r in trg["columnsRead"]} | set(trg["columnsWritten"])
        for ev in trg["events"]:
            referenced |= set(ev.get("columns", []))
        for col in sorted(referenced - cols):
            trigger_failures.append(f"TRIGGER {trg['name']}: column {trg['table']}.{col} does not exist")
        generated_written = sorted(c["name"] for c in t["columns"] if c.get("generated") and c["name"] in trg["columnsWritten"])
        for col in generated_written:
            trigger_failures.append(f"TRIGGER {trg['name']}: writes generated column {col}")
        for call in trg["calls"]:
            pkg, _, member = call.partition(".")
            if member and member not in members.get(pkg, set()):
                missing_calls.append(f"TRIGGER {trg['name']} calls {call}: member not declared in package spec")
    check("DEP-005", "Index/trigger/comment/ALTER TABLE targets resolve", target_failures)
    check("DEP-006", "Trigger column references exist and do not write generated columns", trigger_failures)
    check("DEP-007", "PL/SQL calls from views/triggers resolve to declared package members", missing_calls)

    # ---------------------------------------------------------------- PL/SQL dependency edges
    for u in plsql_units:
        sig = significant(u["statement"].tokens)
        words = {identifier_name(t).upper() for t in sig if t.kind in {"IDENT", "QIDENT"}}
        u["tablesReferenced"] = sorted(words & set(tables))
        u["viewsReferenced"] = sorted(words & set(views))
        u["unitsReferenced"] = sorted((words & packages) - {u["name"]})
        u["findings"] = [_plan_finding("PLS001", u["name"], u["line"])]

    # ---------------------------------------------------------------- namespace and identifier checks
    relation_names: dict[str, list[str]] = {}

    def claim(name: str, owner: str) -> None:
        relation_names.setdefault(name, []).append(owner)

    for t in tables.values():
        if t["emit"]:
            claim(t["targetName"], f"TABLE {t['name']}")
            for con in t["constraints"]:
                if con["emit"] and con["kind"] in {"PRIMARY KEY", "UNIQUE"}:
                    claim(con["targetName"], f"{con['kind']} {con['name']}")
    for ix in indexes:
        if ix["emit"]:
            claim(ix["targetName"], f"INDEX {ix['name']}")
    for v in views.values():
        if v["emit"]:
            claim(target_name(v["name"]), f"VIEW {v['name']}")
    for s in sequences.values():
        claim(target_name(s["name"]), f"SEQUENCE {s['name']}")
    collisions = [f"{name}: {', '.join(owners_)}" for name, owners_ in sorted(relation_names.items()) if len(owners_) > 1]
    long_names = []
    fold: dict[str, set[str]] = {}
    all_names = list(tables) + list(views) + [ix["name"] for ix in indexes] + list(sequences)
    for t in tables.values():
        all_names += [c["name"] for c in t["columns"]] + [con["name"] for con in t["constraints"]]
    for n in all_names:
        if len(n.lower().encode("utf-8")) > 63:
            long_names.append(f"{n} ({len(n.encode('utf-8'))} bytes) truncated to {target_name(n)}")
    for t in tables.values():
        for c in t["columns"]:
            fold.setdefault(f"{t['name']}.{c['name'].lower()}", set()).add(c["name"])
    for n in list(tables) + list(views):
        fold.setdefault(n.lower(), set()).add(n)
    case_collisions = [f"{k}: {', '.join(sorted(v))}" for k, v in sorted(fold.items()) if len(v) > 1]
    check("DEP-008", "No PostgreSQL relation-namespace collisions (tables, views, indexes, key indexes, sequences)", collisions)
    check("DEP-009", "Identifiers fit 63 bytes and do not collide after case folding", long_names + case_collisions)

    # ---------------------------------------------------------------- independent inventory cross-check
    inventory = analyze_ddl(source)
    inv_counts = {k.replace(" ", "_"): v for k, v in inventory["summary"]["object_counts"].items()}
    plan_counts = Counter({"TABLE": len(tables), "VIEW": len(views), "INDEX": len(indexes),
                           "TRIGGER": len(triggers), "SEQUENCE": len(sequences)})
    for u in plsql_units:
        plan_counts[u["kind"].replace(" ", "_")] += 1
    mismatch = [f"{k}: inventory {inv_counts.get(k, 0)} vs plan {plan_counts.get(k, 0)}"
                for k in sorted(set(inv_counts) | {k for k, v in plan_counts.items() if v})
                if inv_counts.get(k, 0) != plan_counts.get(k, 0)]
    check("DEP-010", "Independent WP8 inventory parser agrees on object counts", mismatch)

    # ---------------------------------------------------------------- objects and dispositions
    objects: list[dict[str, Any]] = []

    def add_object(kind: str, name: str, line: int, findings: list[dict[str, Any]], emitted: bool,
                   **extra: Any) -> None:
        disposition = worst(findings)
        if not emitted and disposition in {"AUTOMATIC", "ASSISTED"} and not extra.get("covered"):
            disposition = "MANUAL"
        objects.append({"type": kind, "name": name, "line": line, "disposition": disposition,
                        "emitted": emitted, "findingCodes": sorted({f["code"] for f in findings}),
                        **{k: v for k, v in extra.items() if v not in (None, [], {})}})

    for t in tables.values():
        tf = list(t["findings"])
        for c in t["columns"]:
            tf.extend(c["findings"])
        omitted = [f"{c['name']}: {o}" for c in t["columns"] for o in c["omitted"]]
        omitted += [f"{con['kind']} {con['name']}" for con in t["constraints"]
                    if not con["emit"] and con["kind"] != "FOREIGN KEY"]
        for con in t["constraints"]:
            if not con["emit"] and con["kind"] != "FOREIGN KEY":
                tf.extend(con["findings"])
        t["omitted"] = omitted
        add_object("TABLE", t["name"], t["line"], tf, t["emit"], blockedReasons=t["blockedReasons"],
                   omitted=omitted)
        for con in t["constraints"]:
            add_object(con["kind"], con["name"], con["line"], con["findings"], con["emit"] and t["emit"],
                       table=t["name"], blockedBy=con.get("blockedBy") or ([] if t["emit"] else [t["name"]]))
        for c in t["columns"]:
            if c.get("identity"):
                add_object("IDENTITY", f"{t['name']}.{c['name']}", c["line"],
                           [f for f in c["findings"] if f["code"] in {"SCH005", "SCH006", "SCH007", "SCH008"}],
                           t["emit"] and not c.get("blocked"))
            if c.get("generated"):
                add_object("GENERATED COLUMN", f"{t['name']}.{c['name']}", c["line"],
                           [f for f in c["findings"] if f["code"].startswith(("SCH009", "SCH010", "EXP"))],
                           t["emit"] and not c.get("blocked"))
    for ix in indexes:
        add_object("INDEX", ix["name"], ix["line"], ix["findings"], ix["emit"], table=ix.get("table"),
                   blockedBy=ix.get("blockedBy"), covered=ix.get("coveredByConstraint"))
    for v in views.values():
        add_object("VIEW", v["name"], v["line"], v["findings"], v["emit"], blockedBy=v["blockedBy"],
                   dependencyOrder=v["dependencyOrder"])
    for trg in triggers:
        add_object("TRIGGER", trg["name"], trg["line"], trg["findings"], bool(trg.get("emit")), table=trg["table"])
    for u in plsql_units:
        add_object(u["kind"], u["name"], u["line"], u["findings"], False)
    for s in sequences.values():
        add_object("SEQUENCE", s["name"], s["line"], s["findings"], not s.get("blocked"))
    for d in data_statements:
        add_object("DATA", f"{d['verb']} {d['target'] or '(block)'}", d["line"], d["findings"], False)
    for o in other_statements:
        add_object(o["kind"], o["kind"], o["line"], o["findings"], False)

    unaccounted = [f"statement {e['index']} (line {e['line']}, {e['kind']})" for e in statement_log
                   if not e.get("object")]
    check("DEP-011", "Every source statement is accounted for with a disposition", unaccounted,
          notes=[f"{k}: {v}" for k, v in sorted(Counter(e["kind"] for e in statement_log).items())])

    # ---------------------------------------------------------------- APEX consumer validation
    if apex_references is not None:
        failures = []
        for ref in apex_references:
            obj = ref["object"].upper()
            if ref["kind"] == "PLSQL_CALL":
                if obj not in packages:
                    failures.append(f"{ref['source']}: package {obj} not defined")
                elif ref["member"] not in members.get(obj, set()):
                    failures.append(f"{ref['source']}: {obj}.{ref['member']} not declared in package spec")
                else:
                    ref["resolvedAs"] = "PACKAGE MEMBER"
                continue
            if obj in tables:
                cols = {c["name"] for c in tables[obj]["columns"]}
                ref["resolvedAs"] = "TABLE" if tables[obj]["emit"] else "TABLE (not emitted)"
            elif obj in views:
                cols = set(views[obj]["outputColumns"] or [])
                ref["resolvedAs"] = "VIEW" if views[obj]["emit"] else "VIEW (not emitted)"
            else:
                failures.append(f"{ref['source']}: object {obj} not defined")
                continue
            for col in ref.get("columns", []):
                if col.upper() not in cols:
                    failures.append(f"{ref['source']}: {obj}.{col} not found")
        not_emitted = sorted({f"{r['object']} ({r['resolvedAs']})" for r in apex_references
                              if "not emitted" in r.get("resolvedAs", "")})
        check("DEP-012", "APEX consumer object/column/package references resolve against the source schema", failures,
              notes=[f"{len(apex_references)} reference(s) checked"] +
                    [f"consumer depends on not-emitted object: {x}" for x in not_emitted])
    else:
        checks.append({"id": "DEP-012", "title": "APEX consumer object/column references resolve against the source schema",
                       "status": "NOT_RUN", "failures": [], "notes": ["No APEX export supplied."]})

    for rec in override_records:
        for o in objects:
            if f"{o['type']} {o['name']}" == rec["object"]:
                o["definitionSource"] = "dictionary override"
    sql = _emit_sql(tables, indexes, views, order, comments, sequences, target_schema,
                    source_name, source_hash, objects, override_records, transaction_wrapper,
                    [trg for trg in triggers if trg.get("emit")])
    deferred_sql = _emit_deferred_sql(views, order, target_schema, source_name, source_hash,
                                      mapping_records, transaction_wrapper, comments)
    post_load = _emit_post_load(tables, sequences, target_schema)
    expected_catalog = _expected_catalog(tables, indexes, views, sequences)
    load_plan = {t["targetName"]: {
        "columns": [c["targetName"] for c in t["columns"] if not c.get("generated")],
        "excludedGenerated": [c["targetName"] for c in t["columns"] if c.get("generated")],
        "identity": {c["targetName"]: ("OVERRIDING SYSTEM VALUE" if c["identity"]["mode"] == "ALWAYS" else "explicit values accepted")
                     for c in t["columns"] if c.get("identity")},
    } for t in tables.values() if t["emit"]}

    by_type: dict[str, Counter[str]] = {}
    for o in objects:
        by_type.setdefault(o["type"], Counter())[o["disposition"]] += 1
    summary = {
        "statements": len(statement_log),
        "objectsByType": {k: dict(sorted(v.items())) for k, v in sorted(by_type.items())},
        "dispositions": dict(sorted(Counter(o["disposition"] for o in objects).items())),
        "tables": {"source": len(tables), "emitted": sum(t["emit"] for t in tables.values())},
        "views": {"source": len(views), "emitted": sum(v["emit"] for v in views.values())},
        "indexes": {"source": len(indexes), "emitted": sum(ix["emit"] for ix in indexes)},
        **({"triggers": {"source": len(triggers), "emitted": sum(bool(t.get("emit")) for t in triggers)}}
           if convert_triggers else {}),
        "validationPassed": all(c["status"] != "FAIL" for c in checks),
    }
    return {
        "format": PLAN_FORMAT,
        "converterVersion": SCHEMA_CONVERTER_VERSION,
        "ruleRegistrySha256": rule_registry()["sha256"],
        "source": {"name": source_name, "sha256": source_hash, "bytes": len(original_source.encode("utf-8"))},
        "effectiveSource": {"sha256": "sha256:" + hashlib.sha256(source.encode("utf-8")).hexdigest(),
                            "bytes": len(source.encode("utf-8")),
                            "note": "Line numbers refer to the effective source (script with dictionary overrides applied)."},
        "overrides": override_records,
        "overrideEvidence": (overrides or {}).get("evidence", []),
        "targetSchema": target_schema,
        "summary": summary,
        "checks": checks,
        "objects": objects,
        "tables": _clean(list(tables.values())),
        "indexes": _clean(indexes),
        "views": _clean([views[n] for n in order]),
        "triggers": triggers,
        "plsqlUnits": _clean(plsql_units),
        "dataStatements": data_statements,
        "otherStatements": other_statements,
        "statements": statement_log,
        "loadPlan": load_plan,
        "expectedCatalog": expected_catalog,
        "apexReferences": apex_references,
        "sql": sql,
        "deferredSql": deferred_sql,
        "functionMappings": mapping_records,
        "transactionWrapper": transaction_wrapper,
        "postLoadSql": post_load,
        "limitations": [
            "Static conversion of a source script; it does not prove the objects are installed, valid, or granted in Oracle. Oracle dictionary reconciliation is a separate WP9.3 step.",
            ("Triggers in the converted subset are emitted as PL/pgSQL triggers (R4a); other triggers and PL/SQL packages are inventoried, not converted (WP9.4)."
             if convert_triggers else
             "Business logic in triggers and PL/SQL packages is inventoried, not converted (WP9.4)."),
            "Seed/configuration DML is inventoried, not migrated (WP9.6).",
            "Views calling PL/SQL functions are not emitted until target functions/services exist.",
            "Generated SQL is a reviewed draft; it is not approved for any shared environment.",
        ],
    }


# --------------------------------------------------------------------------- emission


def _column_sql(c: dict[str, Any]) -> str:
    parts = [pg_ident(c["name"]), c["targetType"]]
    if c.get("identity"):
        parts.append(c["identity"]["target"])
    elif c.get("generated"):
        parts.append(f"GENERATED ALWAYS AS ({c['generated']['target']}) STORED")
    elif c.get("default") and c["default"].get("target"):
        parts.append("DEFAULT " + c["default"]["target"])
    if not c["nullable"] and not c.get("identity"):
        parts.append("NOT NULL")
    return " ".join(parts)


def _constraint_state(con: dict[str, Any]) -> str:
    out = ""
    if con.get("deferrable"):
        out += " DEFERRABLE"
        if con.get("initiallyDeferred"):
            out += " INITIALLY DEFERRED"
    return out


def _validate_function_mappings(spec: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not spec:
        return []
    if spec.get("format") != "apex2next.function-mappings.v1":
        raise ValueError("function mappings must use format apex2next.function-mappings.v1")
    out = []
    for m in spec["mappings"]:
        source = m["source"].upper()
        if not re.fullmatch(r"[A-Z][A-Z0-9_$#]*\.[A-Z][A-Z0-9_$#]*", source):
            raise ValueError(f"mapping source {m['source']!r} must be PACKAGE.MEMBER")
        if not re.fullmatch(r"[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*", m["target"]):
            raise ValueError(f"mapping target {m['target']!r} must be a lower-case schema.function")
        out.append({"source": source, "target": m["target"], "providedBy": m.get("providedBy"),
                    "signature": m.get("signature"), "semantics": m.get("semantics")})
    return sorted(out, key=lambda x: x["source"])


def _comment_sql(cm, views, schema) -> str:
    target = f"{pg_ident(schema)}.{pg_ident(cm['table'])}" + (f".{pg_ident(cm['column'])}" if cm["column"] else "")
    kind = "COLUMN" if cm["column"] else ("VIEW" if cm["table"] in views else "TABLE")
    return f"COMMENT ON {kind} {target} IS '" + cm["text"].replace("'", "''") + "';"


def _comment_phase(cm, views) -> str | None:
    """Migration that creates the commented object: 'schema', 'deferred', or None when it is not emitted."""
    if not cm.get("emit"):
        return None
    view = views.get(cm["table"])
    if view is None:
        return "schema"
    if not view["emit"]:
        return None
    return "deferred" if view.get("phase") == "deferred" else "schema"


def _emit_deferred_sql(views, order, schema, source_name, source_hash, mapping_records,
                       transaction_wrapper, comments=()) -> str:
    deferred = [views[n] for n in order if views[n]["emit"] and views[n].get("phase") == "deferred"]
    if not deferred:
        return ""
    s = pg_ident(schema)
    out = ["-- APEX2NEXT deferred view migration (generated DRAFT; review required)",
           f"-- Source: {source_name} {source_hash}",
           "-- Requires the reviewed target functions below to exist before this migration runs:",
           *[f"--   {m['source'].lower()} -> {m['target']}  (provided by {m['providedBy']})" for m in mapping_records],
           ""]
    if transaction_wrapper:
        out.append("BEGIN;")
    out.append(f"SET LOCAL search_path TO {s};")
    out += [""] + [view_sql(v, schema) for v in deferred]
    deferred_comments = [c for c in comments if _comment_phase(c, views) == "deferred"]
    if deferred_comments:
        out += ["", "-- Comments"] + [_comment_sql(c, views, schema) for c in deferred_comments]
    if transaction_wrapper:
        out += ["", "COMMIT;"]
    out.append("")
    return "\n".join(out)


def _emit_sql(tables, indexes, views, order, comments, sequences, schema, source_name, source_hash,
              objects, override_records=(), transaction_wrapper=True, triggers=()) -> str:
    s = pg_ident(schema)
    out = [
        "-- APEX2NEXT WP9.3 PostgreSQL schema migration (generated DRAFT; review required)",
        f"-- Source: {source_name} {source_hash}",
        f"-- Converter: schema-plan {SCHEMA_CONVERTER_VERSION}; rules sha256 {rule_registry()['sha256'][:16]}",
        *[f"-- Dictionary override: {r['object'].lower()} ({r['action']}, {r['overrideSha256'][:19]}…)" for r in override_records],
        "-- Deterministic output: change conversion rules/decisions and regenerate; do not hand-edit.",
        "-- Not executed by the generator. Not approved for shared environments.",
        *([] if transaction_wrapper else ["-- Runner format: no transaction-control statements; the migration runner wraps this file in one transaction."]),
        "",
        *(["BEGIN;", ""] if transaction_wrapper else []),
        f"CREATE SCHEMA IF NOT EXISTS {s};",
        f"SET LOCAL search_path TO {s};",
    ]
    if sequences:
        out += ["", "-- Sequences"]
        for seq in sequences.values():
            if seq.get("blocked"):
                continue
            clause, _ = identity_clause(seq["options"], "bigint")
            options = clause.strip()[1:-1] if clause else ""
            out.append(f"CREATE SEQUENCE {s}.{pg_ident(seq['name'])} AS bigint{' ' + options if options else ''};")
    if any("guid_number()" in ((c.get("default") or {}).get("target") or "") for t in tables.values() if t["emit"]
           for c in t["columns"]) or any("guid_number()" in trg["targetSql"] for trg in triggers):
        out += ["", "-- Helper for Oracle TO_NUMBER(SYS_GUID(), 'X...X') key defaults (EXP022): random 128-bit integer",
                "CREATE OR REPLACE FUNCTION guid_number() RETURNS numeric LANGUAGE sql VOLATILE PARALLEL SAFE AS $$",
                "  SELECT round(sum(get_byte(b, i)::numeric * (256::numeric ^ (15 - i))))  -- scale 0: an integer key",
                "    FROM (SELECT uuid_send(gen_random_uuid()) AS b) g, generate_series(0, 15) AS i",
                "$$;"]
    out += ["", "-- Tables"]
    for t in tables.values():
        if not t["emit"]:
            continue
        lines = ["    " + _column_sql(c) for c in t["columns"]]
        for kind in ("PRIMARY KEY", "UNIQUE", "CHECK"):
            for con in t["constraints"]:
                if con["kind"] != kind or not con["emit"] or con.get("notValid"):
                    continue
                if kind == "CHECK":
                    body = f"CHECK ({con['targetExpression']})"
                else:
                    body = f"{kind} (" + ", ".join(pg_ident(c) for c in con["columns"]) + ")"
                lines.append(f"    CONSTRAINT {pg_ident(con['targetName'])} {body}{_constraint_state(con)}")
        out.append(f"CREATE TABLE {s}.{pg_ident(t['name'])} (\n" + ",\n".join(lines) + "\n);")
        for item in t["omitted"]:
            out.append(f"-- OMITTED from {t['targetName']} (see report): {item}")
    fks = [(t, con) for t in tables.values() for con in t["constraints"]
           if con["kind"] == "FOREIGN KEY" and con["emit"]]
    late_checks = [(t, con) for t in tables.values() for con in t["constraints"]
                   if con["kind"] == "CHECK" and con["emit"] and con.get("notValid") and t["emit"]]
    if fks or late_checks:
        out += ["", "-- Foreign keys and NOT VALID constraints"]
    for t, con in fks:
        action = f" ON DELETE {con['onDelete']}" if con.get("onDelete") else ""
        nv = " NOT VALID" if con.get("notValid") else ""
        out.append(
            f"ALTER TABLE {s}.{pg_ident(t['name'])} ADD CONSTRAINT {pg_ident(con['targetName'])} "
            f"FOREIGN KEY (" + ", ".join(pg_ident(c) for c in con["columns"]) + ") "
            f"REFERENCES {s}.{pg_ident(con['target'])} (" + ", ".join(pg_ident(c) for c in con["targetColumns"]) + ")"
            f"{action}{_constraint_state(con)}{nv};")
    for t, con in late_checks:
        out.append(f"ALTER TABLE {s}.{pg_ident(t['name'])} ADD CONSTRAINT {pg_ident(con['targetName'])} "
                   f"CHECK ({con['targetExpression']}) NOT VALID;")
    emitted_ix = [ix for ix in indexes if ix["emit"]]
    if emitted_ix:
        out += ["", "-- Indexes"]
    for ix in emitted_ix:
        unique = "UNIQUE " if ix["unique"] else ""
        out.append(f"CREATE {unique}INDEX {pg_ident(ix['targetName'])} ON {s}.{pg_ident(ix['table'])} "
                   f"(" + ", ".join(ix["targetElements"]) + ");")
    if triggers:
        out += ["", "-- Triggers converted from Oracle (R4a; review required). Skipped while apex2next.loading = 'on'."]
        if any(trg.get("usesAppUser") for trg in triggers):
            out += ["-- APEX APP_USER: the runtime sets app.username per transaction (set_config(..., true)).",
                    f"CREATE OR REPLACE FUNCTION {APP_USER_SQL[:-2]}() RETURNS text LANGUAGE sql STABLE PARALLEL SAFE AS $$",
                    "  SELECT nullif(current_setting('app.username', true), '')",
                    "$$;"]
        for trg in triggers:
            out.append(trg["targetSql"])
    emitted_views = [views[n] for n in order if views[n]["emit"] and views[n].get("phase") != "deferred"]
    if emitted_views:
        out += ["", "-- Views (dependency order)"]
    for v in emitted_views:
        out.append(view_sql(v, schema))
    # a comment goes with the migration that creates its object; none for a view that is not emitted
    emitted_comments = [c for c in comments if _comment_phase(c, views) == "schema"]
    if emitted_comments:
        out += ["", "-- Comments"]
    for cm in emitted_comments:
        out.append(_comment_sql(cm, views, schema))
    not_emitted = [o for o in objects if not o["emitted"] and o["type"] in
                   {"TABLE", "VIEW", "INDEX", "FOREIGN KEY", "CHECK", "PRIMARY KEY", "UNIQUE", "SEQUENCE"}
                   and not o.get("covered")]
    if not_emitted:
        out += ["", "-- Not emitted (disposition in schema plan report):"]
        for o in not_emitted:
            reason = ", ".join(o.get("blockedBy", [])) or ", ".join(o["findingCodes"])
            out.append(f"--   {o['type']} {o['name'].lower()}: {o['disposition']} ({reason})")
    out += ["", "COMMIT;", ""] if transaction_wrapper else [""]
    return "\n".join(out)


def _emit_post_load(tables, sequences, schema) -> str:
    s = pg_ident(schema)
    out = ["-- APEX2NEXT WP9.3 post-load identity/sequence alignment (run after data load, before writes)",
           "BEGIN;"]
    for t in tables.values():
        if not t["emit"]:
            continue
        for c in t["columns"]:
            if c.get("identity"):
                rel = f"{s}.{pg_ident(t['name'])}"
                col = pg_ident(c["name"])
                start = c["identity"]["options"].get("start", 1)
                out.append(f"SELECT setval(pg_get_serial_sequence('{rel}', '{c['targetName']}'), "
                           f"GREATEST(COALESCE((SELECT max({col}) FROM {rel}), 0) + 1, {start}), false);")
    out += ["COMMIT;", ""]
    return "\n".join(out)


def _expected_catalog(tables, indexes, views, sequences) -> dict[str, Any]:
    cat: dict[str, Any] = {"tables": {}, "indexes": {}, "views": {}}
    for t in tables.values():
        if not t["emit"]:
            continue
        cat["tables"][t["targetName"]] = {
            "columns": [{
                "name": c["targetName"],
                "type": catalog_type(c["targetType"]),
                "nullable": bool(c["nullable"]) and not c.get("identity"),
                "identity": ("a" if c["identity"]["mode"] == "ALWAYS" else "d") if c.get("identity") else "",
                "generated": "s" if c.get("generated") else "",
            } for c in t["columns"]],
            "constraints": sorted(
                ({"name": con["targetName"], "type": CONSTRAINT_CODES[con["kind"]]}
                 for con in t["constraints"] if con["emit"]), key=lambda x: x["name"]),
        }
    for ix in indexes:
        if ix["emit"]:
            cat["indexes"][ix["targetName"]] = {"table": target_name(ix["table"]), "unique": ix["unique"]}
    for v in views.values():
        if v["emit"]:
            key = "deferredViews" if v.get("phase") == "deferred" else "views"
            cat.setdefault(key, {})[target_name(v["name"])] = (
                [c.lower() for c in v["outputColumns"]] if v["outputColumns"] else None)
    cat["sequences"] = sorted(target_name(s["name"]) for s in sequences.values() if not s.get("blocked"))
    return cat


# --------------------------------------------------------------------------- CLI


def references_from_export_dir(directory: Path) -> list[dict[str, Any]]:
    """Read an unpacked APEX SQL export (never executed) and collect consumer references."""
    from apex2next_extractor.apex_export import extract_export  # optional cross-worker dependency

    from .apex_references import collect_apex_references

    calls = {}
    for path in sorted(directory.rglob("*.sql")):
        rel = path.relative_to(directory).as_posix()
        calls[rel] = extract_export(path.read_text(encoding="utf-8", errors="replace"))["calls"]
    return collect_apex_references(calls)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a WP9.3 PostgreSQL schema plan from an Oracle install script")
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="JSON schema plan report")
    parser.add_argument("--sql-output", type=Path, help="Generated PostgreSQL migration SQL")
    parser.add_argument("--post-load-output", type=Path, help="Generated post-load alignment SQL")
    parser.add_argument("--apex-references", type=Path, help="JSON list of APEX consumer references")
    parser.add_argument("--apex-export", type=Path,
                        help="Unpacked APEX SQL export directory (requires apex2next_extractor on PYTHONPATH)")
    parser.add_argument("--overrides", type=Path, help="Dictionary overrides JSON (apex2next.dictionary-overrides.v1)")
    parser.add_argument("--function-mappings", type=Path, help="Reviewed PL/SQL -> PostgreSQL function mappings JSON")
    parser.add_argument("--deferred-sql-output", type=Path, help="Generated deferred view migration SQL")
    parser.add_argument("--convert-triggers", action="store_true",
                        help="R4a: emit PL/pgSQL triggers for triggers in the converted subset")
    parser.add_argument("--runner-format", action="store_true",
                        help="Omit BEGIN/COMMIT (the migration runner wraps each file in a transaction)")
    parser.add_argument("--source-name", default=None)
    parser.add_argument("--target-schema", default="app")
    args = parser.parse_args()
    refs = json.loads(args.apex_references.read_text(encoding="utf-8")) if args.apex_references else None
    if args.apex_export:
        refs = (refs or []) + references_from_export_dir(args.apex_export)
    plan = build_schema_plan(args.source.read_text(encoding="utf-8"),
                             source_name=args.source_name or args.source.name,
                             target_schema=args.target_schema, apex_references=refs,
                             overrides=load_overrides(args.overrides) if args.overrides else None,
                             function_mappings=(json.loads(args.function_mappings.read_text(encoding="utf-8"))
                                                if args.function_mappings else None),
                             transaction_wrapper=not args.runner_format,
                             convert_triggers=args.convert_triggers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.sql_output:
        args.sql_output.write_text(plan["sql"], encoding="utf-8")
    if args.deferred_sql_output:
        args.deferred_sql_output.write_text(plan["deferredSql"], encoding="utf-8")
    if args.post_load_output:
        args.post_load_output.write_text(plan["postLoadSql"], encoding="utf-8")
    return 0 if plan["summary"]["validationPassed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
