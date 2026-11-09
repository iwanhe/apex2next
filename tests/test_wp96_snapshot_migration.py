"""WP9.6 snapshot migration: parsing/verification (offline) and load + reconciliation on PostgreSQL 16.

The PostgreSQL tests need a DISPOSABLE database (APEX2NEXT_TEST_DATABASE_URL); they drop schema "app".
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from decimal import Decimal
from pathlib import Path

import pytest

from apex2next_schema_analyzer.snapshot_migration import (
    VIEW_KEYS, compare_row, migrate, norm, parse_snapshot, render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "examples" / "f170134-target"
PLAN = json.loads((TARGET / "db" / "schema-plan.json").read_text(encoding="utf-8"))
DSN = os.environ.get("APEX2NEXT_TEST_DATABASE_URL")

# Rows as Oracle JSON_OBJECT(*) renders them: upper-case keys, DATE as ISO without zone, numbers as JSON numbers.
AUDIT = {"CREATED_BY": "IWAN", "CREATED_ON": "2026-11-04T09:00:00", "UPDATED_BY": "IWAN", "UPDATED_ON": "2026-11-04T09:30:00"}
TABLES: dict[str, dict[str, dict]] = {
    "APX_DEMO_ROLES": {r: {"ROLE_CODE": r, "ROLE_NAME": n, "DESCRIPTION": None} for r, n in
                       [("ADMIN", "Administrator"), ("DIRECTOR", "Director"), ("MANAGER", "Department Manager"),
                        ("REQUESTER", "Requester")]},
    "APX_DEMO_USER_ROLES": {
        "3": {"USER_ROLE_ID": 3, "USERNAME": "IWAN", "ROLE_CODE": "ADMIN", **AUDIT},
        "7": {"USER_ROLE_ID": 7, "USERNAME": "IWAN", "ROLE_CODE": "REQUESTER", **AUDIT},
    },
    "APX_DEMO_DOC_TYPES": {"REQ": {
        "DOC_TYPE": "REQ", "DOC_NAME": "Permintaan Barang", "PREFIX": "REQ", "TABLE_NAME": "APX_DEMO_REQUESTS",
        "PK_COLUMN": "REQUEST_ID", "NUMBER_COLUMN": "REQUEST_NO", "STATUS_COLUMN": "STATUS",
        "AMOUNT_EXPR": "(select nvl(sum(l.line_amount), 0) from apx_demo_request_lines l where l.request_id = t.request_id)",
        "VALIDATE_PROC": "apx_demo_request_pkg.check_submit", "APPROVER1_ROLE": "MANAGER", "APPROVER2_ROLE": "DIRECTOR",
        "LEVEL2_LIMIT": 10000000}},
    "APX_DEMO_DOC_SEQ": {"REQ|2026": {"DOC_TYPE": "REQ", "PERIOD": "2026", "LAST_NO": 2}},
    "APX_DEMO_DEPARTMENTS": {"1": {"DEPARTMENT_ID": 1, "DEPT_CODE": "OPS", "DEPT_NAME": "Operations", "ACTIVE_YN": "Y", **AUDIT}},
    "APX_DEMO_ITEMS": {"21": {"ITEM_ID": 21, "ITEM_CODE": "ATK-001", "ITEM_NAME": "Kertas A4", "CATEGORY": "ATK", "UOM": "RIM",
                              "STD_PRICE": 55000.5, "ACTIVE_YN": "Y", **AUDIT}},
    "APX_DEMO_REQUESTS": {
        "41": {"REQUEST_ID": 41, "REQUEST_NO": "REQ-2026-0001", "DEPARTMENT_ID": 1, "REQUEST_DATE": "2026-11-04T00:00:00",
               "NEED_DATE": None, "PURPOSE": "ATK", "NOTES": None, "STATUS": "SUBMITTED", **AUDIT},
        "42": {"REQUEST_ID": 42, "REQUEST_NO": "REQ-2026-0002", "DEPARTMENT_ID": 1, "REQUEST_DATE": "2026-11-05T00:00:00",
               "NEED_DATE": "2026-11-20T00:00:00", "PURPOSE": "Kertas", "NOTES": "x", "STATUS": "DRAFT", **AUDIT},
    },
    "APX_DEMO_REQUEST_LINES": {
        "61": {"LINE_ID": 61, "REQUEST_ID": 41, "ITEM_ID": 21, "QTY": 3, "UNIT_PRICE": 55000.5, "LINE_AMOUNT": 165001.5, **AUDIT},
        "62": {"LINE_ID": 62, "REQUEST_ID": 42, "ITEM_ID": 21, "QTY": 0.25, "UNIT_PRICE": 4, "LINE_AMOUNT": 1, **AUDIT},
    },
    "APX_DEMO_APPROVALS": {"81": {
        "APPROVAL_ID": 81, "DOC_TYPE": "REQ", "DOC_ID": 41, "DOC_NO": "REQ-2026-0001", "APPROVAL_LEVEL": 1,
        "APPROVER_ROLE": "MANAGER", "AMOUNT": 165001.5, "REQUESTED_BY": "IWAN", "REQUESTED_ON": "2026-11-04T10:00:00",
        "STATUS": "PENDING", "ACTED_BY": None, "ACTED_ON": None, "NOTE": None}},
}
SESSION = {"db_user": "APEX_PUBLIC_USER", "apex_app_user": "IWAN", "pkg_app_user": "IWAN", "sysdate": "2026-11-09T06:00:00",
           "db_charset": "AL32UTF8"}
IDENTITY = {("APX_DEMO_REQUESTS", "REQUEST_ID"): 61, ("APX_DEMO_USER_ROLES", "USER_ROLE_ID"): 1}


def _line(section, obj, pk, doc):
    return [section, obj, pk, doc, hashlib.sha256(doc.encode("utf-8")).hexdigest().upper()]


def build_csv(tables=TABLES, views=None, *, mutate=None) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["SECTION", "OBJ", "PK", "DOC", "SHA256"])
    w.writerow(_line("SNAPSHOT", "SESSION", "-", json.dumps(SESSION)))
    for (t, c), last in IDENTITY.items():
        w.writerow(_line("IDENTITY", t, c, json.dumps({"sequence": f"ISEQ$$_{t}", "last_number": last, "increment_by": 1,
                                                        "cache_size": 20, "generation_type": "BY DEFAULT"})))
    for t, rows in tables.items():
        w.writerow(_line("COUNT", t, "-", str(len(rows))))
        for pk, row in rows.items():
            w.writerow(_line("ROW", t, pk, json.dumps(row, separators=(",", ":"))))
    for v, rows in (views or {}).items():
        w.writerow(_line("COUNT", v, "-", str(len(rows))))
        for pk, row in rows.items():
            w.writerow(_line("VIEW", v, pk, json.dumps(row, separators=(",", ":"))))
    text = out.getvalue()
    return mutate(text) if mutate else text


# ----------------------------------------------------------------------------------------------- offline
def test_parse_verifies_hashes_counts_and_decimals():
    snap = parse_snapshot("﻿" + build_csv(views={v: {} for v in VIEW_KEYS}))
    assert snap.problems == []
    assert snap.session["pkg_app_user"] == "IWAN"
    assert snap.rows["APX_DEMO_ITEMS"]["21"]["std_price"] == Decimal("55000.5"), "exact decimals, keys lower-cased"
    assert snap.identities["APX_DEMO_REQUESTS.REQUEST_ID"]["last_number"] == 61

    tampered = parse_snapshot(build_csv(mutate=lambda t: t.replace("Operations", "Operation$", 1)))
    assert [p["check"] for p in tampered.problems] == ["SNP-001", "SNP-002"], "damaged DOC is rejected and the count no longer matches"

    short = parse_snapshot(build_csv(mutate=lambda t: "\n".join(
        x for x in t.splitlines() if not x.startswith("ROW,APX_DEMO_REQUEST_LINES,62,"))))
    assert any(p["check"] == "SNP-002" and p["obj"] == "APX_DEMO_REQUEST_LINES" for p in short.problems)

    assert parse_snapshot("A,B\n1,2\n").problems[0]["check"] == "SNP-003"


def test_normalization_is_exact():
    from datetime import datetime
    assert norm(Decimal("55000.50")) == norm(55000.5) == "55000.5"
    assert norm(Decimal("0E-10")) == "0"
    assert norm(datetime(2026, 11, 4, 10, 15, 30)) == "2026-11-04T10:15:30"
    assert compare_row({"a": "2026-11-04T10:15:30.000000"}, {"a": datetime(2026, 11, 4, 10, 15, 30)}) == []
    assert compare_row({"a": "2026-11-04T10:15:30.500000"}, {"a": datetime(2026, 11, 4, 10, 15, 31)}) != [], \
        "a fraction rounded away by timestamp(0) is reported"
    assert compare_row({"a": Decimal("1.10")}, {"a": Decimal("1.1")}) == []
    assert compare_row({"a": 1}, {"b": 1}) == [{"column": "a", "issue": "missing in target"}, {"column": "b", "issue": "missing in source"}]


# ----------------------------------------------------------------------------------------------- PostgreSQL
pg = pytest.mark.skipif(not DSN, reason="APEX2NEXT_TEST_DATABASE_URL not set")


@pytest.fixture()
def conn():
    psycopg = pytest.importorskip("psycopg")
    with psycopg.connect(DSN, autocommit=True) as c:
        _fresh(c)
        yield c
        c.execute("DROP SCHEMA IF EXISTS app CASCADE")


def _fresh(c):
    c.execute("DROP SCHEMA IF EXISTS app CASCADE")
    for f in sorted((TARGET / "db" / "migrations").glob("*.sql")):
        c.execute(f.read_text(encoding="utf-8"))


def _oracle_like_views(c) -> dict:
    """Render the target views like Oracle JSON_OBJECT(*) (upper-case keys), as the source would export them."""
    views = {}
    c.execute("SELECT set_config('app.username', 'IWAN', false)")
    for v, key in VIEW_KEYS.items():
        rows = c.execute(f"SELECT to_jsonb(x) FROM app.{v.lower()} x").fetchall()
        views[v] = {}
        for (doc,) in rows:
            k = doc[key]
            views[v][str(k)] = {name.upper(): value for name, value in doc.items()}
    c.execute("SELECT set_config('app.username', '', false)")
    return views


@pg
@pytest.mark.postgres
def test_migrate_loads_aligns_and_reconciles(conn):
    from apex2next_schema_analyzer.snapshot_migration import load_snapshot
    # Derive the expected view rows from a first load (machinery test; real view parity comes from Oracle).
    with conn.transaction():
        load_snapshot(conn, parse_snapshot(build_csv(views={v: {} for v in VIEW_KEYS})), PLAN)
    views = _oracle_like_views(conn)
    assert views["APX_DEMO_DASH_KPI_V"]["2"]["METRIC_VALUE"] == 1, "one DRAFT request"
    _fresh(conn)

    report = migrate(conn, parse_snapshot(build_csv(views=views)), PLAN, snapshot_name="synthetic.csv")
    assert report["checks"] == {k: "PASS" for k in report["checks"]}, json.dumps(report, default=str)[:2000]
    assert report["committed"] is True
    assert report["load"]["order"].index("apx_demo_requests") < report["load"]["order"].index("apx_demo_request_lines")
    assert conn.execute("SELECT line_amount FROM app.apx_demo_request_lines WHERE line_id = 62").fetchone()[0] == Decimal("1.00")
    ident = {(i["table"], i["column"]): i for i in report["identity"]}
    assert ident[("apx_demo_requests", "request_id")]["next"] == 61, "Oracle high-water mark wins over max(key)+1"
    assert ident[("apx_demo_user_roles", "user_role_id")]["next"] == 8, "max(key)+1 wins over a lower LAST_NUMBER"
    assert conn.execute("SELECT nextval(pg_get_serial_sequence('app.apx_demo_requests','request_id'))").fetchone()[0] == 61
    assert "| TBL-001 | PASS |" in render_markdown(report)

    # A second run must refuse a non-empty target.
    again = migrate(conn, parse_snapshot(build_csv(views=views)), PLAN)
    assert again["checks"]["LOD-001"] == "FAIL" and again["committed"] is False


@pg
@pytest.mark.postgres
def test_migrate_reports_differences_and_rolls_back(conn):
    from apex2next_schema_analyzer.snapshot_migration import load_snapshot
    with conn.transaction():
        load_snapshot(conn, parse_snapshot(build_csv(views={v: {} for v in VIEW_KEYS})), PLAN)
    views = _oracle_like_views(conn)
    _fresh(conn)
    tables = json.loads(json.dumps(TABLES))
    tables["APX_DEMO_REQUEST_LINES"]["61"]["LINE_AMOUNT"] = 165000  # source virtual column disagrees with qty*price
    tables["APX_DEMO_REQUESTS"]["41"]["UPDATED_ON"] = "2026-11-04T09:30:00.600000"  # fraction lost in timestamp(0)
    views["APX_DEMO_APPROVALS_V"]["81"]["CAN_ACT_YN"] = "Y"  # source says the principal may act
    report = migrate(conn, parse_snapshot(build_csv(tables, views)), PLAN)
    assert report["committed"] is False
    assert report["checks"]["TBL-001"] == "FAIL" and report["checks"]["VIW-001"] == "FAIL"
    rec = report["reconciliation"]
    assert rec["tables"]["apx_demo_request_lines"]["differences"]["61"] == [
        {"column": "line_amount", "source": "165000", "target": "165001.5"}]
    assert rec["tables"]["apx_demo_requests"]["differences"]["41"][0]["column"] == "updated_on"
    assert rec["views"]["apx_demo_approvals_v"]["differences"]["81"] == [{"column": "can_act_yn", "source": "Y", "target": "N"}]
    assert conn.execute("SELECT count(*) FROM app.apx_demo_requests").fetchone()[0] == 0, "rolled back"


@pg
@pytest.mark.postgres
def test_migrate_reports_a_constraint_violation_without_partial_load(conn):
    tables = json.loads(json.dumps(TABLES))
    tables["APX_DEMO_ITEMS"]["21"]["CATEGORY"] = "FOOD"  # violates APX_DEMO_ITEMS_CK1
    report = migrate(conn, parse_snapshot(build_csv(tables, {v: {} for v in VIEW_KEYS})), PLAN)
    assert report["committed"] is False and report["checks"] == {"LOD-002": "FAIL"}
    assert "apx_demo_items_ck1" in report["problems"][-1]["message"]
    assert conn.execute("SELECT count(*) FROM app.apx_demo_roles").fetchone()[0] == 0


@pg
@pytest.mark.postgres
def test_compare_state_matches_by_natural_keys(conn):
    from apex2next_schema_analyzer.snapshot_migration import compare_state, compare_views_after, load_snapshot
    with conn.transaction():
        load_snapshot(conn, parse_snapshot(build_csv(views={v: {} for v in VIEW_KEYS})), PLAN)
    views = _oracle_like_views(conn)
    # The "later" source snapshot has other surrogate keys and clock values for the same business rows.
    tables = json.loads(json.dumps(TABLES))
    tables["APX_DEMO_APPROVALS"] = {"5": {**tables["APX_DEMO_APPROVALS"]["81"], "APPROVAL_ID": 5, "REQUESTED_ON": "2026-11-09T08:00:00"}}
    views["APX_DEMO_APPROVALS_V"] = {"5": {**views["APX_DEMO_APPROVALS_V"]["81"], "APPROVAL_ID": 5}}
    later = parse_snapshot(build_csv(tables, views))
    state = compare_state(conn, later)
    assert all(not t["differences"] for t in state.values()), state
    assert all(not v["differences"] for v in compare_views_after(conn, later)["views"].values())
    conn.execute("UPDATE app.apx_demo_requests SET status = 'APPROVED' WHERE request_no = 'REQ-2026-0002'")
    state = compare_state(conn, later)
    assert state["apx_demo_requests"]["differences"] == {
        "REQ-2026-0002": [{"column": "status", "source": "DRAFT", "target": "APPROVED"}]}
