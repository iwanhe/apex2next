"""R3 Oracle -> PostgreSQL translation of APEX region and LOV queries.

Built on the token-level expression converter of WP9.3 (``sql_expression``): only registered rewrites are
applied and every rewrite is a finding with a disposition. On top of it this module handles what region SQL
adds to plain view SQL:

* page-item and session binds (``:P302_REQUEST_ID``, ``v('P1_X')``) become positional ``$n`` parameters that
  the server supplies; no request text is ever concatenated into SQL;
* a few Oracle functions that are common in region queries (``NVL2``, ``DECODE``) are rewritten;
* objects after FROM/JOIN are qualified with the target schema, because the API does not rely on search_path.

A query with a MANUAL or UNSUPPORTED finding is reported and **not** emitted for execution.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .sql_expression import DISPOSITION_RANK, FROM_TERMINATORS, FUNCTION_FROM, SQL_KEYWORDS, convert_expression
from .sql_tokens import (Token, TokenizeError, find_matching, identifier_name, render, significant, split_top_level,
                         string_value, tokenize)

# code: (disposition, description)
REGION_RULES: dict[str, tuple[str, str]] = {
    "RGN001": ("AUTOMATIC", "Bind variable replaced by a positional parameter supplied by the server."),
    "RGN002": ("ASSISTED", "TO_NUMBER(:bind) reduced to the parameter; PostgreSQL takes the type from the compared column."),
    "RGN003": ("AUTOMATIC", "V()/NV() session-state call replaced by a positional parameter."),
    "RGN004": ("ASSISTED", "NVL2 rewritten to CASE WHEN ... IS NOT NULL."),
    "RGN005": ("ASSISTED", "DECODE rewritten to CASE with IS NOT DISTINCT FROM (DECODE treats NULL as equal to NULL)."),
    "RGN006": ("AUTOMATIC", "Object after FROM/JOIN qualified with the target schema."),
    "RGN007": ("MANUAL", "Not a single SELECT statement (PL/SQL function body returning SQL, or several statements)."),
    "RGN008": ("MANUAL", "Query text could not be tokenized."),
    "RGN009": ("MANUAL", "LOV query must return exactly two columns (display, return)."),
    "RGN010": ("ASSISTED", "LOV has no ORDER BY; the display column is used."),
    "RGN011": ("MANUAL", "LOV ORDER BY is not the display or the return column; choose the order by hand."),
    "RGN012": ("MANUAL", "V()/NV() argument is not a string literal."),
    "RGN013": ("MANUAL", "APEX substitution string (&ITEM.) inside a string literal; it needs a trusted server-side value."),
}

_PLACEHOLDER = "A2NBIND_{}_"
_PLACEHOLDER_RE = re.compile(r"\bA2NBIND_(\d+)_\b")


def _finding(code: str, detail: str | None = None) -> dict[str, Any]:
    disposition, message = REGION_RULES[code]
    out: dict[str, Any] = {"code": code, "disposition": disposition, "message": message}
    if detail:
        out["detail"] = detail
    return out


def worst_disposition(findings: list[dict[str, Any]]) -> str:
    worst = "AUTOMATIC"
    for f in findings:
        if DISPOSITION_RANK[f["disposition"]] > DISPOSITION_RANK[worst]:
            worst = f["disposition"]
    return worst


@dataclass
class TranslatedQuery:
    source: str
    sql: str | None = None
    binds: list[str] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    columns: list[str] | None = None
    order_by: str | None = None
    simple: dict[str, Any] | None = None
    objects: list[str] = field(default_factory=list)

    @property
    def disposition(self) -> str:
        return worst_disposition(self.findings)

    @property
    def usable(self) -> bool:
        return self.sql is not None and DISPOSITION_RANK[self.disposition] <= DISPOSITION_RANK["ASSISTED"]

    def codes(self) -> list[str]:
        return sorted({f["code"] for f in self.findings})


class _Context:
    def __init__(self) -> None:
        self.binds: list[str] = []
        self.findings: list[dict[str, Any]] = []
        self._seen: set[tuple[str, str]] = set()

    def add(self, code: str, detail: str | None = None) -> None:
        key = (code, detail or "")
        if key not in self._seen:
            self._seen.add(key)
            self.findings.append(_finding(code, detail))

    def placeholder(self, name: str) -> str:
        name = name.upper()
        if name not in self.binds:
            self.binds.append(name)
        return _PLACEHOLDER.format(self.binds.index(name) + 1)


def _clean(sql: str) -> str:
    return sql.strip().rstrip(";").strip()


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def collapse_sql(sql: str) -> str:
    """One-line form of executable SQL: white space collapsed and comments dropped, string literals untouched."""
    return _join_keeping_literals(tokenize(sql))


def _join_keeping_literals(tokens: list[Token]) -> str:
    out: list[str] = []
    for t in tokens:
        if t.kind in {"WS", "COMMENT"}:
            if out and out[-1] != " ":
                out.append(" ")
        else:
            out.append(t.text)
    return "".join(out).strip()


def _case_from_decode(args: list[str]) -> str:
    expr = args[0]
    pairs = args[1:]
    out = ["CASE"]
    while len(pairs) >= 2:
        out.append(f"WHEN ({expr}) IS NOT DISTINCT FROM {pairs[0]} THEN {pairs[1]}")
        pairs = pairs[2:]
    if pairs:
        out.append(f"ELSE {pairs[0]}")
    out.append("END")
    return " ".join(out)


def _rewrite_once(tokens: list[Token], ctx: _Context) -> str | None:
    """Apply the first applicable call/bind rewrite and return the new text, or None when nothing is left."""
    sig = [i for i, t in enumerate(tokens) if t.significant]

    def replace(first: int, last: int, text: str) -> str:
        return render(tokens[:first]) + text + render(tokens[last + 1:])

    for pos, i in enumerate(sig):
        t = tokens[i]
        if t.kind == "BIND":
            ctx.add("RGN001", t.text)
            return replace(i, i, ctx.placeholder(t.text[1:]))
        if t.kind != "IDENT" or t.upper not in {"TO_NUMBER", "V", "NV", "NVL2", "DECODE"}:
            continue
        if pos + 1 >= len(sig) or tokens[sig[pos + 1]].text != "(" or tokens[sig[pos + 1]].kind != "OP":
            continue
        if pos > 0 and tokens[sig[pos - 1]].kind == "OP" and tokens[sig[pos - 1]].text == ".":
            continue
        open_i = sig[pos + 1]
        close_i = find_matching(tokens, open_i)
        args = split_top_level(tokens[open_i + 1:close_i])
        arg_sig = [significant(a) for a in args]
        if t.upper == "TO_NUMBER":
            if len(args) == 1 and len(arg_sig[0]) == 1 and arg_sig[0][0].kind == "BIND":
                ctx.add("RGN002", arg_sig[0][0].text)
                return replace(i, close_i, ctx.placeholder(arg_sig[0][0].text[1:]))
            continue
        if t.upper in {"V", "NV"}:
            if len(args) == 1 and len(arg_sig[0]) == 1 and arg_sig[0][0].kind == "STRING":
                item = string_value(arg_sig[0][0])
                ctx.add("RGN003", f"{t.upper}('{item}')")
                return replace(i, close_i, ctx.placeholder(item))
            ctx.add("RGN012", render(tokens[i:close_i + 1]))
            continue
        texts = [render(a).strip() for a in args]
        if t.upper == "NVL2" and len(texts) == 3:
            ctx.add("RGN004")
            return replace(i, close_i, f"CASE WHEN ({texts[0]}) IS NOT NULL THEN {texts[1]} ELSE {texts[2]} END")
        if t.upper == "DECODE" and len(texts) >= 3:
            ctx.add("RGN005")
            return replace(i, close_i, _case_from_decode(texts))
    return None


def _rewrite(sql: str, ctx: _Context) -> list[Token]:
    tokens = tokenize(sql)
    for _ in range(500):
        text = _rewrite_once(tokens, ctx)
        if text is None:
            return tokens
        tokens = tokenize(text)
    raise TokenizeError("Too many rewrites.")


def _qualify(sql: str, known: frozenset[str], schema: str, ctx: _Context) -> tuple[str, list[str]]:
    """Prefix known objects after FROM/JOIN (and in comma lists of a FROM clause) with the target schema."""
    tokens = tokenize(sql)
    out = [t.text for t in tokens]
    sig = [i for i, t in enumerate(tokens) if t.significant]
    in_from = [False]
    function_paren = [False]  # EXTRACT(field FROM expr): that FROM is not a table reference
    expect = False
    objects: list[str] = []
    for pos, i in enumerate(sig):
        t = tokens[i]
        if t.kind == "OP":
            if t.text == "(":
                before = tokens[sig[pos - 1]] if pos else None
                in_from.append(False)
                function_paren.append(before is not None and before.kind == "IDENT" and before.upper in FUNCTION_FROM)
                expect = False
            elif t.text == ")":
                if len(in_from) > 1:
                    in_from.pop()
                    function_paren.pop()
                expect = False
            elif t.text == "," and in_from[-1]:
                expect = True
            continue
        if t.kind == "IDENT" and t.upper == "FROM":
            before = tokens[sig[pos - 1]] if pos else None
            if function_paren[-1] or (before is not None and before.kind == "IDENT" and before.upper == "DISTINCT"
                                      and pos > 1 and tokens[sig[pos - 2]].upper in {"IS", "NOT"}):
                continue
            in_from[-1] = True
            expect = True
            continue
        if t.kind == "IDENT" and t.upper == "JOIN":
            expect = True
            continue
        if t.kind == "IDENT" and t.upper in FROM_TERMINATORS:
            in_from[-1] = False
            expect = False
            continue
        if expect and t.kind in {"IDENT", "QIDENT"}:
            expect = False
            name = identifier_name(t)
            nxt = tokens[sig[pos + 1]] if pos + 1 < len(sig) else None
            if nxt is not None and nxt.kind == "OP" and nxt.text == ".":
                continue
            if name in known:
                out[i] = f"{schema}.{t.text}"
                if name not in objects:
                    objects.append(name)
                ctx.add("RGN006")
            continue
        if t.kind == "IDENT" and t.upper not in SQL_KEYWORDS:
            expect = False
    return "".join(out), objects


def _top_level_index(tokens: list[Token], words: tuple[str, ...]) -> int | None:
    """Index of the first token sequence ``words`` at parenthesis depth 0."""
    depth = 0
    sig = [i for i, t in enumerate(tokens) if t.significant]
    for pos, i in enumerate(sig):
        t = tokens[i]
        if t.kind == "OP" and t.text == "(":
            depth += 1
        elif t.kind == "OP" and t.text == ")":
            depth -= 1
        elif depth == 0 and t.kind == "IDENT" and t.upper == words[0]:
            following = [tokens[j].upper for j in sig[pos + 1:pos + len(words)]]
            if following == list(words[1:]):
                return i
    return None


def _output_columns(tokens: list[Token]) -> list[str] | None:
    from .view_conversion import select_list_columns
    names = select_list_columns(tokens)
    return [n.lower() for n in names] if names is not None else None


def _convert(sql: str, ctx: _Context, *, known: frozenset[str], source_schemas: frozenset[str],
             function_mappings: dict[str, str] | None, schema: str) -> tuple[str, list[str]]:
    tokens = _rewrite(sql, ctx)
    result = convert_expression(tokens, known_objects=known, source_schemas=source_schemas,
                                function_mappings=function_mappings)
    for f in result.findings:
        key = (f["code"], f.get("detail") or "")
        if key not in ctx._seen:
            ctx._seen.add(key)
            ctx.findings.append(dict(f))
    text, objects = _qualify(result.sql, known, schema, ctx)
    return _PLACEHOLDER_RE.sub(lambda m: f"${m.group(1)}", text), objects


def _simple_shape(tokens: list[Token], known: frozenset[str]) -> dict[str, Any] | None:
    """``select c1, c2 from one_object [where ...]``: plain columns of one known object, no alias, no join."""
    sig = significant(tokens)
    if not sig or sig[0].upper != "SELECT":
        return None
    from_i = _top_level_index(tokens, ("FROM",))
    if from_i is None:
        return None
    select: list[str] = []
    for item in split_top_level(tokens[tokens.index(sig[0]) + 1:from_i]):
        s = significant(item)
        if len(s) != 1 or s[0].kind != "IDENT" or s[0].upper in SQL_KEYWORDS:
            return None
        select.append(s[0].text.lower())
    rest = significant(tokens[from_i + 1:])
    if not rest or rest[0].kind != "IDENT" or identifier_name(rest[0]) not in known:
        return None
    shape: dict[str, Any] = {"view": rest[0].text.lower(), "select": select, "whereTokens": None}
    if len(rest) == 1:
        return shape
    if rest[1].kind != "IDENT" or rest[1].upper != "WHERE":
        return None
    where = tokens[tokens.index(rest[1]) + 1:]
    if any(t.kind == "IDENT" and t.upper in {"GROUP", "HAVING", "UNION", "MINUS", "INTERSECT", "CONNECT", "FETCH"}
           for t in significant(where)):
        return None
    shape["whereTokens"] = where
    return shape


def translate_query(sql: str, *, known_objects: set[str] | frozenset[str], source_schemas: set[str] | frozenset[str] = frozenset(),
                    function_mappings: dict[str, str] | None = None, target_schema: str = "app") -> TranslatedQuery:
    """Translate one region query. ``known_objects`` are Oracle (upper-case) table and view names of the plan."""
    source = _clean(sql)
    out = TranslatedQuery(source=source)
    ctx = _Context()
    known = frozenset(known_objects)
    schemas = frozenset(source_schemas)
    try:
        tokens = tokenize(source)
        sig = significant(tokens)
        if not sig or sig[0].upper not in {"SELECT", "WITH"} or any(t.kind == "OP" and t.text == ";" for t in sig):
            ctx.add("RGN007")
            out.findings = ctx.findings
            return out
        for t in sig:
            if t.kind == "STRING" and re.search(r"&[A-Za-z_][A-Za-z0-9_$#]*\.", t.text):
                ctx.add("RGN013", t.text)
        order_i = _top_level_index(tokens, ("ORDER", "BY"))
        body = tokens[:order_i] if order_i is not None else tokens
        if order_i is not None:
            out.order_by = _collapse(render(tokens[order_i:]))[len("order by"):].strip()
        out.columns = _output_columns(body)
        shape = _simple_shape(body, known)
        out.sql, out.objects = _convert(render(tokens), ctx, known=known, source_schemas=schemas,
                                        function_mappings=function_mappings, schema=target_schema)
        if shape is not None:
            simple: dict[str, Any] = {"view": shape["view"], "select": shape["select"]}
            if shape["whereTokens"] is not None:
                where_source = render(shape["whereTokens"])
                where_ctx = _Context()
                where_ctx.binds = ctx.binds  # same $n numbering as the whole query
                where_sql, _ = _convert(where_source, where_ctx, known=known, source_schemas=schemas,
                                        function_mappings=function_mappings, schema=target_schema)
                simple["where"] = {"sql": collapse_sql(where_sql), "source": _collapse(where_source)}
            out.simple = simple
    except TokenizeError as exc:
        ctx.add("RGN008", str(exc))
        out.sql = None
    out.binds = ctx.binds
    out.findings = ctx.findings
    if not out.usable:
        out.sql = None
        out.simple = None
    return out


def translate_lov(sql: str, *, known_objects: set[str] | frozenset[str], source_schemas: set[str] | frozenset[str] = frozenset(),
                  function_mappings: dict[str, str] | None = None, target_schema: str = "app",
                  numeric_columns: dict[str, set[str]] | None = None) -> dict[str, Any]:
    """Translate a shared-component LOV query (display column, return column).

    Returns ``{source, sql, orderBy: 'd'|'r', numeric, binds, findings, disposition}``; ``sql`` is the query
    without its ORDER BY (the runtime orders the derived table with binary collation, as NLS_SORT=BINARY does).
    ``numeric_columns`` maps an upper-case object name to its numeric column names (upper-case).
    """
    source = _clean(sql)
    query = translate_query(source, known_objects=known_objects, source_schemas=source_schemas,
                            function_mappings=function_mappings, target_schema=target_schema)
    findings = list(query.findings)
    out: dict[str, Any] = {"source": source, "sql": None, "orderBy": "d", "numeric": False, "binds": query.binds}
    items: list[list[Token]] = []
    try:
        tokens = tokenize(source)
        sig = significant(tokens)
        from_i = _top_level_index(tokens, ("FROM",))
        if sig and sig[0].upper == "SELECT" and from_i is not None:
            items = split_top_level(tokens[tokens.index(sig[0]) + 1:from_i])
    except TokenizeError:
        items = []
    if query.sql is not None and len(items) != 2:
        findings.append(_finding("RGN009", f"{len(items)} column(s)"))
    elif query.sql is not None:
        sql_tokens = tokenize(query.sql)
        order_i = _top_level_index(sql_tokens, ("ORDER", "BY"))
        out["sql"] = collapse_sql(render(sql_tokens[:order_i] if order_i is not None else sql_tokens))
        exprs = []
        for item in items:
            s = significant(item)
            alias = s[-1].text.upper() if len(s) > 1 and s[-1].kind == "IDENT" else None
            bare = s[0].text.upper() if s and s[0].kind == "IDENT" and len(s) <= 2 else None
            exprs.append({"alias": alias, "bare": bare})
        target = None
        if query.order_by is None:
            findings.append(_finding("RGN010"))
            target = 0
        else:
            order = significant(tokenize(query.order_by))
            if len(order) == 2 and order[1].kind == "IDENT" and order[1].upper == "ASC":
                order = order[:1]
            if len(order) == 1 and order[0].kind == "NUMBER" and order[0].text in {"1", "2"}:
                target = int(order[0].text) - 1
            elif len(order) == 1 and order[0].kind == "IDENT":
                name = order[0].upper
                target = next((n for n, e in enumerate(exprs) if name in {e["alias"], e["bare"]}), None)
            if target is None:
                findings.append(_finding("RGN011", query.order_by))
                target = 0
        out["orderBy"] = "dr"[target]
        bare = exprs[target]["bare"]
        if bare and numeric_columns and len(query.objects) == 1:
            out["numeric"] = bare in numeric_columns.get(query.objects[0], set())
    out["findings"] = findings
    out["disposition"] = worst_disposition(findings)
    if DISPOSITION_RANK[out["disposition"]] > DISPOSITION_RANK["ASSISTED"]:
        out["sql"] = None
    return out
