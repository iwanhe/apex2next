"""Offline normalization and reconciliation of Oracle dictionary CSV exports."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

FORMAT = "apex2next.oracle.metadata-manifest.v1"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {path}")
        return [{str(k or "").strip().lower(): str(v or "").strip()
                 for k, v in row.items()} for row in reader]


def object_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("owner", "")).upper(),
            str(row.get("objectType", row.get("object_type", ""))).upper(),
            str(row.get("objectName", row.get("object_name", ""))).upper())


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def build_manifest(dictionary_csv: Path, ddl_dir: Path, *, extracted_at: str,
                   owner_filter: str | None = None) -> dict[str, Any]:
    if not extracted_at.strip():
        raise ValueError("extracted_at must be a non-empty ISO-8601 timestamp")
    objects: list[dict[str, Any]] = []
    diagnostics: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in read_csv(dictionary_csv):
        owner, kind, name = row.get("owner", "").upper(), row.get("object_type", "").upper(), row.get("object_name", "")
        if owner_filter and owner != owner_filter.upper():
            continue
        if not owner or not kind or not name:
            diagnostics.append({"code": "ORA_META001", "severity": "ERROR", "message": "Missing OWNER, OBJECT_TYPE, or OBJECT_NAME."})
            continue
        key = (owner, kind, name.upper())
        if key in seen:
            diagnostics.append({"code": "ORA_META002", "severity": "ERROR", "message": f"Duplicate dictionary object: {owner}.{name} ({kind})."})
            continue
        seen.add(key)
        ddl_file = row.get("ddl_file", "")
        ddl: dict[str, Any] = {"status": "NOT_REQUESTED", "file": None, "sha256": None}
        if ddl_file:
            root, candidate = ddl_dir.resolve(), (ddl_dir / ddl_file).resolve()
            if root not in candidate.parents:
                ddl["status"] = "REJECTED_PATH"
                diagnostics.append({"code": "ORA_META003", "severity": "ERROR", "message": f"DDL path escapes extraction directory: {owner}.{name}."})
            elif candidate.is_file():
                ddl = {"status": "EXTRACTED", "file": candidate.relative_to(root).as_posix(), "sha256": file_hash(candidate)}
            else:
                ddl = {"status": "MISSING", "file": ddl_file, "sha256": None}
                diagnostics.append({"code": "ORA_META004", "severity": "WARNING", "message": f"DDL file missing: {owner}.{name} ({ddl_file})."})
        objects.append({"owner": owner, "objectType": kind, "objectName": name,
                        "status": row.get("status") or None, "lastDdlTime": row.get("last_ddl_time") or None,
                        "ddl": ddl})
    objects.sort(key=lambda x: (x["owner"], x["objectType"], x["objectName"].upper()))
    counts = Counter(x["objectType"] for x in objects)
    return {"format": FORMAT, "extractedAt": extracted_at,
            "source": {"dictionaryCsv": dictionary_csv.name, "ddlDirectory": ddl_dir.name},
            "objects": objects,
            "summary": {"dictionaryObjects": len(objects),
                        "ddlExtracted": sum(x["ddl"]["status"] == "EXTRACTED" for x in objects),
                        "ddlMissing": sum(x["ddl"]["status"] == "MISSING" for x in objects),
                        "byObjectType": dict(sorted(counts.items())), "diagnostics": len(diagnostics)},
            "diagnostics": sorted(diagnostics, key=lambda x: (x["code"], x["message"]))}


def reconcile_manifest(manifest: dict[str, Any], dictionary_csv: Path) -> dict[str, Any]:
    if manifest.get("format") != FORMAT:
        raise ValueError(f"Unsupported manifest format: {manifest.get('format')!r}")
    expected = {object_key({"owner": r.get("owner"), "object_type": r.get("object_type"),
                            "object_name": r.get("object_name")}) for r in read_csv(dictionary_csv)}
    expected.discard(("", "", ""))
    actual = {object_key(item) for item in manifest.get("objects", [])}
    missing, unexpected = sorted(expected - actual), sorted(actual - expected)
    exp_counts, act_counts = Counter(k[1] for k in expected), Counter(k[1] for k in actual)
    types = sorted(set(exp_counts) | set(act_counts))
    by_type = [{"objectType": t, "dictionaryCount": exp_counts[t], "manifestCount": act_counts[t],
                "matches": exp_counts[t] == act_counts[t]} for t in types]
    return {"format": "apex2next.oracle.metadata-reconciliation.v1",
            "status": "PASS" if not missing and not unexpected else "MISMATCH",
            "dictionaryObjectCount": len(expected), "manifestObjectCount": len(actual),
            "missingFromManifest": [list(k) for k in missing],
            "unexpectedInManifest": [list(k) for k in unexpected],
            "byObjectType": by_type, "ddlCoverage": manifest.get("summary", {})}


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize Oracle dictionary CSV exports")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("dictionary_csv", type=Path)
    build.add_argument("--ddl-dir", type=Path, required=True)
    build.add_argument("--extracted-at", required=True)
    build.add_argument("--owner")
    build.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("reconcile")
    check.add_argument("manifest", type=Path)
    check.add_argument("dictionary_csv", type=Path)
    check.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        result = build_manifest(args.dictionary_csv, args.ddl_dir, extracted_at=args.extracted_at, owner_filter=args.owner)
    else:
        result = reconcile_manifest(json.loads(args.manifest.read_text(encoding="utf-8")), args.dictionary_csv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 1 if result.get("status") == "MISMATCH" else 0


if __name__ == "__main__":
    raise SystemExit(main())
