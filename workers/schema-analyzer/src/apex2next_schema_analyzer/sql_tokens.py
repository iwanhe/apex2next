"""Lossless Oracle SQL tokenizer and SQL*Plus script splitter (WP9.3).

The tokenizer keeps every character of the input (whitespace and comments are
tokens too), so a statement can be rebuilt exactly after targeted rewrites.
The splitter understands the SQL*Plus conventions used by APEX supporting
objects and DBMS_METADATA output: ``;``-terminated SQL, ``/``-terminated
PL/SQL units, and line-oriented SQL*Plus commands. Nothing is executed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


class TokenizeError(ValueError):
    """Raised for unterminated literals, quoted identifiers, or comments."""


@dataclass(frozen=True)
class Token:
    kind: str  # WS, COMMENT, STRING, QIDENT, NUMBER, IDENT, BIND, OP
    text: str
    offset: int

    @property
    def upper(self) -> str:
        return self.text.upper()

    @property
    def significant(self) -> bool:
        return self.kind not in {"WS", "COMMENT"}


_MULTI_OPS = ("<=", ">=", "<>", "!=", "^=", "||", "=>", ":=", "**", "..")
_IDENT_START = re.compile(r"[A-Za-z_]")
_IDENT_BODY = re.compile(r"[A-Za-z0-9_$#]*")
_NUMBER = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
_Q_CLOSERS = {"[": "]", "{": "}", "(": ")", "<": ">"}


def _string_end(text: str, start: int) -> int:
    """Return index after a '...' literal starting at ``start`` (the quote)."""
    i = start + 1
    while i < len(text):
        if text[i] == "'":
            if i + 1 < len(text) and text[i + 1] == "'":
                i += 2
                continue
            return i + 1
        i += 1
    raise TokenizeError(f"Unterminated string literal at offset {start}.")


def _q_string_end(text: str, quote: int) -> int:
    """Return index after q'Xtext X' where ``quote`` is the position of the quote."""
    if quote + 1 >= len(text):
        raise TokenizeError(f"Unterminated q-quoted literal at offset {quote}.")
    opener = text[quote + 1]
    closer = _Q_CLOSERS.get(opener, opener)
    end = text.find(closer + "'", quote + 2)
    if end < 0:
        raise TokenizeError(f"Unterminated q-quoted literal at offset {quote}.")
    return end + 2


def _is_q_quote(text: str, i: int) -> int | None:
    """Detect q'..' / nq'..' starting at i; return quote position or None."""
    if i > 0 and (text[i - 1].isalnum() or text[i - 1] in "_$#"):
        return None
    j = i
    if text[j] in "nN" and j + 1 < len(text) and text[j + 1] in "qQ":
        j += 1
    if text[j] in "qQ" and j + 1 < len(text) and text[j + 1] == "'":
        return j + 1
    return None


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            j = i + 1
            while j < n and text[j].isspace():
                j += 1
            tokens.append(Token("WS", text[i:j], i))
            i = j
            continue
        if text.startswith("--", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            tokens.append(Token("COMMENT", text[i:j], i))
            i = j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            if j < 0:
                raise TokenizeError(f"Unterminated block comment at offset {i}.")
            tokens.append(Token("COMMENT", text[i:j + 2], i))
            i = j + 2
            continue
        q = _is_q_quote(text, i)
        if q is not None:
            j = _q_string_end(text, q)
            tokens.append(Token("STRING", text[i:j], i))
            i = j
            continue
        if ch in "nN" and i + 1 < n and text[i + 1] == "'" and not (
            i > 0 and (text[i - 1].isalnum() or text[i - 1] in "_$#")
        ):
            j = _string_end(text, i + 1)
            tokens.append(Token("STRING", text[i:j], i))
            i = j
            continue
        if ch == "'":
            j = _string_end(text, i)
            tokens.append(Token("STRING", text[i:j], i))
            i = j
            continue
        if ch == '"':
            j = i + 1
            while True:
                if j >= n:
                    raise TokenizeError(f"Unterminated quoted identifier at offset {i}.")
                if text[j] == '"':
                    if j + 1 < n and text[j + 1] == '"':
                        j += 2
                        continue
                    break
                j += 1
            tokens.append(Token("QIDENT", text[i:j + 1], i))
            i = j + 1
            continue
        if ch.isdigit() or (ch == "." and i + 1 < n and text[i + 1].isdigit()):
            m = _NUMBER.match(text, i)
            assert m is not None
            tokens.append(Token("NUMBER", m.group(0), i))
            i = m.end()
            continue
        if _IDENT_START.match(ch):
            m = _IDENT_BODY.match(text, i + 1)
            assert m is not None
            tokens.append(Token("IDENT", text[i:m.end()], i))
            i = m.end()
            continue
        if ch == ":" and i + 1 < n and _IDENT_START.match(text[i + 1]):
            m = _IDENT_BODY.match(text, i + 2)
            assert m is not None
            tokens.append(Token("BIND", text[i:m.end()], i))
            i = m.end()
            continue
        op = next((o for o in _MULTI_OPS if text.startswith(o, i)), None)
        if op:
            tokens.append(Token("OP", op, i))
            i += len(op)
            continue
        tokens.append(Token("OP", ch, i))
        i += 1
    return tokens


def significant(tokens: list[Token]) -> list[Token]:
    return [t for t in tokens if t.significant]


def render(tokens: list[Token]) -> str:
    return "".join(t.text for t in tokens)


def identifier_name(token: Token) -> str:
    """Oracle name for an identifier token (unquoted names fold to upper case)."""
    if token.kind == "QIDENT":
        return token.text[1:-1].replace('""', '"')
    return token.text.upper()


def string_value(token: Token) -> str:
    """Decode an Oracle string literal token (standard, N'', or q-quoted)."""
    text = token.text
    if text[:1] in "nN" and text[1:2] in "qQ'":
        text = text[1:]
    if text[:1] in "qQ":
        return text[3:-2]
    return text[1:-1].replace("''", "'")


def pg_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def find_matching(tokens: list[Token], open_index: int) -> int:
    """Index of the ')' matching tokens[open_index] == '(' (raises if unbalanced)."""
    depth = 0
    for idx in range(open_index, len(tokens)):
        tok = tokens[idx]
        if tok.kind == "OP" and tok.text == "(":
            depth += 1
        elif tok.kind == "OP" and tok.text == ")":
            depth -= 1
            if depth == 0:
                return idx
    raise TokenizeError("Unbalanced parentheses.")


def split_top_level(tokens: list[Token], separator: str = ",") -> list[list[Token]]:
    """Split tokens on a separator at parenthesis depth 0."""
    parts: list[list[Token]] = [[]]
    depth = 0
    for tok in tokens:
        if tok.kind == "OP" and tok.text == "(":
            depth += 1
        elif tok.kind == "OP" and tok.text == ")":
            depth -= 1
        if depth == 0 and tok.kind == "OP" and tok.text == separator:
            parts.append([])
            continue
        parts[-1].append(tok)
    return [p for p in parts if significant(p)]


# --------------------------------------------------------------------------- splitter

SQLPLUS_COMMANDS = {
    "SET", "PROMPT", "PRO", "SPOOL", "REM", "REMARK", "WHENEVER", "DEFINE", "DEF",
    "UNDEFINE", "UNDEF", "COLUMN", "COL", "TTITLE", "BTITLE", "CLEAR", "BREAK", "COMPUTE",
    "SHOW", "PAUSE", "ACCEPT", "VARIABLE", "VAR", "PRINT", "CONNECT", "CONN", "DISCONNECT",
    "EXIT", "QUIT", "EXEC", "EXECUTE", "HOST", "TIMING",
}
_PLSQL_START = re.compile(
    r"(?:CREATE\s+(?:OR\s+REPLACE\s+)?(?:(?:NON)?EDITIONABLE\s+)?"
    r"(?:PACKAGE|TRIGGER|PROCEDURE|FUNCTION|TYPE|LIBRARY|JAVA)\b|DECLARE\b|BEGIN\b)",
    re.I,
)


@dataclass
class Statement:
    kind: str
    text: str
    offset: int
    line: int
    tokens: list[Token] = field(default_factory=list)
    error: str | None = None

    @property
    def words(self) -> list[str]:
        return [t.upper for t in self.tokens if t.kind in {"IDENT", "QIDENT"}][:8]


def _skip_lexical(text: str, i: int) -> int:
    """If text[i] starts a quote/comment, return the index after it; else i."""
    if text.startswith("--", i):
        j = text.find("\n", i)
        return len(text) if j < 0 else j
    if text.startswith("/*", i):
        j = text.find("*/", i + 2)
        if j < 0:
            raise TokenizeError(f"Unterminated block comment at offset {i}.")
        return j + 2
    q = _is_q_quote(text, i)
    if q is not None:
        return _q_string_end(text, q)
    if text[i] == "'":
        return _string_end(text, i)
    if text[i] == '"':
        j = text.find('"', i + 1)
        if j < 0:
            raise TokenizeError(f"Unterminated quoted identifier at offset {i}.")
        return j + 1
    return i


def _line_bounds(text: str, i: int) -> tuple[int, int]:
    start = text.rfind("\n", 0, i) + 1
    end = text.find("\n", i)
    return start, len(text) if end < 0 else end


def _is_slash_line(text: str, i: int) -> bool:
    start, end = _line_bounds(text, i)
    return text[start:end].strip() == "/"


def classify(tokens: list[Token]) -> str:
    words = [t.upper for t in significant(tokens) if t.kind in {"IDENT", "QIDENT"}]
    if not words:
        return "EMPTY"
    head = words[0]
    if head == "CREATE":
        rest = [w for w in words[1:] if w not in {"OR", "REPLACE", "EDITIONABLE",
                                                  "NONEDITIONABLE", "FORCE", "NO",
                                                  "GLOBAL", "TEMPORARY", "PRIVATE",
                                                  "UNIQUE", "BITMAP", "PUBLIC"}]
        if not rest:
            return "OTHER"
        if rest[0] in {"PACKAGE", "TYPE"} and len(rest) > 1 and rest[1] == "BODY":
            return rest[0] + "_BODY"
        if rest[0] == "MATERIALIZED":
            return "MATERIALIZED_VIEW"
        if rest[0] in {"TABLE", "VIEW", "INDEX", "SEQUENCE", "SYNONYM", "TRIGGER", "PACKAGE",
                       "PROCEDURE", "FUNCTION", "TYPE"}:
            return rest[0]
        return "CREATE_OTHER"
    if head == "ALTER" and len(words) > 1:
        return "ALTER_" + words[1]
    if head == "COMMENT":
        return "COMMENT"
    if head in {"INSERT", "UPDATE", "DELETE", "MERGE"}:
        return "DML"
    if head in {"COMMIT", "ROLLBACK", "SAVEPOINT"}:
        return "TCL"
    if head in {"GRANT", "REVOKE"}:
        return "DCL"
    if head == "DROP":
        return "DROP"
    if head in {"BEGIN", "DECLARE"}:
        return "ANONYMOUS_BLOCK"
    if head == "SELECT":
        return "QUERY"
    return "OTHER"


def split_script(text: str) -> list[Statement]:
    """Split a SQL*Plus-style script into statements without executing anything."""
    statements: list[Statement] = []
    i = 0
    n = len(text)
    while i < n:
        # Skip whitespace, comments, and stray slash lines between statements.
        if text[i].isspace():
            i += 1
            continue
        if text.startswith("--", i) or text.startswith("/*", i):
            i = _skip_lexical(text, i)
            continue
        if text[i] == "/" and _is_slash_line(text, i):
            _, end = _line_bounds(text, i)
            i = end
            continue
        line_no = text.count("\n", 0, i) + 1
        word_match = re.match(r"@{1,2}|[A-Za-z]+", text[i:])
        word = word_match.group(0).upper() if word_match else ""
        if word.startswith("@") or (word in SQLPLUS_COMMANDS and not re.match(
                r"SET\s+(?:TRANSACTION|ROLE|CONSTRAINTS?)\b", text[i:], re.I)):
            _, end = _line_bounds(text, i)
            # SQL*Plus continuation character '-' at end of line.
            while text[i:end].rstrip().endswith(" -") and end < n:
                _, end = _line_bounds(text, end + 1)
            statements.append(Statement("SQLPLUS", text[i:end].strip(), i, line_no))
            i = end
            continue
        plsql = bool(_PLSQL_START.match(text, i))
        start = i
        depth = 0
        end_stmt = None
        next_i = n
        j = i
        try:
            while j < n:
                skipped = _skip_lexical(text, j)
                if skipped != j:
                    j = skipped
                    continue
                ch = text[j]
                if ch == "/" and _is_slash_line(text, j) and text[_line_bounds(text, j)[0]:j].strip() == "":
                    end_stmt = j
                    next_i = _line_bounds(text, j)[1]
                    break
                if not plsql:
                    if ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
                    elif ch == ";" and depth <= 0:
                        end_stmt = j
                        next_i = j + 1
                        break
                j += 1
        except TokenizeError as exc:
            statements.append(Statement("ERROR", text[start:].strip(), start, line_no,
                                        error=str(exc)))
            break
        if end_stmt is None:
            end_stmt = n
        body = text[start:end_stmt].rstrip()
        if plsql:
            body = body.rstrip()
        try:
            toks = tokenize(body)
            kind = classify(toks)
            statements.append(Statement(kind, body, start, line_no, toks))
        except TokenizeError as exc:
            statements.append(Statement("ERROR", body, start, line_no, error=str(exc)))
        i = next_i
    return statements
