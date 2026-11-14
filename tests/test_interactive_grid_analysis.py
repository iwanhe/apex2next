from __future__ import annotations

from apex2next_extractor.interactive_grid_analysis import analyze_editable_interactive_grids


def _inventory(*, editable=True, table=True, visible=True, key=True, query_only=False,
               read_only=False, process=True, operations="i:u:d"):
    region_props = {
        "plug_source_type": "NATIVE_IG",
        "is_editable": editable,
        "query_type": "TABLE" if table else "SQL",
        "query_table": "APP.ORDERS" if table else None,
        "edit_operations": operations,
        "lost_update_check_type": "ROW_VERSION",
    }
    column_props = {
        "source_expression": "ORDER_ID", "is_visible": visible,
        "is_primary_key": key, "is_query_only": query_only, "is_readonly": read_only,
    }
    components = [
        {"kind": "REGION", "name": "Orders Grid", "props": region_props},
        {"kind": "REGION_COLUMN", "name": "Orders Grid.ORDER_ID", "props": column_props},
        {"kind": "REGION_COLUMN", "name": "Orders Grid.STATUS", "props": {
            "source_expression": "STATUS", "is_visible": True, "is_primary_key": False,
            "is_query_only": False, "is_readonly": False,
        }},
    ]
    if process:
        components.append({"kind": "PROCESS", "name": "SAVE_ORDERS", "props": {
            "native_ig_dml_candidate": True, "region": "Orders Grid",
        }})
    return {"pages": [{"id": 10, "scheme": "AUTHENTICATED", "components": components}]}


def test_fully_described_editable_grid_is_review_required_not_auto_generated():
    result = analyze_editable_interactive_grids(_inventory())
    grid = result["grids"][0]
    assert grid["classification"] == "REVIEW_REQUIRED"
    assert grid["auto_generate"] is False
    assert grid["primary_key"] == "order_id"
    assert grid["writable_columns"] == ["status"]
    assert grid["operations"] == ["d", "i", "u"]
    assert {f["code"] for f in grid["findings"]} == {"IG011", "IG012", "IG013"}
    assert result["summary"]["auto_generate"] == 0


def test_missing_visibility_or_writeability_fails_closed():
    result = analyze_editable_interactive_grids(_inventory(visible=None, query_only=None, read_only=None))
    grid = result["grids"][0]
    codes = {f["code"] for f in grid["findings"]}
    assert grid["classification"] == "MANUAL"
    assert {"IG003", "IG006"} <= codes


def test_missing_or_unsupported_primary_key_and_operations_fail_closed():
    result = analyze_editable_interactive_grids(_inventory(key=False, operations="i:u:merge"))
    grid = result["grids"][0]
    codes = {f["code"] for f in grid["findings"]}
    assert grid["classification"] == "MANUAL"
    assert {"IG007", "IG009"} <= codes


def test_missing_table_source_or_native_dml_association_fails_closed():
    result = analyze_editable_interactive_grids(_inventory(table=False, process=False))
    grid = result["grids"][0]
    codes = {f["code"] for f in grid["findings"]}
    assert grid["classification"] == "MANUAL"
    assert {"IG001", "IG010"} <= codes


def test_read_only_and_unspecified_grids_are_not_treated_as_editable():
    for editable in (False, None):
        result = analyze_editable_interactive_grids(_inventory(editable=editable))
        assert result["summary"]["editable_grids"] == 0
