"""WP9.3 lexical trigger behavior inventory.

Triggers are business logic: they are never converted automatically. This
module records *what* each trigger does (events, columns written, guards,
error codes, called units, cross-table access) so WP9.4 can rebuild the
behavior as explicit service/domain invariants, and so dependency validation
can see trigger edges. It is lexical evidence, not a PL/SQL parser.
"""
from __future__ import annotations

from typing import Any

from .schema_conversion import Cursor, _read_name, finding
from .sql_tokens import Statement, Token, identifier_name, render, significant, string_value

TRIGGER_RULES: dict[str, tuple[str, str]] = {
    "TRG001": ("MANUAL", "Row trigger business logic must be re-implemented as explicit target behavior (service write path or reviewed PostgreSQL trigger)."),
    "TRG002": ("MANUAL", "Trigger handles ORA-04091 (mutating table); Oracle-specific pattern must be redesigned."),
    "TRG003": ("MANUAL", "Trigger reads package state/bypass flag; pooled-connection semantics must be redesigned."),
    "TRG004": ("UNSUPPORTED", "Compound/INSTEAD OF/system trigger has no registered conversion."),
    "TRG005": ("MANUAL", "Autonomous transaction in trigger requires redesign."),
}
AUDIT_COLUMNS = ("CREATED_BY", "CREATED_ON", "CREATED_AT", "UPDATED_BY", "UPDATED_ON",
                 "UPDATED_AT", "MODIFIED_BY", "MODIFIED_ON")
NORMALIZERS = {"UPPER", "LOWER", "TRIM", "LTRIM", "RTRIM", "INITCAP"}


def _trg_finding(code: str, obj: str, line: int, detail: str | None = None) -> dict[str, Any]:
    disposition, message = TRIGGER_RULES[code]
    return finding(code, obj=obj, line=line, detail=detail, disposition=disposition, message=message)


def _classify_assignment(column: str, rhs: list[Token], known_packages: set[str]) -> str:
    sig = significant(rhs)
    words = {t.upper for t in sig if t.kind == "IDENT"}
    binds = [t.upper for t in sig if t.kind == "BIND"]
    if column in AUDIT_COLUMNS and not (binds == [":OLD"]):
        return "audit-principal" if column.endswith("_BY") else "audit-clock"
    if any(w in words for w in ("SYSDATE", "SYSTIMESTAMP", "CURRENT_DATE", "CURRENT_TIMESTAMP")):
        return "audit-clock" if column in AUDIT_COLUMNS else "clock"
    if "APP_USER" in words or "SYS_CONTEXT" in words or "USER" in words:
        return "audit-principal" if column in AUDIT_COLUMNS else "principal"
    if binds == [":OLD"] and len(sig) == 3 and sig[2].upper == column:
        return "field-lock"
    if sig and sig[0].upper in NORMALIZERS and ":NEW" in binds:
        return "normalization"
    if len(sig) == 1 and sig[0].kind in {"STRING", "NUMBER"}:
        return "forced-literal"
    if words & known_packages:
        return "derived-by-call"
    return "derived"


def parse_trigger(stmt: Statement, *, known_tables: set[str], known_packages: set[str]) -> dict[str, Any]:
    cur = Cursor(stmt.tokens)
    while cur.word() != "TRIGGER":
        cur.take()
    cur.take()
    owner, name = _read_name(cur)
    timing = cur.take().upper
    if timing == "INSTEAD":
        cur.accept("OF")
        timing = "INSTEAD OF"
    events: list[dict[str, Any]] = []
    while not cur.done() and cur.word() != "ON":
        w = cur.take().upper
        if w in {"INSERT", "UPDATE", "DELETE"}:
            ev: dict[str, Any] = {"event": w}
            if w == "UPDATE" and cur.word() == "OF":
                cur.take()
                cols = []
                while cur.peek() is not None and cur.peek().kind in {"IDENT", "QIDENT"} and cur.word() not in {"OR", "ON"}:
                    cols.append(identifier_name(cur.take()))
                    if cur.is_op(","):
                        cur.take()
                ev["columns"] = cols
            events.append(ev)
    cur.take()  # ON
    _, table = _read_name(cur) if not cur.done() else (None, None)
    for_each_row = False
    compound = False
    when = None
    while not cur.done() and cur.word() not in {"DECLARE", "BEGIN", "CALL"}:
        if cur.accept("FOR", "EACH", "ROW"):
            for_each_row = True
        elif cur.word() == "COMPOUND":
            compound = True
            break
        elif cur.word() == "WHEN" and cur.is_op("(", 1):
            cur.take()
            when = render(cur.paren_group()).strip()
        else:
            cur.take()
    body = cur.all[cur.all.index(cur.peek()):] if not cur.done() else []
    sig = significant(body)
    writes: dict[str, list[dict[str, str]]] = {}
    reads: set[str] = set()
    errors: list[dict[str, Any]] = []
    calls: set[str] = set()
    tables_read: set[str] = set()
    tables_written: set[str] = set()
    branch_stack: list[str | None] = []
    findings: list[dict[str, Any]] = []
    mutating = autonomous = uses_bypass = False
    i = 0
    while i < len(sig):
        t = sig[i]
        nxt = sig[i + 1] if i + 1 < len(sig) else None
        if t.kind == "BIND" and t.upper in {":NEW", ":OLD"} and nxt is not None and nxt.text == "." and i + 2 < len(sig):
            col = identifier_name(sig[i + 2])
            if t.upper == ":NEW" and i + 3 < len(sig) and sig[i + 3].text == ":=":
                j = i + 4
                depth = 0
                while j < len(sig) and not (sig[j].text == ";" and depth == 0):
                    depth += sig[j].text == "("
                    depth -= sig[j].text == ")"
                    j += 1
                rhs_start = body.index(sig[i + 4])
                rhs_end = body.index(sig[j]) if j < len(sig) else len(body)
                rhs = body[rhs_start:rhs_end]
                writes.setdefault(col, []).append({
                    "expression": render(rhs).strip(),
                    "classification": _classify_assignment(col, rhs, known_packages),
                    "branch": " / ".join(b for b in branch_stack if b) or "always",
                })
                i = j
                continue
            reads.add(f"{t.upper[1:]}.{col}")
            i += 3
            continue
        if t.kind == "IDENT":
            up = t.upper
            if up in {"INSERTING", "UPDATING", "DELETING"}:
                if branch_stack and branch_stack[-1] is None:
                    branch_stack[-1] = up
            elif up == "IF" and not (i > 0 and sig[i - 1].upper == "END"):
                branch_stack.append(None)
            elif up in {"ELSIF", "ELSE"} and branch_stack:
                prev = branch_stack[-1]
                branch_stack[-1] = f"NOT {prev}" if prev and not prev.startswith("NOT ") else None
            elif up == "END" and nxt is not None and nxt.upper == "IF" and branch_stack:
                branch_stack.pop()
            elif up == "RAISE_APPLICATION_ERROR" and nxt is not None and nxt.text == "(":
                code = None
                if i + 3 < len(sig) and sig[i + 2].text == "-" and sig[i + 3].kind == "NUMBER":
                    code = -int(sig[i + 3].text)
                message = next((string_value(s) for s in sig[i + 2:i + 12] if s.kind == "STRING"), None)
                errors.append({"code": code, "message": message})  # first literal fragment only
            elif up == "PRAGMA" and nxt is not None and nxt.upper == "AUTONOMOUS_TRANSACTION":
                autonomous = True
            elif up == "PRAGMA" and nxt is not None and nxt.upper == "EXCEPTION_INIT":
                window = "".join(s.text for s in sig[i:i + 8])
                if "-4091" in window:
                    mutating = True
            elif up in known_packages and nxt is not None and nxt.text == "." and i + 2 < len(sig):
                member = identifier_name(sig[i + 2])
                calls.add(f"{up}.{member}")
                if member == "BYPASS":
                    uses_bypass = True
            elif up in {"FROM", "JOIN"} and nxt is not None and nxt.kind in {"IDENT", "QIDENT"}:
                if identifier_name(nxt).upper() in known_tables:
                    tables_read.add(identifier_name(nxt).upper())
            elif up in {"INTO", "UPDATE"} and nxt is not None and nxt.kind in {"IDENT", "QIDENT"}:
                if identifier_name(nxt).upper() in known_tables:
                    tables_written.add(identifier_name(nxt).upper())
            elif up == "DELETE" and nxt is not None and nxt.upper == "FROM" and i + 2 < len(sig):
                if identifier_name(sig[i + 2]).upper() in known_tables:
                    tables_written.add(identifier_name(sig[i + 2]).upper())
        i += 1
    findings.append(_trg_finding("TRG001", name, stmt.line))
    if mutating:
        findings.append(_trg_finding("TRG002", name, stmt.line))
    if uses_bypass:
        findings.append(_trg_finding("TRG003", name, stmt.line))
    if autonomous:
        findings.append(_trg_finding("TRG005", name, stmt.line))
    if compound or timing in {"INSTEAD OF", "FOR"} or table is None:
        findings.append(_trg_finding("TRG004", name, stmt.line, timing))
    behaviors = sorted({w["classification"] for ws in writes.values() for w in ws}
                       | ({"guard"} if errors else set())
                       | ({"cross-table-read"} if tables_read - {table} else set()))
    return {
        "kind": "TRIGGER", "name": name, "owner": owner, "line": stmt.line, "table": table,
        "timing": timing, "events": events, "forEachRow": for_each_row, "when": when,
        "columnsWritten": {k: v for k, v in sorted(writes.items())},
        "columnsRead": sorted(reads), "errors": errors, "calls": sorted(calls),
        "tablesRead": sorted(tables_read), "tablesWritten": sorted(tables_written),
        "mutatingTableHandler": mutating, "usesBypassState": uses_bypass,
        "behaviors": behaviors, "findings": findings,
        "targetDesign": _design(behaviors, errors, mutating, uses_bypass),
    }


def _design(behaviors: list[str], errors: list[dict[str, Any]], mutating: bool, bypass: bool) -> list[str]:
    out = []
    if {"audit-clock", "audit-principal"} & set(behaviors):
        out.append("Audit stamps: set in the NestJS repository write path from the authenticated principal and one clock policy (or a narrow reviewed BEFORE trigger reading a trusted session setting).")
    if "normalization" in behaviors:
        out.append("Normalization: apply in request DTO/service before persistence; keep the stored form identical (e.g. upper-case codes).")
    if "derived-by-call" in behaviors:
        out.append("Derived values (e.g. document number): compute in the domain service inside the same transaction as the insert.")
    if "forced-literal" in behaviors or "field-lock" in behaviors or errors:
        out.append("State/field guards: implement as an explicit state machine and immutable-field rules in the domain service; preserve error codes " + ", ".join(str(e["code"]) for e in errors if e["code"] is not None) + " in the API error contract." if errors else "State/field guards: implement as explicit domain invariants.")
    if "cross-table-read" in behaviors:
        out.append("Parent-state guard: lock the parent row (SELECT ... FOR UPDATE) in the service transaction before modifying children.")
    if mutating:
        out.append("ORA-04091 cascade handling: define explicit delete semantics; PostgreSQL has no mutating-table error.")
    if bypass:
        out.append("Bypass flag: replace package global state with an explicit internal service path; never expose a client-controlled bypass.")
    return out
