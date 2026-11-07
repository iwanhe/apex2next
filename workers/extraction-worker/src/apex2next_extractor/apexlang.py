"""Static inventory parser for APEXLang application source directories."""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any

DECLARATION_TYPES = {
    "app":"APPLICATION", "page":"PAGE", "region":"REGION", "pageitem":"ITEM",
    "button":"BUTTON", "process":"PROCESS", "validation":"VALIDATION",
    "dynamicaction":"DYNAMIC_ACTION", "action":"DYNAMIC_ACTION_ACTION",
    "column":"COLUMN", "displaycolumn":"DISPLAY_COLUMN", "lov":"LOV",
    "entry":"COMPONENT_ENTRY", "authorization":"AUTHORIZATION",
    "authentication":"AUTHENTICATION", "list":"LIST", "listitem":"LIST_ITEM",
    "breadcrumb":"BREADCRUMB", "theme":"THEME", "pagegroup":"PAGE_GROUP",
    "staticfile":"STATIC_FILE", "buildoption":"BUILD_OPTION",
    "componentsetting":"COMPONENT_SETTING", "supportingobject":"SUPPORTING_OBJECT",
    "supportingobjects":"SUPPORTING_OBJECT", "savedreport":"SAVED_REPORT",
    "sort":"REPORT_SORT", "parameter":"PARAMETER", "series":"CHART_SERIES",
    "axis":"CHART_AXIS",
}
DECLARATION_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<kind>[A-Za-z][A-Za-z0-9_-]*)"
    r"(?:[ \t]+(?P<name>[A-Za-z0-9_.-]+))?[ \t]*\(", re.MULTILINE
)
REFERENCE_RE = re.compile(r"(?<![A-Za-z0-9_])@(?P<ref>[A-Za-z0-9_./-]+)")


def _mask_non_code(source: str) -> str:
    chars, i = list(source), 0
    fence = chr(96) * 3
    while i < len(source):
        if source.startswith(fence, i) or source.startswith("~~~", i):
            marker = source[i:i + 3]
            end = source.find(marker, i + 3)
            end = len(source) if end < 0 else end + 3
            for pos in range(i, end):
                if chars[pos] != "\n":
                    chars[pos] = " "
            i = end
            continue
        if source.startswith("//", i) or source.startswith("--", i):
            end = source.find("\n", i + 2)
            end = len(source) if end < 0 else end
            for pos in range(i, end):
                chars[pos] = " "
            i = end
            continue
        if source.startswith("/*", i):
            end = source.find("*/", i + 2)
            end = len(source) if end < 0 else end + 2
            for pos in range(i, end):
                if chars[pos] != "\n":
                    chars[pos] = " "
            i = end
            continue
        if source[i] == "'" or source[i] == chr(34):
            quote, start = source[i], i
            i += 1
            while i < len(source):
                if source[i] == quote:
                    if i + 1 < len(source) and source[i + 1] == quote:
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            for pos in range(start, i):
                if chars[pos] != "\n":
                    chars[pos] = " "
            continue
        i += 1
    return "".join(chars)


def _matching_close(masked: str, opening: int) -> int | None:
    depth = 1
    for i in range(opening + 1, len(masked)):
        if masked[i] == "(":
            depth += 1
        elif masked[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return None


def _decode_property_literal(raw: str) -> tuple[str, Any, str | None]:
    """Decode only unambiguous scalar literals; retain all other source as an expression."""
    value = raw.strip()
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return "STRING", value[1:-1].replace("''", "'"), None
    if len(value) >= 2 and value[0] == chr(34) and value[-1] == chr(34):
        try:
            return "STRING", json.loads(value), None
        except json.JSONDecodeError:
            return "UNKNOWN", None, value
    if value.lower() in {"true", "false"}:
        return "BOOLEAN", value.lower() == "true", None
    if value.lower() in {"null", "none"}:
        return "NULL", None, None
    if re.fullmatch(r"[+-]?\d+", value):
        return "NUMBER", int(value), None
    if re.fullmatch(r"[+-]?(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?|[+-]?\d+[eE][+-]?\d+", value):
        return "NUMBER", float(value), None
    return "UNKNOWN", None, value


def _property_records(
    body: str, *, start_line: int = 1, start_column: int = 1
) -> list[dict[str, Any]]:
    """Extract direct and nested brace-delimited properties without evaluating expressions."""
    masked = _mask_non_code(body)
    roots: dict[str, Any] = {}
    stack: list[tuple[dict[str, Any], dict[str, Any], str, int, list[str]]] = []
    line_start = 0

    def locator_for(prefix: str, line_number: int) -> tuple[int, int]:
        column = (
            start_column + len(prefix)
            if line_number == start_line
            else len(prefix) + 1
        )
        return line_number, column

    lines = body.splitlines(keepends=True)
    masked_lines = masked.splitlines(keepends=True)
    if len(masked_lines) < len(lines):
        masked_lines.extend([""] * (len(lines) - len(masked_lines)))

    for raw_line_with_newline, masked_line_with_newline in zip(lines, masked_lines):
        raw_line = raw_line_with_newline.rstrip("\r\n")
        masked_line = masked_line_with_newline.rstrip("\r\n")
        line_number = start_line + body.count("\n", 0, line_start)
        line_start += len(raw_line_with_newline)
        stripped_masked = masked_line.strip()
        if not stripped_masked:
            continue

        close_count = 1 if re.fullmatch(r"}", stripped_masked) else 0
        for _ in range(close_count):
            if stack:
                parent_map, record, key, block_start, raw_parts = stack.pop()
                record["value"] = parent_map
                record["valueType"] = "OBJECT"
                record["extensions"] = {
                    "rawBlock": "\n".join(raw_parts + [raw_line.strip()])
                }

        match = re.match(
            r"^[ \t]*([A-Za-z][A-Za-z0-9_]*)\s*(?::\s*)?(.*?)[ \t]*$",
            raw_line,
        )
        masked_match = re.match(
            r"^[ \t]*([A-Za-z][A-Za-z0-9_]*)\s*(?::\s*)?(.*?)[ \t]*$",
            masked_line,
        )
        if not match or not masked_match:
            continue

        name, raw_value = match.groups()
        _, masked_value = masked_match.groups()
        prefix = raw_line[:match.start(1)]
        prop_line, prop_column = locator_for(prefix, line_number)
        opens_block = masked_value.strip() == "{"
        if opens_block:
            record: dict[str, Any] = {
                "name": name,
                "value_type": "OBJECT",
                "line": prop_line,
                "column": prop_column,
                "raw": raw_value.strip(),
                "children": [],
            }
            target = stack[-1][0] if stack else roots
            target[name] = record
            raw_parts = [raw_line.strip()]
            stack.append(({}, record, name, line_number, raw_parts))
            continue

        # The masked value is intentionally blank for quoted literals; decode from raw source.
        value_type, value, raw_expression = _decode_property_literal(raw_value)
        record = {
            "name": name,
            "value_type": value_type,
            "line": prop_line,
            "column": prop_column,
            "raw": raw_value.strip(),
        }
        if value_type in {"STRING", "NUMBER", "BOOLEAN", "NULL"}:
            record["value"] = value
        if raw_expression is not None:
            record["raw_expression"] = raw_expression
        target = stack[-1][0] if stack else roots
        target[name] = record

        # Keep raw source lines for any enclosing object block.
        for frame in stack:
            frame[4].append(raw_line.strip())

    def as_records(mapping: dict[str, Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for value in mapping.values():
            record = dict(value)
            if record.get("value_type") == "OBJECT":
                nested = record.get("value", {})
                record["children"] = as_records(nested)
                record["value"] = {
                    child["name"]: _record_to_property(child)
                    for child in record["children"]
                }
            result.append(record)
        return result

    return as_records(roots)


def _record_to_property(record: dict[str, Any]) -> dict[str, Any]:
    value_type = record.get("value_type", "UNKNOWN")
    result: dict[str, Any] = {"valueType": value_type}
    if "value" in record:
        result["value"] = record["value"]
    if "raw_expression" in record:
        result["rawExpression"] = record["raw_expression"]
        result["preserved"] = True
    if value_type == "OBJECT":
        result["value"] = {
            child["name"]: _record_to_property(child)
            for child in record.get("children", [])
        }
        result["extensions"] = record.get("extensions", {})
    return result


def _direct_properties(body: str) -> dict[str, Any]:
    """Backward-compatible scalar/property map for existing inventory consumers."""
    result: dict[str, Any] = {}
    for record in _property_records(body):
        if "value" in record:
            result[record["name"]] = record["value"]
        else:
            result[record["name"]] = record["raw_expression"]
    return result


def parse_apexlang_text(source: str, file_path: str = "") -> dict[str, Any]:
    masked = _mask_non_code(source)
    declarations, diagnostics = [], []
    for match in DECLARATION_RE.finditer(masked):
        kind = match.group("kind")
        object_type = DECLARATION_TYPES.get(kind.lower(), "UNKNOWN")
        if object_type == "UNKNOWN":
            diagnostics.append({
                "code": "APEXLANG003",
                "severity": "WARNING",
                "file": file_path,
                "line": source.count("\n", 0, match.start()) + 1,
                "message": f"Unmapped declaration preserved as UNKNOWN: {kind}",
            })
        opening = source.find("(", match.start(), match.end())
        closing = _matching_close(masked, opening)
        line = source.count("\n", 0, match.start()) + 1
        line_start = source.rfind("\n", 0, match.start()) + 1
        column = match.start() - line_start + 1
        indent = len(match.group("indent").expandtabs(4))
        if closing is None:
            diagnostics.append({"code":"APEXLANG001","severity":"ERROR","file":file_path,
                                "line":line,"message":f"Unterminated declaration: {kind}"})
            continue
        declarations.append({
            "object_type":object_type, "kind":kind, "name":match.group("name") or "",
            "line":line, "column":column, "indent":indent, "file":file_path,
            "properties":_direct_properties(source[opening + 1:closing]),
            "property_details":_property_records(
                source[opening + 1:closing],
                start_line=source.count("\n", 0, opening) + 1,
                start_column=(opening - source.rfind("\n", 0, opening) + 1),
            ),
            "raw_body":source[opening + 1:closing],
        })
    return {
        "declarations":declarations,
        "references":sorted(set(REFERENCE_RE.findall(masked))),
        "diagnostics":diagnostics,
    }


def extract_apexlang(source_dir: str | Path) -> dict[str, Any]:
    root = Path(source_dir).resolve()
    files = sorted(
        path for path in root.rglob("*.apx")
        if path.is_file() and not path.is_symlink() and root in path.resolve().parents
    )
    declarations, references, diagnostics, file_summaries = [], set(), [], []
    for path in files:
        relative = path.relative_to(root).as_posix()
        parsed = parse_apexlang_text(path.read_text(encoding="utf-8"), relative)
        declarations.extend(parsed["declarations"])
        references.update(parsed["references"])
        diagnostics.extend(parsed["diagnostics"])
        file_summaries.append({"file":relative,"declaration_count":len(parsed["declarations"])})
    version_path = root / ".apex" / "apexlang.json"
    mmd_version = None
    if version_path.is_file() and not version_path.is_symlink() and root in version_path.resolve().parents:
        try:
            mmd_version = json.loads(version_path.read_text(encoding="utf-8")).get("mmdVersion")
        except (json.JSONDecodeError, OSError) as exc:
            diagnostics.append({"code":"APEXLANG002","severity":"WARNING",
                                "file":".apex/apexlang.json","message":str(exc)})
    counts: dict[str, int] = {}
    for item in declarations:
        counts[item["object_type"]] = counts.get(item["object_type"], 0) + 1
    pages = [item for item in declarations if item["object_type"] == "PAGE"]
    app = next((item for item in declarations if item["object_type"] == "APPLICATION"), None)
    return {
        "format":"apex2next.apexlang-inventory.v1","source_format":"APEXLANG",
        "apexlang_mmd_version":mmd_version,"application":app,
        "summary":{"file_count":len(files),"declaration_count":len(declarations),
                   "page_count":len(pages),"object_counts":counts,
                   "reference_count":len(references)},
        "pages":pages,"declarations":declarations,"references":sorted(references),
        "files":file_summaries,"diagnostics":diagnostics,
        "limitations":[
            "Static declaration inventory only; no APEXLang execution or semantic evaluation.",
            "Nested property blocks are not yet converted into a complete normalized application IR.",
            "SQL, PL/SQL, JavaScript, authorization expressions, and deployment behavior remain source expressions.",
            "Reference collection is lexical; target resolution and dangling-reference validation are not implemented.",
            "mmdVersion is APEXLang metadata and is not proof of the Oracle APEX runtime release.",
        ],
    }
