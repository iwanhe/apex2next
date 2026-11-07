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
    """Extract direct scalar properties with exact raw text and source coordinates."""
    masked = _mask_non_code(body)
    records: list[dict[str, Any]] = []
    paren = brace = bracket = 0
    line_start = 0
    for index, char in enumerate(masked + "\n"):
        if char == "(":
            paren += 1
        elif char == ")":
            paren -= 1
        elif char == "{":
            brace += 1
        elif char == "}":
            brace -= 1
        elif char == "[":
            bracket += 1
        elif char == "]":
            bracket -= 1
        elif char == "\n":
            raw_line = body[line_start:index]
            if paren == brace == bracket == 0:
                match = re.match(r"^[ \t]*([A-Za-z][A-Za-z0-9_]*)\s*:\s*(.*?)\s*$", raw_line)
                if match:
                    name, raw_value = match.groups()
                    value_type, value, raw_expression = _decode_property_literal(raw_value)
                    prefix = raw_line[:match.start(1)]
                    line_number = start_line + body.count("\n", 0, line_start)
                    column = (
                        start_column + len(prefix)
                        if line_number == start_line
                        else len(prefix) + 1
                    )
                    record: dict[str, Any] = {
                        "name": name,
                        "value_type": value_type,
                        "line": line_number,
                        "column": column,
                        "raw": raw_value,
                    }
                    if value_type in {"STRING", "NUMBER", "BOOLEAN", "NULL"}:
                        record["value"] = value
                    if raw_expression is not None:
                        record["raw_expression"] = raw_expression
                    records.append(record)
            line_start = index + 1
    return records


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
                start_line=source.count("\\n", 0, opening) + 1,
                start_column=(opening - source.rfind("\\n", 0, opening) + 1),
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
