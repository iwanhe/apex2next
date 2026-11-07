from copy import deepcopy
import pytest
from apex2next_schema_analyzer.plsql_workbench import MAX_SOURCE_CHARS, RULE_REGISTRY_VERSION, analyze_plsql, rule_registry

def test_registry_is_versioned_unique_and_never_automatic():
    registry = rule_registry()
    ids = [item["id"] for item in registry["rules"]]
    assert registry["version"] == RULE_REGISTRY_VERSION
    assert len(ids) == len(set(ids))
    assert registry["automaticRewriteCount"] == 0
    assert all(item["disposition"] != "AUTOMATIC" for item in registry["rules"])

def test_nvl_is_assisted_and_source_is_unchanged():
    source = "BEGIN\n  v_result := NVL(v_input, 'fallback');\nEND;"
    report = analyze_plsql(source, source_name="orders.sql")
    assert report["status"] == "MANUAL"
    assert report["artifactKind"] == "ANONYMOUS_BLOCK"
    assert report["candidateSource"] == source and report["rewriteCount"] == 0
    assert report["diagnostics"][0]["code"] == "PLW001"
    assert report["diagnostics"][0]["disposition"] == "ASSISTED"
    assert report["diagnostics"][0]["source"] == {"name": "orders.sql", "line": 2, "column": 15}

def test_comments_and_literals_do_not_trigger_rules():
    source = """BEGIN
  -- NVL(x, y) is a comment
  v_text := 'DECODE(x, 1, 2)';
  /* SYSDATE and DBMS_OUTPUT are documentation */
  NULL;
END;"""
    assert analyze_plsql(source)["diagnostics"] == []

def test_nested_comments_and_escaped_quotes_are_masked():
    source = """BEGIN
  v_text := 'it''s NVL(x,y)';
  /* outer NVL(x,y) /* inner DECODE(x,y,z) */ still comment */
  NULL;
END;"""
    assert analyze_plsql(source)["diagnostics"] == []

def test_unsupported_construct_takes_precedence():
    report = analyze_plsql("SELECT * FROM t CONNECT BY PRIOR id = parent_id")
    assert report["status"] == "UNSUPPORTED"
    assert any(x["code"] == "PLW006" for x in report["diagnostics"])

def test_dynamic_sql_and_anchored_types_are_reported():
    report = analyze_plsql("DECLARE\n l_value employees.salary%TYPE;\nBEGIN\n EXECUTE IMMEDIATE 'select 1' INTO l_value;\nEND;")
    assert {x["code"] for x in report["diagnostics"]} == {"PLW008", "PLW009"}
    assert report["status"] == "MANUAL"

def test_package_body_and_statement_inventory():
    report = analyze_plsql("CREATE OR REPLACE PACKAGE BODY pkg AS PROCEDURE run_job IS BEGIN SELECT id FROM jobs; UPDATE jobs SET status='DONE'; COMMIT; END; END pkg;")
    assert report["artifactKind"] == "PLSQL_UNIT"
    assert report["statementInventory"]["select"] == 1
    assert report["statementInventory"]["update"] == 1
    assert report["statementInventory"]["commit"] == 1

def test_deterministic_and_input_immutable():
    source = "BEGIN v := DECODE(x, 1, 2); END;"
    before = deepcopy(source)
    assert analyze_plsql(source) == analyze_plsql(source)
    assert source == before

def test_unknown_construct_is_not_claimed_automatic():
    report = analyze_plsql("BEGIN custom_vendor_magic(); END;")
    assert report["status"] == "REVIEW_REQUIRED"
    assert report["rewriteCount"] == 0
    assert "AUTOMATIC" not in {x["disposition"] for x in report["diagnostics"]}

def test_limits_and_argument_validation():
    with pytest.raises(ValueError, match="exceeds"): analyze_plsql("x" * (MAX_SOURCE_CHARS + 1))
    with pytest.raises(ValueError, match="source_name"): analyze_plsql("BEGIN NULL; END;", source_name=" ")
    with pytest.raises(TypeError, match="source"): analyze_plsql(None)  # type: ignore[arg-type]

def test_unterminated_literal_does_not_create_false_positive():
    assert analyze_plsql("BEGIN v := 'NVL(x,y); END;")["diagnostics"] == []
