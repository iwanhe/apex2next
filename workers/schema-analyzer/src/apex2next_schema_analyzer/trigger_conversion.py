"""R4a trigger conversion: Oracle BEFORE ROW triggers -> PL/pgSQL trigger functions.

Only a small, explicit statement language is converted; anything else leaves the
trigger MANUAL (inventoried by ``trigger_analysis`` as before). Supported:

* trigger: ``BEFORE INSERT [OR UPDATE [OF cols]] [OR DELETE] ON table FOR EACH ROW [WHEN (...)]``
* body: ``BEGIN ... END;`` without DECLARE or EXCEPTION sections, made of
  ``:NEW.col := expr;``, ``SELECT expr INTO :NEW.col FROM DUAL;``,
  ``IF cond THEN ... [ELSIF cond THEN ...] [ELSE ...] END IF;``, ``NULL;``, ``RETURN;`` and
  ``RAISE_APPLICATION_ERROR(-20nnn, message);``
* expressions and conditions through the registered expression rewrites (``sql_expression``), plus
  ``:NEW.col`` / ``:OLD.col``, ``INSERTING`` / ``UPDATING`` / ``DELETING``, the APEX user
  (``V('APP_USER')``, ``SYS_CONTEXT('APEX$SESSION','APP_USER')``, ``APEX_APPLICATION.G_USER``,
  ``WWV_FLOW.G_USER``, ``:APP_USER``), ``USER``, ``CURRENT_DATE`` and ``sequence.NEXTVAL`` of a converted sequence.

Every expression finding must be AUTOMATIC or ASSISTED; a MANUAL/UNSUPPORTED finding (unknown function,
other bind, Oracle-only function, package call) keeps the whole trigger MANUAL. The generated function
skips its body while ``apex2next.loading`` is ``on`` so migrated rows keep their source values.
"""
from __future__ import annotations

from typing import Any

from .sql_expression import DISPOSITION_RANK, convert_expression, pg_ident
from .sql_tokens import Statement, Token, identifier_name, pg_string_literal, tokenize

TRIGGER_CONVERSION_RULES: dict[str, tuple[str, str]] = {
    "TRC001": ("ASSISTED", "Trigger converted to a PL/pgSQL BEFORE ROW trigger; review the generated function and run the application's parity journeys."),
    "TRC002": ("ASSISTED", "APEX APP_USER read from the transaction setting app.username (set by the runtime per request); NULL outside a request."),
    "TRC003": ("ASSISTED", "Oracle USER (the parsing schema) rewritten to upper(current_user), the database role of the target."),
    "TRC004": ("ASSISTED", "Oracle CURRENT_DATE (date and time of the session) rewritten to LOCALTIMESTAMP(0); confirm the time zone policy."),
    "TRC005": ("ASSISTED", "RAISE_APPLICATION_ERROR rewritten to RAISE EXCEPTION (SQLSTATE P0001, DETAIL ORA-20nnn); the runtime shows it as 'ORA-20nnn: message'. Confirm the text APEX shows in the parity journeys."),
    "TRC006": ("MANUAL", "Trigger statement or form outside the converted subset; re-implement by hand."),
}

APP_USER_SQL = "apex_app_user()"
LOADING_GUARD = "current_setting('apex2next.loading', true) = 'on'"


class Unsupported(Exception):
    pass


def _ident_token(text: str, like: Token) -> Token:
    return Token("IDENT", text, like.offset)


class _Converter:
    def __init__(self, *, schema: str, columns: set[str], sequences: set[str], known_objects: set[str]):
        self.schema = schema
        self.columns = columns
        self.sequences = sequences
        self.known_objects = known_objects
        self.findings: dict[str, dict[str, Any]] = {}
        self.uses_app_user = False
        self.expression_findings: list[dict[str, Any]] = []
        self.return_row = "NEW"

    def note(self, code: str, detail: str | None = None) -> None:
        disposition, message = TRIGGER_CONVERSION_RULES[code]
        key = code + (detail or "")
        self.findings.setdefault(key, {"code": code, "disposition": disposition, "message": message,
                                       **({"detail": detail} if detail else {})})

    # ------------------------------------------------------------- expressions
    def _row_ref(self, which: str, col_tok: Token) -> Token:
        col = identifier_name(col_tok)
        if col not in self.columns:
            raise Unsupported(f"{which}.{col}: column not in table")
        return _ident_token(f"{which}.{pg_ident(col)}", col_tok)

    def prepare(self, tokens: list[Token], *, when_clause: bool = False) -> list[Token]:
        """Replace trigger-specific constructs with already-converted IDENT tokens."""
        out: list[Token] = []
        sig = [i for i, t in enumerate(tokens) if t.significant]
        pos = {i: n for n, i in enumerate(sig)}
        skip_to = -1

        def s(n: int) -> Token | None:
            return tokens[sig[n]] if 0 <= n < len(sig) else None

        def op(n: int, text: str) -> bool:
            t = s(n)
            return t is not None and t.kind == "OP" and t.text == text

        def w(n: int) -> str | None:
            t = s(n)
            return t.upper if t is not None and t.kind == "IDENT" else None

        for i, t in enumerate(tokens):
            if i <= skip_to:
                continue
            if not t.significant:
                out.append(t)
                continue
            n = pos[i]
            prev_dot = op(n - 1, ".")
            nxt = s(n + 2)
            # :NEW.col / :OLD.col (NEW.col / OLD.col in a WHEN clause)
            row = None
            if t.kind == "BIND" and t.upper in {":NEW", ":OLD"}:
                row = t.upper[1:]
            elif when_clause and t.kind == "IDENT" and t.upper in {"NEW", "OLD"} and not prev_dot:
                row = t.upper
            if row and op(n + 1, ".") and nxt is not None and nxt.kind in {"IDENT", "QIDENT"}:
                out.append(self._row_ref(row, nxt))
                skip_to = sig[n + 2]
                continue
            if t.kind == "BIND" and t.upper == ":APP_USER":
                out.append(_ident_token(APP_USER_SQL, t))
                self.uses_app_user = True
                self.note("TRC002")
                continue
            if t.kind == "IDENT" and not prev_dot:
                up = t.upper
                # V('APP_USER') / NV('APP_USER')
                if up in {"V"} and op(n + 1, "(") and s(n + 2) is not None and s(n + 2).kind == "STRING" \
                        and s(n + 2).text.upper() == "'APP_USER'" and op(n + 3, ")"):
                    out.append(_ident_token(APP_USER_SQL, t))
                    self.uses_app_user = True
                    self.note("TRC002")
                    skip_to = sig[n + 3]
                    continue
                # SYS_CONTEXT('APEX$SESSION', 'APP_USER')
                if up == "SYS_CONTEXT" and op(n + 1, "(") and s(n + 2) is not None and s(n + 2).kind == "STRING" \
                        and s(n + 2).text.upper() == "'APEX$SESSION'" and op(n + 3, ",") and s(n + 4) is not None \
                        and s(n + 4).kind == "STRING" and s(n + 4).text.upper() == "'APP_USER'" and op(n + 5, ")"):
                    out.append(_ident_token(APP_USER_SQL, t))
                    self.uses_app_user = True
                    self.note("TRC002")
                    skip_to = sig[n + 5]
                    continue
                # APEX_APPLICATION.G_USER (WWV_FLOW.G_USER in older code)
                if up in {"APEX_APPLICATION", "WWV_FLOW"} and op(n + 1, ".") and w(n + 2) == "G_USER":
                    out.append(_ident_token(APP_USER_SQL, t))
                    self.uses_app_user = True
                    self.note("TRC002")
                    skip_to = sig[n + 2]
                    continue
                # sequence.NEXTVAL / CURRVAL
                if op(n + 1, ".") and w(n + 2) in {"NEXTVAL", "CURRVAL"}:
                    seq = identifier_name(t)
                    if seq not in self.sequences:
                        raise Unsupported(f"{seq}.{w(n + 2)}: sequence not converted")
                    fn = "nextval" if w(n + 2) == "NEXTVAL" else "currval"
                    target = f"{pg_ident(self.schema)}.{pg_ident(seq)}"
                    out.append(_ident_token(f"{fn}({pg_string_literal(target)})", t))
                    skip_to = sig[n + 2]
                    continue
                if op(n + 1, ".") and not op(n + 3, "("):
                    # a trigger body has no FROM clause: x.y can only be package state or another schema's object
                    raise Unsupported(f"{t.text}.{s(n + 2).text if s(n + 2) else ''}: package variable or qualified name")
                if up == "USER" and not op(n + 1, "(") and not op(n + 1, "."):
                    out.append(_ident_token("upper(current_user)", t))
                    self.note("TRC003")
                    continue
                if up == "CURRENT_DATE":
                    out.append(_ident_token("LOCALTIMESTAMP(0)", t))
                    self.note("TRC004")
                    continue
                if up in {"INSERTING", "UPDATING", "DELETING"}:
                    if op(n + 1, "("):
                        raise Unsupported(f"{up}(column)")
                    op_name = {"INSERTING": "INSERT", "UPDATING": "UPDATE", "DELETING": "DELETE"}[up]
                    out.append(_ident_token(f"(TG_OP = '{op_name}')", t))
                    continue
            out.append(t)
        return out

    def expr(self, tokens: list[Token], *, when_clause: bool = False) -> str:
        prepared = self.prepare(tokens, when_clause=when_clause)
        result = convert_expression(prepared, known_objects=self.known_objects)
        for f in result.findings:
            if DISPOSITION_RANK[f["disposition"]] > DISPOSITION_RANK["ASSISTED"]:
                raise Unsupported(f"{f['code']} {f.get('detail') or ''}".strip())
            self.expression_findings.append(f)
        if result.has_subquery:
            raise Unsupported("subquery in trigger expression")
        return " ".join(result.sql.split())

    # ------------------------------------------------------------- statements
    def block(self, toks: list[Token], indent: str) -> list[str]:
        """Convert a statement list (significant tokens only)."""
        lines: list[str] = []
        i = 0
        while i < len(toks):
            i = self.statement(toks, i, indent, lines)
        return lines

    def _until(self, toks: list[Token], i: int, stop: set[str], *, op_stop: str | None = None) -> int:
        """Index of the next top-level token whose upper text is in ``stop`` (or the operator ``op_stop``)."""
        depth = 0
        while i < len(toks):
            t = toks[i]
            if depth == 0 and ((t.kind == "IDENT" and t.upper in stop) or (op_stop and t.kind == "OP" and t.text == op_stop)):
                return i
            if t.kind == "OP" and t.text == "(":
                depth += 1
            elif t.kind == "OP" and t.text == ")":
                depth -= 1
            i += 1
        raise Unsupported(f"expected {' / '.join(sorted(stop)) or op_stop}")

    def _matching_if_parts(self, toks: list[Token], i: int) -> tuple[list[tuple[list[Token] | None, list[Token]]], int]:
        """Split IF ... END IF; at the top nesting level into (condition, body) branches."""
        parts: list[tuple[list[Token] | None, list[Token]]] = []
        j = i + 1
        then = self._until(toks, j, {"THEN"})
        cond: list[Token] | None = toks[j:then]
        start = then + 1
        depth = 0
        k = start
        while k < len(toks):
            t = toks[k]
            up = t.upper if t.kind == "IDENT" else None
            if up == "IF" and not (k > 0 and toks[k - 1].kind == "IDENT" and toks[k - 1].upper == "END"):
                depth += 1
            elif up == "END" and k + 1 < len(toks) and toks[k + 1].upper == "IF":
                if depth == 0:
                    parts.append((cond, toks[start:k]))
                    if not (k + 2 < len(toks) and toks[k + 2].text == ";"):
                        raise Unsupported("END IF without ;")
                    return parts, k + 3
                depth -= 1
                k += 1
            elif depth == 0 and up == "ELSIF":
                parts.append((cond, toks[start:k]))
                then = self._until(toks, k + 1, {"THEN"})
                cond = toks[k + 1:then]
                start = then + 1
                k = then
            elif depth == 0 and up == "ELSE":
                parts.append((cond, toks[start:k]))
                cond = None
                start = k + 1
            k += 1
        raise Unsupported("IF without END IF")

    def statement(self, toks: list[Token], i: int, indent: str, lines: list[str]) -> int:
        t = toks[i]
        up = t.upper if t.kind == "IDENT" else None
        if up == "NULL" and i + 1 < len(toks) and toks[i + 1].text == ";":
            lines.append(f"{indent}NULL;")
            return i + 2
        if up == "RETURN" and i + 1 < len(toks) and toks[i + 1].text == ";":
            lines.append(f"{indent}RETURN {self.return_row};")
            return i + 2
        if t.kind == "BIND" and t.upper == ":NEW" and i + 3 < len(toks) and toks[i + 1].text == "." \
                and toks[i + 3].text == ":=":
            target = self._row_ref("NEW", toks[i + 2]).text
            end = self._until(toks, i + 4, set(), op_stop=";")
            lines.append(f"{indent}{target} := {self.expr(self._with_ws(toks[i + 4:end]))};")
            return end + 1
        if up == "SELECT":
            into = self._until(toks, i + 1, {"INTO"})
            dual = into + 5
            if dual + 2 < len(toks) and toks[dual].upper == "SYS" and toks[dual + 1].text == ".":
                dual += 2  # FROM SYS.DUAL
            if not (dual + 1 < len(toks) and toks[into + 1].kind == "BIND" and toks[into + 1].upper == ":NEW"
                    and toks[into + 2].text == "." and toks[into + 4].upper == "FROM" and toks[dual].upper == "DUAL"
                    and toks[dual + 1].text == ";"):
                raise Unsupported("SELECT INTO other than one :NEW column FROM DUAL")
            target = self._row_ref("NEW", toks[into + 3]).text
            lines.append(f"{indent}{target} := {self.expr(self._with_ws(toks[i + 1:into]))};")
            return dual + 2
        if up == "IF":
            parts, nxt = self._matching_if_parts(toks, i)
            for n, (cond, body) in enumerate(parts):
                if cond is None:
                    lines.append(f"{indent}ELSE")
                else:
                    lines.append(f"{indent}{'IF' if n == 0 else 'ELSIF'} {self.expr(self._with_ws(cond))} THEN")
                inner = self.block(body, indent + "  ")
                lines.extend(inner or [f"{indent}  NULL;"])
            lines.append(f"{indent}END IF;")
            return nxt
        if up == "RAISE_APPLICATION_ERROR" and i + 1 < len(toks) and toks[i + 1].text == "(":
            if not (toks[i + 2].text == "-" and toks[i + 3].kind == "NUMBER" and toks[i + 4].text == ","):
                raise Unsupported("RAISE_APPLICATION_ERROR without a literal error number")
            code = int(toks[i + 3].text)
            close = self._until(toks, i + 5, set(), op_stop=")")
            # _until stops at the first top-level ")" after the message: the call's closing parenthesis
            if not (20000 <= code <= 20999) or close + 1 >= len(toks) or toks[close + 1].text != ";":
                raise Unsupported("RAISE_APPLICATION_ERROR form")
            message = self.expr(self._with_ws(toks[i + 5:close]))
            self.note("TRC005", f"ORA-{code}")
            lines.append(f"{indent}RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = {message}, DETAIL = 'ORA-{code}';")
            return close + 2
        raise Unsupported(f"statement starting with {t.text!r}")

    def _with_ws(self, sig_tokens: list[Token]) -> list[Token]:
        """Significant tokens of a fragment with single spaces between them (layout is normalized)."""
        out: list[Token] = []
        prev: Token | None = None
        for t in sig_tokens:
            tight = prev is None or (t.kind == "OP" and t.text in {")", ",", ";", "."}) \
                or (prev.kind == "OP" and prev.text in {"(", "."}) \
                or (t.kind == "OP" and t.text == "(" and prev.kind in {"IDENT", "QIDENT"})
            if not tight:
                out.append(Token("WS", " ", t.offset))
            out.append(t)
            prev = t
        return out


def convert_trigger(stmt: Statement, trg: dict[str, Any], *, schema: str, table: dict[str, Any] | None,
                    sequences: set[str], known_objects: set[str]) -> dict[str, Any]:
    """Return {"converted": bool, "sql"?, "findings", "usesAppUser"?, "reason"?} for one parsed trigger."""
    def refuse(reason: str) -> dict[str, Any]:
        disposition, message = TRIGGER_CONVERSION_RULES["TRC006"]
        return {"converted": False, "reason": reason,
                "findings": [{"code": "TRC006", "disposition": disposition, "message": message, "detail": reason}]}

    if table is None or not table.get("emit"):
        return refuse("table not emitted")
    if trg["timing"] != "BEFORE" or not trg["forEachRow"]:
        return refuse(f"{trg['timing']} {'ROW' if trg['forEachRow'] else 'STATEMENT'} trigger")
    if any(f["code"] in {"TRG002", "TRG003", "TRG004", "TRG005"} for f in trg["findings"]):
        return refuse(", ".join(f["code"] for f in trg["findings"] if f["code"] != "TRG001"))
    columns = {c["name"] for c in table["columns"]}
    generated = {c["name"] for c in table["columns"] if c.get("generated") or c.get("identity", {}).get("mode") == "ALWAYS"}
    if set(trg["columnsWritten"]) & generated:
        return refuse("writes a generated or identity column")
    conv = _Converter(schema=schema, columns=columns, sequences=sequences, known_objects=known_objects)
    has_delete = any(e["event"] == "DELETE" for e in trg["events"])
    # In a BEFORE DELETE call NEW is NULL: returning it would cancel the delete.
    conv.return_row = "CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END" if has_delete else "NEW"
    sig = [t for t in stmt.tokens if t.significant]
    # body: from BEGIN to the final END [name] ;
    begin = next((n for n, t in enumerate(sig) if t.kind == "IDENT" and t.upper in {"BEGIN", "DECLARE", "CALL"}), None)
    if begin is None or sig[begin].upper != "BEGIN":
        return refuse("DECLARE section or CALL body")
    body = sig[begin + 1:]
    while body and body[-1].text in {"/", ";"}:
        body = body[:-1]
    if body and body[-1].kind in {"IDENT", "QIDENT"} and body[-1].upper != "END":
        body = body[:-1]  # END trigger_name
    if not body or body[-1].upper != "END":
        return refuse("body does not end with END")
    body = body[:-1]
    if any(t.kind == "IDENT" and t.upper == "EXCEPTION" for t in body):
        return refuse("EXCEPTION section")
    try:
        when_sql = None
        if trg.get("when"):
            when_sql = conv.expr(tokenize(trg["when"]), when_clause=True)
        lines = conv.block(body, "  ")
    except Unsupported as exc:
        return refuse(str(exc))
    except (IndexError, ValueError) as exc:
        return refuse(f"unparsed trigger body ({exc})")
    final = f"RETURN {conv.return_row};"
    s = pg_ident(schema)
    name = pg_ident(trg["name"])
    fn = f"{s}.{pg_ident('trg_' + trg['name'])}"
    events = []
    for e in trg["events"]:
        if e["event"] == "UPDATE" and e.get("columns"):
            events.append("UPDATE OF " + ", ".join(pg_ident(c) for c in e["columns"]))
        else:
            events.append(e["event"])
    conv.note("TRC001")
    sql = "\n".join([
        f"-- {trg['name']} (Oracle line {trg['line']}): converted R4a trigger (review required)",
        f"CREATE FUNCTION {fn}() RETURNS trigger LANGUAGE plpgsql SET search_path = {s}, pg_temp AS $$",
        "BEGIN",
        f"  IF {LOADING_GUARD} THEN {final} END IF;  -- data migration keeps the source values",
        *lines,
        f"  {final}",
        "END",
        "$$;",
        f"CREATE TRIGGER {name} BEFORE {' OR '.join(events)} ON {s}.{pg_ident(trg['table'])}",
        f"  FOR EACH ROW{f' WHEN ({when_sql})' if when_sql else ''} EXECUTE FUNCTION {fn}();",
    ])
    seen: set[tuple[str, str]] = set()
    expression_findings = []
    for f in conv.expression_findings:
        key = (f["code"], f.get("detail", ""))
        if key not in seen:
            seen.add(key)
            expression_findings.append(f)
    return {"converted": True, "sql": sql, "usesAppUser": conv.uses_app_user,
            "findings": list(conv.findings.values()) + expression_findings}
