"""WP9.3 pilot artifacts for Demo Permintaan Barang (170134).

The supplied install.sql and APEX export are not committed (chain-of-custody policy
from WP9.1/9.2). These tests pin the committed, generated artifacts to the recorded
source hash and verify internal consistency. When the source files are available
locally, set APEX2NEXT_F170134_INSTALL_SQL and APEX2NEXT_F170134_EXPORT_DIR to prove
byte-identical regeneration.
"""
import json
import os
from pathlib import Path

import pytest

from apex2next_schema_analyzer.schema_plan import build_schema_plan, references_from_export_dir, rule_registry
from apex2next_schema_analyzer.schema_report import render_report
from apex2next_schema_analyzer.source_overrides import load_overrides

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "docs" / "migration" / "wp9.3" / "f170134"
SOURCE_SHA = "sha256:7c71e9c56b76d5fe893d2f357e692b9e7c458adc37791784379842ec1712d66d"
TITLE = "WP9.3 — Schema Conversion Report: Demo Permintaan Barang (170134)"


@pytest.fixture(scope="module")
def plan():
    return json.loads((D / "schema-plan.json").read_text(encoding="utf-8"))


def test_artifacts_are_pinned_to_wp92_source_and_current_rules(plan):
    assert plan["source"] == {"name": "install.sql", "sha256": SOURCE_SHA, "bytes": 38098}
    assert plan["ruleRegistrySha256"] == rule_registry()["sha256"]
    assert (D / "0001_wp93_schema.sql").read_text(encoding="utf-8") == plan["sql"]
    assert (D / "post-load-identity-alignment.sql").read_text(encoding="utf-8") == plan["postLoadSql"]
    assert (D / "schema-conversion-report.md").read_text(encoding="utf-8") == render_report(plan, title=TITLE)


def test_wp93_acceptance_counts(plan):
    s = plan["summary"]
    assert s["tables"] == {"source": 9, "emitted": 9}
    assert s["views"] == {"source": 10, "emitted": 8}
    assert s["indexes"] == {"source": 4, "emitted": 4}
    by_type = {o["type"] for o in plan["objects"]}
    assert {"PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "CHECK", "INDEX", "IDENTITY", "GENERATED COLUMN"} <= by_type
    counts = {k: sum(v.values()) for k, v in s["objectsByType"].items()}
    assert counts["PRIMARY KEY"] == 9 and counts["FOREIGN KEY"] == 7 and counts["UNIQUE"] == 4
    assert counts["CHECK"] == 8 and counts["IDENTITY"] == 6 and counts["GENERATED COLUMN"] == 1
    assert counts["TRIGGER"] == 5 and counts["PACKAGE"] == 4 and counts["PACKAGE BODY"] == 4
    assert all(o["disposition"] in {"AUTOMATIC", "ASSISTED", "MANUAL", "UNSUPPORTED"} for o in plan["objects"])
    every_view_designed = all(v.get("design") for v in plan["views"])
    assert every_view_designed and len(plan["views"]) == 10


def test_dependency_validation_passes_with_dictionary_override(plan):
    assert all(c["status"] == "PASS" for c in plan["checks"]), [c for c in plan["checks"] if c["failures"]]
    # D-001/SRC-001: the installed KPI view (USER_VIEWS) replaces the stale install.sql definition.
    assert [o["object"] for o in plan["overrides"]] == ["VIEW APX_DEMO_DASH_KPI_V"]
    assert plan["overrides"][0]["action"] == "replaced"
    kpi = next(v for v in plan["views"] if v["name"] == "APX_DEMO_DASH_KPI_V")
    assert kpi["outputColumns"] == ["SEQ", "ICON", "LABEL", "METRIC_VALUE"]
    assert json.loads((D / "dictionary-overrides.json").read_text(encoding="utf-8"))["evidence"][0]["sha256"] == \
        "45e57dece6e0449151b536ad7f3082d2e4de7e0d9c0ca73b2d67f60bde579b6c"


def test_not_emitted_views_are_the_plsql_dependent_ones(plan):
    blocked = {v["name"]: v for v in plan["views"] if not v["emit"]}
    assert set(blocked) == {"APX_DEMO_APPROVALS_V", "APX_DEMO_DASH_KPI_V"}
    assert blocked["APX_DEMO_APPROVALS_V"]["plsqlCalls"] == ["APX_DEMO_APPROVAL_PKG.CAN_ACT_YN"]
    assert blocked["APX_DEMO_DASH_KPI_V"]["blockedBy"] == ["APX_DEMO_APPROVALS_V"]


@pytest.mark.skipif(not os.environ.get("APEX2NEXT_F170134_INSTALL_SQL"),
                    reason="source install.sql not available (not committed by policy)")
def test_regeneration_from_source_is_byte_identical(plan):
    source = Path(os.environ["APEX2NEXT_F170134_INSTALL_SQL"]).read_text(encoding="utf-8")
    refs = None
    if os.environ.get("APEX2NEXT_F170134_EXPORT_DIR"):
        refs = references_from_export_dir(Path(os.environ["APEX2NEXT_F170134_EXPORT_DIR"]))
    regenerated = json.loads(json.dumps(build_schema_plan(
        source, source_name="install.sql", apex_references=refs,
        overrides=load_overrides(D / "dictionary-overrides.json"))))
    assert regenerated == plan
