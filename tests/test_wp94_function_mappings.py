import json
import os
from pathlib import Path

import pytest

from apex2next_schema_analyzer.schema_plan import build_schema_plan, references_from_export_dir
from apex2next_schema_analyzer.source_overrides import load_overrides

SOURCE = """create table t (id number(9) primary key, v varchar2(10));
create or replace package pkg as function f(p number) return varchar2; end pkg;
/
create or replace force view v1 as select id, pkg.f(id) flag from t;
create or replace force view v2 as select id, flag from v1;
create or replace force view v3 as select id from t;
"""
MAPPINGS = {"format": "apex2next.function-mappings.v1",
            "mappings": [{"source": "pkg.f", "target": "app.f", "providedBy": "0002_x.sql"}]}


def _views(plan):
    return {v["name"]: v for v in plan["views"]}


def test_mapped_call_is_rewritten_and_dependent_views_are_deferred():
    plan = build_schema_plan(SOURCE, function_mappings=MAPPINGS, transaction_wrapper=False)
    v = _views(plan)
    assert v["V1"]["emit"] and v["V1"]["phase"] == "deferred" and v["V1"]["mappedCalls"] == ["PKG.F"]
    assert v["V2"]["phase"] == "deferred", "a view over a deferred view is deferred too"
    assert v["V3"]["phase"] == "schema"
    assert "app.f(id) flag" in plan["deferredSql"]
    assert "CREATE VIEW app.v1" not in plan["sql"] and "CREATE VIEW app.v3" in plan["sql"]
    assert plan["deferredSql"].index("app.v1") < plan["deferredSql"].index("app.v2")
    assert set(plan["expectedCatalog"]["deferredViews"]) == {"v1", "v2"}
    assert "EXP021" in next(o for o in plan["objects"] if o["name"] == "V1")["findingCodes"]
    assert plan["summary"]["validationPassed"]


def test_without_mapping_the_views_stay_held():
    plan = build_schema_plan(SOURCE)
    v = _views(plan)
    assert not v["V1"]["emit"] and not v["V2"]["emit"] and plan["deferredSql"] == ""


def test_runner_format_has_no_transaction_control():
    wrapped = build_schema_plan(SOURCE)["sql"]
    runner = build_schema_plan(SOURCE, transaction_wrapper=False)["sql"]
    assert "BEGIN;" in wrapped and "COMMIT;" in wrapped
    assert "BEGIN;" not in runner and "COMMIT;" not in runner and "SET LOCAL search_path TO app;" in runner


@pytest.mark.parametrize("mapping", [
    {"source": "f", "target": "app.f"},
    {"source": "pkg.f", "target": "App.F"},
    {"source": "pkg.f", "target": "app.f; drop table x"},
])
def test_invalid_mappings_are_rejected(mapping):
    with pytest.raises(ValueError):
        build_schema_plan(SOURCE, function_mappings={"format": "apex2next.function-mappings.v1", "mappings": [mapping]})
    with pytest.raises(ValueError):
        build_schema_plan(SOURCE, function_mappings={"format": "other", "mappings": []})


# ----------------------------------------------------------------- committed WP9.4 pilot plan

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "examples" / "f170134-target" / "db"


def test_pilot_plan_emits_all_views_and_pins_migrations():
    plan = json.loads((T / "schema-plan.json").read_text(encoding="utf-8"))
    assert plan["summary"]["views"] == {"source": 10, "emitted": 10}
    assert all(c["status"] == "PASS" for c in plan["checks"])
    assert plan["transactionWrapper"] is False
    assert (T / "migrations" / "0001_wp93_schema.sql").read_text(encoding="utf-8") == plan["sql"]
    assert (T / "migrations" / "0003_wp94_deferred_views.sql").read_text(encoding="utf-8") == plan["deferredSql"]
    assert (T / "post-load-identity-alignment.sql").read_text(encoding="utf-8") == plan["postLoadSql"]
    deferred = {v["name"] for v in plan["views"] if v.get("phase") == "deferred"}
    assert deferred == {"APX_DEMO_APPROVALS_V", "APX_DEMO_DASH_KPI_V"}
    provided = (T / "migrations" / "0002_wp94_business_functions.sql").read_text(encoding="utf-8")
    for m in plan["functionMappings"]:
        assert f"CREATE FUNCTION {m['target']}(" in provided, m


@pytest.mark.skipif(not os.environ.get("APEX2NEXT_F170134_INSTALL_SQL"), reason="source install.sql not available")
def test_pilot_plan_regenerates_identically():
    source = Path(os.environ["APEX2NEXT_F170134_INSTALL_SQL"]).read_text(encoding="utf-8")
    refs = references_from_export_dir(Path(os.environ["APEX2NEXT_F170134_EXPORT_DIR"])) \
        if os.environ.get("APEX2NEXT_F170134_EXPORT_DIR") else None
    plan = build_schema_plan(source, source_name="install.sql", apex_references=refs,
                             overrides=load_overrides(ROOT / "docs/migration/wp9.3/f170134/dictionary-overrides.json"),
                             function_mappings=json.loads((T / "function-mappings.json").read_text(encoding="utf-8")),
                             transaction_wrapper=False)
    assert json.loads(json.dumps(plan)) == json.loads((T / "schema-plan.json").read_text(encoding="utf-8"))
