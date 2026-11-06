"""Extract APEX import API calls from a text export without executing them.

This first parser intentionally extracts a safe metadata subset. It preserves raw
argument expressions and source locations; it is not a PL/SQL interpreter.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


CALL_PREFIXES = ("wwv_flow_imp", "apex_application_install")
OBJECT_TYPES = {
    "create_flow": "APPLICATION",
    "create_page": "PAGE",
    "create_page_plug": "REGION",
    "create_page_item": "ITEM",
    "create_page_button": "BUTTON",
    "create_page_branch": "BRANCH",
    "create_page_validation": "VALIDATION",
    "create_page_process": "PROCESS",
    "create_page_da_event": "DYNAMIC_ACTION",
    "create_page_da_action": "DYNAMIC_ACTION_ACTION",
    "create_list": "LIST",
    "create_list_item": "LIST_ITEM",
    "create_lov": "LOV",
    "create_authentication": "AUTHENTICATION",
    "create_authorization": "AUTHORIZATION",
    "create_theme": "THEME",
    "create_plugin": "PLUGIN",
}


@dataclass(frozen=True)
class ExportCall:
    routine: str
    object_type: str
    line: int
    column: int
    arguments: dict[str, Any]
    raw_arguments: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _skip_quoted(text: str, index: int) -> int:
    # Oracle alternative quoting: q'[text]', q'{text}', q'(text)', q'<text>'.
    if index > 0 and text[index - 1] in "qQ" and index + 1 < len(text):
        opener = text[index + 1]
        closer = {"[": "]", "{": "}", "(": ")", "<": ">"}.get(opener, opener)
        end = text.find(closer + "'", index + 2)
        return len(text) if end < 0 else end + 2

    quote = text[index]
    cursor = index + 1
    while cursor < len(text):
        if text[cursor] == quote:
            if cursor + 1 < len(text) and text[cursor + 1] == quote:
                cursor += 2
                continue
            return cursor + 1
        cursor += 1
    return len(text)


def _skip_trivia(text: str, index: int) -> int:
    cursor = index
    while cursor < len(text):
        if text[cursor].isspace():
            cursor += 1
        elif text.startswith("--", cursor):
            newline = text.find("\n", cursor + 2)
            cursor = len(text) if newline < 0 else newline + 1
        elif text.startswith("/*", cursor):
            end = text.find("*/", cursor + 2)
            cursor = len(text) if end < 0 else end + 2
        else:
            break
    return cursor


def _read_identifier(text: str, index: int) -> tuple[str, int]:
    cursor = index
    while cursor < len(text) and (text[cursor].isalnum() or text[cursor] in "_$# ."):
        cursor += 1
    return text[index:cursor].strip(), cursor


def _read_call_body(text: str, open_paren: int) -> tuple[str, int] | None:
    depth = 1
    cursor = open_paren + 1
    start = cursor
    while cursor < len(text):
        if text.startswith("--", cursor):
            newline = text.find("\n", cursor + 2)
            cursor = len(text) if newline < 0 else newline + 1
            continue
        if text.startswith("/*", cursor):
            end = text.find("*/", cursor + 2)
            if end < 0:
                return None
            cursor = end + 2
            continue
        if text[cursor] == "'":
            cursor = _skip_quoted(text, cursor)
            continue
        if text[cursor] == "(":
            depth += 1
        elif text[cursor] == ")":
            depth -= 1
            if depth == 0:
                return text[start:cursor], cursor + 1
        cursor += 1
    return None


def _split_top_level(value: str, delimiter: str = ",") -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    cursor = 0
    while cursor < len(value):
        if value.startswith("--", cursor):
            newline = value.find("\n", cursor + 2)
            cursor = len(value) if newline < 0 else newline + 1
            continue
        if value.startswith("/*", cursor):
            end = value.find("*/", cursor + 2)
            if end < 0:
                break
            cursor = end + 2
            continue
        char = value[cursor]
        if char == "'":
            cursor = _skip_quoted(value, cursor)
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == delimiter and depth == 0:
            parts.append(value[start:cursor].strip())
            start = cursor + 1
        cursor += 1
    tail = value[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _split_named_argument(argument: str) -> tuple[str | None, str]:
    depth = 0
    cursor = 0
    while cursor < len(argument):
        if argument[cursor] == "'":
            cursor = _skip_quoted(argument, cursor)
            continue
        if argument[cursor] == "(":
            depth += 1
        elif argument[cursor] == ")":
            depth -= 1
        elif depth == 0 and argument.startswith("=>", cursor):
            return argument[:cursor].strip().lower(), argument[cursor + 2 :].strip()
        cursor += 1
    return None, argument.strip()


def _decode_value(raw: str) -> Any:
    value = raw.strip()
    if value.lower() == "null":
        return None
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", value):
        return float(value) if "." in value else int(value)
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return {"expression": value}


def _parse_arguments(body: str) -> tuple[dict[str, Any], dict[str, str]]:
    parsed: dict[str, Any] = {}
    raw_values: dict[str, str] = {}
    positional = 0
    for argument in _split_top_level(body):
        name, raw = _split_named_argument(argument)
        if name is None:
            positional += 1
            name = f"$arg{positional}"
        raw_values[name] = raw
        parsed[name] = _decode_value(raw)
    return parsed, raw_values


def extract_export(text: str) -> dict[str, Any]:
    """Return normalized metadata calls, summary counts, and parser diagnostics."""
    calls: list[ExportCall] = []
    diagnostics: list[dict[str, Any]] = []
    cursor = 0
    while cursor < len(text):
        if text.startswith("--", cursor):
            newline = text.find("\n", cursor + 2)
            cursor = len(text) if newline < 0 else newline + 1
            continue
        if text.startswith("/*", cursor):
            end = text.find("*/", cursor + 2)
            if end < 0:
                diagnostics.append({"code": "APEXEXP001", "severity": "ERROR", "message": "Unterminated block comment"})
                break
            cursor = end + 2
            continue
        if text[cursor] == "'":
            cursor = _skip_quoted(text, cursor)
            continue
        if text[cursor].isalpha() or text[cursor] == "_":
            identifier, end = _read_identifier(text, cursor)
            normalized = identifier.replace(" ", "").lower()
            after = _skip_trivia(text, end)
            if normalized.startswith(CALL_PREFIXES) and after < len(text) and text[after] == "(":
                body_result = _read_call_body(text, after)
                if body_result is None:
                    line = text.count("\n", 0, cursor) + 1
                    diagnostics.append({
                        "code": "APEXEXP002",
                        "severity": "ERROR",
                        "message": f"Unterminated argument list for {identifier}",
                        "line": line,
                    })
                    break
                body, next_cursor = body_result
                arguments, raw_arguments = _parse_arguments(body)
                routine = normalized.rsplit(".", 1)[-1]
                line = text.count("\n", 0, cursor) + 1
                last_newline = text.rfind("\n", 0, cursor)
                column = cursor - last_newline
                calls.append(ExportCall(
                    routine=routine,
                    object_type=OBJECT_TYPES.get(routine, "OTHER"),
                    line=line,
                    column=column,
                    arguments=arguments,
                    raw_arguments=raw_arguments,
                ))
                cursor = next_cursor
                continue
            cursor = end
            continue
        cursor += 1

    counts: dict[str, int] = {}
    for call in calls:
        counts[call.object_type] = counts.get(call.object_type, 0) + 1
    return {
        "format": "apex2next.apex-export.v1",
        "calls": [call.to_dict() for call in calls],
        "summary": {"total_calls": len(calls), "object_counts": counts},
        "diagnostics": diagnostics,
    }
