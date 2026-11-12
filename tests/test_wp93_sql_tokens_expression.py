from apex2next_schema_analyzer.sql_expression import convert_expression
from apex2next_schema_analyzer.sql_tokens import render, split_script, tokenize


def _convert(sql, **kw):
    return convert_expression(tokenize(sql), **kw)


def test_tokenizer_is_lossless_including_q_quotes_and_quoted_identifiers():
    text = "select q'[it's]' a, n'x' b, \"Mixed\"\"Name\" c -- tail ;\nfrom dual /* c */"
    assert render(tokenize(text)) == text


def test_splitter_handles_sqlplus_plsql_slash_and_semicolons_in_literals():
    script = (
        "SET DEFINE OFF\n"
        "PROMPT it's a prompt with an apostrophe\n"
        "create table t (id number, v varchar2(10) default ';');\n"
        "create or replace package p as\n  procedure x; -- ;\nend p;\n/\n"
        "insert into t (v) values ('a;b');\n"
        "/\n"
        "commit;\n"
        "@child.sql\n"
    )
    kinds = [(s.kind, s.line) for s in split_script(script)]
    assert kinds == [("SQLPLUS", 1), ("SQLPLUS", 2), ("TABLE", 3), ("PACKAGE", 4), ("DML", 8),
                     ("TCL", 10), ("SQLPLUS", 11)]


def test_unterminated_literal_becomes_error_statement_not_silent_loss():
    statements = split_script("create table t (v varchar2(5) default 'x);\n")
    assert statements[-1].kind == "ERROR"


def test_registered_rewrites_nvl_sysdate_trunc_dual_minus():
    res = _convert("select nvl(a, 0), sysdate, trunc(sysdate) from dual minus select 1, 2, 3 from dual")
    assert "COALESCE(a, 0)" in res.sql
    assert "LOCALTIMESTAMP(0)" in res.sql
    assert "CAST(CURRENT_DATE AS timestamp(0))" in res.sql
    assert "dual" not in res.sql.lower()
    assert "EXCEPT" in res.sql
    assert {"EXP001", "EXP002", "EXP019", "EXP004", "EXP007"} <= res.codes()
    assert res.disposition == "ASSISTED"


def test_literals_and_comments_are_not_rewritten():
    res = _convert("select 'nvl(x, sysdate) from dual' -- nvl(\n from t", known_objects={"T"})
    assert "'nvl(x, sysdate) from dual'" in res.sql
    assert res.codes() == set()


def test_package_calls_and_oracle_functions_are_manual_never_assumed_portable():
    res = _convert("select pkg.fn(id), decode(a, 1, 'x'), my_fn(b) from t", known_objects={"T"})
    assert res.plsql_calls == {"PKG.FN", "MY_FN"}
    assert {"EXP009", "EXP010", "EXP014"} <= res.codes()
    assert res.disposition == "MANUAL"


def test_hierarchical_query_is_unsupported():
    res = _convert("select id from t start with parent_id is null connect by prior id = parent_id",
                   known_objects={"T"})
    assert res.disposition == "UNSUPPORTED"


def test_concat_null_semantics_and_empty_string_are_flagged():
    res = _convert("select a || b, '' from t", known_objects={"T"})
    assert {"EXP005", "EXP006"} <= res.codes()


def test_unresolved_from_reference_and_owner_prefix():
    res = _convert("select * from owner1.t1 join missing_tab m on 1 = 1",
                   known_objects={"T1"}, source_schemas={"OWNER1"})
    assert res.object_refs == {"T1"}
    assert res.unresolved_refs == {"MISSING_TAB"}
    assert "owner1." not in res.sql.lower()
    assert {"EXP016", "EXP020"} <= res.codes()
