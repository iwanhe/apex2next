"""WP9.3b Oracle Dictionary reconciliation.

Compares a WP9.3 schema plan (built from an install script) with read-only
Oracle dictionary evidence exported by
``sql/dictionary_inventory_apex_workshop.sql``. The goal is to prove — or
disprove — that the script used for conversion describes the objects that are
actually installed, and to list every drift explicitly.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .source_overrides import apply_overrides, load_overrides
from .sql_tokens import split_script

RECONCILIATION_FORMAT = "apex2next.dictionary-reconciliation.v1"
RECONCILER_VERSION = "0.1.0"
PLSQL_STATEMENT_KINDS = {"PACKAGE": "PACKAGE", "PACKAGE_BODY": "PACKAGE BODY", "TRIGGER": "TRIGGER",
                         "PROCEDURE": "PROCEDURE", "FUNCTION": "FUNCTION", "TYPE": "TYPE",
                         "TYPE_BODY": "TYPE BODY"}


def _norm(expr: str | None) -> str:
    """Normalize an Oracle expression for equality: drop quotes/whitespace, lower-case."""
    if expr is None:
        return ""
    return re.sub(r"\s+", "", expr.replace('"', "")).lower()


def parse_workshop_csv(text: str) -> dict[str, Any]:
    """Parse the CSV produced by dictionary_inventory_apex_workshop.sql."""
    rows = list(csv.DictReader(io.StringIO(text)))
    required = {"SECTION", "OBJ", "ITEM", "C1", "C2", "C3", "C4", "C5"}
    if not rows or not required <= set(rows[0]):
        raise ValueError("Input is not a dictionary_inventory_apex_workshop.sql export.")
    d: dict[str, Any] = {"snapshot": None, "objectCounts": {}, "objects": {}, "columns": defaultdict(list),
                         "identity": {}, "constraints": {}, "consColumns": defaultdict(list), "indexes": {},
                         "indColumns": defaultdict(list), "triggers": {}, "dependencies": [], "errors": [],
                         "grants": [], "sourceLines": {}}
    for r in rows:
        s, obj, item = r["SECTION"], r["OBJ"], r["ITEM"]
        c = [r[f"C{i}"] for i in range(1, 6)]
        if s == "SNAPSHOT":
            d["snapshot"] = {"schema": obj, "timestamp": item, "dbVersion": c[0], "dbName": c[1],
                             "container": c[2], "schemaObjectCount": int(c[3] or 0)}
        elif s == "OBJECT_COUNT":
            d["objectCounts"][obj] = {"total": int(c[0]), "inScope": int(c[1]), "notValid": int(c[2])}
        elif s == "OBJECT":
            d["objects"][(obj, item)] = {"type": obj, "name": item, "status": c[0], "created": c[1],
                                         "lastDdl": c[2], "generated": c[3]}
        elif s == "COLUMN":
            length, precision, scale, char_used, char_length = (c[1].split(",") + [""] * 5)[:5]
            nullable, virtual, identity, on_null = (c[2].split("/") + [""] * 4)[:4]
            d["columns"][obj].append({
                "name": item, "dataType": c[0], "dataLength": length, "precision": precision, "scale": scale,
                "charUsed": char_used, "charLength": char_length, "nullable": nullable == "Y",
                "virtual": virtual == "YES", "identity": identity == "YES", "defaultOnNull": on_null == "YES",
                "default": c[3].strip() or None, "columnId": int(c[4]) if c[4] else None})
        elif s == "IDENTITY":
            opts = dict(re.findall(r"([A-Z_ ]+):\s*([^,]+)", c[1] or ""))
            d["identity"][(obj, item)] = {"generation": c[0], "options": {k.strip(): v.strip() for k, v in opts.items()}}
        elif s == "CONSTRAINT":
            status, validated, deferrable, deferred, generated = (c[1].split("/") + [""] * 5)[:5]
            d["constraints"][item] = {"table": obj, "name": item, "type": c[0], "status": status,
                                      "validated": validated, "deferrable": deferrable, "deferred": deferred,
                                      "generatedName": generated == "GENERATED NAME", "rConstraint": c[2] or None,
                                      "deleteRule": c[3] or None, "searchCondition": c[4] or None}
        elif s == "CONS_COLUMN":
            d["consColumns"][item].append((int(c[1]) if c[1] else 0, c[0]))
        elif s == "INDEX":
            d["indexes"][item] = {"table": obj, "name": item, "type": c[0], "uniqueness": c[1], "status": c[2]}
        elif s == "IND_COLUMN":
            d["indColumns"][item].append((int(c[1]), c[0], c[2]))
        elif s == "TRIGGER":
            d["triggers"][item] = {"table": obj, "name": item, "type": c[0], "event": c[1], "status": c[2]}
        elif s == "DEPENDENCY":
            d["dependencies"].append({"type": obj, "name": item, "refType": c[0], "ref": c[1], "kind": c[2]})
        elif s == "ERROR":
            d["errors"].append({"type": obj, "name": item, "position": c[0], "attribute": c[1], "text": c[2]})
        elif s == "GRANT":
            d["grants"].append({"type": obj, "name": item, "grantee": c[0], "privilege": c[1]})
        elif s == "SOURCE_LINES":
            d["sourceLines"][(obj, item)] = {"lines": int(c[0]), "chars": int(c[1] or 0)}
    if d["snapshot"] is None:
        raise ValueError("SNAPSHOT row missing.")
    for name in d["consColumns"]:
        d["consColumns"][name] = [col for _, col in sorted(d["consColumns"][name])]
    for name in d["indColumns"]:
        d["indColumns"][name] = sorted(d["indColumns"][name])
    for table in d["columns"]:
        d["columns"][table].sort(key=lambda x: x["columnId"] or 0)
    return d


def parse_view_texts(text: str) -> dict[str, dict[str, Any]]:
    """Parse a USER_VIEWS export with VIEW_NAME, TEXT_LENGTH, TEXT_VC."""
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows or not {"VIEW_NAME", "TEXT_LENGTH", "TEXT_VC"} <= set(rows[0]):
        raise ValueError("Input is not a USER_VIEWS (VIEW_NAME, TEXT_LENGTH, TEXT_VC) export.")
    return {r["VIEW_NAME"].upper(): {"length": int(r["TEXT_LENGTH"]), "text": r["TEXT_VC"]} for r in rows}


def _source_type(src: str | None) -> tuple[str, str]:
    m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_ ]*?)\s*(?:\((.*)\))?\s*$", src or "")
    return (m.group(1).upper(), (m.group(2) or "").strip()) if m else ("", "")


def _type_matches(plan_col: dict[str, Any], dc: dict[str, Any]) -> tuple[bool, str]:
    name, args = _source_type(plan_col.get("sourceType"))
    if plan_col.get("generated") and not plan_col.get("sourceType"):
        return True, "virtual (type derived)"
    if name in {"VARCHAR2", "VARCHAR", "NVARCHAR2", "CHAR", "NCHAR"}:
        m = re.fullmatch(r"(\d+)(?:\s+(BYTE|CHAR))?", args, re.I)
        if not m or dc["dataType"] != ("VARCHAR2" if name == "VARCHAR" else name):
            return False, f"{plan_col['sourceType']} vs {dc['dataType']}"
        semantics = (m.group(2) or "").upper()
        ok = dc["charLength"] == m.group(1) and (not semantics or dc["charUsed"] == semantics[0])
        note = "" if semantics else f"length semantics {'BYTE' if dc['charUsed'] == 'B' else 'CHAR'} (database default)"
        return ok, note if ok else f"{plan_col['sourceType']} vs {dc['dataType']}({dc['charLength']} {dc['charUsed']})"
    if name == "NUMBER":
        p, _, s = args.partition(",")
        ok = dc["dataType"] == "NUMBER" and dc["precision"] == p.strip().replace("*", "") and \
            (dc["scale"] or "") == (s.strip() or ("0" if p.strip() and p.strip() != "*" else ""))
        return ok, "" if ok else f"{plan_col['sourceType']} vs NUMBER({dc['precision']},{dc['scale']})"
    return dc["dataType"].startswith(name), "" if dc["dataType"].startswith(name) else f"{plan_col['sourceType']} vs {dc['dataType']}"


def reconcile(plan: dict[str, Any], dictionary: dict[str, Any], source: str, *,
              dictionary_name: str = "report.csv", dictionary_sha256: str | None = None,
              view_texts: dict[str, dict[str, Any]] | None = None, view_texts_name: str | None = None,
              view_texts_sha256: str | None = None, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    drift: list[dict[str, Any]] = []
    resolutions: list[dict[str, Any]] = []
    source, _ = apply_overrides(source, overrides)
    overridden = {r["object"]: r for r in plan.get("overrides", [])}
    if overrides is not None and {f"{o['object'].upper()} {o['name'].upper()}" for o in overrides["overrides"]} != set(overridden):
        raise ValueError("Overrides file does not match the overrides recorded in the plan.")

    def check(cid: str, title: str, failures: list[str], notes: list[str] | None = None) -> None:
        checks.append({"id": cid, "title": title, "status": "FAIL" if failures else "PASS",
                       "failures": failures, "notes": notes or []})

    objects = dictionary["objects"]
    in_scope = {name for (_, name) in objects}
    tables = {t["name"]: t for t in plan["tables"]}
    views = {v["name"]: v for v in plan["views"]}
    triggers = {t["name"]: t for t in plan["triggers"]}
    units = {(u["kind"], u["name"]) for u in plan["plsqlUnits"]}

    # ---------------------------------------------------------------- REC-001 inventory
    expected: dict[tuple[str, str], str] = {}
    for t in tables.values():
        expected[("TABLE", t["name"])] = "table"
        for con in t["constraints"]:
            if con["kind"] in {"PRIMARY KEY", "UNIQUE"}:
                expected[("INDEX", con["name"])] = f"{con['kind']} index of {t['name']}"
    for ix in plan["indexes"]:
        expected[("INDEX", ix["name"])] = "index"
    for v in views:
        expected[("VIEW", v)] = "view"
    for trg in triggers:
        expected[("TRIGGER", trg)] = "trigger"
    for kind, name in units:
        expected[(kind, name)] = kind.lower()
    missing = sorted(f"{k[0]} {k[1]}" for k in expected if k not in objects)
    extra = sorted(f"{k[0]} {k[1]}" for k in objects if k not in expected)
    invalid = sorted(f"{o['type']} {o['name']} {o['status']}" for o in objects.values() if o["status"] != "VALID")
    check("REC-001", "Every script object is installed, VALID, and no unexplained in-scope object exists",
          missing + [f"unexplained: {x}" for x in extra] + invalid,
          notes=[f"{len(objects)} in-scope dictionary objects; {len(expected)} expected from script"])

    # ---------------------------------------------------------------- REC-002 columns / REC-005 identity
    col_failures: list[str] = []
    col_notes: set[str] = set()
    ident_failures: list[str] = []
    ident_notes: list[str] = []
    for tname, t in tables.items():
        dcols = dictionary["columns"].get(tname, [])
        plan_names = [c["name"] for c in t["columns"]]
        dict_names = [c["name"] for c in dcols]
        if plan_names != dict_names:
            col_failures.append(f"{tname}: column order/set script {plan_names} vs dictionary {dict_names}")
            continue
        for pc, dc in zip(t["columns"], dcols):
            label = f"{tname}.{pc['name']}"
            ok, note = _type_matches(pc, dc)
            if not ok:
                col_failures.append(f"{label}: type {note}")
            elif note:
                col_notes.add(note)
            if pc["nullable"] != dc["nullable"]:
                col_failures.append(f"{label}: nullable script {pc['nullable']} vs dictionary {dc['nullable']}")
            if pc.get("generated"):
                if not dc["virtual"] or _norm(dc["default"]) != _norm(pc["generated"]["source"]):
                    col_failures.append(f"{label}: virtual expression {pc['generated']['source']!r} vs {dc['default']!r}")
            elif pc.get("identity"):
                di = dictionary["identity"].get((tname, pc["name"]))
                if not dc["identity"] or di is None:
                    ident_failures.append(f"{label}: identity missing in dictionary")
                    continue
                mode = pc["identity"]["mode"]
                if di["generation"] != mode or dc["defaultOnNull"] != pc["identity"]["onNull"]:
                    ident_failures.append(f"{label}: {mode}{' ON NULL' if pc['identity']['onNull'] else ''} vs "
                                          f"{di['generation']}{' ON NULL' if dc['defaultOnNull'] else ''}")
                opts = pc["identity"]["options"]
                if str(opts.get("start", 1)) != di["options"].get("START WITH") or \
                        str(opts.get("increment", 1)) != di["options"].get("INCREMENT BY"):
                    ident_failures.append(f"{label}: START/INCREMENT script {opts} vs dictionary {di['options']}")
                ident_notes.append(f"{label}: CACHE {di['options'].get('CACHE_SIZE')}, MAXVALUE "
                                   f"{di['options'].get('MAX_VALUE')} (Oracle defaults; PostgreSQL uses CACHE 1, bigint max)")
            else:
                script_default = pc.get("default", {}).get("source") if pc.get("default") else None
                if _norm(script_default) != _norm(dc["default"]):
                    col_failures.append(f"{label}: default {script_default!r} vs {dc['default']!r}")
            if dc["virtual"] and not pc.get("generated"):
                col_failures.append(f"{label}: virtual in dictionary only")
    missing_tables = sorted(set(tables) - set(dictionary["columns"]))
    check("REC-002", "Table columns match (order, datatype, length semantics, nullability, defaults, virtual expression)",
          col_failures + [f"{t}: no columns in dictionary" for t in missing_tables], notes=sorted(col_notes))
    check("REC-003", "Identity columns match (BY DEFAULT ON NULL, START WITH, INCREMENT BY)", ident_failures,
          notes=sorted(set(re.sub(r"^[^:]+: ", "", n) for n in ident_notes)) + [f"{len(ident_notes)} identity column(s)"])

    # ---------------------------------------------------------------- REC-004 constraints
    con_failures: list[str] = []
    named = {name: c for name, c in dictionary["constraints"].items() if not c["generatedName"]}
    plan_cons = {}
    for tname, t in tables.items():
        for con in t["constraints"]:
            plan_cons[con["name"]] = (tname, con)
    for name in sorted(set(plan_cons) | set(named)):
        if name not in named:
            con_failures.append(f"{name}: in script, not in dictionary")
            continue
        if name not in plan_cons:
            con_failures.append(f"{name}: in dictionary only ({named[name]['type']} on {named[name]['table']})")
            continue
        tname, con = plan_cons[name]
        dcon = named[name]
        kind = {"PRIMARY KEY": "P", "UNIQUE": "U", "CHECK": "C", "FOREIGN KEY": "R"}[con["kind"]]
        if dcon["type"] != kind or dcon["table"] != tname:
            con_failures.append(f"{name}: {con['kind']} on {tname} vs type {dcon['type']} on {dcon['table']}")
        if dcon["status"] != "ENABLED" or dcon["validated"] != "VALIDATED" or dcon["deferrable"] != "NOT DEFERRABLE":
            con_failures.append(f"{name}: state {dcon['status']}/{dcon['validated']}/{dcon['deferrable']}")
        if kind in {"P", "U", "R"} and dictionary["consColumns"].get(name) != con["columns"]:
            con_failures.append(f"{name}: columns {con['columns']} vs {dictionary['consColumns'].get(name)}")
        if kind == "C" and _norm(dcon["searchCondition"]) != _norm(con.get("expression")):
            con_failures.append(f"{name}: condition {con.get('expression')!r} vs {dcon['searchCondition']!r}")
        if kind == "R":
            ref = dictionary["constraints"].get(dcon["rConstraint"] or "")
            if ref is None or ref["table"] != con["target"] or dictionary["consColumns"].get(ref["name"]) != con["targetColumns"]:
                con_failures.append(f"{name}: references {con['target']}({con['targetColumns']}) vs {dcon['rConstraint']}")
            if (dcon["deleteRule"] or "NO ACTION") != (con.get("onDelete") or "NO ACTION"):
                con_failures.append(f"{name}: ON DELETE {con.get('onDelete') or 'NO ACTION'} vs {dcon['deleteRule']}")
    nn_failures = []
    for name, c in dictionary["constraints"].items():
        if not c["generatedName"]:
            continue
        cols = dictionary["consColumns"].get(name, [])
        m = re.fullmatch(r'"([^"]+)" IS NOT NULL', c["searchCondition"] or "")
        if c["type"] != "C" or not m or cols != [m.group(1)]:
            nn_failures.append(f"{name} on {c['table']}: system-named constraint is not a simple NOT NULL")
            continue
        pt = tables.get(c["table"])
        pc = next((x for x in pt["columns"] if x["name"] == m.group(1)), None) if pt else None
        if pc is None or pc["nullable"]:
            nn_failures.append(f"{name}: NOT NULL {c['table']}.{m.group(1)} not declared in script")
    check("REC-004", "Named constraints match (type, columns, condition, references, delete rule, state); "
          "system-named constraints are NOT NULL declared in the script",
          con_failures + nn_failures,
          notes=[f"{len(named)} named, {len(dictionary['constraints']) - len(named)} system-named NOT NULL"])

    # ---------------------------------------------------------------- REC-005 indexes
    ix_failures = []
    plan_ix: dict[str, tuple[str, list[str], bool]] = {}
    for ix in plan["indexes"]:
        plan_ix[ix["name"]] = (ix["table"], [e.get("column") for e in ix["elements"]], ix["unique"])
    for tname, t in tables.items():
        for con in t["constraints"]:
            if con["kind"] in {"PRIMARY KEY", "UNIQUE"}:
                plan_ix.setdefault(con["name"], (tname, list(con["columns"]), True))
    for name in sorted(set(plan_ix) | set(dictionary["indexes"])):
        if name not in dictionary["indexes"] or name not in plan_ix:
            ix_failures.append(f"{name}: {'script only' if name in plan_ix else 'dictionary only'}")
            continue
        tname, cols, unique = plan_ix[name]
        di = dictionary["indexes"][name]
        dcols = [c for _, c, _ in dictionary["indColumns"].get(name, [])]
        if di["table"] != tname or dcols != cols or (di["uniqueness"] == "UNIQUE") != unique or di["status"] != "VALID":
            ix_failures.append(f"{name}: {tname}{cols} unique={unique} vs {di['table']}{dcols} {di['uniqueness']} {di['status']}")
    check("REC-005", "Indexes match (table, columns, uniqueness, VALID)", ix_failures,
          notes=[f"{len(dictionary['indexes'])} dictionary indexes incl. constraint-backing indexes"])

    # ---------------------------------------------------------------- REC-006 triggers
    trg_failures = []
    for name, trg in triggers.items():
        dt = dictionary["triggers"].get(name)
        if dt is None:
            trg_failures.append(f"{name}: not in dictionary")
            continue
        events = " OR ".join(e["event"] for e in trg["events"])
        timing = f"{trg['timing']} EACH ROW" if trg["forEachRow"] else f"{trg['timing']} STATEMENT"
        if (dt["table"], dt["type"], dt["event"], dt["status"]) != (trg["table"], timing, events, "ENABLED"):
            trg_failures.append(f"{name}: {trg['table']} {timing} {events} vs {dt['table']} {dt['type']} {dt['event']} {dt['status']}")
    check("REC-006", "Triggers match (table, timing, events) and are ENABLED", trg_failures)

    # ---------------------------------------------------------------- REC-007 view columns
    view_failures = []
    for name, v in views.items():
        dcols = [c["name"] for c in dictionary["columns"].get(name, [])]
        if v["outputColumns"] != dcols:
            view_failures.append(f"{name}: script columns {v['outputColumns']} vs dictionary {dcols}")
            drift.append({"object": f"VIEW {name}", "kind": "definition",
                          "detail": f"columns {v['outputColumns']} in script, {dcols} installed",
                          "lastDdl": objects.get(("VIEW", name), {}).get("lastDdl")})
    check("REC-007", "View output columns match the script definitions", view_failures)

    # ---------------------------------------------------------------- REC-008 source fingerprint
    src_failures = []
    src_notes = []
    for stmt in split_script(source):
        kind = PLSQL_STATEMENT_KINDS.get(stmt.kind)
        if not kind:
            continue
        text = re.sub(r"^create\s+(?:or\s+replace\s+)?(?:(?:non)?editionable\s+)?", "", stmt.text, flags=re.I)
        m = re.match(r"(?:package\s+body|type\s+body|package|trigger|procedure|function|type)\s+(?:\"?\w+\"?\.)?\"?(\w+)\"?",
                     text, re.I)
        name = m.group(1).upper() if m else "?"
        observed = dictionary["sourceLines"].get((kind, name))
        script = {"lines": text.count("\n") + 1, "chars": len(text)}
        if observed is None:
            src_failures.append(f"{kind} {name}: no USER_SOURCE rows")
        elif observed != script:
            src_failures.append(f"{kind} {name}: script {script} vs installed {observed}")
        else:
            src_notes.append(f"{kind} {name}: {script['lines']} lines / {script['chars']} chars identical")
    check("REC-008", "Installed PL/SQL and trigger source size equals the script text (USER_SOURCE fingerprint)",
          src_failures, notes=src_notes)

    # ---------------------------------------------------------------- REC-009 static dependencies
    owner = dictionary["snapshot"]["schema"]
    plan_edges: set[tuple[str, str]] = set()
    for v in views.values():
        plan_edges |= {(v["name"], d) for d in v["dependencies"]}
        # source-level calls count whether or not a reviewed function mapping replaced them in the target
        plan_edges |= {(v["name"], c.split(".")[0]) for c in v["plsqlCalls"] + v.get("mappedCalls", [])}
    for trg in triggers.values():
        plan_edges |= {(trg["name"], trg["table"])} | {(trg["name"], c.split(".")[0]) for c in trg["calls"]}
        plan_edges |= {(trg["name"], x) for x in trg["tablesRead"] + trg["tablesWritten"]}
    for u in plan["plsqlUnits"]:
        refs = set(u["tablesReferenced"]) | set(u["viewsReferenced"]) | set(u["unitsReferenced"])
        if u["kind"] == "PACKAGE BODY":
            refs.add(u["name"])
        plan_edges |= {(f"{u['kind']}:{u['name']}", r) for r in refs}
    dict_edges: set[tuple[str, str]] = set()
    external: set[str] = set()
    for dep in dictionary["dependencies"]:
        ref_owner, _, ref_name = dep["ref"].partition(".")
        src = f"{dep['type']}:{dep['name']}" if dep["type"] in {"PACKAGE", "PACKAGE BODY"} else dep["name"]
        if ref_owner == owner and ref_name in in_scope:
            dict_edges.add((src, ref_name))
        else:
            external.add(dep["ref"])
    graph: dict[str, set[str]] = defaultdict(set)
    for a, b in plan_edges:
        graph[a.split(":")[-1]].add(b)

    def reachable(a: str, b: str) -> bool:
        seen, stack = set(), [a.split(":")[-1]]
        while stack:
            n = stack.pop()
            for m in graph.get(n, ()):
                if m == b:
                    return True
                if m not in seen:
                    seen.add(m)
                    stack.append(m)
        return False

    transitive = sorted(f"{a} -> {b}" for a, b in dict_edges - plan_edges if reachable(a, b))
    dep_failures = sorted(f"{a} -> {b}: installed dependency not derived from script"
                          for a, b in dict_edges - plan_edges if not reachable(a, b))
    lexical_only = sorted(f"{a} -> {b}" for a, b in plan_edges - dict_edges)
    check("REC-009", "Installed static dependencies are all derived from the script",
          dep_failures, notes=[f"{len(dict_edges)} in-scope static edges; external: {', '.join(sorted(external))}"]
          + [f"explained transitively through script dependencies: {x}" for x in transitive]
          + [f"script-only (dynamic SQL, %TYPE, or lexical over-approximation): {x}" for x in lexical_only])

    # ---------------------------------------------------------------- REC-010 errors and grants
    check("REC-010", "No compile errors; grants recorded",
          [f"{e['type']} {e['name']} {e['position']}: {e['text']}" for e in dictionary["errors"]],
          notes=[f"{len(dictionary['grants'])} object grant(s) on in-scope objects"]
          + [f"{g['type']} {g['name']} -> {g['grantee']}: {g['privilege']}" for g in dictionary["grants"]])

    # ---------------------------------------------------------------- REC-012 view text
    text_identical: set[str] = set()
    if view_texts is not None:
        text_failures = []
        text_notes = []
        for name, vt in sorted(view_texts.items()):
            if vt["length"] != len(vt["text"]):
                text_failures.append(f"{name}: TEXT_LENGTH {vt['length']} but exported {len(vt['text'])} chars (truncated)")
                continue
            v = views.get(name)
            if v is None:
                text_failures.append(f"{name}: not a view in the plan")
            elif _norm(v["source"]) == _norm(vt["text"]):
                text_identical.add(f"VIEW {name}")
                text_notes.append(f"{name}: installed text identical to "
                                  + ("dictionary override" if f"VIEW {name}" in overridden else "script"))
            else:
                text_failures.append(f"{name}: installed text differs from the plan definition")
                drift.append({"object": f"VIEW {name}", "kind": "definition", "detail": "installed view text differs",
                              "lastDdl": objects.get(("VIEW", name), {}).get("lastDdl")})
        check("REC-012", "Installed view text equals the definition used by the plan", text_failures, notes=text_notes)

    # ---------------------------------------------------------------- REC-011 change timeline
    created = [datetime.fromisoformat(o["created"]) for o in objects.values() if o["created"]]
    window_end = max(created) + timedelta(minutes=1) if created else None
    late = []
    late_notes = []
    for o in sorted(objects.values(), key=lambda x: x["name"]):
        if not (window_end and o["lastDdl"] and datetime.fromisoformat(o["lastDdl"]) > window_end):
            continue
        key = f"{o['type']} {o['name']}"
        if key in overridden and key in text_identical:
            late_notes.append(f"{key} last DDL {o['lastDdl']}: redefined after install; captured by dictionary override")
            resolutions.append({"object": key, "resolution": "dictionary override",
                                "detail": overridden[key].get("reason"), "lastDdl": o["lastDdl"]})
        elif key in text_identical:
            late_notes.append(f"{key} last DDL {o['lastDdl']}: text identical to script (recompilation)")
            resolutions.append({"object": key, "resolution": "recompilation; text verified identical",
                                "detail": "LAST_DDL_TIME after install window, installed text equals script", "lastDdl": o["lastDdl"]})
        else:
            changed = any(d["object"] == key for d in drift)
            late.append(f"{key} last DDL {o['lastDdl']}" + (" (definition differs from plan)" if changed
                        else " (columns match; supply USER_VIEWS/USER_SOURCE text to verify)"))
            if not changed:
                drift.append({"object": key, "kind": "post-install DDL",
                              "detail": "LAST_DDL_TIME after install window; text not verified", "lastDdl": o["lastDdl"]})
    check("REC-011", "Every in-scope object changed after the install window is verified or overridden",
          late, notes=[f"install window {min(created).isoformat() if created else '?'} .. "
                       f"{max(created).isoformat() if created else '?'}"] + late_notes)
    checks.sort(key=lambda c: c["id"])

    snapshot = dictionary["snapshot"]
    outside_invalid = {k: v["notValid"] for k, v in dictionary["objectCounts"].items() if v["notValid"]}
    return {
        "format": RECONCILIATION_FORMAT,
        "reconcilerVersion": RECONCILER_VERSION,
        "plan": {"source": plan["source"], "converterVersion": plan["converterVersion"]},
        "overrides": plan.get("overrides", []),
        "dictionary": {"name": dictionary_name, "sha256": dictionary_sha256, "snapshot": snapshot,
                       "viewTexts": ({"name": view_texts_name, "sha256": view_texts_sha256, "views": sorted(view_texts)}
                                     if view_texts is not None else None),
                       "consistency": "Single-session query; no SCN (not granted). Rows are not guaranteed to be one point in time.",
                       "inScopeObjects": len(objects),
                       "schemaObjectCounts": dictionary["objectCounts"],
                       "notValidOutsideScope": outside_invalid},
        "summary": {"checks": {c["id"]: c["status"] for c in checks},
                    "reconciled": all(c["status"] == "PASS" for c in checks),
                    "drift": len(drift), "resolved": len(resolutions)},
        "checks": checks,
        "drift": drift,
        "resolutions": resolutions,
    }


def render_markdown(rec: dict[str, Any], *, title: str) -> str:
    snap = rec["dictionary"]["snapshot"]
    out = [f"# {title}", "", "> Generated by `apex2next_schema_analyzer.dictionary_reconciliation`. Do not edit by hand.", "",
           f"- **Script:** `{rec['plan']['source']['name']}` `{rec['plan']['source']['sha256']}`",
           f"- **Dictionary evidence:** `{rec['dictionary']['name']}` `sha256:{rec['dictionary']['sha256']}`",
           f"- **Snapshot:** schema `{snap['schema']}`, {snap['timestamp']}, Oracle {snap['dbVersion']} "
           f"({snap['dbName']}), {snap['schemaObjectCount']} objects in schema, {rec['dictionary']['inScopeObjects']} in scope",
           f"- **Consistency:** {rec['dictionary']['consistency']}",
           *([f"- **View text evidence:** `{rec['dictionary']['viewTexts']['name']}` `sha256:{rec['dictionary']['viewTexts']['sha256']}`"]
             if rec["dictionary"].get("viewTexts") else []),
           *[f"- **Dictionary override:** {o['object']} ({o['action']}; {o['reason']})" for o in rec.get("overrides", [])],
           f"- **Reconciled:** {'yes' if rec['summary']['reconciled'] else 'NO — see failures'}; open drift: {rec['summary']['drift']}; resolved: {rec['summary']['resolved']}",
           "", "## Checks", "", "| Check | Status | Title | Failures / notes |", "|---|---|---|---|"]
    for c in rec["checks"]:
        detail = "; ".join(c["failures"]) if c["failures"] else "; ".join(c["notes"][:6])
        out.append(f"| {c['id']} | {c['status']} | {c['title']} | {detail.replace('|', '/') or '—'} |")
    out += ["", "## Open drift", ""]
    out += [f"- **{d['object']}** ({d['kind']}, last DDL {d['lastDdl']}): {d['detail']}" for d in rec["drift"]] or ["- none"]
    out += ["", "## Resolved", ""]
    out += [f"- **{r['object']}** (last DDL {r['lastDdl']}): {r['resolution']} — {r['detail']}" for r in rec["resolutions"]] or ["- none"]
    if rec["dictionary"]["notValidOutsideScope"]:
        out += ["", "## Schema hygiene outside scope", "",
                "The schema is shared with other applications. Objects that are not VALID outside the `APX_DEMO_` prefix:", ""]
        out += [f"- {k}: {v}" for k, v in sorted(rec["dictionary"]["notValidOutsideScope"].items())]
    out.append("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile a WP9.3 schema plan with Oracle dictionary evidence")
    parser.add_argument("plan", type=Path)
    parser.add_argument("source", type=Path, help="install script used to build the plan")
    parser.add_argument("dictionary", type=Path, help="CSV from dictionary_inventory_apex_workshop.sql")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--view-texts", type=Path, help="USER_VIEWS export (VIEW_NAME, TEXT_LENGTH, TEXT_VC)")
    parser.add_argument("--overrides", type=Path, help="dictionary overrides used to build the plan")
    parser.add_argument("--title", default="WP9.3b Oracle Dictionary Reconciliation")
    args = parser.parse_args()
    raw = args.dictionary.read_bytes()
    vraw = args.view_texts.read_bytes() if args.view_texts else None
    rec = reconcile(json.loads(args.plan.read_text(encoding="utf-8")), parse_workshop_csv(raw.decode("utf-8")),
                    args.source.read_text(encoding="utf-8"), dictionary_name=args.dictionary.name,
                    dictionary_sha256=hashlib.sha256(raw).hexdigest(),
                    view_texts=parse_view_texts(vraw.decode("utf-8")) if vraw is not None else None,
                    view_texts_name=args.view_texts.name if args.view_texts else None,
                    view_texts_sha256=hashlib.sha256(vraw).hexdigest() if vraw is not None else None,
                    overrides=load_overrides(args.overrides) if args.overrides else None)
    args.output.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.write_text(render_markdown(rec, title=args.title), encoding="utf-8")
    return 0 if rec["summary"]["reconciled"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
