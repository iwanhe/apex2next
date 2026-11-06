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
    "componentsetting":"COMPONENT_SETTING", "supportingobject":"SUPPORTING_OBJECTS",
    "supportingobjects":"SUPPORTING_OBJECTS", "savedreport":"SAVED_REPORT",
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


def _direct_properties(body: str) -> dict[str, Any]:
    masked = _mask_non_code(body)
    result: dict[str, Any] = {}
    paren = brace = bracket = 0
    line_start = 0
    for i, ch in enumerate(masked + "\n"):
        if ch == "(":\n            paren += 1
        elif ch == ")":\n            paren -= 1
        elif ch == "{":\n            brace += 1
        elif ch == "}":\n            brace -= 1
        elif ch == "[":\n            bracket += 1
        elif ch == "]":\n            bracket -= 1
        elif ch == "\n":
            if paren == brace == bracket == 0:
                raw_line = body[line_start:i].strip()
                match = re.match(r"([A-Za-z][A-Za-z0-9_]*)\s*:\s*(.*?)\s*$", raw_line)
                if match:
                    key, raw = match.groups()
                    if raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
                        value: Any = raw[1:-1].replace("''", "'")
                    elif raw.lower() in {"true", "false"}:
                        value = raw.lower() == "true"
                    elif re.fullmatch(r"-?\d+", raw):
                        value = int(raw)
                    else:
                        value = raw
                    result[key] = value
            line_start = i + 1
    return result


def parse_apexlang_text(source: str, file_path: str = "") -> dict[str, Any]:
    masked = _mask_non_code(source)
    declarations, diagnostics = [], []
    for match in DECLARATION_RE.finditer(masked):
        kind = match.group("kind")
        object_type = DECLARATION_TYPES.get(kind.lower())
        if not object_type:
            continue
        opening = source.find("(", match.start(), match.end())
        closing = _matching_close(masked, opening)
        line = source.count("\n", 0, match.start()) + 1
        if closing is None:
            diagnostics.append({"code":"APEXLANG001","severity":"ERROR","file":file_path,
                                "line":line,"message":f"Unterminated declaration: {kind}"})
            continue
        declarations.append({
            "object_type":object_type, "kind":kind, "name":match.group("name") or "",
            "line":line, "file":file_path,
            "properties":_direct_properties(source[opening + 1:closing]),
        })
    return {
        "declarations":declarations,
        "references":sorted(set(REFERENCE_RE.findall(masked))),
        "diagnostics":diagnostics,
    }


def extract_apexlang(source_dir: str | Path) -> dict[str, Any]:
    root = Path(source_dir)
    files = sorted(path for path in root.rglob("*.apx") if path.is_file())
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
    if version_path.exists():
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
