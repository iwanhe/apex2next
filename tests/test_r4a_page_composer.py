"""R4a: pages composed region by region (static content, lists, classic reports, Cards) and their safety rules."""
import json
import subprocess
import sys
from pathlib import Path

from apex2next_schema_analyzer.app_generator import Inputs, classify, default_map, generate
from apex2next_schema_analyzer.page_composer import sanitize_html

ROOT = Path(__file__).resolve().parents[1]


def test_static_html_is_reduced_to_allowlisted_structure():
    s = sanitize_html('<p class="x" onclick="alert(1)">Hi <b>there</b><script>alert(1)</script></p>'
                      '<a href="javascript:alert(1)">bad</a><a href="https://oracle.com/apex">ok</a>'
                      '<img src="#IMAGE_PREFIX#a.png"><iframe src="x">t</iframe><ul><li>a</li></ul>')
    assert s["nodes"] == [{"t": "p", "c": ["Hi ", {"t": "b", "c": ["there"]}]},
                          {"t": "a", "href": "javascript:alert(1)", "c": ["bad"]},
                          {"t": "a", "href": "https://oracle.com/apex", "c": ["ok"]},
                          {"t": "ul", "c": [{"t": "li", "c": ["a"]}]}]
    assert s["dropped"] == ["iframe", "img", "script"] and s["substitutions"] == []  # only in a dropped img
    assert sanitize_html("Hello &APP_NAME. and &P2_ID!ATTR.")["substitutions"] == ["APP_NAME", "P2_ID"]


def _c(page, kind, name, **props):
    return {"key": f"P{page}:{kind}:{name}", "kind": kind, "name": name, "props": props}


def _app(tmp_path: Path, *, extra_page1=(), button_condition=None, region_condition="ITEM_IS_NOT_NULL"):
    detail = [
        _c(1, "ITEM", "P1_DEPT_ID", display_as="NATIVE_HIDDEN", source_type="ALWAYS_NULL"),
        _c(1, "REGION", "About", plug_source='<p>Pick a department in <a href="f?p=&APP_ID.:1:&SESSION.">&APP_NAME.</a>.</p>'
                                              '<script>x</script>', plug_display_sequence=10),
        _c(1, "REGION", "Pages", plug_source_type="NATIVE_LIST", list="Demo Pages", plug_display_sequence=20),
        _c(1, "REGION", "Selector", plug_source_type="NATIVE_DISPLAY_SELECTOR", plug_display_sequence=5),
        _c(1, "REPORT_REGION", "Departments", source="select deptno, dname from dept", display_sequence=30,
           query_num_rows=10),
        _c(1, "REPORT_COLUMN", "Departments.DEPTNO", column_display_sequence=1, hidden_column="Y"),
        _c(1, "REPORT_COLUMN", "Departments.DNAME", column_display_sequence=2,
           column_link="f?p=&APP_ID.:1:&SESSION.::&DEBUG.::P1_DEPT_ID:#DEPTNO#"),
        _c(1, "REPORT_REGION", "Employees", query_type="TABLE", query_table="EMP", query_where="deptno = :P1_DEPT_ID",
           query_order_by="ename", display_sequence=40, display_condition_type=region_condition,
           display_when_condition="P1_DEPT_ID"),
        _c(1, "REPORT_COLUMN", "Employees.EMPNO", column_display_sequence=1,
           column_link="f?p=&APP_ID.:2:&SESSION.::&DEBUG.:RP:P2_EMPNO:#EMPNO#"),
        _c(1, "REPORT_COLUMN", "Employees.ENAME", column_display_sequence=2),
        _c(1, "BUTTON", "ADD", button_image_alt="Add Employee", button_action="REDIRECT_PAGE", button_sequence=10,
           button_redirect_url="f?p=&APP_ID.:2:&SESSION.::&DEBUG.:RP,2:P2_DEPTNO:&P1_DEPT_ID.",
           button_condition_type=button_condition or "ITEM_IS_NOT_NULL", button_condition="P1_DEPT_ID"),
        _c(1, "BUTTON", "RECALC", button_image_alt="Recalculate", button_action="SUBMIT", button_sequence=20),
        *extra_page1,
    ]
    form = [
        _c(2, "REGION", "Employee", plug_source_type="NATIVE_FORM", query_type="TABLE", query_table="EMP",
           edit_operations="i:u:d"),
        _c(2, "ITEM", "P2_EMPNO", display_as="NATIVE_HIDDEN", source="EMPNO", is_primary_key=True),
        _c(2, "ITEM", "P2_ENAME", display_as="NATIVE_TEXT_FIELD", source="ENAME", prompt="Name"),
        _c(2, "ITEM", "P2_DEPTNO", display_as="NATIVE_HIDDEN", source="DEPTNO"),
    ]
    inventory = {
        "format": "apex2next.apex-page-inventory.v1", "sha256": "0" * 64,
        "application": {"name": "Demo"}, "authorizations": [], "navigation": [], "navigationBar": [],
        "breadcrumbs": [], "lovs": [],
        "lists": [{"name": "Demo Pages", "items": [
            {"label": "Departments", "target": "f?p=&APP_ID.:1:&SESSION.", "sequence": 10, "description": "All of them"},
            {"label": "Docs", "target": "https://docs.oracle.com/", "sequence": 20},
            {"label": "Elsewhere", "target": "f?p=&APP_ID.:99:&SESSION.", "sequence": 30}]}],
        "pages": [{"id": 1, "name": "Departments", "alias": "DEPARTMENTS", "title": "Departments", "mode": "NORMAL",
                   "components": detail},
                  {"id": 2, "name": "Employee", "alias": "EMPLOYEE", "title": "Employee", "mode": "MODAL",
                   "components": form}],
    }
    plan = {"targetSchema": "app", "functionMappings": [], "views": [],
            "tables": [{"name": n, "targetName": n.lower(), "emit": True,
                        "constraints": [{"kind": "PRIMARY KEY", "columns": [k]}],
                        "columns": [{"name": k, "targetName": k.lower(), "targetType": "bigint", "typeFamily": "integer"}]}
                       for n, k in (("EMP", "EMPNO"), ("DEPT", "DEPTNO"))]}
    (tmp_path / "ui").mkdir()
    (tmp_path / "db").mkdir()
    (tmp_path / "ui/apex-page-inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
    (tmp_path / "db/schema-plan.json").write_text(json.dumps(plan), encoding="utf-8")
    (tmp_path / "ui/app-map.json").write_text(json.dumps(default_map(Inputs(tmp_path))), encoding="utf-8")
    return tmp_path


def test_composed_page_with_static_list_reports_binds_and_buttons(tmp_path):
    app = _app(tmp_path)
    assert classify(Inputs(app).pages[1])[0] == "COMPOSED"
    files, report = generate(app)
    page = next(p for p in report["pages"] if p["id"] == 1)
    assert page["status"] == "PARTIAL"  # the SUBMIT button needs server logic
    codes = {t["code"]: t.get("detail") for t in page["todo"]}
    assert codes["GEN020"] == "RECALC" and codes["GEN015"] == "Selector"
    assert codes["GEN021"] == "About: script" and codes["GEN019"] == "Pages: Elsewhere"
    tsx = files["apps/web/app/(app)/departments/page.tsx"]
    assert "const items = { P1_DEPT_ID: first(sp.p1_dept_id) ?? null };" in tsx
    # static: link to the page itself resolved, &APP_NAME. replaced, script gone
    assert ('<StaticRegion title="About" nodes={[{"t": "p", "c": ["Pick a department in ", '
            '{"t": "a", "href": "/departments", "c": ["Demo"]}, "."]}]} />') in tsx
    assert "{ label: 'Docs', href: `https://docs.oracle.com/` }" in tsx and "{ label: 'Elsewhere' }" in tsx
    assert "columnLinks={{ dname: (r) => `/departments?p1_dept_id=${encodeURIComponent(r.deptno ?? '')}` }}" in tsx
    assert ("{items.P1_DEPT_ID !== null && (\n        <ReportRegion pageId={1} region=\"employees\" regionName=\"Employees\" "
            "basePath={back} sp={sp} items={{ P1_DEPT_ID: items.P1_DEPT_ID }} columnLinks={{ empno: (r) => "
            "`/departments/${encodeURIComponent(r.empno ?? '')}` }} />)}") in tsx
    assert ("{items.P1_DEPT_ID !== null && allowed['ADD'] && <Link className={'btn' + (false ? ' btn-hot' : '')} "
            "href={`/departments/new?deptno=${encodeURIComponent(items.P1_DEPT_ID ?? '')}`}>") in tsx
    assert tsx.index("About") < tsx.index("Pages") < tsx.index('region="departments"') < tsx.index('region="employees"')
    src = files["apps/api/src/pages/app-sources.generated.ts"]
    assert "view: 'emp',\n    select: ['empno', 'ename'],\n    where: { sql: 'deptno = $1', source: 'deptno = :P1_DEPT_ID' }," in src
    assert "binds: ['P1_DEPT_ID']," in src


def test_unsupported_condition_keeps_the_page_manual(tmp_path):
    files, report = generate(_app(tmp_path, region_condition="EXISTS"))
    page = next(p for p in report["pages"] if p["id"] == 1)
    assert page["status"] == "MANUAL" and any(t["code"] == "GEN018" for t in page["todo"])
    assert "apps/web/app/(app)/departments/page.tsx" not in files


def test_bind_of_an_input_item_is_not_served_generically(tmp_path):
    extra = [_c(1, "REPORT_REGION", "Search", source="select ename from emp where ename like :P1_TEXT", display_sequence=50)]
    files, report = generate(_app(tmp_path, extra_page1=extra))
    region = next(r for r in report["regions"] if r["region"] == "Search")
    assert region["status"] == "MANUAL" and "GEN016" in region["findings"]


def test_hand_written_pages_are_never_overwritten(tmp_path):
    app = _app(tmp_path)
    page = app / "apps/web/app/(app)/departments/page.tsx"
    page.parent.mkdir(parents=True)
    page.write_text("export default function Page() { return null; }\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "tools/apex2next"), "generate", app], capture_output=True, text=True)
    assert r.returncode != 0 and "refusing to overwrite hand-written page(s): apps/web/app/(app)/departments/page.tsx" in r.stderr
    assert page.read_text() == "export default function Page() { return null; }\n"
    amap = json.loads((app / "ui/app-map.json").read_text())
    amap["pages"]["1"]["manual"] = True
    (app / "ui/app-map.json").write_text(json.dumps(amap))
    r = subprocess.run([sys.executable, str(ROOT / "tools/apex2next"), "generate", app], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    report = json.loads((app / "ui/generation-report.json").read_text())
    assert next(p for p in report["pages"] if p["id"] == 1)["todo"][0]["code"] == "GEN022"


def test_two_forms_below_one_page_get_their_own_routes():
    proposed = default_map(Inputs(ROOT / "examples/f170134-target"))
    routes = [e["route"] for e in proposed["pages"].values() if e.get("form")]
    assert len(routes) == len(set(routes))


def test_read_only_table_backed_interactive_grid_generates_only_visible_columns(tmp_path):
    app = _app(tmp_path)
    inventory_path = app / "ui/apex-page-inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    page = next(p for p in inventory["pages"] if p["id"] == 1)
    page["components"].extend([
        _c(1, "REGION", "Department Grid", plug_source_type="NATIVE_IG", query_type="TABLE",
           query_table="DEPT", query_order_by="DNAME", is_editable=False, plug_display_sequence=35),
        _c(1, "REGION_COLUMN", "Department Grid.DEPTNO", source_expression="DEPTNO",
           is_visible="Y", display_sequence=1, heading="Department ID"),
        _c(1, "REGION_COLUMN", "Department Grid.DNAME", source_expression="DNAME",
           is_visible="Y", display_sequence=2, heading="Department Name"),
        _c(1, "REGION_COLUMN", "Department Grid.INTERNAL_NOTE", source_expression="INTERNAL_NOTE",
           is_visible="N", display_sequence=3, heading="Internal Note"),
    ])
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    plan_path = app / "db/schema-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    dept = next(t for t in plan["tables"] if t["name"] == "DEPT")
    dept["columns"].extend([
        {"name": "DNAME", "targetName": "dname", "targetType": "text", "typeFamily": "STRING"},
        {"name": "INTERNAL_NOTE", "targetName": "internal_note", "targetType": "text", "typeFamily": "STRING"},
    ])
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    (app / "ui/app-map.json").write_text(json.dumps(default_map(Inputs(app))), encoding="utf-8")

    assert classify(Inputs(app).pages[1])[0] == "COMPOSED"
    files, report = generate(app)
    page_report = next(p for p in report["pages"] if p["id"] == 1)
    assert page_report["status"] in {"GENERATED", "PARTIAL"}
    assert '<ReportRegion pageId={1} region="departmentGrid"' in files["apps/web/app/(app)/departments/page.tsx"]
    sources = files["apps/api/src/pages/app-sources.generated.ts"]
    assert "region: 'Department Grid', kind: 'CLASSIC'" in sources
    assert "select: ['deptno', 'dname']" in sources
    assert "internal_note" not in sources



def test_interactive_grid_rejects_unreviewed_table_identifiers_and_predicates(tmp_path):
    cases = [
        {"query_table": "DEPT; DROP TABLE EMP"},
        {"query_table": "DEPT", "query_where": "1=1 OR 1=1"},
    ]
    for index, overrides in enumerate(cases):
        case_dir = tmp_path / f"case-{index}"
        case_dir.mkdir()
        app = _app(case_dir)
        inventory_path = app / "ui/apex-page-inventory.json"
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        page = next(p for p in inventory["pages"] if p["id"] == 1)
        grid_props = {"plug_source_type": "NATIVE_IG", "query_type": "TABLE",
                      "query_table": "DEPT", "is_editable": False}
        grid_props.update(overrides)
        page["components"].append(_c(1, "REGION", "Unsafe Grid", **grid_props))
        page["components"].append(_c(1, "REGION_COLUMN", "Unsafe Grid.DEPTNO",
                                     source_expression="DEPTNO", is_visible=True, display_sequence=1))
        inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
        (app / "ui/app-map.json").write_text(json.dumps(default_map(Inputs(app))), encoding="utf-8")

        _, report = generate(app)
        region = next(r for r in report["regions"] if r["region"] == "Unsafe Grid")
        assert region["status"] == "MANUAL"
        assert "GEN027" in region["findings"]



def test_interactive_grid_never_falls_back_to_select_star_on_incomplete_columns(tmp_path):
    cases = [
        # Missing visibility metadata.
        {"source_expression": "DEPTNO"},
        # Computed expressions are not projected.
        {"source_expression": "UPPER(DNAME)", "is_visible": True},
        # Explicitly hidden-only grids have no safe projection.
        {"source_expression": "INTERNAL_NOTE", "is_visible": False},
        # A simple identifier is still rejected when it is not in the target table plan.
        {"source_expression": "NOT_A_REAL_COLUMN", "is_visible": True},
    ]
    for index, column_props in enumerate(cases):
        case_dir = tmp_path / f"projection-{index}"
        case_dir.mkdir()
        app = _app(case_dir)
        inventory_path = app / "ui/apex-page-inventory.json"
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        page = next(p for p in inventory["pages"] if p["id"] == 1)
        page["components"].extend([
            _c(1, "REGION", "Restricted Grid", plug_source_type="NATIVE_IG", query_type="TABLE",
               query_table="DEPT", is_editable=False),
            _c(1, "REGION_COLUMN", "Restricted Grid.COLUMN", display_sequence=1, **column_props),
        ])
        inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
        (app / "ui/app-map.json").write_text(json.dumps(default_map(Inputs(app))), encoding="utf-8")

        files, report = generate(app)
        source = files["apps/api/src/pages/app-sources.generated.ts"]
        assert "restrictedGrid" not in source
        region = next(r for r in report["regions"] if r["region"] == "Restricted Grid")
        assert region["status"] == "MANUAL"
        assert any(code in region["findings"] for code in ("GEN003", "GEN013", "GEN027"))



def test_editable_or_unspecified_interactive_grid_stays_manual(tmp_path):
    app = _app(tmp_path)
    inventory_path = app / "ui/apex-page-inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    page = next(p for p in inventory["pages"] if p["id"] == 1)
    page["components"].append(_c(1, "REGION", "Editable Grid", plug_source_type="NATIVE_IG",
                                 query_type="TABLE", query_table="DEPT", is_editable=True))
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    assert classify(Inputs(app).pages[1])[0] == "MANUAL"

    page["components"][-1]["props"].pop("is_editable")
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    assert classify(Inputs(app).pages[1])[0] == "MANUAL"


def test_unknown_interactive_grid_visibility_flag_keeps_region_manual(tmp_path):
    app = _app(tmp_path)
    inventory_path = app / "ui/apex-page-inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    page = next(p for p in inventory["pages"] if p["id"] == 1)
    page["components"].extend([
        _c(1, "REGION", "Department Grid", plug_source_type="NATIVE_IG", query_type="TABLE",
           query_table="DEPT", is_editable=False),
        _c(1, "REGION_COLUMN", "Department Grid.DEPTNO", source_expression="DEPTNO",
           is_visible="UNKNOWN", display_sequence=1),
    ])
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    (app / "ui/app-map.json").write_text(json.dumps(default_map(Inputs(app))), encoding="utf-8")

    files, report = generate(app)
    page_report = next(p for p in report["pages"] if p["id"] == 1)
    region_report = next(r for r in report["regions"] if r["region"] == "Department Grid")
    assert page_report["status"] == "MANUAL"
    assert region_report["status"] == "MANUAL"
    assert any(code in region_report["findings"] for code in ("GEN003", "GEN013", "GEN027", "RGN007"))
    assert "apps/web/app/(app)/departments/page.tsx" not in files
