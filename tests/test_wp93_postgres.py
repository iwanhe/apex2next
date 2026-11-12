"""WP9.3 PostgreSQL 16 integration tests for generated schema migrations.

Requires a DISPOSABLE database: set APEX2NEXT_TEST_DATABASE_URL. Each test drops and
recreates schema ``app``. Skipped when the variable or psycopg is unavailable.
"""
import json
import os
from decimal import Decimal
from pathlib import Path

import pytest

from apex2next_schema_analyzer.schema_plan import build_schema_plan

psycopg = pytest.importorskip("psycopg")
DSN = os.environ.get("APEX2NEXT_TEST_DATABASE_URL")
pytestmark = [pytest.mark.postgres,
              pytest.mark.skipif(not DSN, reason="APEX2NEXT_TEST_DATABASE_URL not set")]

ROOT = Path(__file__).resolve().parents[1]
F170134 = ROOT / "docs" / "migration" / "wp9.3" / "f170134"
SYNTHETIC = Path(__file__).parent / "fixtures" / "wp9.3" / "synthetic-dbms-metadata.sql"


@pytest.fixture()
def conn():
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("DROP SCHEMA IF EXISTS app CASCADE")
        yield c
        c.execute("DROP SCHEMA IF EXISTS app CASCADE")


def snapshot(c, schema="app"):
    q = lambda sql: c.execute(sql, (schema,)).fetchall()  # noqa: E731
    tables: dict = {}
    for rel, name, typ, nullable, ident, gen in q(
            "select c.relname, a.attname, format_type(a.atttypid, a.atttypmod), not a.attnotnull,"
            " a.attidentity, a.attgenerated from pg_attribute a join pg_class c on c.oid = a.attrelid"
            " join pg_namespace n on n.oid = c.relnamespace where n.nspname = %s and c.relkind = 'r'"
            " and a.attnum > 0 and not a.attisdropped order by c.relname, a.attnum"):
        tables.setdefault(rel, {"columns": [], "constraints": []})["columns"].append(
            {"name": name, "type": typ, "nullable": nullable, "identity": ident, "generated": gen})
    for rel, name, typ in q(
            "select c.relname, k.conname, k.contype::text from pg_constraint k join pg_class c on c.oid = k.conrelid"
            " join pg_namespace n on n.oid = c.relnamespace where n.nspname = %s and k.contype in ('p','u','c','f')"
            " order by c.relname, k.conname"):
        tables[rel]["constraints"].append({"name": name, "type": typ})
    indexes = {name: {"table": rel, "unique": uniq} for name, rel, uniq in q(
        "select ic.relname, tc.relname, i.indisunique from pg_index i join pg_class ic on ic.oid = i.indexrelid"
        " join pg_class tc on tc.oid = i.indrelid join pg_namespace n on n.oid = ic.relnamespace"
        " where n.nspname = %s and not exists (select 1 from pg_constraint k where k.conindid = i.indexrelid)")}
    views: dict = {}
    for rel, name in q(
            "select c.relname, a.attname from pg_attribute a join pg_class c on c.oid = a.attrelid"
            " join pg_namespace n on n.oid = c.relnamespace where n.nspname = %s and c.relkind = 'v'"
            " and a.attnum > 0 order by c.relname, a.attnum"):
        views.setdefault(rel, []).append(name)
    sequences = sorted(r[0] for r in q(
        "select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = %s"
        " and c.relkind = 'S' and not exists (select 1 from pg_depend d where d.objid = c.oid and d.deptype = 'i')"))
    return {"tables": tables, "indexes": indexes, "views": views, "sequences": sequences}


def test_f170134_migration_applies_and_catalog_matches_plan(conn):
    plan = json.loads((F170134 / "schema-plan.json").read_text())
    conn.execute((F170134 / "0001_wp93_schema.sql").read_text())
    assert snapshot(conn) == plan["expectedCatalog"]


def test_f170134_reapply_is_rejected_atomically_and_fresh_apply_is_identical(conn):
    sql = (F170134 / "0001_wp93_schema.sql").read_text()
    conn.execute(sql)
    before = snapshot(conn)
    with pytest.raises(psycopg.errors.DuplicateTable):
        conn.execute(sql)
    conn.execute("ROLLBACK")
    assert snapshot(conn) == before
    conn.execute("DROP SCHEMA app CASCADE")
    conn.execute(sql)
    assert snapshot(conn) == before


def _expect(c, error, sql, params=None):
    with pytest.raises(error):
        with c.transaction():
            c.execute(sql, params)


def test_f170134_constraint_identity_generated_and_view_behaviour(conn):
    conn.execute((F170134 / "0001_wp93_schema.sql").read_text())
    c = conn
    c.execute("set search_path to app")
    c.execute("insert into apx_demo_roles (role_code, role_name) values ('MANAGER', 'Manager')")
    dept = c.execute("insert into apx_demo_departments (dept_code, dept_name) values ('OPS', 'Operations')"
                     " returning department_id, active_yn").fetchone()
    assert dept == (1, "Y")
    item = c.execute("insert into apx_demo_items (item_code, item_name, category, uom, std_price)"
                     " values ('IT-001', 'Laptop', 'IT', 'UNIT', 12500000) returning item_id").fetchone()[0]
    req, req_date, status = c.execute(
        "insert into apx_demo_requests (department_id, purpose) values (%s, 'Laptop')"
        " returning request_id, request_date, status", (dept[0],)).fetchone()
    assert status == "DRAFT"
    assert req_date == c.execute("select CAST(CURRENT_DATE AS timestamp(0))").fetchone()[0]
    amount = c.execute("insert into apx_demo_request_lines (request_id, item_id, qty, unit_price)"
                       " values (%s, %s, 2, 12500000) returning line_amount", (req, item)).fetchone()[0]
    assert amount == Decimal("25000000")

    # Documented semantic differences and enforced constraints
    _expect(c, psycopg.errors.NotNullViolation,
            "insert into apx_demo_departments (department_id, dept_code, dept_name) values (null, 'FIN', 'Finance')")
    _expect(c, psycopg.errors.GeneratedAlways,
            "insert into apx_demo_request_lines (request_id, item_id, qty, unit_price, line_amount) values (%s, %s, 1, 1, 9)",
            (req, item))
    for sql in (
        "update apx_demo_requests set status = 'BOGUS'",
        "update apx_demo_items set category = 'FOOD'",
        "update apx_demo_items set std_price = -1",
        "update apx_demo_items set active_yn = 'X'",
        "update apx_demo_departments set active_yn = 'X'",
        "update apx_demo_request_lines set qty = -1",
        "update apx_demo_request_lines set unit_price = -1",
    ):
        _expect(c, psycopg.errors.CheckViolation, sql)
    _expect(c, psycopg.errors.UniqueViolation,
            "insert into apx_demo_departments (dept_code, dept_name) values ('OPS', 'Dup')")
    _expect(c, psycopg.errors.ForeignKeyViolation,
            "insert into apx_demo_request_lines (request_id, item_id, qty) values (999, %s, 1)", (item,))
    _expect(c, psycopg.errors.ForeignKeyViolation,
            "insert into apx_demo_user_roles (username, role_code) values ('X', 'NOPE')")

    # Converted views compute the same aggregates as the Oracle definitions
    summary = c.execute("select line_count, total_amount, dept_name from apx_demo_request_summary_v").fetchone()
    assert summary == (1, Decimal("25000000"), "Operations")
    empty = c.execute("insert into apx_demo_requests (department_id, purpose) values (%s, 'empty')"
                      " returning request_id", (dept[0],)).fetchone()[0]
    assert c.execute("select total_amount from apx_demo_request_summary_v where request_id = %s",
                     (empty,)).fetchone()[0] == 0  # NVL(SUM(...),0) -> COALESCE
    assert c.execute("select label, value from apx_demo_dash_c2_s1_v").fetchall() == [("Operations", Decimal("25000000"))]
    assert c.execute("select label, value from apx_demo_dash_c1_s1_v").fetchall() == [("DRAFT", 2)]
    assert c.execute("select department_id_dsp from apx_demo_requests_v where request_id = %s",
                     (req,)).fetchone()[0] == "OPS - Operations"

    # ON DELETE CASCADE
    c.execute("delete from apx_demo_requests where request_id = %s", (req,))
    assert c.execute("select count(*) from apx_demo_request_lines").fetchone()[0] == 0


def test_f170134_post_load_alignment_continues_after_explicit_ids(conn):
    conn.execute((F170134 / "0001_wp93_schema.sql").read_text())
    conn.execute("insert into app.apx_demo_departments (department_id, dept_code, dept_name) values (500, 'A', 'A')")
    conn.execute((F170134 / "post-load-identity-alignment.sql").read_text())
    nxt = conn.execute("insert into app.apx_demo_departments (dept_code, dept_name) values ('B', 'B')"
                       " returning department_id").fetchone()[0]
    assert nxt == 501


def test_synthetic_dbms_metadata_migration_applies_and_matches_plan(conn):
    plan = build_schema_plan(SYNTHETIC.read_text(), source_name=SYNTHETIC.name)
    conn.execute(plan["sql"])
    assert snapshot(conn) == plan["expectedCatalog"]
    c = conn
    assert c.execute("select convalidated from pg_constraint where conname = 'syn_customers_ck2'").fetchone()[0] is False
    assert c.execute("select condeferrable, condeferred from pg_constraint where conname = 'syn_orders_pk'").fetchone() == (True, True)
    assert c.execute("select nextval('app.syn_batch_seq')").fetchone()[0] == 21
    assert c.execute("select obj_description('app.syn_customers'::regclass)").fetchone()[0] == "Customer master (synthetic)"
    cid = c.execute("insert into app.syn_customers (customer_code) values ('C1') returning customer_id").fetchone()[0]
    assert cid == 100
    _expect(c, psycopg.errors.GeneratedAlways,
            "insert into app.syn_customers (customer_id, customer_code) values (1, 'C2')")
    total = c.execute("insert into app.syn_orders (customer_id, qty, price) values (%s, 3, 2.555) returning total",
                      (cid,)).fetchone()[0]
    assert total == Decimal("7.68")
    assert c.execute("select order_count, total_value from app.syn_order_totals_v").fetchone() == (1, Decimal("7.68"))


def test_r4a_guid_key_default_generates_distinct_numeric_keys(conn):
    """APEX key default TO_NUMBER(SYS_GUID(), 'X...X') (EXP022) becomes guid_number(), created with the schema."""
    ddl = ("create table t (id number default on null to_number(sys_guid(),'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX') "
           "primary key, name varchar2(10));\n")
    plan = build_schema_plan(ddl, source_name="t.sql")
    col = plan["tables"][0]["columns"][0]
    assert col["default"]["target"] == "guid_number()"
    assert "EXP022" in {f["code"] for f in col["findings"]}
    conn.execute(plan["sql"])
    ids = [conn.execute("insert into app.t (name) values ('x') returning id").fetchone()[0] for _ in range(20)]
    assert len(set(ids)) == 20 and all(0 <= i < 2 ** 128 and i == int(i) for i in ids)
    # scale 0: the key prints as an integer (no ".0000000000000000"), as the Oracle NUMBER key does
    assert all(i.as_tuple().exponent == 0 for i in ids)
