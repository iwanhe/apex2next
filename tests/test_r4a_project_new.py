"""R4a: runnable project skeleton, generic form DML flag, authorization scheme rules, login page, home page."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import test_r4a_page_composer as composer  # noqa: E402
from apex2next_schema_analyzer.app_generator import generate  # noqa: E402
from apex2next_schema_analyzer.project_new import TEMPLATE, create_project  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _with_plan_files(app: Path) -> Path:
    (app / "db/0001_schema.sql").write_text("CREATE SCHEMA IF NOT EXISTS app;\n", encoding="utf-8")
    return app


def test_project_skeleton_is_copied_with_placeholders_and_never_overwrites(tmp_path):
    app = _with_plan_files(composer._app(tmp_path))
    (app / "apps/api/src/business").mkdir(parents=True)
    (app / "apps/api/src/business/security.ts").write_text("// reviewed\n", encoding="utf-8")
    out = create_project(app, oracle_schema="WKSP_DEMO", runtime="link")
    assert "apps/api/src/business/security.ts" in out["kept"]
    assert (app / "apps/api/src/business/security.ts").read_text() == "// reviewed\n"
    assert (app / "db/migrations/0001_schema.sql").exists() and (app / "db/migrations/0902_iam_account_roles.sql").exists()
    texts = [p.read_text(encoding="utf-8") for p in app.rglob("*") if p.is_file() and p.suffix in {".ts", ".tsx", ".json", ".yaml"}]
    assert not any("__APP_SLUG__" in t or "__ORACLE_SCHEMA__" in t or "__RUNTIME_PACKAGES__" in t for t in texts)
    assert "'WKSP_DEMO'" in (app / "apps/api/src/app.module.ts").read_text()
    assert json.loads((app / "apps/api/package.json").read_text())["name"] == "@demo/api"
    assert "/packages/runtime-*" in (app / "pnpm-workspace.yaml").read_text()
    # nothing of the pilot leaks into the template
    for p in TEMPLATE.rglob("*"):
        if p.is_file() and p.suffix in {".ts", ".tsx", ".mjs", ".json", ".sql"}:
            text = p.read_text(encoding="utf-8").lower()
            assert "apx_demo" not in text and "170134" not in text and "wksp_kcsi" not in text, p


def test_generated_schemes_login_page_home_and_dml(tmp_path):
    app = composer._app(tmp_path)
    inv = json.loads((app / "ui/apex-page-inventory.json").read_text())
    inv["authorizations"] = [
        {"name": "Everyone", "type": "NATIVE_FUNCTION_BODY", "expression": "plsql_function_body\nreturn true;", "errorMessage": None},
        {"name": "Admins", "type": "NATIVE_IS_IN_GROUP", "expression": "name\nAdministrator,Contributor\ntype\nA", "errorMessage": "No."},
        {"name": "Staff", "type": "NATIVE_EXISTS", "expression": "sql_query\nselect 1 from emp where ename = :APP_USER", "errorMessage": None},
        {"name": "Custom", "type": "NATIVE_FUNCTION_BODY", "expression": "plsql_function_body\nreturn my_pkg.ok;", "errorMessage": None},
    ]
    inv["pages"].append({"id": 101, "name": "Login", "alias": "LOGIN", "title": "Login", "mode": "NORMAL", "components": [
        composer._c(101, "ITEM", "P101_USERNAME", display_as="NATIVE_TEXT_FIELD", prompt="User"),
        composer._c(101, "ITEM", "P101_PASSWORD", display_as="NATIVE_PASSWORD", prompt="Password"),
        composer._c(101, "BUTTON", "LOGIN", button_action="SUBMIT", button_image_alt="Sign In")]})
    inv["pages"][1]["components"] += [
        composer._c(2, "PROCESS", "Process Row of EMP", process_type="NATIVE_FORM_DML", process_point="AFTER_SUBMIT"),
        composer._c(2, "ITEM", "P2_ACTIVE", display_as="NATIVE_YES_NO", source="ACTIVE"),
        composer._c(2, "ITEM", "P2_PHOTO", display_as="NATIVE_FILE", source_type="ALWAYS_NULL")]
    (app / "ui/apex-page-inventory.json").write_text(json.dumps(inv))
    files, report = generate(app)
    schemes = files["apps/api/src/business/security-schemes.generated.ts"]
    assert "'Everyone': { name: 'Everyone', errorMessage: null, rule: { allow: true } }" in schemes
    assert "rule: { roles: ['ADMINISTRATOR', 'CONTRIBUTOR'] }" in schemes
    assert "rule: { exists: 'select 1 from app.emp where ename = $1', appUser: true, }" in schemes
    assert "'Custom': { name: 'Custom', errorMessage: null, rule: null }" in schemes
    assert [t["detail"] for t in report["todo"] if t["code"] == "GEN010"] == ["Custom"]
    routes = files["apps/web/lib/app-routes.generated.ts"]
    assert ("LOGIN_PAGE = { page: 101, username: 'P101_USERNAME', password: 'P101_PASSWORD', remember: null, "
            "button: 'LOGIN' } as const;") in routes
    assert "apps/web/app/(app)/page.tsx" in files and "PAGE_ROUTES[n.page!]" in files["apps/web/app/(app)/page.tsx"]
    assert "employee: { page: 2, region: 'Employee', dml: ['i', 'u', 'd'] }," in files["apps/api/src/pages/app-sources.generated.ts"]
    form = next(p for p in report["pages"] if p["id"] == 2)
    codes = {t["code"]: t["detail"] for t in form["todo"]}
    assert "GEN009" not in codes and codes["GEN024"] == "P2_ACTIVE (NATIVE_YES_NO)" and codes["GEN023"] == "P2_PHOTO (NATIVE_FILE)"
    # a table with source triggers that are not converted keeps the DML manual
    plan = json.loads((app / "db/schema-plan.json").read_text())
    plan["triggers"] = [{"name": "EMP_BIU", "table": "EMP", "emit": False}]
    (app / "db/schema-plan.json").write_text(json.dumps(plan))
    files, report = generate(app)
    assert "employee: { page: 2, region: 'Employee' }," in files["apps/api/src/pages/app-sources.generated.ts"]
    form = next(p for p in report["pages"] if p["id"] == 2)
    assert any(t["code"] == "GEN009" and "triggers that are not converted" in t["detail"] for t in form["todo"])


def test_generic_page_layer_compiles_against_the_runtime_contract():
    service = (TEMPLATE / "apps/api/src/pages/pages.service.ts").read_text()
    for name in ("insertRow", "updateRow", "deleteRow", "validateForInsert", "regionBinds", "lovSql"):
        assert name in service
    index = (ROOT / "packages/runtime-api/src/index.ts").read_text()
    assert "./generic/table-dml" in index and "./generic/schemes" in index


def test_form_with_an_ungenerated_lov_is_not_written_nor_linked(tmp_path):
    """GEN025: a select item whose shared LOV is manual would make the generated page fail when it opens."""
    app = composer._app(tmp_path)
    inv = json.loads((app / "ui/apex-page-inventory.json").read_text())
    inv["lovs"] = [{"name": "DEPTS", "location": "LOCAL", "query": "select dname, deptno from dept order by loc"}]
    inv["pages"][1]["components"].append(
        composer._c(2, "ITEM", "P2_DEPT", display_as="NATIVE_SELECT_LIST", source="DEPTNO", named_lov="DEPTS"))
    (app / "ui/apex-page-inventory.json").write_text(json.dumps(inv))
    files, report = generate(app)
    form = next(p for p in report["pages"] if p["id"] == 2)
    assert form["status"] == "MANUAL" and [t["detail"] for t in form["todo"] if t["code"] == "GEN025"] == ["P2_DEPT: DEPTS"]
    assert not any("pageId={2}" in body for body in files.values())
    listing = next(p for p in report["pages"] if p["id"] == 1)
    assert any(t["code"] == "GEN005" for t in listing["todo"])  # the row link to the form is left out
