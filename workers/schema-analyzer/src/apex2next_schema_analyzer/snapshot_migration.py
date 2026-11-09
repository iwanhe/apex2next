"""WP9.6 data migration from an APEX SQL Workshop JSON snapshot into the PostgreSQL target, with reconciliation.

Input is the CSV produced by ``extract_snapshot_apex_workshop.sql`` (one read-consistent SELECT):
SECTION, OBJ, PK, DOC, SHA256. Every DOC is verified against the SHA-256 computed in Oracle before
anything is loaded. Loading runs in one transaction into an empty, migrated schema, in foreign-key order,
with explicit identity values; afterwards identity sequences are aligned to the Oracle high-water mark.

Reconciliation compares, independently of PostgreSQL casts, every source row with the loaded row
(values normalized in Python: exact decimals, timestamps, strings) and every source view row with the
target view evaluated under the same principal (``app.username`` = the APP_USER of the snapshot).

Checks (all must PASS):
  SNP-001 every DOC matches its Oracle SHA-256      SNP-002 COUNT rows equal the ROW/VIEW rows received
  SNP-003 snapshot has SESSION facts and all tables/views of the plan, unique keys, valid JSON
  LOD-001 target tables were empty before loading    LOD-002 row counts after load equal the source
  IDN-001 identity next values are above every key and at least the Oracle high-water mark
  TBL-001 every column of every row equals the source (generated columns included)
  VIW-001 every view row equals the source view row under the same principal
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

FORMAT = "apex2next.snapshot-migration.v1"
csv.field_size_limit(1 << 24)


@dataclass
class Snapshot:
    session: dict[str, Any]
    counts: dict[str, int]
    identities: dict[str, dict[str, Any]]
    rows: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    views: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    sha256: str = ""
    problems: list[dict[str, Any]] = field(default_factory=list)


def _decode(doc: str) -> dict[str, Any]:
    return json.loads(doc, parse_float=Decimal, parse_int=Decimal)


def parse_snapshot(text: str) -> Snapshot:
    """Parse and verify the snapshot CSV. Problems are collected, not raised, so the report shows all."""
    if text.startswith("﻿"):
        text = text[1:]
    reader = csv.DictReader(io.StringIO(text))
    fields = [f.strip().upper() for f in reader.fieldnames or []]
    snap = Snapshot(session={}, counts={}, identities={}, sha256=hashlib.sha256(text.encode("utf-8")).hexdigest())
    if fields[:5] != ["SECTION", "OBJ", "PK", "DOC", "SHA256"]:
        snap.problems.append({"check": "SNP-003", "message": f"unexpected header {fields}"})
        return snap
    for n, raw in enumerate(reader, start=2):
        rec = {k.strip().upper(): (v or "") for k, v in raw.items() if k}
        section, obj, pk, doc, digest = (rec["SECTION"], rec["OBJ"], rec["PK"], rec["DOC"], rec["SHA256"].lower())
        if hashlib.sha256(doc.encode("utf-8")).hexdigest() != digest:
            snap.problems.append({"check": "SNP-001", "message": f"line {n}: DOC does not match its SHA-256", "obj": obj, "pk": pk})
            continue
        try:
            if section == "COUNT":
                snap.counts[obj] = int(doc)
                continue
            value = _decode(doc)
        except (ValueError, json.JSONDecodeError) as exc:
            snap.problems.append({"check": "SNP-003", "message": f"line {n}: invalid value ({exc})", "obj": obj, "pk": pk})
            continue
        if section == "SNAPSHOT":
            snap.session = value
        elif section == "IDENTITY":
            snap.identities[f"{obj}.{pk}"] = value
        elif section in ("ROW", "VIEW"):
            target = snap.rows if section == "ROW" else snap.views
            bucket = target.setdefault(obj, {})
            if pk in bucket:
                snap.problems.append({"check": "SNP-003", "message": f"line {n}: duplicate key", "obj": obj, "pk": pk})
            bucket[pk] = {k.lower(): v for k, v in value.items()}
        else:
            snap.problems.append({"check": "SNP-003", "message": f"line {n}: unknown section {section}"})
    for obj, expected in sorted(snap.counts.items()):
        got = len(snap.rows.get(obj, snap.views.get(obj, {})))
        if got != expected:
            snap.problems.append({"check": "SNP-002", "message": f"{obj}: COUNT {expected}, received {got} rows", "obj": obj})
    if not snap.session:
        snap.problems.append({"check": "SNP-003", "message": "SNAPSHOT/SESSION row missing"})
    return snap


# ------------------------------------------------------------------------------------------ normalization
def norm(value: Any) -> Any:
    """Comparable form: exact decimals, ISO timestamps without trailing zero fractions, plain strings."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, Decimal, float)):
        d = Decimal(str(value)).normalize()
        return "0" if d == 0 else format(d, "f")
    if isinstance(value, datetime):
        text = value.isoformat()
        return text.rstrip("0").rstrip(".") if "." in text else text
    if isinstance(value, date):
        return value.isoformat() + "T00:00:00"
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, default=str)


def _norm_source(value: Any, target: Any) -> Any:
    """Source JSON value in the comparable form of the target value's type."""
    if value is None:
        return None
    if isinstance(target, (datetime, date)) and isinstance(value, str):
        text = value.replace(" ", "T")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text
    return norm(value)


def compare_row(source: dict[str, Any], target: dict[str, Any]) -> list[dict[str, Any]]:
    diffs = []
    for col in sorted(set(source) | set(target)):
        if col not in target:
            diffs.append({"column": col, "issue": "missing in target"})
        elif col not in source:
            diffs.append({"column": col, "issue": "missing in source"})
        else:
            s, t = _norm_source(source[col], target[col]), norm(target[col])
            if s != t:
                diffs.append({"column": col, "source": s, "target": t})
    return diffs


# ------------------------------------------------------------------------------------------ database
def _ident(name: str) -> str:
    if not name.replace("_", "").isalnum() or not name[0].isalpha():
        raise ValueError(f"unsafe identifier {name!r}")
    return name


def _fk_order(conn, schema: str, tables: list[str]) -> list[str]:
    rows = conn.execute(
        """SELECT c.conrelid::regclass::text, c.confrelid::regclass::text FROM pg_constraint c
            JOIN pg_namespace n ON n.oid = c.connamespace WHERE c.contype = 'f' AND n.nspname = %s""", (schema,)).fetchall()
    deps = {t: set() for t in tables}
    for child, parent in rows:
        child, parent = child.split(".")[-1], parent.split(".")[-1]
        if child in deps and parent in deps and child != parent:
            deps[child].add(parent)
    order: list[str] = []
    while deps:
        ready = sorted(t for t, d in deps.items() if not d - set(order))
        if not ready:
            raise ValueError(f"foreign-key cycle among {sorted(deps)}")
        for t in ready:
            order.append(t)
            deps.pop(t)
    return order


def load_snapshot(conn, snap: Snapshot, plan: dict[str, Any], schema: str = "app") -> dict[str, Any]:
    """Load all ROW sections in one transaction (the caller commits). Returns the load report."""
    load_plan = plan["loadPlan"]
    tables = list(load_plan)
    order = _fk_order(conn, schema, tables)
    report: dict[str, Any] = {"order": order, "tables": {}, "problems": []}
    for t in order:
        n = conn.execute(f"SELECT count(*) FROM {_ident(schema)}.{_ident(t)}").fetchone()[0]
        if n:
            report["problems"].append({"check": "LOD-001", "message": f"{t} is not empty ({n} rows)"})
    if report["problems"]:
        return report
    for t in order:
        spec = load_plan[t]
        cols = [c for c in spec["columns"] if c not in spec.get("excludedGenerated", [])]
        rows = snap.rows.get(t.upper(), {})
        col_list = ", ".join(_ident(c) for c in cols)
        sql = (f"INSERT INTO {schema}.{t} ({col_list}) SELECT {col_list} "
               f"FROM jsonb_populate_record(NULL::{schema}.{t}, %s::jsonb)")
        for pk in sorted(rows, key=_sort_key):
            row = rows[pk]
            extra = sorted(set(row) - set(spec["columns"]) - set(spec.get("excludedGenerated", [])))
            if extra:
                report["problems"].append({"check": "LOD-002", "message": f"{t}/{pk}: source columns not in target: {extra}"})
            conn.execute(sql, (json.dumps({c: row.get(c) for c in cols}, default=str),))
        got = conn.execute(f"SELECT count(*) FROM {schema}.{t}").fetchone()[0]
        report["tables"][t] = {"source": len(rows), "loaded": got}
        if got != len(rows) or snap.counts.get(t.upper()) not in (None, got):
            report["problems"].append({"check": "LOD-002", "message": f"{t}: source {len(rows)}, loaded {got}"})
    return report


def _sort_key(pk: str):
    return (0, int(pk), pk) if pk.isdigit() else (1, 0, pk)


def align_identities(conn, snap: Snapshot, plan: dict[str, Any], schema: str = "app") -> list[dict[str, Any]]:
    """Next value = max(max(key) + 1, Oracle LAST_NUMBER) so the target never reuses a source value."""
    out = []
    for t, spec in plan["loadPlan"].items():
        for col in spec.get("identity", {}):
            mx = conn.execute(f"SELECT max({_ident(col)}) FROM {schema}.{_ident(t)}").fetchone()[0] or 0
            ora = snap.identities.get(f"{t.upper()}.{col.upper()}", {})
            last = int(ora.get("last_number") or 0)
            nxt = max(int(mx) + 1, last, 1)
            conn.execute("SELECT setval(pg_get_serial_sequence(%s, %s), %s, false)", (f"{schema}.{t}", col, nxt))
            out.append({"table": t, "column": col, "maxKey": int(mx), "oracleLastNumber": last or None, "next": nxt})
    return out


def _fetch(conn, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    cur = conn.execute(sql, params)
    names = [d.name for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


VIEW_KEYS = {
    "APX_DEMO_USER_ROLES_V": "user_role_id", "APX_DEMO_DEPARTMENTS_V": "department_id", "APX_DEMO_ITEMS_V": "item_id",
    "APX_DEMO_REQUESTS_V": "request_id", "APX_DEMO_REQUEST_LINES_V": "line_id", "APX_DEMO_REQUEST_SUMMARY_V": "request_no",
    "APX_DEMO_APPROVALS_V": "approval_id", "APX_DEMO_DASH_C1_S1_V": "label", "APX_DEMO_DASH_C2_S1_V": "label",
    "APX_DEMO_DASH_KPI_V": "seq",
}


def _key_text(value: Any) -> str:
    return norm(value) if not isinstance(value, str) else value


def reconcile(conn, snap: Snapshot, plan: dict[str, Any], schema: str = "app") -> dict[str, Any]:
    tables: dict[str, Any] = {}
    for t, spec in plan["loadPlan"].items():
        pk_cols = _pk_columns(conn, schema, t)
        target = {"|".join(_key_text(r[c]) for c in pk_cols): r for r in _fetch(conn, f"SELECT * FROM {schema}.{_ident(t)}")}
        source = snap.rows.get(t.upper(), {})
        diffs = {}
        for pk in sorted(set(source) | set(target), key=_sort_key):
            if pk not in target:
                diffs[pk] = [{"issue": "row missing in target"}]
            elif pk not in source:
                diffs[pk] = [{"issue": "row not in source"}]
            else:
                d = compare_row(source[pk], target[pk])
                if d:
                    diffs[pk] = d
        tables[t] = {"rows": len(source), "differences": diffs}
    principal = snap.session.get("pkg_app_user") or snap.session.get("apex_app_user") or ""
    conn.execute("SELECT set_config('app.username', %s, true)", (principal,))
    views: dict[str, Any] = {}
    for v, key in VIEW_KEYS.items():
        source = snap.views.get(v, {})
        target = {_key_text(r[key]): r for r in _fetch(conn, f"SELECT * FROM {schema}.{_ident(v.lower())}")}
        diffs = {}
        for pk in sorted(set(source) | set(target), key=_sort_key):
            if pk not in target:
                diffs[pk] = [{"issue": "row missing in target"}]
            elif pk not in source:
                diffs[pk] = [{"issue": "row not in source"}]
            else:
                d = compare_row(source[pk], target[pk])
                if d:
                    diffs[pk] = d
        views[v.lower()] = {"rows": len(source), "differences": diffs}
    return {"principal": principal, "tables": tables, "views": views}


def _pk_columns(conn, schema: str, table: str) -> list[str]:
    rows = conn.execute(
        """SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = %s::regclass AND i.indisprimary ORDER BY array_position(i.indkey, a.attnum)""",
        (f"{schema}.{table}",)).fetchall()
    return [r[0] for r in rows]


def migrate(conn, snap: Snapshot, plan: dict[str, Any], schema: str = "app", *, snapshot_name: str = "snapshot.csv") -> dict[str, Any]:
    """Load + align + reconcile in one transaction; commits only if every check passes."""
    checks: dict[str, str] = {}
    problems = list(snap.problems)
    expected = {t.upper() for t in plan["loadPlan"]} | set(VIEW_KEYS)
    missing = sorted(expected - set(snap.counts))
    if missing:
        problems.append({"check": "SNP-003", "message": f"COUNT missing for {missing}"})
    report: dict[str, Any] = {"format": FORMAT, "snapshot": {"name": snapshot_name, "sha256": snap.sha256, "session": snap.session,
                                                             "counts": snap.counts}}
    if problems:
        report.update(checks={"SNP": "FAIL"}, problems=problems, committed=False)
        return report
    import psycopg

    with conn.transaction():
        try:
            load = load_snapshot(conn, snap, plan, schema)
        except psycopg.Error as exc:  # e.g. a constraint the source data violates: report, never half-load
            detail = getattr(getattr(exc, "diag", None), "message_detail", None)
            problems.append({"check": "LOD-002", "message": f"load failed: {str(exc).splitlines()[0]}"
                             + (f" ({detail})" if detail else "")})
            report.update(checks={"LOD-002": "FAIL"}, problems=problems, committed=False)
            raise psycopg.Rollback() from exc
        problems += load.pop("problems")
        identity = align_identities(conn, snap, plan, schema) if not problems else []
        rec = reconcile(conn, snap, plan, schema) if not problems else {"tables": {}, "views": {}}
        tbl_diffs = sum(len(x["differences"]) for x in rec["tables"].values())
        view_diffs = sum(len(x["differences"]) for x in rec["views"].values())
        idn_ok = all(i["next"] > i["maxKey"] and i["next"] >= (i["oracleLastNumber"] or 0) for i in identity)
        checks = {
            "SNP-001": "PASS", "SNP-002": "PASS", "SNP-003": "PASS",
            "LOD-001": "FAIL" if any(p["check"] == "LOD-001" for p in problems) else "PASS",
            "LOD-002": "FAIL" if any(p["check"] == "LOD-002" for p in problems) else "PASS",
            "IDN-001": "PASS" if identity and idn_ok else "FAIL",
            "TBL-001": "PASS" if rec["tables"] and tbl_diffs == 0 else "FAIL",
            "VIW-001": "PASS" if rec["views"] and view_diffs == 0 else "FAIL",
        }
        ok = all(v == "PASS" for v in checks.values())
        report.update(checks=checks, problems=problems, load=load, identity=identity, reconciliation=rec, committed=ok)
        if not ok:
            raise psycopg.Rollback()
    return report


def render_markdown(report: dict[str, Any]) -> str:
    s = report["snapshot"]
    lines = [f"# WP9.6 data migration report — {s['name']}", "",
             f"Snapshot SHA-256 `{s['sha256']}`; Oracle session: user `{s['session'].get('db_user')}`, "
             f"APP_USER `{s['session'].get('pkg_app_user')}`, sysdate `{s['session'].get('sysdate')}`, "
             f"DB charset `{s['session'].get('db_charset')}`.", "",
             f"**Committed:** {'yes' if report.get('committed') else 'no (rolled back)'}", "", "| Check | Result |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in report.get("checks", {}).items()]
    if report.get("problems"):
        lines += ["", "## Problems", ""] + [f"- {p['check']}: {p['message']}" for p in report["problems"]]
    if report.get("load"):
        lines += ["", "## Load (foreign-key order)", "", "| Table | Source rows | Loaded |", "|---|---|---|"]
        lines += [f"| {t} | {v['source']} | {v['loaded']} |" for t, v in report["load"]["tables"].items()]
    if report.get("identity"):
        lines += ["", "## Identity alignment", "", "| Column | Max key | Oracle LAST_NUMBER | Next value |", "|---|---|---|---|"]
        lines += [f"| {i['table']}.{i['column']} | {i['maxKey']} | {i['oracleLastNumber']} | {i['next']} |" for i in report["identity"]]
    rec = report.get("reconciliation")
    if rec:
        lines += ["", f"## Reconciliation (views evaluated as `{rec.get('principal')}`)", "", "| Object | Rows | Differences |", "|---|---|---|"]
        for kind in ("tables", "views"):
            lines += [f"| {o} | {v['rows']} | {len(v['differences'])} |" for o, v in rec[kind].items()]
        for kind in ("tables", "views"):
            for o, v in rec[kind].items():
                for pk, d in list(v["differences"].items())[:20]:
                    lines.append(f"- `{o}` `{pk}`: {json.dumps(d, ensure_ascii=False, default=str)}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Load and reconcile an APEX SQL Workshop data snapshot (WP9.6)")
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--schema", default="app")
    parser.add_argument("--output", type=Path, required=True, help="JSON report")
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    import psycopg

    snap = parse_snapshot(args.snapshot.read_text(encoding="utf-8"))
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    with psycopg.connect(args.database_url) as conn:
        report = migrate(conn, snap, plan, args.schema, snapshot_name=args.snapshot.name)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    if args.markdown:
        args.markdown.write_text(render_markdown(report), encoding="utf-8")
    return 0 if report.get("committed") else 1


if __name__ == "__main__":
    raise SystemExit(main())


# ------------------------------------------------------------------------------------------ journey parity
#: Natural keys per table (surrogate IDs differ between source and target after independent inserts).
NATURAL_KEYS: dict[str, list[str]] = {
    "apx_demo_roles": ["role_code"], "apx_demo_user_roles": ["username", "role_code"], "apx_demo_doc_types": ["doc_type"],
    "apx_demo_doc_seq": ["doc_type", "period"], "apx_demo_departments": ["dept_code"], "apx_demo_items": ["item_code"],
    "apx_demo_requests": ["request_no"], "apx_demo_approvals": ["doc_type", "doc_no", "approval_level", "requested_on_seq"],
    "apx_demo_request_lines": ["request_no", "item_code", "line_seq"],
}
#: Columns that legitimately differ between two independent executions (clock, surrogate keys).
VOLATILE = {"created_on", "updated_on", "requested_on", "acted_on", "user_role_id", "department_id", "item_id",
            "request_id", "line_id", "approval_id", "doc_id"}


def _natural_rows(table: str, rows: list[dict[str, Any]], lookups: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    enriched = []
    for r in rows:
        r = dict(r)
        if table == "apx_demo_request_lines":
            r["request_no"] = lookups["request_no"].get(norm(r["request_id"]))
            r["item_code"] = lookups["item_code"].get(norm(r["item_id"]))
        if table == "apx_demo_requests":
            r["department_code"] = lookups["dept_code"].get(norm(r["department_id"]))
        enriched.append(r)
    # deterministic ordinal for rows sharing a key prefix (line order, repeated approval rounds)
    ordinal_key = {"apx_demo_request_lines": ("line_seq", "line_id"), "apx_demo_approvals": ("requested_on_seq", "approval_id")}
    if table in ordinal_key:
        seq_col, by = ordinal_key[table]
        base = [k for k in NATURAL_KEYS[table] if k != seq_col]
        counters: dict[tuple, int] = {}
        for r in sorted(enriched, key=lambda x: int(norm(x[by]))):
            k = tuple(norm(r.get(c)) for c in base)
            counters[k] = counters.get(k, 0) + 1
            r[seq_col] = counters[k]
    for r in enriched:
        key = "|".join(str(norm(r.get(c))) for c in NATURAL_KEYS[table])
        out[key] = {k: v for k, v in r.items() if k not in VOLATILE and k not in ("line_seq", "requested_on_seq")}
    return out


def _lookups(rows: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    return {
        "request_no": {norm(r["request_id"]): r["request_no"] for r in rows.get("apx_demo_requests", [])},
        "item_code": {norm(r["item_id"]): r["item_code"] for r in rows.get("apx_demo_items", [])},
        "dept_code": {norm(r["department_id"]): r["dept_code"] for r in rows.get("apx_demo_departments", [])},
    }


def compare_state(conn, snap: Snapshot, schema: str = "app") -> dict[str, Any]:
    """Compare the target database with a later source snapshot after the same journey ran on both sides.

    Rows are matched by natural keys; surrogate keys and clock columns are excluded (VOLATILE), the rest must be
    equal. Returns per-table differences; an empty report means state parity.
    """
    src_rows = {t.lower(): list(rows.values()) for t, rows in snap.rows.items()}
    tgt_rows = {t: _fetch(conn, f"SELECT * FROM {schema}.{_ident(t)}") for t in NATURAL_KEYS}
    src_l, tgt_l = _lookups(src_rows), _lookups(tgt_rows)
    result: dict[str, Any] = {}
    for t in NATURAL_KEYS:
        s = _natural_rows(t, src_rows.get(t, []), src_l)
        g = _natural_rows(t, tgt_rows[t], tgt_l)
        diffs = {}
        for k in sorted(set(s) | set(g)):
            if k not in g:
                diffs[k] = [{"issue": "only in source"}]
            elif k not in s:
                diffs[k] = [{"issue": "only in target"}]
            else:
                d = compare_row(s[k], g[k])
                if d:
                    diffs[k] = d
        result[t] = {"source": len(s), "target": len(g), "differences": diffs}
    return result
