"""WP9.3b dictionary overrides: replace stale script statements with installed DDL.

An override is an explicit, evidence-backed decision record. The original
script is never edited. The effective source is computed deterministically
by replacing the statement that defines the overridden object, or by appending
it if the object is not in the script, and every replacement is reported.

Override file format (JSON)::

    {"format": "apex2next.dictionary-overrides.v1",
     "evidence": [{"name": "...csv", "sha256": "...", "query": "..."}],
     "overrides": [{"object": "VIEW", "name": "X", "reason": "...", "lastDdl": "...",
                    "ddl": "create or replace force view x as <installed text>"}]}
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .sql_tokens import identifier_name, significant, split_script

OVERRIDES_FORMAT = "apex2next.dictionary-overrides.v1"
SUPPORTED = {"VIEW", "TABLE", "INDEX", "TRIGGER", "PACKAGE", "PACKAGE_BODY", "SEQUENCE"}


def _sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _defined_object(stmt) -> tuple[str, str] | None:
    if stmt.kind not in SUPPORTED:
        return None
    sig = significant(stmt.tokens)
    keyword = {"PACKAGE_BODY": "BODY"}.get(stmt.kind, stmt.kind)
    for i, t in enumerate(sig[:-1]):
        if t.upper == keyword:
            j = i + 1
            if j + 2 < len(sig) and sig[j + 1].text == ".":
                j += 2
            return stmt.kind, identifier_name(sig[j])
    return None


def load_overrides(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != OVERRIDES_FORMAT:
        raise ValueError(f"{path} is not an {OVERRIDES_FORMAT} file.")
    return data


def apply_overrides(source: str, overrides: dict[str, Any] | None) -> tuple[str, list[dict[str, Any]]]:
    """Return (effective source, replacement records)."""
    if not overrides:
        return source, []
    records: list[dict[str, Any]] = []
    statements = split_script(source)
    replacements: list[tuple[int, int, str]] = []
    appended: list[str] = []
    for ov in overrides["overrides"]:
        kind = ov["object"].replace(" ", "_").upper()
        name = ov["name"].upper()
        ddl = ov["ddl"].strip().rstrip(";").rstrip()
        check = split_script(ddl + ";\n" if kind not in {"TRIGGER", "PACKAGE", "PACKAGE_BODY"} else ddl + "\n/\n")
        if len(check) != 1 or _defined_object(check[0]) != (kind, name):
            raise ValueError(f"Override for {kind} {name} does not define exactly that object.")
        target = next((s for s in statements if _defined_object(s) == (kind, name)), None)
        record = {"object": f"{ov['object'].upper()} {name}", "reason": ov.get("reason"),
                  "lastDdl": ov.get("lastDdl"), "overrideSha256": _sha(ddl)}
        if target is not None:
            if source[target.offset:target.offset + len(target.text)] != target.text:
                raise ValueError(f"Cannot locate statement for {kind} {name} in source.")
            replacements.append((target.offset, target.offset + len(target.text), ddl))
            record.update({"action": "replaced", "line": target.line, "originalSha256": _sha(target.text)})
        else:
            appended.append(ddl)
            record.update({"action": "appended"})
        records.append(record)
    effective = source
    for start, end, ddl in sorted(replacements, reverse=True):
        effective = effective[:start] + ddl + effective[end:]
    for ddl in appended:
        effective = effective.rstrip("\n") + "\n\n" + ddl + ";\n"
    return effective, records


def view_override(name: str, text: str, *, force: bool = True, reason: str, last_ddl: str | None) -> dict[str, Any]:
    """Build a VIEW override from USER_VIEWS.TEXT_VC."""
    if not re.match(r"\s*(select|with)\b", text, re.I):
        raise ValueError("View text must start with SELECT or WITH.")
    head = "create or replace force view" if force else "create or replace view"
    return {"object": "VIEW", "name": name.upper(), "reason": reason, "lastDdl": last_ddl,
            "ddl": f"{head} {name.lower()} as\n{text.rstrip()}"}


def main() -> int:
    """Build an overrides file from USER_VIEWS text exported as CSV (VIEW_NAME, TEXT_LENGTH, TEXT_VC)."""
    import argparse
    import csv

    parser = argparse.ArgumentParser(description="Create dictionary overrides for drifted views")
    parser.add_argument("view_texts", type=Path, help="CSV with VIEW_NAME, TEXT_LENGTH, TEXT_VC")
    parser.add_argument("--view", action="append", required=True, help="view to override (repeatable)")
    parser.add_argument("--dictionary", type=Path, help="dictionary inventory CSV (for LAST_DDL_TIME)")
    parser.add_argument("--reason", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.view_texts.read_bytes()
    rows = {r["VIEW_NAME"].upper(): r for r in csv.DictReader(raw.decode("utf-8").splitlines(keepends=True))}
    last_ddl = {}
    evidence = [{"name": args.view_texts.name, "sha256": hashlib.sha256(raw).hexdigest(),
                 "query": "select view_name, text_length, text_vc from user_views where view_name in (...)"}]
    if args.dictionary:
        draw = args.dictionary.read_bytes()
        for r in csv.DictReader(draw.decode("utf-8").splitlines(keepends=True)):
            if r["SECTION"] == "OBJECT":
                last_ddl[(r["OBJ"], r["ITEM"])] = r["C3"]
        evidence.append({"name": args.dictionary.name, "sha256": hashlib.sha256(draw).hexdigest(),
                         "query": "sql/dictionary_inventory_apex_workshop.sql"})
    overrides = []
    for name in args.view:
        row = rows[name.upper()]
        if int(row["TEXT_LENGTH"]) != len(row["TEXT_VC"]):
            raise SystemExit(f"{name}: TEXT_LENGTH {row['TEXT_LENGTH']} != exported length {len(row['TEXT_VC'])} (truncated?)")
        overrides.append(view_override(name, row["TEXT_VC"], reason=args.reason,
                                       last_ddl=last_ddl.get(("VIEW", name.upper()))))
    args.output.write_text(json.dumps({"format": OVERRIDES_FORMAT, "evidence": evidence, "overrides": overrides},
                                      indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
