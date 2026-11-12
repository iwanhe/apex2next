"""Supporting objects of an APEX export: the install scripts, as plain SQL (R4a).

An APEX application can carry the DDL and sample data it needs as *supporting objects*
(``application/deployment/install/*.sql``). The script text is stored as a PL/SQL varchar2 table built from
string literals, ``wwv_flow.LF`` and ``unistr(...)`` pieces. This module decodes that text **without executing
anything** and writes the INSTALL scripts in their install order, so the schema planner can read them as an
``install.sql``.

Only the text forms that the APEX exporter writes are decoded; anything else is an error with the file and the
line, never a guess.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .apex_export import _parse_arguments, _read_call_body

FORMAT = "apex2next.supporting-objects.v1"
_ASSIGN = re.compile(r"wwv_flow_imp\.g_varchar2_table\((\d+)\)\s*:=\s*", re.I)
_RESET = re.compile(r"wwv_flow_imp\.g_varchar2_table\s*:=\s*wwv_flow_imp\.empty_varchar2_table\s*;", re.I)
_CALL = re.compile(r"wwv_flow_imp_shared\.(create_install_script|create_install)\s*\(", re.I)
_CONSTANTS = {"wwv_flow.lf": "\n", "wwv_flow.cr": "\r", "wwv_flow.crlf": "\r\n", "wwv_flow.tab": "\t"}


class DecodeError(ValueError):
    pass


def _literal(text: str, i: int) -> tuple[str, int]:
    """Oracle string literal starting at text[i] == "'"; returns (value, index after it)."""
    out: list[str] = []
    j = i + 1
    while j < len(text):
        if text[j] == "'":
            if text.startswith("''", j):
                out.append("'")
                j += 2
                continue
            return "".join(out), j + 1
        out.append(text[j])
        j += 1
    raise DecodeError("unterminated string literal")


def _unistr(value: str) -> str:
    r"""UNISTR: \XXXX is a UTF-16 code unit, \\ is a backslash."""
    units: list[int] = []
    out: list[str] = []

    def flush() -> None:
        if units:
            out.append(b"".join(u.to_bytes(2, "big") for u in units).decode("utf-16-be"))
            units.clear()

    i = 0
    while i < len(value):
        if value[i] == "\\":
            if value.startswith("\\\\", i):
                flush()
                out.append("\\")
                i += 2
                continue
            code = value[i + 1:i + 5]
            if not re.fullmatch(r"[0-9A-Fa-f]{4}", code):
                raise DecodeError(f"bad UNISTR escape near {value[i:i + 6]!r}")
            units.append(int(code, 16))
            i += 5
            continue
        flush()
        out.append(value[i])
        i += 1
    flush()
    return "".join(out)


def decode_expression(text: str, start: int, end: str = ";") -> tuple[str, int]:
    """Decode ``piece || piece || ... ;`` starting at ``start``; returns (value, index after the terminator).

    A piece is a string literal, a ``wwv_flow`` text constant or ``unistr(<concatenation>)``.
    """
    parts: list[str] = []
    i = start
    expect_piece = True
    while i < len(text):
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if expect_piece:
            if c == "'":
                value, i = _literal(text, i)
                parts.append(value)
            elif text[i:i + 6].lower() == "unistr" and text[i + 6:].lstrip().startswith("("):
                value, i = decode_expression(text, text.index("(", i) + 1, ")")
                parts.append(_unistr(value))
            else:
                m = re.match(r"wwv_flow\.[a-z]+", text[i:], re.I)
                if not m or m.group(0).lower() not in _CONSTANTS:
                    raise DecodeError(f"unexpected text {text[i:i + 30]!r}")
                parts.append(_CONSTANTS[m.group(0).lower()])
                i += len(m.group(0))
            expect_piece = False
            continue
        if text.startswith("||", i):
            i += 2
            expect_piece = True
            continue
        if c == end:
            return "".join(parts), i + 1
        raise DecodeError(f"unexpected text {text[i:i + 30]!r}")
    raise DecodeError("statement not terminated")


@dataclass
class Script:
    file: str
    name: str
    sequence: int
    script_type: str
    text: str
    condition: dict[str, Any] = field(default_factory=dict)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def _line(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def parse_install_file(path: Path, rel: str) -> list[Script]:
    text = path.read_text(encoding="utf-8")
    table: dict[int, str] = {}
    scripts: list[Script] = []
    events: list[tuple[int, str, re.Match[str]]] = []
    for m in _RESET.finditer(text):
        events.append((m.start(), "reset", m))
    for m in _ASSIGN.finditer(text):
        events.append((m.start(), "assign", m))
    for m in _CALL.finditer(text):
        events.append((m.start(), "call", m))
    for _, kind, m in sorted(events, key=lambda e: e[0]):
        try:
            if kind == "reset":
                table = {}
            elif kind == "assign":
                value, _ = decode_expression(text, m.end())
                table[int(m.group(1))] = value
            elif m.group(1).lower() == "create_install_script":
                body = _read_call_body(text, m.end() - 1)
                if body is None:
                    raise DecodeError("unterminated create_install_script call")
                args, raw = _parse_arguments(body[0])
                clob = raw.get("p_script_clob", "")
                if "g_varchar2_table" in clob:
                    if sorted(table) != list(range(1, len(table) + 1)):
                        raise DecodeError("varchar2 table has gaps")
                    script_text = "".join(table[k] for k in sorted(table))
                elif isinstance(args.get("p_script_clob"), str):
                    script_text = args["p_script_clob"]
                else:
                    raise DecodeError(f"unsupported p_script_clob form {clob[:40]!r}")
                condition = {k[2:]: v for k, v in args.items() if k.startswith("p_condition") and v is not None}
                scripts.append(Script(rel, str(args.get("p_name")), int(args.get("p_sequence") or 0),
                                      str(args.get("p_script_type") or "INSTALL"), script_text, condition))
        except DecodeError as exc:
            raise DecodeError(f"{rel}:{_line(text, m.start())}: {exc}") from None
    return scripts


def read_supporting_objects(export_dir: Path) -> list[Script]:
    """INSTALL and UPGRADE scripts of an APEX split export, in install order."""
    app = export_dir / "application" if (export_dir / "application").is_dir() else export_dir
    install_dir = app / "deployment" / "install"
    scripts: list[Script] = []
    for path in sorted(install_dir.glob("*.sql")) if install_dir.is_dir() else []:
        scripts += parse_install_file(path, path.relative_to(app).as_posix())
    return sorted(scripts, key=lambda s: (s.script_type != "INSTALL", s.sequence, s.name))


def render_install_sql(scripts: list[Script], *, title: str) -> str:
    out = [f"-- Supporting objects of {title}: INSTALL scripts in install order.",
           "-- Decoded by `apex2next supporting-objects` from the APEX export; nothing was executed.", ""]
    for s in scripts:
        if s.script_type != "INSTALL":
            continue
        out.append(f"-- >>> script {s.sequence}: {s.name} ({s.file}, sha256 {s.sha256[:16]})")
        if s.condition:
            out.append(f"-- condition: {json.dumps(s.condition, ensure_ascii=False)}")
        body = s.text if s.text.endswith("\n") else s.text + "\n"
        out.append(body)
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the supporting-object install scripts of an APEX export as SQL")
    parser.add_argument("export_dir", type=Path, help="split export directory (contains application/)")
    parser.add_argument("--output", type=Path, required=True, help="install.sql to write")
    parser.add_argument("--manifest", type=Path, help="JSON list of the scripts with their hashes")
    args = parser.parse_args()
    scripts = read_supporting_objects(args.export_dir)
    installs = [s for s in scripts if s.script_type == "INSTALL"]
    if not installs:
        raise SystemExit("no INSTALL supporting-object scripts in this export")
    args.output.write_text(render_install_sql(scripts, title=args.export_dir.name), encoding="utf-8")
    if args.manifest:
        args.manifest.write_text(json.dumps({"format": FORMAT, "scripts": [
            {"file": s.file, "name": s.name, "sequence": s.sequence, "type": s.script_type, "sha256": s.sha256,
             "bytes": len(s.text.encode("utf-8")), **({"condition": s.condition} if s.condition else {})}
            for s in scripts]}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(installs)} install script(s), {sum(len(s.text) for s in installs)} characters -> {args.output}")
    for s in scripts:
        print(f"  {s.script_type:<8} {s.sequence:>4}  {s.name}{'  (conditional)' if s.condition else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
