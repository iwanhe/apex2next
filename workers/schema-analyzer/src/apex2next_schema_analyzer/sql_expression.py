"""Token-level Oracle SQL expression/query conversion for PostgreSQL (WP9.3).

Only explicit, registered rewrites are applied; every rewrite and every
Oracle-specific construct that is *not* rewritten produces a stable finding
with a disposition. Unknown functions are never assumed to be portable.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .sql_tokens import Token, identifier_name, pg_string_literal, string_value

DISPOSITION_RANK = {"AUTOMATIC": 0, "ASSISTED": 1, "MANUAL": 2, "UNSUPPORTED": 3}

# code: (disposition, description)
EXPRESSION_RULES: dict[str, tuple[str, str]] = {
    "EXP001": ("ASSISTED", "NVL rewritten to COALESCE; verify empty-string and type-coercion semantics."),
    "EXP002": ("ASSISTED", "SYSDATE rewritten to LOCALTIMESTAMP(0); confirm database/session timezone policy."),
    "EXP003": ("ASSISTED", "SYSTIMESTAMP rewritten to CURRENT_TIMESTAMP; confirm timezone policy."),
    "EXP004": ("ASSISTED", "FROM DUAL removed (PostgreSQL SELECT without FROM)."),
    "EXP005": ("ASSISTED", "|| concatenation: Oracle treats NULL as '' but PostgreSQL returns NULL; wrap operands in COALESCE where NULLs are possible."),
    "EXP006": ("ASSISTED", "Empty string literal: Oracle '' is NULL, PostgreSQL '' is a value."),
    "EXP007": ("ASSISTED", "MINUS rewritten to EXCEPT."),
    "EXP008": ("AUTOMATIC", "Oracle q-quoted/national literal normalized to a standard PostgreSQL literal."),
    "EXP009": ("MANUAL", "PL/SQL package/function call has no PostgreSQL target yet; requires a target function or service-side redesign."),
    "EXP010": ("MANUAL", "Oracle-specific function requires an explicit target rewrite."),
    "EXP011": ("MANUAL", "Oracle pseudo-column or session function requires redesign."),
    "EXP012": ("MANUAL", "Oracle (+) outer-join syntax must be rewritten to ANSI joins."),
    "EXP013": ("UNSUPPORTED", "Hierarchical/PIVOT/MODEL query construct has no registered conversion."),
    "EXP014": ("MANUAL", "Unknown function; portability is not assumed."),
    "EXP015": ("ASSISTED", "Function exists in PostgreSQL but NULL/empty-string/edge semantics differ."),
    "EXP016": ("ASSISTED", "Source schema owner prefix removed; target schema is resolved through search_path."),
    "EXP017": ("MANUAL", "Bind variable or APEX substitution string requires a trusted server-side value."),
    "EXP018": ("ASSISTED", "Division: PostgreSQL integer/integer truncates; verify operand types."),
    "EXP019": ("ASSISTED", "TRUNC(SYSDATE) rewritten to CAST(CURRENT_DATE AS timestamp(0)); confirm timezone policy."),
    "EXP020": ("MANUAL", "Unresolved object reference after FROM/JOIN."),
}

SQL_KEYWORDS = frozenset("""
ALL AND ANY AS ASC BETWEEN BY CASE CAST CROSS CURRENT_DATE CURRENT_TIMESTAMP DESC DISTINCT
ELSE END ESCAPE EXCEPT EXISTS FALSE FETCH FIRST FOLLOWING FOR FROM FULL GROUP HAVING IN INNER
INTERSECT INTERVAL INTO IS JOIN LAST LATERAL LEFT LIKE LIMIT LOCALTIMESTAMP NATURAL NEXT NOT
NULL NULLS OF OFFSET ON ONLY OR ORDER OUTER OVER PARTITION PRECEDING RANGE RIGHT ROW ROWS
SELECT SET SOME THEN TIES TRUE UNBOUNDED UNION USING VALUES WHEN WHERE WITH WITHIN FILTER
CURRENT AT ZONE YEAR MONTH DAY HOUR MINUTE SECOND
""".split())

PORTABLE_FUNCTIONS = frozenset("""
COALESCE NULLIF UPPER LOWER ABS ROUND CEIL FLOOR MOD POWER SQRT EXP LN SIGN COUNT SUM MIN MAX
AVG REPLACE LPAD RPAD TRIM LTRIM RTRIM CONCAT ROW_NUMBER RANK DENSE_RANK LAG LEAD FIRST_VALUE
LAST_VALUE NTILE STDDEV VARIANCE EXTRACT CAST INITCAP CHR ASCII
""".split())
SEMANTIC_DIFF_FUNCTIONS = frozenset({"LENGTH", "SUBSTR", "GREATEST", "LEAST"})
IMMUTABLE_FUNCTIONS = frozenset({"COALESCE", "NULLIF", "UPPER", "LOWER", "ABS", "ROUND", "CEIL",
                                 "FLOOR", "MOD", "POWER", "TRIM", "LTRIM", "RTRIM", "LPAD", "RPAD",
                                 "REPLACE", "SIGN", "SUBSTR", "LENGTH"})
ORACLE_FUNCTIONS = frozenset("""
DECODE NVL2 TO_CHAR TO_DATE TO_NUMBER TO_TIMESTAMP TRUNC ADD_MONTHS MONTHS_BETWEEN LAST_DAY
NEXT_DAY INSTR REGEXP_LIKE REGEXP_SUBSTR REGEXP_REPLACE REGEXP_INSTR REGEXP_COUNT LISTAGG
SYS_CONTEXT V NV USERENV SYS_GUID RAWTOHEX HEXTORAW DUMP VSIZE TO_CLOB TO_NCHAR LNNVL
SYS_EXTRACT_UTC FROM_TZ NEW_TIME NUMTODSINTERVAL NUMTOYMINTERVAL WM_CONCAT XMLAGG XMLELEMENT
JSON_VALUE JSON_QUERY JSON_TABLE JSON_OBJECT JSON_ARRAYAGG STANDARD_HASH ORA_HASH
""".split())
PSEUDO_COLUMNS = frozenset({"ROWNUM", "ROWID", "LEVEL", "USER", "UID", "ORA_ROWSCN"})
UNSUPPORTED_WORDS = {"CONNECT": "BY", "PRIOR": None, "PIVOT": None, "UNPIVOT": None,
                     "MODEL": None}
FROM_TERMINATORS = frozenset({"WHERE", "GROUP", "ORDER", "UNION", "INTERSECT", "MINUS",
                              "EXCEPT", "HAVING", "FETCH", "CONNECT", "START"})

PG_RESERVED = frozenset("""
ALL ANALYSE ANALYZE AND ANY ARRAY AS ASC ASYMMETRIC BOTH CASE CAST CHECK COLLATE COLUMN
CONSTRAINT CREATE CURRENT_CATALOG CURRENT_DATE CURRENT_ROLE CURRENT_TIME CURRENT_TIMESTAMP
CURRENT_USER DEFAULT DEFERRABLE DESC DISTINCT DO ELSE END EXCEPT FALSE FETCH FOR FOREIGN FROM
GRANT GROUP HAVING IN INITIALLY INTERSECT INTO LATERAL LEADING LIMIT LOCALTIME LOCALTIMESTAMP
NOT NULL OFFSET ON ONLY OR ORDER PLACING PRIMARY REFERENCES RETURNING SELECT SESSION_USER SOME
SYMMETRIC SYSTEM_USER TABLE THEN TO TRAILING TRUE UNION UNIQUE USER USING VARIADIC WHEN WHERE
WINDOW WITH
""".split())


def pg_ident(name: str) -> str:
    """Target identifier: lower_snake_case; quoted only when required."""
    lowered = name.lower()
    if (lowered.replace("_", "a").isalnum() and lowered.isascii() and not lowered[:1].isdigit()
            and lowered.upper() not in PG_RESERVED and lowered == lowered.lower()):
        return lowered
    return '"' + lowered.replace('"', '""') + '"'


@dataclass
class ExpressionResult:
    sql: str
    findings: list[dict] = field(default_factory=list)
    identifiers: set[str] = field(default_factory=set)
    object_refs: set[str] = field(default_factory=set)
    unresolved_refs: set[str] = field(default_factory=set)
    functions: set[str] = field(default_factory=set)
    plsql_calls: set[str] = field(default_factory=set)
    has_subquery: bool = False

    @property
    def disposition(self) -> str:
        worst = "AUTOMATIC"
        for f in self.findings:
            if DISPOSITION_RANK[f["disposition"]] > DISPOSITION_RANK[worst]:
                worst = f["disposition"]
        return worst

    def codes(self) -> set[str]:
        return {f["code"] for f in self.findings}


def _finding(code: str, detail: str | None = None) -> dict:
    disposition, message = EXPRESSION_RULES[code]
    out = {"code": code, "disposition": disposition, "message": message}
    if detail:
        out["detail"] = detail
    return out


def convert_expression(tokens: list[Token], *, known_objects: frozenset[str] | set[str] = frozenset(),
                       source_schemas: frozenset[str] | set[str] = frozenset()) -> ExpressionResult:
    """Rewrite an Oracle expression/query token list to PostgreSQL text.

    ``tokens`` must include whitespace/comment tokens so layout is preserved.
    ``known_objects`` are Oracle (upper-case) table/view names used to record
    dependencies and detect unresolved FROM/JOIN references.
    """
    out = [t.text for t in tokens]
    sig = [i for i, t in enumerate(tokens) if t.significant]
    result = ExpressionResult(sql="")
    seen: set[tuple[str, str]] = set()

    def add(code: str, detail: str | None = None) -> None:
        key = (code, detail or "")
        if key not in seen:
            seen.add(key)
            result.findings.append(_finding(code, detail))

    def tok(k: int) -> Token | None:
        return tokens[sig[k]] if 0 <= k < len(sig) else None

    def is_op(k: int, text: str) -> bool:
        t = tok(k)
        return t is not None and t.kind == "OP" and t.text == text

    def word(k: int) -> str | None:
        t = tok(k)
        return t.upper if t is not None and t.kind == "IDENT" else None

    def blank(k: int) -> None:
        out[sig[k]] = ""

    k = 0
    while k < len(sig):
        t = tok(k)
        assert t is not None
        if t.kind == "STRING":
            raw = t.text
            if raw[:1] in "qQ" or raw[:2].upper() == "NQ":
                out[sig[k]] = pg_string_literal(string_value(t))
                add("EXP008")
            elif raw[:1] in "nN":
                out[sig[k]] = pg_string_literal(string_value(t))
                add("EXP008")
            if string_value(t) == "":
                add("EXP006")
            k += 1
            continue
        if t.kind == "BIND":
            add("EXP017", t.text)
            k += 1
            continue
        if t.kind == "OP":
            if t.text == "||":
                add("EXP005")
            elif t.text == "/":
                add("EXP018")
            elif t.text == "&":
                add("EXP017", "&substitution")
            elif t.text == "(" and is_op(k + 1, "+") and is_op(k + 2, ")"):
                add("EXP012")
                k += 3
                continue
            elif t.text == "(" and word(k + 1) == "SELECT":
                result.has_subquery = True
            k += 1
            continue
        if t.kind == "NUMBER":
            k += 1
            continue
        # IDENT / QIDENT
        name = identifier_name(t)
        upper = name.upper() if t.kind == "IDENT" else name
        prev_dot = is_op(k - 1, ".")

        # Qualified names: a.b, owner.object, pkg.fn(, owner.pkg.fn(
        if not prev_dot and is_op(k + 1, ".") and tok(k + 2) is not None and tok(k + 2).kind in {"IDENT", "QIDENT"}:
            second = identifier_name(tok(k + 2))
            third_dot = is_op(k + 3, ".") and tok(k + 4) is not None and tok(k + 4).kind in {"IDENT", "QIDENT"}
            if third_dot and is_op(k + 5, "("):
                result.plsql_calls.add(f"{second}.{identifier_name(tok(k + 4))}")
                add("EXP009", f"{name}.{second}.{identifier_name(tok(k + 4))}")
                k += 5
                continue
            if is_op(k + 3, "("):
                if upper in source_schemas:
                    result.plsql_calls.add(second)
                else:
                    result.plsql_calls.add(f"{name}.{second}")
                add("EXP009", f"{name}.{second}")
                k += 3
                continue
            if upper in source_schemas:
                blank(k)
                blank(k + 1)
                add("EXP016", f"{name}.{second}")
                if second in known_objects:
                    result.object_refs.add(second)
                k += 2
                continue
            # alias.column
            result.identifiers.add(upper)
            k += 1
            continue

        if prev_dot:
            if t.kind == "QIDENT":
                out[sig[k]] = pg_ident(name)
            result.identifiers.add(upper)
            k += 1
            continue

        nxt_paren = is_op(k + 1, "(")
        if t.kind == "IDENT" and upper in UNSUPPORTED_WORDS:
            follow = UNSUPPORTED_WORDS[upper]
            if follow is None or word(k + 1) == follow:
                add("EXP013", upper)
                k += 1
                continue
        if t.kind == "IDENT" and upper == "START" and word(k + 1) == "WITH":
            add("EXP013", "START WITH")
            k += 2
            continue
        if t.kind == "IDENT" and upper == "FROM" and word(k + 1) == "DUAL":
            follow = tok(k + 2)
            if follow is None or (follow.kind == "OP" and follow.text in {")", ";"}) or (
                    follow.kind == "IDENT" and follow.upper in FROM_TERMINATORS):
                for idx in range(sig[k], sig[k + 1] + 1):
                    out[idx] = ""
                # drop the whitespace directly before FROM to keep output tidy
                before = sig[k] - 1
                if before >= 0 and tokens[before].kind == "WS":
                    out[before] = "\n" if "\n" in tokens[before].text else ""
                add("EXP004")
                k += 2
                continue
        if t.kind == "IDENT" and upper in {"FROM", "JOIN"}:
            target = tok(k + 1)
            if target is not None and target.kind in {"IDENT", "QIDENT"}:
                tname = identifier_name(target)
                tup = tname.upper() if target.kind == "IDENT" else tname
                if not (is_op(k + 2, ".")) and tup not in known_objects and tup not in SQL_KEYWORDS \
                        and tup not in {"DUAL", "LATERAL", "ONLY", "TABLE"}:
                    result.unresolved_refs.add(tup)
                    add("EXP020", tup)
            k += 1
            continue
        if t.kind == "IDENT" and upper == "MINUS":
            out[sig[k]] = "EXCEPT"
            add("EXP007")
            k += 1
            continue
        if t.kind == "IDENT" and upper == "SYSDATE":
            out[sig[k]] = "LOCALTIMESTAMP(0)"
            add("EXP002")
            k += 1
            continue
        if t.kind == "IDENT" and upper == "SYSTIMESTAMP":
            out[sig[k]] = "CURRENT_TIMESTAMP"
            add("EXP003")
            k += 1
            continue
        if nxt_paren and t.kind == "IDENT" and upper not in SQL_KEYWORDS:
            if upper == "TRUNC" and word(k + 2) == "SYSDATE" and is_op(k + 3, ")"):
                out[sig[k]] = "CAST(CURRENT_DATE AS timestamp(0))"
                for j in (k + 1, k + 2, k + 3):
                    blank(j)
                for idx in range(sig[k] + 1, sig[k + 3]):
                    out[idx] = ""
                add("EXP019")
                k += 4
                continue
            result.functions.add(upper)
            if upper == "NVL":
                out[sig[k]] = "COALESCE"
                add("EXP001")
            elif upper in PORTABLE_FUNCTIONS:
                pass
            elif upper in SEMANTIC_DIFF_FUNCTIONS:
                add("EXP015", upper)
            elif upper in ORACLE_FUNCTIONS:
                add("EXP010", upper)
            else:
                result.plsql_calls.add(upper)
                add("EXP014", upper)
            k += 1
            continue
        if t.kind == "IDENT" and upper in PSEUDO_COLUMNS:
            add("EXP011", upper)
            k += 1
            continue
        if t.kind == "QIDENT":
            out[sig[k]] = pg_ident(name)
        if upper not in SQL_KEYWORDS:
            result.identifiers.add(upper)
            if upper in known_objects:
                result.object_refs.add(upper)
        k += 1

    result.sql = "".join(out)
    return result
