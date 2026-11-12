"""R4a: supporting-object install scripts decoded from an APEX export, and comments of views that are not emitted."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from apex2next_extractor.supporting_objects import (DecodeError, decode_expression, read_supporting_objects,
                                                    render_install_sql)

ROOT = Path(__file__).resolve().parents[1]

HEADER = """prompt --application/deployment/install/{name}
begin
wwv_flow_imp.component_begin (p_version_yyyy_mm_dd=>'2026.04.07', p_release=>'26.2.0', p_default_workspace_id=>20
,p_default_application_id=>100, p_default_id_offset=>0, p_default_owner=>'ORACLE');
wwv_flow_imp.g_varchar2_table := wwv_flow_imp.empty_varchar2_table;
"""
FOOTER = """wwv_flow_imp_shared.create_install_script(
 p_id=>wwv_flow_imp.id(1)
,p_install_id=>wwv_flow_imp.id(2)
,p_name=>'{title}'
,p_sequence=>{seq}
,p_script_type=>'INSTALL'
{extra},p_script_clob=>wwv_flow_imp.varchar2_to_clob(wwv_flow_imp.g_varchar2_table)
);
wwv_flow_imp.component_end;
end;
/
"""


def _export(tmp_path: Path) -> Path:
    d = tmp_path / "f100/application/deployment/install"
    d.mkdir(parents=True)
    # split mid-word across table entries, quotes doubled, LF constants, UNISTR over a concatenation (as APEX writes)
    (d / "install_tables.sql").write_text(HEADER.format(name="install_tables") + """wwv_flow_imp.g_varchar2_table(1) := 'create table t ('||wwv_flow.LF||
'  id number primary key, name varchar2(30) default ''x'''||wwv_flow.LF||
');'||wwv_flow.LF||
'comment on table t is ''Caf';
wwv_flow_imp.g_varchar2_table(2) := unistr('\\00E9 '||wwv_flow.LF||
'\\2014 a\\\\b'';')||wwv_flow.LF||
'';
""" + FOOTER.format(title="Create Tables", seq=10, extra=""), encoding="utf-8")
    (d / "install_data.sql").write_text(HEADER.format(name="install_data") + """wwv_flow_imp.g_varchar2_table(1) := 'insert into t values (1, ''a'');';
""" + FOOTER.format(title="Load Data", seq=20, extra=",p_condition_type=>'EXISTS'\n,p_condition=>'select 1 from dual'\n"),
                                       encoding="utf-8")
    return tmp_path / "f100"


def test_scripts_are_decoded_in_install_order(tmp_path):
    scripts = read_supporting_objects(_export(tmp_path))
    assert [(s.sequence, s.name) for s in scripts] == [(10, "Create Tables"), (20, "Load Data")]
    assert scripts[0].text == ("create table t (\n  id number primary key, name varchar2(30) default 'x'\n);\n"
                               "comment on table t is 'Café \n— a\\b';\n")
    assert scripts[1].condition == {"condition_type": "EXISTS", "condition": "select 1 from dual"}
    sql = render_install_sql(scripts, title="f100")
    assert sql.index("Create Tables") < sql.index("Load Data") and '-- condition: {"condition_type": "EXISTS"' in sql


def test_unknown_text_is_an_error_with_file_and_line(tmp_path):
    export = _export(tmp_path)
    bad = export / "application/deployment/install/install_bad.sql"
    bad.write_text(HEADER.format(name="install_bad") + "wwv_flow_imp.g_varchar2_table(1) := 'a'||my_fn('b');\n"
                   + FOOTER.format(title="Bad", seq=30, extra=""), encoding="utf-8")
    with pytest.raises(DecodeError, match=r"deployment/install/install_bad.sql:6: unexpected text"):
        read_supporting_objects(export)
    with pytest.raises(DecodeError, match="unterminated"):
        decode_expression("'abc", 0)


def test_cli_writes_install_sql_that_schema_plan_reads(tmp_path):
    export = _export(tmp_path)
    cli = [sys.executable, str(ROOT / "tools/apex2next")]
    r = subprocess.run([*cli, "supporting-objects", export, "--out", tmp_path / "so"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    manifest = json.loads((tmp_path / "so/supporting-objects.json").read_text())
    assert [s["name"] for s in manifest["scripts"]] == ["Create Tables", "Load Data"]
    r = subprocess.run([*cli, "schema-plan", tmp_path / "so/install.sql", "--out", tmp_path / "plan"],
                       capture_output=True, text=True)
    plan = json.loads((tmp_path / "plan/schema-plan.json").read_text())
    assert [t["name"] for t in plan["tables"]] == ["T"]
    assert "COMMENT ON TABLE app.t IS 'Café \n— a\\b';" in (tmp_path / "plan/0001_schema.sql").read_text()


def test_comment_on_a_view_that_is_not_emitted_is_not_written(tmp_path):
    ddl = tmp_path / "install.sql"
    ddl.write_text("create table t (id number primary key, v varchar2(10));\n"
                   "create or replace view t_v as select id, my_pkg.f(v) v from t;\n"
                   "comment on table t_v is 'Manual view';\n"
                   "comment on column t_v.id is 'Key';\n"
                   "comment on table t is 'Table';\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "tools/apex2next"), "schema-plan", ddl, "--out", tmp_path / "plan"],
                       capture_output=True, text=True)
    sql = (tmp_path / "plan/0001_schema.sql").read_text()
    assert "COMMENT ON TABLE app.t IS 'Table';" in sql, r.stdout + r.stderr
    assert "t_v" not in sql.split("-- Comments")[1].split("-- Not emitted")[0]
