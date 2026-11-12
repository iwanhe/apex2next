"""R4a step 3: Oracle BEFORE ROW triggers converted to PL/pgSQL (schema-plan --convert-triggers)."""
import os

import pytest

from apex2next_schema_analyzer.schema_plan import build_schema_plan

DDL = """
create table demo_status (
  id number primary key,
  cd varchar2(10) not null,
  row_version number,
  created date, created_by varchar2(255), updated date, updated_by varchar2(255),
  start_date date, end_date date
);
create sequence demo_seq;

create or replace trigger biu_demo_status
  before insert or update on demo_status
  for each row
begin
  if :new.id is null then
    select demo_seq.nextval into :new.id from sys.dual;
  end if;
  if inserting then
    :new.created := sysdate;
    :new.created_by := nvl(sys_context('APEX$SESSION','APP_USER'), user);
    :new.row_version := 1;
  elsif updating then
    :new.row_version := nvl(:old.row_version, 0) + 1;
  end if;
  :new.updated := localtimestamp;
  :new.updated_by := nvl(wwv_flow.g_user, user);
  :new.cd := upper(:new.cd);
  if :new.start_date > :new.end_date then
    raise_application_error(-20001, 'Start date must be before end date');
  end if;
end;
/
"""

UNSUPPORTED = """
create table t2 (id number primary key, n number, v varchar2(30));
create or replace trigger t2_pkg before insert on t2 for each row
begin
  :new.n := my_pkg.next_number(:new.id);
end;
/
create or replace trigger t2_decl before insert on t2 for each row
declare
  l number;
begin
  :new.n := 1;
end;
/
create or replace trigger t2_after after insert on t2 for each row
begin
  null;
end;
/
create or replace trigger t2_state before insert on t2 for each row
begin
  :new.v := my_pkg.g_mode;
end;
/
"""


def _trigger(plan, name):
    return next(t for t in plan["triggers"] if t["name"] == name)


def test_conversion_is_off_by_default():
    plan = build_schema_plan(DDL, source_name="t.sql")
    trg = _trigger(plan, "BIU_DEMO_STATUS")
    assert not trg.get("emit") and "TRG001" in {f["code"] for f in trg["findings"]}
    assert "CREATE TRIGGER" not in plan["sql"]
    assert "triggers" not in plan["summary"]


def test_audit_key_version_normalization_and_guard_are_converted():
    plan = build_schema_plan(DDL, source_name="t.sql", convert_triggers=True)
    trg = _trigger(plan, "BIU_DEMO_STATUS")
    assert trg["emit"] is True
    codes = {f["code"] for f in trg["findings"]}
    assert {"TRC001", "TRC002", "TRC003", "TRC005", "EXP001", "EXP002"} <= codes
    assert "TRG001" not in codes and "TRC006" not in codes
    sql = trg["targetSql"]
    assert "NEW.id := nextval('app.demo_seq');" in sql
    assert "IF (TG_OP = 'INSERT') THEN" in sql and "ELSIF (TG_OP = 'UPDATE') THEN" in sql
    assert "NEW.created_by := COALESCE(apex_app_user(), upper(current_user));" in sql
    assert "NEW.row_version := COALESCE(OLD.row_version, 0) + 1;" in sql
    assert "NEW.cd := upper(NEW.cd);" in sql
    assert "RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'Start date must be before end date', DETAIL = 'ORA-20001';" in sql
    assert "current_setting('apex2next.loading', true) = 'on'" in sql
    assert "SET search_path = app, pg_temp" in sql
    assert "CREATE TRIGGER biu_demo_status BEFORE INSERT OR UPDATE ON app.demo_status" in sql
    assert "FUNCTION apex_app_user()" in plan["sql"] and sql in plan["sql"]
    assert plan["summary"]["triggers"] == {"source": 1, "emitted": 1}
    obj = next(o for o in plan["objects"] if o["type"] == "TRIGGER")
    assert obj["emitted"] and obj["disposition"] == "ASSISTED"


def test_triggers_outside_the_subset_stay_manual():
    plan = build_schema_plan(UNSUPPORTED, source_name="t.sql", convert_triggers=True)
    reasons = {t["name"]: next(f["detail"] for f in t["findings"] if f["code"] == "TRC006") for t in plan["triggers"]}
    assert all(not t.get("emit") for t in plan["triggers"])
    assert reasons["T2_PKG"].startswith("EXP009")
    assert reasons["T2_DECL"] == "DECLARE section or CALL body"
    assert reasons["T2_AFTER"] == "AFTER ROW trigger"
    assert "package variable" in reasons["T2_STATE"]
    assert "CREATE TRIGGER" not in plan["sql"]
    assert all(o["disposition"] == "MANUAL" for o in plan["objects"] if o["type"] == "TRIGGER")


def test_only_tables_with_unconverted_triggers_block_native_dml():
    """app_generator blocks native form DML on tables with a trigger whose plan entry is not emitted."""
    plan = build_schema_plan(DDL + UNSUPPORTED, source_name="t.sql", convert_triggers=True)
    blocked = {t["table"].upper() for t in plan["triggers"] if not t.get("emit")}
    assert blocked == {"T2"}


DSN = os.environ.get("APEX2NEXT_TEST_DATABASE_URL")


@pytest.mark.postgres
@pytest.mark.skipif(not DSN, reason="APEX2NEXT_TEST_DATABASE_URL not set")
def test_converted_trigger_runs_on_postgresql():
    psycopg = pytest.importorskip("psycopg")
    plan = build_schema_plan(DDL, source_name="t.sql", convert_triggers=True)
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("DROP SCHEMA IF EXISTS app CASCADE")
        try:
            c.execute(plan["sql"])
            with c.transaction():
                c.execute("select set_config('app.username', 'ALICE', true)")
                row = c.execute("insert into app.demo_status (cd) values ('open') "
                                "returning id, cd, row_version, created_by, updated_by, created").fetchone()
            assert row[0] == 1 and row[1] == "OPEN" and row[2] == 1 and row[3] == "ALICE" == row[4] and row[5]
            with c.transaction():
                c.execute("select set_config('app.username', 'BOB', true)")
                row = c.execute("update app.demo_status set cd = 'closed' returning cd, row_version, created_by, updated_by").fetchone()
            assert row == ("CLOSED", 2, "ALICE", "BOB")
            # without a request principal the Oracle USER fallback applies
            assert c.execute("insert into app.demo_status (cd) values ('x') returning created_by").fetchone()[0] == \
                c.execute("select upper(current_user)").fetchone()[0]
            # guard: RAISE_APPLICATION_ERROR keeps its number in DETAIL
            with pytest.raises(psycopg.errors.RaiseException) as err:
                c.execute("insert into app.demo_status (cd, start_date, end_date) values ('x', date '2026-02-01', date '2026-01-01')")
            assert err.value.diag.message_primary == "Start date must be before end date"
            assert err.value.diag.message_detail == "ORA-20001"
            # data migration: the loading flag keeps source values
            with c.transaction():
                c.execute("select set_config('apex2next.loading', 'on', true)")
                row = c.execute("insert into app.demo_status (id, cd, created_by, row_version) values (99, 'low', 'SRC', 7) "
                                "returning id, cd, created_by, row_version").fetchone()
            assert row == (99, "low", "SRC", 7)
        finally:
            c.execute("DROP SCHEMA IF EXISTS app CASCADE")
