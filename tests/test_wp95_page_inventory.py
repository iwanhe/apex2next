"""WP9.5 APEX page inventory: deterministic UI specification from a SQL export."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from apex2next_extractor.page_inventory import INVENTORY_FORMAT, build_page_inventory, inventory_from_export_dir

ROOT = Path(__file__).resolve().parents[1]
SYNTH = ROOT / "tests" / "fixtures" / "wp9.5" / "synthetic-export"
COMMITTED = ROOT / "examples" / "f170134-target" / "ui" / "apex-page-inventory.json"


def _components(inv):
    return {c["key"]: c for p in inv["pages"] for c in p["components"]}


def test_synthetic_export_inventory():
    inv = inventory_from_export_dir(SYNTH)
    assert inv["format"] == INVENTORY_FORMAT
    assert inv["application"] == {
        "name": "Synthetic App", "alias": "SYN", "logoText": None, "dateFormat": "DD-MON-YYYY", "homeLink": None,
        "timestampFormat": None,
        "version": "Release 1.0", "language": "en", "securityScheme": "APP_USERS", "authentication": "Oracle APEX Accounts",
    }
    assert [a["name"] for a in inv["authorizations"]] == ["ADMIN_RIGHTS", "APP_USERS"]
    yes_no = next(lov for lov in inv["lovs"] if lov["name"] == "YES_NO")
    assert yes_no["values"] == [{"seq": 10, "display": "Ya", "return": "Y"}, {"seq": 20, "display": "Tidak", "return": "N"}], \
        "static values without p_lov_id belong to the preceding LOV, ordered by sequence"
    assert inv["navigation"][1] == {"label": "Things", "page": 2, "sequence": 20, "icon": None, "parent": "Admin", "scheme": None}
    assert inv["navigation"][0]["scheme"] == "ADMIN_RIGHTS"
    assert inv["navigationBar"] == [{"label": "Sign Out", "target": "&LOGOUT_URL.", "sequence": 10, "parent": None}]
    assert inv["breadcrumbs"][1] == {"label": "Things", "page": 2, "parent": "Home"}

    page = inv["pages"][0]
    assert (page["id"], page["mode"], page["scheme"], page["title"]) == (2, "MODAL", "ADMIN_RIGHTS", "Things")
    comps = _components(inv)
    assert set(comps) == {
        "P2:BUTTON:SAVE", "P2:DYNAMIC_ACTION:REFRESH_AFTER_DIALOG", "P2:IR:Report", "P2:IR_COLUMN:Report.NAME",
        "P2:IR_REPORT:Report.1", "P2:ITEM:P2_NAME", "P2:PROCESS:CALL_IT", "P2:REGION:Report", "P2:REGION:Thing",
        "P2:VALIDATION:NAME_OK", "P2:REGION:Read Only Grid", "P2:REGION_COLUMN:Read Only Grid.ID",
        "P2:REGION_COLUMN:Read Only Grid.INTERNAL_NOTE",
    }
    assert comps["P2:REGION:Report"]["props"]["plug_source"] == "select id, name\n  from things", "wwv_flow_string.join decoded"
    assert comps["P2:IR_REPORT:Report.1"]["props"] == {"report_columns": "NAME", "sort_column_1": "NAME", "sort_direction_1": "ASC"}
    assert comps["P2:PROCESS:CALL_IT"]["props"]["when_button"] == "SAVE"
    assert comps["P2:ITEM:P2_NAME"]["props"]["read_only_when"] == ":P2_ID is null"
    assert comps["P2:VALIDATION:NAME_OK"]["props"]["validation"] == ":P2_NAME <> 'x'"
    assert comps["P2:DYNAMIC_ACTION:REFRESH_AFTER_DIALOG"]["props"]["actions"] == [
        {"action": "NATIVE_REFRESH", "result": "TRUE", "region": "Report"}]
    assert inv["summary"] == {"pages": 1, "components": 13}
    grid = comps["P2:REGION:Read Only Grid"]["props"]
    assert (grid["plug_source_type"], grid["query_type"], grid["query_table"], grid["is_editable"]) == (
        "NATIVE_IG", "TABLE", "THINGS", False)
    assert comps["P2:REGION_COLUMN:Read Only Grid.ID"]["props"] == {
        "source_expression": "ID", "is_visible": True, "display_sequence": 1, "heading": "Identifier"}
    assert comps["P2:REGION_COLUMN:Read Only Grid.INTERNAL_NOTE"]["props"]["is_visible"] is False
    assert comps["P2:REGION_COLUMN:Read Only Grid.ID"]["props"]["is_primary_key"] is True
    assert comps["P2:REGION_COLUMN:Read Only Grid.ID"]["props"]["is_query_only"] is False
    assert comps["P2:REGION_COLUMN:Read Only Grid.ID"]["props"]["is_readonly"] is True


def test_inventory_is_deterministic_and_order_independent():
    files = {p.relative_to(SYNTH).as_posix(): p.read_text(encoding="utf-8") for p in sorted(SYNTH.rglob("*.sql"))}
    a = build_page_inventory(files)
    b = build_page_inventory(dict(reversed(list(files.items()))))
    assert a == b
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_committed_f170134_inventory_shape():
    inv = json.loads(COMMITTED.read_text(encoding="utf-8"))
    assert inv["summary"] == {"pages": 19, "components": 269}
    assert sorted(p["id"] for p in inv["pages"]) == [0, 100, 190, 191, 200, 201, 210, 211, 300, 301, 302, 310, 311,
                                                    400, 500, 501, 510, 511, 9999]
    keys = [c["key"] for p in inv["pages"] for c in p["components"]]
    assert len(keys) == len(set(keys)), "component keys are unique"
    page_302 = next(p for p in inv["pages"] if p["id"] == 302)
    assert page_302["name"] == "Detail Permintaan", "D-003: page 302 exists only in the SQL export"


@pytest.mark.skipif(not os.environ.get("APEX2NEXT_F170134_SQL_EXPORT_DIR"),
                    reason="unpacked f170134 SQL export not provided (APEX2NEXT_F170134_SQL_EXPORT_DIR)")
def test_committed_inventory_regenerates_from_the_source_export():
    inv = inventory_from_export_dir(Path(os.environ["APEX2NEXT_F170134_SQL_EXPORT_DIR"]))
    assert inv == json.loads(COMMITTED.read_text(encoding="utf-8"))
