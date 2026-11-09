"""WP9.3 Oracle view conversion design (token based, rule registered)."""
from __future__ import annotations

from typing import Any

from .schema_conversion import Cursor, _read_name, finding, worst
from .sql_expression import convert_expression, pg_ident
from .sql_tokens import Statement, Token, identifier_name, render, significant, split_top_level

VIEW_RULES: dict[str, tuple[str, str]] = {
    "VIW001": ("ASSISTED", "FORCE removed; PostgreSQL requires dependencies first, so views are emitted in dependency order."),
    "VIW002": ("ASSISTED", "WITH READ ONLY removed; PostgreSQL simple views are auto-updatable, so DML must be denied by privileges."),
    "VIW003": ("ASSISTED", "WITH CHECK OPTION preserved; verify updatable-view semantics."),
    "VIW004": ("MANUAL", "View depends on an object that is not defined in this input."),
    "VIW005": ("MANUAL", "View depends on an object that is blocked or not emitted; view is not emitted."),
    "VIW006": ("MANUAL", "Dependency cycle between views."),
    "VIW007": ("ASSISTED", "Output column list derived lexically from the select list; verified against PostgreSQL catalog in integration tests."),
}


def _view_finding(code: str, obj: str, line: int, detail: str | None = None) -> dict[str, Any]:
    disposition, message = VIEW_RULES[code]
    return finding(code, obj=obj, line=line, detail=detail, disposition=disposition, message=message)


def select_list_columns(body: list[Token]) -> list[str] | None:
    """Return output column names of the first SELECT branch, or None if unknown."""
    sig = significant(body)
    if not sig or sig[0].upper != "SELECT":
        return None
    start = body.index(sig[0]) + 1
    depth = 0
    end = None
    for idx in range(start, len(body)):
        t = body[idx]
        if t.kind == "OP" and t.text == "(":
            depth += 1
        elif t.kind == "OP" and t.text == ")":
            depth -= 1
        elif depth == 0 and t.kind == "IDENT" and t.upper == "FROM":
            end = idx
            break
    items = split_top_level(body[start:end] if end is not None else body[start:])
    names: list[str] = []
    for item in items:
        s = significant(item)
        if s and s[0].kind == "IDENT" and s[0].upper == "DISTINCT":
            s = s[1:]
        if not s:
            return None
        last = s[-1]
        if last.kind == "OP" and last.text == "*":
            return None
        if last.kind in {"IDENT", "QIDENT"}:
            names.append(identifier_name(last))
        else:
            return None
    return names


def parse_view(stmt: Statement) -> dict[str, Any]:
    cur = Cursor(stmt.tokens)
    force = False
    while cur.word() != "VIEW":
        w = cur.take().upper
        if w == "FORCE":
            force = cur.peek(-2) is None or cur.peek(-2).upper != "NO"
    cur.take()
    owner, name = _read_name(cur)
    columns = None
    if cur.is_op("("):
        columns = [identifier_name(significant(p)[0]) for p in split_top_level(cur.paren_group())]
    while not cur.done() and cur.word() != "AS":
        cur.take()
    cur.take()  # AS
    body = cur.all[cur.all.index(cur.peek()):] if not cur.done() else []
    sig = significant(body)
    with_option = None
    tail_words = [t.upper for t in sig[-5:]]
    if tail_words[-3:] == ["WITH", "READ", "ONLY"]:
        with_option = "READ ONLY"
        body = body[:body.index(sig[-3])]
    elif "WITH" in tail_words and "CHECK" in tail_words and "OPTION" in tail_words:
        cut = len(sig) - 1
        while sig[cut].upper != "WITH":
            cut -= 1
        with_option = "CHECK OPTION"
        body = body[:body.index(sig[cut])]
    return {"kind": "VIEW", "name": name, "owner": owner, "line": stmt.line, "force": force,
            "columns": columns, "bodyTokens": body, "source": render(body).strip(),
            "withOption": with_option, "statement": stmt.text}


def convert_view(view: dict[str, Any], *, known_objects: set[str],
                 source_schemas: set[str], function_mappings: dict[str, str] | None = None) -> dict[str, Any]:
    name, line = view["name"], view["line"]
    result = convert_expression(view["bodyTokens"], known_objects=frozenset(known_objects),
                                source_schemas=frozenset(source_schemas), function_mappings=function_mappings)
    findings: list[dict[str, Any]] = []
    if view["force"]:
        findings.append(_view_finding("VIW001", name, line))
    if view["withOption"] == "READ ONLY":
        findings.append(_view_finding("VIW002", name, line))
    elif view["withOption"] == "CHECK OPTION":
        findings.append(_view_finding("VIW003", name, line))
    for f in result.findings:
        findings.append(finding(f["code"], obj=name, line=line, detail=f.get("detail"),
                                disposition=f["disposition"], message=f["message"]))
    for missing in sorted(result.unresolved_refs):
        findings.append(_view_finding("VIW004", name, line, missing))
    output_columns = view["columns"] or select_list_columns(view["bodyTokens"])
    if output_columns is not None and not view["columns"]:
        findings.append(_view_finding("VIW007", name, line))
    view.update({
        "candidateSql": result.sql.strip(),
        "dependencies": sorted(result.object_refs - {name}),
        "plsqlCalls": sorted(result.plsql_calls),
        "mappedCalls": sorted(result.mapped_calls),
        "unresolved": sorted(result.unresolved_refs),
        "outputColumns": output_columns,
        "findings": findings,
        "ownDisposition": worst(findings),
    })
    return view


def view_sql(view: dict[str, Any], target_schema: str) -> str:
    cols = ""
    if view["columns"]:
        cols = " (" + ", ".join(pg_ident(c) for c in view["columns"]) + ")"
    option = "\nWITH CHECK OPTION" if view["withOption"] == "CHECK OPTION" else ""
    return (f"CREATE VIEW {pg_ident(target_schema)}.{pg_ident(view['name'])}{cols} AS\n"
            f"{view['candidateSql']}{option};")


def view_design(view: dict[str, Any]) -> str:
    if view.get("phase") == "deferred":
        via = ", ".join(view["mappedCalls"]) if view["mappedCalls"] else "a deferred dependency"
        return ("Emitted in the deferred migration after the reviewed target functions exist "
                f"({via}).")
    if view["plsqlCalls"]:
        return ("Implement " + ", ".join(view["plsqlCalls"]) + " as reviewed PostgreSQL SQL "
                "function(s) in WP9.4, or move the predicate into the NestJS read service; "
                "then emit this view from the candidate SQL.")
    if view.get("blockedBy"):
        return "Emit after blocking dependencies are converted: " + ", ".join(view["blockedBy"]) + "."
    if view["ownDisposition"] in {"MANUAL", "UNSUPPORTED"}:
        return "Rewrite the flagged Oracle constructs by hand and add a regression fixture."
    return "Emit as an ordinary PostgreSQL view (dependency-ordered); review listed findings."
