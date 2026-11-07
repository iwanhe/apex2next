"""Lossless structural tokenizer and declaration AST for APEXLang source.

This is an incremental parser foundation. It recognizes declaration boundaries
and preserves source spans/raw bodies; it does not evaluate expressions or claim
complete APEXLang grammar coverage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


TokenKind = Literal["IDENTIFIER", "NUMBER", "STRING", "REFERENCE", "RAW_BLOCK", "SYMBOL"]


@dataclass(frozen=True)
class SourceSpan:
    start_offset: int
    end_offset: int
    start_line: int
    start_column: int
    end_line: int
    end_column: int


@dataclass(frozen=True)
class ApexLangToken:
    kind: TokenKind
    value: str
    span: SourceSpan


@dataclass
class ApexLangDeclaration:
    kind: str
    name: str | None
    span: SourceSpan
    body_span: SourceSpan
    raw_body: str
    children: list["ApexLangDeclaration"] = field(default_factory=list)


@dataclass
class ApexLangAst:
    declarations: list[ApexLangDeclaration]
    tokens: list[ApexLangToken]
    diagnostics: list[dict[str, object]]


def _span(source: str, start: int, end: int) -> SourceSpan:
    prefix = source[:start]
    through = source[:end]
    start_line = prefix.count("\n") + 1
    end_line = through.count("\n") + 1
    start_col = start - (prefix.rfind("\n") + 1) + 1
    end_col = end - (through.rfind("\n") + 1) + 1
    return SourceSpan(start, end, start_line, start_col, end_line, end_col)


def tokenize_apexlang(source: str) -> tuple[list[ApexLangToken], list[dict[str, object]]]:
    """Tokenize source while retaining offsets; comments are skipped, strings/fences are atomic."""
    tokens: list[ApexLangToken] = []
    diagnostics: list[dict[str, object]] = []
    i, n = 0, len(source)

    def emit(kind: TokenKind, start: int, end: int) -> None:
        tokens.append(ApexLangToken(kind, source[start:end], _span(source, start, end)))

    while i < n:
        if source[i].isspace():
            i += 1
            continue
        if source.startswith("~~~", i) or source.startswith("```", i):
            marker = source[i:i + 3]
            end_marker = source.find(marker, i + 3)
            if end_marker < 0:
                emit("RAW_BLOCK", i, n)
                diagnostics.append({
                    "code": "AST001", "severity": "WARNING",
                    "message": "Unterminated fenced source block was preserved to end of file.",
                    "span": _span(source, i, n).__dict__,
                })
                i = n
            else:
                end = end_marker + 3
                emit("RAW_BLOCK", i, end)
                i = end
            continue
        if source.startswith("//", i) or source.startswith("--", i):
            end = source.find("\n", i)
            i = n if end < 0 else end
            continue
        if source.startswith("/*", i):
            end = source.find("*/", i + 2)
            if end < 0:
                diagnostics.append({
                    "code": "AST002", "severity": "WARNING",
                    "message": "Unterminated block comment.",
                    "span": _span(source, i, n).__dict__,
                })
                i = n
            else:
                i = end + 2
            continue
        if source[i] in {"'", '"'}:
            quote, start = source[i], i
            i += 1
            while i < n:
                if source[i] == quote:
                    if i + 1 < n and source[i + 1] == quote:
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            else:
                diagnostics.append({
                    "code": "AST003", "severity": "WARNING",
                    "message": "Unterminated quoted string.",
                    "span": _span(source, start, n).__dict__,
                })
            emit("STRING", start, i)
            continue
        if source[i] == "@" and i + 1 < n and (source[i + 1].isalnum() or source[i + 1] in "_./-"):
            start = i
            i += 1
            while i < n and (source[i].isalnum() or source[i] in "_./-"):
                i += 1
            emit("REFERENCE", start, i)
            continue
        if source[i].isalpha() or source[i] == "_":
            start = i
            i += 1
            while i < n and (source[i].isalnum() or source[i] in "_.-"):
                i += 1
            emit("IDENTIFIER", start, i)
            continue
        if source[i].isdigit() or (
            source[i] in "+-" and i + 1 < n and source[i + 1].isdigit()
        ):
            start = i
            i += 1
            while i < n and (source[i].isalnum() or source[i] in ".+-"):
                i += 1
            emit("NUMBER", start, i)
            continue
        emit("SYMBOL", i, i + 1)
        i += 1
    return tokens, diagnostics


def parse_apexlang_ast(source: str) -> ApexLangAst:
    """Build declaration nodes from tokenized source; nested declarations are structural children."""
    tokens, diagnostics = tokenize_apexlang(source)
    declarations: list[ApexLangDeclaration] = []
    stack: list[tuple[ApexLangDeclaration, int, int]] = []
    i = 0

    def token_value(index: int) -> str:
        return tokens[index].value if 0 <= index < len(tokens) else ""

    def is_symbol(index: int, value: str) -> bool:
        return 0 <= index < len(tokens) and tokens[index].kind == "SYMBOL" and token_value(index) == value

    while i < len(tokens):
        token = tokens[i]
        # Declaration heads must begin a logical line. This avoids treating function calls
        # inside property expressions as declaration nodes.
        line_prefix = source[source.rfind("\n", 0, token.span.start_offset) + 1:token.span.start_offset]
        at_line_start = not line_prefix.strip()
        previous_value = token_value(i - 1) if i > 0 else ""
        expression_continuation = previous_value in {"(", "[", ",", ":"}
        if token.kind != "IDENTIFIER" or not at_line_start or expression_continuation:
            if is_symbol(i, "(") and stack:
                node, opening, nested_parens = stack[-1]
                stack[-1] = (node, opening, nested_parens + 1)
            elif is_symbol(i, ")") and stack:
                node, opening, nested_parens = stack[-1]
                if nested_parens:
                    stack[-1] = (node, opening, nested_parens - 1)
                else:
                    stack.pop()
                    closing = token.span.end_offset
                    node.span = _span(source, node.span.start_offset, closing)
                    node.body_span = _span(source, opening + 1, token.span.start_offset)
                    node.raw_body = source[opening + 1:token.span.start_offset]
            i += 1
            continue

        name_index = i + 1
        declaration_name: str | None = None
        if name_index < len(tokens) and tokens[name_index].kind in {"IDENTIFIER", "NUMBER"}:
            if is_symbol(name_index + 1, "("):
                declaration_name = tokens[name_index].value
                open_index = name_index + 1
            else:
                open_index = -1
        elif is_symbol(name_index, "("):
            open_index = name_index
        else:
            open_index = -1

        if open_index < 0:
            i += 1
            continue

        opening_token = tokens[open_index]
        node = ApexLangDeclaration(
            kind=token.value,
            name=declaration_name,
            span=_span(source, token.span.start_offset, opening_token.span.end_offset),
            body_span=_span(source, opening_token.span.end_offset, opening_token.span.end_offset),
            raw_body="",
        )
        if stack:
            stack[-1][0].children.append(node)
        else:
            declarations.append(node)
        stack.append((node, opening_token.span.start_offset, 0))
        i = open_index + 1

    if stack:
        for node, opening, _nested_parens in stack:
            diagnostics.append({
                "code": "AST004", "severity": "WARNING",
                "message": f"Unterminated declaration: {node.kind} {node.name or ''}".strip(),
                "span": _span(source, node.span.start_offset, len(source)).__dict__,
            })
            node.raw_body = source[opening + 1:]
            node.body_span = _span(source, opening + 1, len(source))
            node.span = _span(source, node.span.start_offset, len(source))
    return ApexLangAst(declarations, tokens, diagnostics)
