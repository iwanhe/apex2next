"""Recursive, non-evaluating APEXLang property-value parser."""
from __future__ import annotations

import re
from typing import Any

from apex2next_extractor.apexlang_ast import (
    ApexLangProperty,
    _decode_ast_scalar,
    _span,
    tokenize_apexlang,
)

_MAX_PROPERTY_DEPTH = 128


def _trim_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _matching(text: str, start: int) -> int | None:
    tokens, _ = tokenize_apexlang(text[start:])
    opening = text[start]
    closing = {"{": "}", "[": "]"}.get(opening)
    if closing is None:
        return None
    depth = 0
    for token in tokens:
        if token.kind != "SYMBOL":
            continue
        if token.value == opening:
            depth += 1
        elif token.value == closing:
            depth -= 1
            if depth == 0:
                return start + token.span.start_offset
    return None


def _split_top_level(
    text: str, start: int, end: int, *, commas: bool = True
) -> list[tuple[int, int]]:
    tokens, _ = tokenize_apexlang(text[start:end])
    depth: list[str] = []
    separators: set[int] = set()
    pairs = {")": "(", "]": "[", "}": "{"}
    for token in tokens:
        absolute = start + token.span.start_offset
        if token.kind != "SYMBOL":
            continue
        if token.value in "([{":
            depth.append(token.value)
        elif token.value in ")]}":
            if depth and depth[-1] == pairs[token.value]:
                depth.pop()
        elif token.value == "," and commas and not depth:
            separators.add(absolute)

    newline_positions: list[int] = []
    cursor = start
    while cursor < end:
        newline = text.find("\n", cursor, end)
        if newline < 0:
            break
        newline_positions.append(newline)
        cursor = newline + 1

    token_index = 0
    nesting: list[str] = []
    for newline in newline_positions:
        while (
            token_index < len(tokens)
            and start + tokens[token_index].span.start_offset < newline
        ):
            token = tokens[token_index]
            if token.kind == "SYMBOL":
                if token.value in "([{":
                    nesting.append(token.value)
                elif token.value in ")]}":
                    if nesting and nesting[-1] == pairs[token.value]:
                        nesting.pop()
            token_index += 1
        next_line = newline + 1
        while next_line < end and text[next_line] in " \t":
            next_line += 1
        if not nesting and re.match(
            r"[A-Za-z_][A-Za-z0-9_.-]*\s*:", text[next_line:end]
        ):
            separators.add(newline)

    result: list[tuple[int, int]] = []
    cursor = start
    for separator in sorted(separators):
        left, right = _trim_bounds(text, cursor, separator)
        if left < right:
            result.append((left, right))
        cursor = separator + 1
    left, right = _trim_bounds(text, cursor, end)
    if left < right:
        result.append((left, right))
    return result


def _property(
    name: str,
    source: str,
    value_start: int,
    value_end: int,
    *,
    base_offset: int,
    full_source: str,
    depth: int,
    diagnostics: list[dict[str, Any]],
) -> ApexLangProperty:
    raw_start, raw_end = _trim_bounds(source, value_start, value_end)
    raw = source[raw_start:raw_end]
    span = _span(full_source, base_offset + value_start, base_offset + value_end)
    if depth > _MAX_PROPERTY_DEPTH:
        diagnostics.append(
            {
                "code": "AST103",
                "severity": "ERROR",
                "message": f"Property nesting exceeds {_MAX_PROPERTY_DEPTH} levels.",
                "span": span.__dict__,
            }
        )
        return ApexLangProperty(name, "UNKNOWN", raw, None, span)

    if raw.startswith(("{", "[")):
        close = _matching(source, raw_start)
        expected = "}" if raw[0] == "{" else "]"
        if close is None or close >= raw_end or source[close] != expected:
            container = "object" if expected == "}" else "array"
            diagnostics.append(
                {
                    "code": "AST101",
                    "severity": "WARNING",
                    "message": f"Unterminated {container} property: {name}",
                    "span": span.__dict__,
                }
            )
            return ApexLangProperty(name, "UNKNOWN", raw, None, span)

        inner_start, inner_end = raw_start + 1, close
        if expected == "}":
            children = _parse_object(
                source,
                inner_start,
                inner_end,
                base_offset=base_offset,
                full_source=full_source,
                depth=depth + 1,
                diagnostics=diagnostics,
            )
            value = {child.name: child.value for child in children}
            return ApexLangProperty(
                name, "OBJECT", raw, value, span, children=children
            )

        items = [
            _property(
                "",
                source,
                item_start,
                item_end,
                base_offset=base_offset,
                full_source=full_source,
                depth=depth + 1,
                diagnostics=diagnostics,
            )
            for item_start, item_end in _split_top_level(
                source, inner_start, inner_end
            )
        ]
        return ApexLangProperty(
            name, "ARRAY", raw, [item.value for item in items], span, items=items
        )

    value_type, value = _decode_ast_scalar(raw)
    return ApexLangProperty(name, value_type, raw, value, span)


def _parse_object(
    source: str,
    start: int,
    end: int,
    *,
    base_offset: int,
    full_source: str,
    depth: int,
    diagnostics: list[dict[str, Any]],
) -> list[ApexLangProperty]:
    result: list[ApexLangProperty] = []
    seen: set[str] = set()
    for segment_start, segment_end in _split_top_level(source, start, end):
        segment = source[segment_start:segment_end]
        match = re.match(
            r"\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*:\s*", segment
        )
        if not match:
            diagnostics.append(
                {
                    "code": "AST104",
                    "severity": "WARNING",
                    "message": (
                        "Object member is not a property declaration; "
                        "parent raw value is retained."
                    ),
                    "span": _span(
                        full_source,
                        base_offset + segment_start,
                        base_offset + segment_end,
                    ).__dict__,
                }
            )
            continue

        name = match.group(1)
        value_start = segment_start + match.end()
        prop = _property(
            name,
            source,
            value_start,
            segment_end,
            base_offset=base_offset,
            full_source=full_source,
            depth=depth,
            diagnostics=diagnostics,
        )
        if name in seen:
            diagnostics.append(
                {
                    "code": "AST102",
                    "severity": "WARNING",
                    "message": f"Duplicate property name preserved: {name}",
                    "span": prop.span.__dict__,
                }
            )
        seen.add(name)
        result.append(prop)
    return result


def parse_apexlang_properties(
    source: str,
    *,
    base_offset: int = 0,
    full_source: str | None = None,
) -> tuple[list[ApexLangProperty], list[dict[str, Any]]]:
    """Parse direct properties and recursively support inline/multiline containers."""
    original = full_source if full_source is not None else source
    diagnostics: list[dict[str, Any]] = []
    lines = source.splitlines(keepends=True)
    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line)

    candidates: list[tuple[int, re.Match[str]]] = []
    for line_no, line in enumerate(lines):
        match = re.match(
            r"^(?P<indent>[ \t]*)(?P<name>[A-Za-z_][A-Za-z0-9_.-]*)\s*:\s*",
            line.rstrip("\r\n"),
        )
        if match:
            candidates.append((line_no, match))
    if not candidates:
        return [], diagnostics

    direct_indent = min(
        len(match.group("indent").expandtabs(4)) for _, match in candidates
    )
    direct = [
        (line_no, match)
        for line_no, match in candidates
        if len(match.group("indent").expandtabs(4)) == direct_indent
    ]

    properties: list[ApexLangProperty] = []
    seen: set[str] = set()
    for index, (line_no, match) in enumerate(direct):
        name = match.group("name")
        value_start = offsets[line_no] + match.end()
        value_end = (
            offsets[direct[index + 1][0]]
            if index + 1 < len(direct)
            else len(source)
        )
        if index + 1 == len(direct):
            # A child declaration at the same indentation ends this declaration's
            # direct property region; do not absorb its properties into this value.
            for candidate_line in range(line_no + 1, len(lines)):
                candidate = lines[candidate_line].rstrip()
                if not candidate.strip():
                    continue
                indent = len(candidate) - len(candidate.lstrip(" \\t"))
                stripped = candidate.lstrip(" \\t")
                if indent <= direct_indent and stripped.endswith("("):
                    value_end = offsets[candidate_line]
                    break
                if indent < direct_indent and stripped.startswith(")"):
                    value_end = offsets[candidate_line]
                    break
        value_start, value_end = _trim_bounds(source, value_start, value_end)
        prop = _property(
            name,
            source,
            value_start,
            value_end,
            base_offset=base_offset,
            full_source=original,
            depth=0,
            diagnostics=diagnostics,
        )
        if name in seen:
            diagnostics.append(
                {
                    "code": "AST102",
                    "severity": "WARNING",
                    "message": f"Duplicate property name preserved: {name}",
                    "span": prop.span.__dict__,
                }
            )
        seen.add(name)
        properties.append(prop)
    return properties, diagnostics
