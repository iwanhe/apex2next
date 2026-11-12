"""R3: Oracle -> PostgreSQL translation of APEX region and LOV queries."""
from apex2next_schema_analyzer.region_sql import REGION_RULES, translate_lov, translate_query
from apex2next_schema_analyzer.sql_expression import convert_expression
from apex2next_schema_analyzer.sql_tokens import tokenize

KNOWN = {"APX_DEMO_REQUESTS_V", "APX_DEMO_REQUEST_LINES_V", "APX_DEMO_DEPARTMENTS", "APX_DEMO_REQUEST_LINES",
         "APX_DEMO_ROLES", "EMP", "DEPT"}


def _q(sql, **kw):
    return translate_query(sql, known_objects=KNOWN, **kw)


def test_plain_column_list_is_recognized_and_schema_qualified():
    q = _q("select request_id\n      ,request_no\n  from apx_demo_requests_v")
    assert q.disposition == "AUTOMATIC" and q.binds == [] and q.columns == ["request_id", "request_no"]
    assert q.simple == {"view": "apx_demo_requests_v", "select": ["request_id", "request_no"]}
    assert "from app.apx_demo_requests_v" in q.sql


def test_to_number_bind_becomes_a_positional_parameter():
    q = _q("select line_id, qty from apx_demo_request_lines_v\n where request_id = to_number(:P302_REQUEST_ID)")
    assert q.binds == ["P302_REQUEST_ID"] and q.disposition == "ASSISTED" and "RGN002" in q.codes()
    assert q.simple["where"] == {"sql": "request_id = $1", "source": "request_id = to_number(:P302_REQUEST_ID)"}
    assert q.sql.endswith("where request_id = $1")


def test_binds_are_numbered_by_first_use_and_reused():
    q = _q("select e.ename from emp e join dept d on d.deptno = e.deptno "
           "where e.mgr = :P1_MGR and e.job = v('P1_JOB') and e.boss = :p1_mgr and e.owner = :APP_USER order by 1")
    assert q.binds == ["P1_MGR", "P1_JOB", "APP_USER"]
    assert "e.mgr = $1 and e.job = $2 and e.boss = $1 and e.owner = $3" in q.sql
    assert "from app.emp e join app.dept d" in q.sql and q.simple is None and q.order_by == "1"


def test_nvl2_decode_and_nested_calls_are_rewritten():
    q = _q("select nvl2(comm, 'Y', 'N') a, decode(deptno, 10, 'A', nvl(x, 20), decode(y, 1, 'B'), 'Z') b from emp")
    assert q.disposition == "ASSISTED" and {"RGN004", "RGN005", "EXP001"} <= set(q.codes())
    assert "CASE WHEN (comm) IS NOT NULL THEN 'Y' ELSE 'N' END a" in q.sql
    assert ("CASE WHEN (deptno) IS NOT DISTINCT FROM 10 THEN 'A' WHEN (deptno) IS NOT DISTINCT FROM COALESCE(x, 20) "
            "THEN CASE WHEN (y) IS NOT DISTINCT FROM 1 THEN 'B' END ELSE 'Z' END b") in q.sql


def test_comma_joins_subqueries_and_owner_prefix_are_qualified():
    q = _q("select a from emp, dept where emp.d = dept.d and exists (select 1 from WKSP.dept x where x.a = emp.a)",
           source_schemas={"WKSP"})
    assert q.sql == "select a from app.emp, app.dept where emp.d = dept.d and exists (select 1 from app.dept x where x.a = emp.a)"


def test_extract_from_is_not_a_table_reference():
    q = _q("select ename from emp where extract(year from hiredate) = 2020 and trim(both ' ' from ename) = 'A'")
    assert q.disposition == "AUTOMATIC", q.findings
    assert "extract(year from hiredate)" in q.sql
    # the WP9.3 converter itself no longer reports the column as an unresolved object
    assert "EXP020" not in convert_expression(tokenize("select extract(year from d) y from emp"), known_objects={"EMP"}).codes()


def test_untranslatable_queries_are_reported_and_not_emitted():
    cases = {
        "declare x number; begin return 'select 1 from dual'; end;": "RGN007",
        "select a from emp e, dept d where e.d = d.d(+)": "EXP012",
        "select a from emp where ename like '&P1_X.%'": "RGN013",
        "select a from emp where b = &P1_X.": "EXP017",
        "select a from other_table": "EXP020",
        "select level from emp connect by prior empno = mgr": "EXP013",
        "select a from emp where b = v(c)": "RGN012",
        "select 'x from emp": "RGN008",
    }
    for sql, code in cases.items():
        q = _q(sql)
        assert code in q.codes(), (sql, q.findings)
        assert q.disposition in {"MANUAL", "UNSUPPORTED"} and q.sql is None and q.simple is None and not q.usable


def test_lov_order_column_and_numeric_sort():
    numeric = {"APX_DEMO_REQUEST_LINES": {"LINE_ID"}}
    dept = translate_lov("select dept_code || ' - ' || dept_name d, department_id r\n  from apx_demo_departments\n"
                         " where active_yn = 'Y'\n order by 1", known_objects=KNOWN, numeric_columns=numeric)
    assert dept["sql"] == ("select dept_code || ' - ' || dept_name d, department_id r from app.apx_demo_departments "
                           "where active_yn = 'Y'")
    assert (dept["orderBy"], dept["numeric"], dept["disposition"]) == ("d", False, "ASSISTED")
    lines = translate_lov("select line_id d, line_id r from apx_demo_request_lines order by 1",
                          known_objects=KNOWN, numeric_columns=numeric)
    assert (lines["orderBy"], lines["numeric"], lines["disposition"]) == ("d", True, "AUTOMATIC")
    roles = translate_lov("select role_code || ' - ' || role_name d, role_code r from apx_demo_roles order by role_code",
                          known_objects=KNOWN)
    assert (roles["orderBy"], roles["numeric"]) == ("r", False)


def test_lov_shape_problems_are_manual():
    three = translate_lov("select a, b, c from dept order by 1", known_objects=KNOWN)
    assert three["sql"] is None and three["disposition"] == "MANUAL"
    odd = translate_lov("select dname, deptno from dept order by loc desc", known_objects=KNOWN)
    assert odd["sql"] is None and "RGN011" in {f["code"] for f in odd["findings"]}
    unordered = translate_lov("select dname, deptno from dept", known_objects=KNOWN)
    assert unordered["sql"] == "select dname, deptno from app.dept" and unordered["orderBy"] == "d"
    assert "RGN010" in {f["code"] for f in unordered["findings"]}


def test_rule_registry_dispositions_are_known():
    assert all(d in {"AUTOMATIC", "ASSISTED", "MANUAL", "UNSUPPORTED"} for d, _ in REGION_RULES.values())


def test_one_line_sql_keeps_string_literals_and_drops_comments():
    from apex2next_schema_analyzer.region_sql import collapse_sql
    assert collapse_sql("select 'a  b' x -- note\n  from t /* c */ where y = 'p\n q'") == "select 'a  b' x from t where y = 'p\n q'"
    lov = translate_lov("select dname || '  -  ' || loc d, -- display\n deptno r\n from dept order by 1", known_objects=KNOWN)
    assert lov["sql"] == "select dname || '  -  ' || loc d, deptno r from app.dept"


def test_lov_order_by_columns_that_are_not_selected():
    """R4a: `order by display_order` (a column the LOV does not show) is carried as extra columns o1..on."""
    cols = {"EBA_STATUS": {"CD", "DESCRIPTION", "DISPLAY_ORDER", "UPDATED"}}
    numeric = {"EBA_STATUS": {"DISPLAY_ORDER"}}
    lov = translate_lov("select description d, cd r\nfrom eba_status\norder by display_order, updated desc",
                        known_objects={"EBA_STATUS"}, numeric_columns=numeric, object_columns=cols)
    assert lov["sql"] == "select description d, cd r, display_order, updated from app.eba_status"
    assert lov["orderBy"] == "o" and lov["order"] == [{"dir": "ASC", "numeric": True}, {"dir": "DESC"}]
    assert "RGN011" not in {f["code"] for f in lov["findings"]}
    # unknown column or no catalog: still manual
    unknown = translate_lov("select description d, cd r from eba_status order by nope",
                            known_objects={"EBA_STATUS"}, numeric_columns=numeric, object_columns=cols)
    no_catalog = translate_lov("select description d, cd r from eba_status order by display_order",
                               known_objects={"EBA_STATUS"})
    assert unknown["sql"] is None and no_catalog["sql"] is None
