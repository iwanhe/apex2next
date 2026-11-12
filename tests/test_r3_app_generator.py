"""R3: application generator (region/LOV sources, routes, pages, TODO report) and snapshot query generator."""
import json
import re
from pathlib import Path

import pytest

from apex2next_schema_analyzer.app_generator import (Inputs, classify, default_map, generate, parse_link,
                                                     stale_generated_pages)
from apex2next_schema_analyzer.snapshot_query import build_snapshot_query

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "examples" / "f170134-target"


# ----------------------------------------------------------------------------------------------- pilot 170134
@pytest.fixture(scope="module")
def pilot():
    return generate(PILOT)


def test_pilot_generated_files_are_current_and_complete(pilot):
    files, _ = pilot
    for rel, text in files.items():
        assert (PILOT / rel).read_text(encoding="utf-8") == text, f"stale: {rel} (run tools/apex2next generate {PILOT.name})"
    assert stale_generated_pages(PILOT, files) == []
    assert generate(PILOT)[0] == files, "generation is deterministic"


def test_pilot_summary_and_what_stays_manual(pilot):
    _, report = pilot
    s = report["summary"]
    assert s["pages"] == {"GENERATED": 15, "MANUAL": 2, "NOT_APPLICABLE": 1, "PROVIDED": 1}
    assert s["regions"] == {"GENERATED": 11, "MANUAL": 3} and s["lovs"] == {"GENERATED": 5, "PROVIDED": 3}
    manual = {p["id"]: p for p in report["pages"] if p["status"] == "MANUAL"}
    assert set(manual) == {100, 302}  # dashboard (charts, metric cards) and master-detail
    assert manual[100]["todo"][0]["code"] == "GEN001"
    assert manual[302]["todo"][0]["code"] == "GEN022"  # composable since R4a, kept hand-written by the app map
    by_page = {p["id"]: [f["code"] for f in p["todo"]] for p in report["pages"]}
    assert by_page[191].count("GEN006") == 2 and by_page[301].count("GEN007") == 1  # approve/reject, need-date validation
    assert "GEN008" not in by_page[201], "CREATE/SAVE/DELETE by primary key are standard, not open items"
    assert [t["detail"] for t in report["todo"] if t["code"] == "GEN010"] == [
        a["name"] for a in json.loads((PILOT / "ui/apex-page-inventory.json").read_text(encoding="utf-8"))["authorizations"]]


def test_pilot_region_sources_carry_the_reviewed_shapes(pilot):
    files, _ = pilot
    src = files["apps/api/src/pages/app-sources.generated.ts"]
    assert "where: { sql: 'request_id = $1', source: 'request_id = to_number(:P302_REQUEST_ID)' }" in src
    assert "binds: ['P302_REQUEST_ID']" in src
    assert "types: { item_id: 'NUMBER', std_price: 'NUMBER', updated_on: 'DATE' }" in src and "hidden: ['item_id']" in src
    assert "facets: [{ item: 'P300_STATUS', column: 'STATUS' }, { item: 'P300_DEPARTMENT_ID_DSP', column: 'DEPARTMENT_ID_DSP' }]" in src
    assert "orderBy: 'd', numeric: true" in src and "orderBy: 'r'" in src
    assert "from app.apx_demo_departments where active_yn = \\'Y\\''" in src
    routes = files["apps/web/lib/app-routes.generated.ts"]
    assert "302: '/requests/detail'" in routes and "191:" not in routes and "requestSummary: 'Rekap Permintaan'" in routes


def test_pilot_pages_follow_the_app_map(pilot):
    files, _ = pilot
    edit = files["apps/web/app/(app)/admin/document-types/[docType]/page.tsx"]
    assert "form=\"docType\" id={docType}" in edit and "returnTo={safeReturn(first(sp.return), '/admin/document-types')}" in edit
    assert "apps/web/app/(app)/admin/document-types/new/page.tsx" not in files  # edit_operations 'u'
    assert "apps/web/app/(app)/approvals/new/page.tsx" not in files  # a view-based form without insert
    assert "extraItems={{ P191_NOTE: { column: 'note' } }}" in files["apps/web/app/(app)/approvals/[id]/page.tsx"]
    assert "load={`/forms/requestLine${qs({ request_id: first(sp.request_id) })}`}" in files[
        "apps/web/app/(app)/request-lines/new/page.tsx"]
    assert "columnLinks={{ request_no: (r, back) => `/requests/${encodeURIComponent(r.request_id ?? '')}?return=" in files[
        "apps/web/app/(app)/requests/page.tsx"]
    assert 'kind="CARDS" searchItem="P210_SEARCH" cardKey="item_id"' in files["apps/web/app/(app)/items/page.tsx"]


def test_default_map_proposes_routes_below_the_list_page():
    proposed = default_map(Inputs(PILOT))
    assert proposed["pages"]["100"] == {"route": "/"} and proposed["pages"]["9999"] == {"route": "/login"}
    assert proposed["pages"]["311"] == {"route": "/request-lines", "form": "barisPermintaan"}  # IR detail link wins over a button
    assert proposed["pages"]["201"] == {"route": "/departments", "form": "department"}
    keys = list(proposed["regions"].values())
    assert len(keys) == len(set(keys)) and proposed["regions"]["310:Baris Permintaan"] == "barisPermintaan310"


def test_link_parsing_and_page_patterns():
    link = parse_link("f?p=&APP_ID.:201:&SESSION.::&DEBUG.:201:P201_DEPARTMENT_ID:\\#DEPARTMENT_ID#\\")
    assert link == {"page": 201, "items": {"P201_DEPARTMENT_ID": "#DEPARTMENT_ID#"}}
    assert parse_link("f?p=&APP_ID.:311:&SESSION.::&DEBUG.:311") == {"page": 311, "items": {}}
    assert parse_link("javascript:void(0)") is None and parse_link(None) is None
    pages = {p["id"]: classify(p)[0] for p in Inputs(PILOT).inventory["pages"]}
    assert pages == {0: "GLOBAL", 100: "MANUAL", 190: "IR_PAGE", 191: "FORM_DIALOG", 200: "IR_PAGE", 201: "FORM_DIALOG",
                     210: "FACETED_CARDS", 211: "FORM_DIALOG", 300: "FACETED_REPORT", 301: "FORM_DIALOG", 302: "COMPOSED",
                     310: "IR_PAGE", 311: "FORM_DIALOG", 400: "IR_PAGE", 500: "IR_PAGE", 501: "FORM_DIALOG",
                     510: "IR_PAGE", 511: "FORM_DIALOG", 9999: "LOGIN"}


# ----------------------------------------------------------------------------------------------- synthetic app
def _component(page, kind, name, **props):
    return {"key": f"P{page}:{kind}:{name}", "kind": kind, "name": name, "props": props}


def _app(tmp_path, region_sql, *, lov_sql="select ename d, empno r from emp order by 1", catalog=True, detail_link=None):
    ir_props = {"download_formats": "CSV:HTML"}
    if detail_link:
        ir_props["detail_link"] = detail_link
    columns = ["EMPNO", "ENAME", "DNAME"]
    inventory = {
        "format": "apex2next.apex-page-inventory.v1", "sha256": "0" * 64,
        "application": {"name": "Synthetic", "securityScheme": "USERS"},
        "authorizations": [{"name": "USERS", "errorMessage": "no"}],
        "lovs": [{"name": "EMPS", "location": "LOCAL", "query": lov_sql, "values": []}],
        "navigation": [], "navigationBar": [], "breadcrumbs": [],
        "pages": [
            {"id": 1, "name": "Employees", "alias": "EMPLOYEES", "title": "Employees", "mode": "NORMAL", "scheme": None,
             "components": [
                 _component(1, "REGION", "Employees", plug_source_type="NATIVE_IR", query_type="SQL", plug_source=region_sql),
                 _component(1, "IR", "Employees", **ir_props),
                 *[_component(1, "IR_COLUMN", f"Employees.{c}", column_type="STRING") for c in columns]]},
            {"id": 2, "name": "Staff", "alias": "STAFF", "title": "Staff", "mode": "NORMAL", "scheme": None,
             "components": [
                 _component(2, "REGION", "Filter", plug_source_type="NATIVE_FACETED_SEARCH"),
                 _component(2, "ITEM", "P2_SEARCH", display_as="NATIVE_SEARCH", source_type="FACET_COLUMN", item_sequence=10),
                 _component(2, "REPORT_REGION", "Staff", source="select empno, ename from emp_v", query_num_rows=20)]},
        ],
    }
    plan = {
        "targetSchema": "app", "functionMappings": [],
        "tables": [{"name": n, "targetName": n.lower(), "emit": True,
                    "constraints": [{"kind": "PRIMARY KEY", "columns": [k]}],
                    "columns": [{"name": k, "targetName": k.lower(), "targetType": "bigint", "typeFamily": "integer"},
                                {"name": "NAME", "targetName": "name", "targetType": "varchar(50)", "typeFamily": "text"}]}
                   for n, k in (("EMP", "EMPNO"), ("DEPT", "DEPTNO"))],
        "views": [{"name": "EMP_V", "emit": True, "columns": None, "outputColumns": ["EMPNO", "ENAME"]}],
    }
    (tmp_path / "ui").mkdir()
    (tmp_path / "db").mkdir()
    (tmp_path / "ui/apex-page-inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
    (tmp_path / "db/schema-plan.json").write_text(json.dumps(plan), encoding="utf-8")
    if catalog:
        (tmp_path / "db/target-catalog.json").write_text(json.dumps({
            "format": "apex2next.target-catalog.v1", "schema": "app",
            "relations": {"emp_v": {"empno": "bigint", "ename": "character varying(50)"}}}), encoding="utf-8")
    (tmp_path / "ui/app-map.json").write_text(json.dumps(default_map(Inputs(tmp_path))), encoding="utf-8")
    return tmp_path


JOIN = ("select e.empno, e.ename, d.dname from emp e join dept d on d.deptno = e.deptno "
        "where e.mgr = :APP_USER and nvl(e.active, 'Y') = 'Y'")


def test_join_query_becomes_a_derived_table_with_binds(tmp_path):
    files, report = generate(_app(tmp_path, JOIN))
    src = files["apps/api/src/pages/app-sources.generated.ts"]
    assert ("sql: 'select e.empno, e.ename, d.dname from app.emp e join app.dept d on d.deptno = e.deptno "
            "where e.mgr = $1 and COALESCE(e.active, \\'Y\\') = \\'Y\\'',") in src
    assert "select: ['empno', 'ename', 'dname']," in src and "binds: ['APP_USER']," in src
    assert report["summary"]["pages"] == {"GENERATED": 2} and report["summary"]["regions"] == {"GENERATED": 2}
    staff = re.search(r"staff: \{.*?\n  \},", src, re.S).group(0)
    assert "types: { empno: 'NUMBER' }" in staff and "searchable: true, sortable: false, rowsPerPage: 20" in staff
    assert "employees: 'Employees'" in files["apps/web/lib/app-routes.generated.ts"]
    page = files["apps/web/app/(app)/employees/page.tsx"]
    assert '<IrPage pageId={1} region="employees" regionName="Employees" basePath="/employees"' in page and "detailLink" not in page


def test_untranslatable_region_is_reported_and_its_page_is_not_generated(tmp_path):
    files, report = generate(_app(tmp_path, "select empno, ename, dname from emp e, dept d where e.deptno = d.deptno(+)"))
    assert "employees:" not in files["apps/api/src/pages/app-sources.generated.ts"]
    assert "apps/web/app/(app)/employees/page.tsx" not in files
    region = next(r for r in report["regions"] if r["region"] == "Employees")
    assert region["status"] == "MANUAL" and {"EXP012", "GEN003"} <= set(region["findings"])
    page = next(p for p in report["pages"] if p["id"] == 1)
    assert page["status"] == "MANUAL" and page["todo"][0]["code"] == "GEN003"
    assert any(t.get("region") == "Employees" and t["code"] == "EXP012" for t in report["todo"])


def test_missing_catalog_link_to_a_normal_page_and_cascading_lov_are_flagged(tmp_path):
    app = _app(tmp_path, "select empno, ename, dname from emp", catalog=False, lov_sql="select ename, empno from emp where deptno = :P1_DEPT",
               detail_link="f?p=&APP_ID.:2:&SESSION.::&DEBUG.::P2_EMPNO:#EMPNO#")
    files, report = generate(app)
    staff = next(r for r in report["regions"] if r["region"] == "Staff")
    assert staff["status"] == "GENERATED" and "GEN004" in staff["findings"]  # generated, types default to text
    assert "types:" not in files["apps/api/src/pages/app-sources.generated.ts"]
    page = next(p for p in report["pages"] if p["id"] == 1)
    assert page["status"] == "GENERATED" and [f["code"] for f in page["todo"]] == ["GEN005"]
    assert "detailLink" not in files["apps/web/app/(app)/employees/page.tsx"]
    lov = report["lovs"][0]
    assert lov["status"] == "MANUAL" and "EMPS" not in files["apps/api/src/pages/app-sources.generated.ts"]


def test_check_mode_detects_stale_and_orphan_files(tmp_path):
    app = _app(tmp_path, "select empno, ename, dname from emp")
    files, _ = generate(app)
    for rel, text in files.items():
        (app / rel).parent.mkdir(parents=True, exist_ok=True)
        (app / rel).write_text(text, encoding="utf-8")
    assert stale_generated_pages(app, files) == []
    orphan = app / "apps/web/app/(app)/old/page.tsx"
    orphan.parent.mkdir(parents=True)
    orphan.write_text(files["apps/web/app/(app)/employees/page.tsx"], encoding="utf-8")
    hand = app / "apps/web/app/(app)/custom/page.tsx"
    hand.parent.mkdir(parents=True)
    hand.write_text("export default function Page() { return null; }\n", encoding="utf-8")
    assert stale_generated_pages(app, files) == ["apps/web/app/(app)/old/page.tsx"]  # hand-written pages are left alone


def test_app_map_is_validated(tmp_path):
    app = _app(tmp_path, "select empno, ename, dname from emp")
    path = app / "ui/app-map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["pages"]["1"]["route"] = "/Bad Route"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SystemExit, match="route"):
        generate(app)
    path.unlink()
    with pytest.raises(SystemExit, match="--init-map"):
        generate(app)


# ----------------------------------------------------------------------------------------------- snapshot query
def _branches(text):
    return {re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.startswith("union all select")}


def test_snapshot_query_of_the_pilot_is_current_and_equals_the_proven_query():
    load = lambda rel: json.loads((PILOT / rel).read_text(encoding="utf-8"))  # noqa: E731
    sql = build_snapshot_query(load("db/schema-plan.json"), catalog=load("db/target-catalog.json"),
                               config=load("migration/snapshot-config.json"),
                               title="application 170134 (Demo Permintaan Barang)")
    assert (PILOT / "migration/oracle/snapshot_apex_workshop.generated.sql").read_text(encoding="utf-8") == sql
    proven = (PILOT / "migration/oracle/extract_snapshot_apex_workshop.sql").read_text(encoding="utf-8")
    assert _branches(sql) == _branches(proven) and len(_branches(sql)) == 38  # 19 counts, 9 tables, 10 views
    session = lambda t: re.sub(r"\s+", " ", t[t.index("select 'SNAPSHOT'"):t.index("from dual")])  # noqa: E731
    assert session(sql) == session(proven)
    assert sql.rstrip().endswith("order by section, obj, pk") and ":" not in sql.split("from dual")[1].replace("::", "")


def test_snapshot_query_keys_and_refusals():
    plan = {"tables": [{"name": "T", "emit": True, "constraints": [{"kind": "PRIMARY KEY", "columns": ["A", "D", "N"]}],
                        "columns": [{"name": "A", "typeFamily": "text"}, {"name": "D", "typeFamily": "timestamp"},
                                    {"name": "N", "typeFamily": "numeric"}]}],
            "views": [{"name": "V", "emit": True, "columns": None, "outputColumns": ["X", "Y"]}]}
    sql = build_snapshot_query(plan)
    assert "'ROW', 'T', a || '|' || to_char(d, 'YYYY-MM-DD\"T\"HH24:MI:SS') || '|' || to_char(n), json_object(" in sql
    assert "'VIEW', 'V', to_char(x), json_object(" in sql and "pkg_app_user" not in sql
    assert "where c.table_name in ('T')" in sql
    assert "'VIEW', 'V', y || '|' || to_char(x)," in build_snapshot_query(
        plan, config={"viewKeys": {"V": ["Y", "X"]}}, catalog={"relations": {"v": {"y": "text", "x": "bigint"}}})
    with pytest.raises(ValueError, match="appUserExpr"):
        build_snapshot_query(plan, config={"appUserExpr": "x; drop table t"})
    with pytest.raises(ValueError, match="not in the plan"):
        build_snapshot_query(plan, config={"viewKeys": {"NOPE": ["A"]}})
    with pytest.raises(ValueError, match="no primary key"):
        build_snapshot_query({"tables": [{"name": "T", "constraints": [], "columns": []}], "views": []})
