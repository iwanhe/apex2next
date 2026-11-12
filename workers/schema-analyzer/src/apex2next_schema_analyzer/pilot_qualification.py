"""Offline WP9 pilot qualification assessor; validates declared evidence only."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

INPUT_VERSION = "apex2next.wp9-pilot-input.v1"
REPORT_VERSION = "apex2next.wp9-pilot-qualification.v1"
SHA = re.compile(r"^sha256:[0-9a-f]{64}$")
GATES = (
    ("WP9-001", "Source package intake and integrity"),
    ("WP9-002", "APEX runtime/version and scope confirmed"),
    ("WP9-003", "Extraction and normalized IR reviewed"),
    ("WP9-004", "Oracle schema and metadata inventory reconciled"),
    ("WP9-005", "PL/SQL and dependency dispositions reviewed"),
    ("WP9-006", "Target schema and generated runtime reviewed"),
    ("WP9-007", "Data migration rehearsal and reconciliation"),
    ("WP9-008", "Critical journey functional parity"),
    ("WP9-009", "Security and authorization parity"),
    ("WP9-010", "Performance and operational acceptance"),
    ("WP9-011", "Backup restore and rollback rehearsal"),
    ("WP9-012", "Business and technical owner acceptance"),
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _source_checks(source: Any) -> list[dict[str, Any]]:
    source = source if isinstance(source, dict) else {}
    checks: list[dict[str, Any]] = []
    supported = source.get("format") in {"APEX_SQL_EXPORT", "APEXLANG_DIRECTORY"}
    checks.append({
        "id": "SRC-001",
        "status": "PASS" if supported else "FAIL",
        "message": "Supported source format declared." if supported else "Unsupported or missing source format.",
    })
    sanitized = source.get("sanitized")
    checks.append({
        "id": "SRC-002",
        "status": "PASS" if sanitized is True else "FAIL" if sanitized is False else "NOT_VERIFIED",
        "message": "Sanitization attested by submitter." if sanitized is True
        else "Source package must be explicitly confirmed sanitized.",
    })
    for key, code in (("applicationId", "SRC-003"), ("apexRuntimeVersion", "SRC-004"), ("snapshotId", "SRC-005")):
        present = _text(source.get(key))
        checks.append({
            "id": code,
            "status": "PASS" if present else "NOT_VERIFIED",
            "message": f"{key} declared." if present else f"{key} missing.",
        })

    artifacts = source.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        checks.append({"id": "SRC-006", "status": "NOT_VERIFIED", "message": "Source artifact inventory missing."})
        return checks

    seen: set[str] = set()
    invalid: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            invalid.append("malformed artifact")
            continue
        path = artifact.get("path")
        digest = artifact.get("sha256")
        size = artifact.get("sizeBytes")
        if not _text(path) or path.startswith(("/", "\\")) or ".." in Path(path).parts or path in seen:
            invalid.append(f"{path}: unsafe or duplicate path")
        if not isinstance(digest, str) or not SHA.fullmatch(digest):
            invalid.append(f"{path}: invalid SHA-256")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            invalid.append(f"{path}: invalid size")
        if _text(path):
            seen.add(path)
    checks.append({
        "id": "SRC-006",
        "status": "FAIL" if invalid else "PASS",
        "message": "; ".join(invalid[:8]) if invalid else "Artifact paths, sizes, and hash declarations are structurally valid.",
    })
    return checks


def assess_pilot(manifest: dict[str, Any]) -> dict[str, Any]:
    """Assess the WP9 evidence manifest without opening source artifacts or connecting to systems."""
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    if manifest.get("manifestVersion") != INPUT_VERSION:
        raise ValueError(f"manifestVersion must be {INPUT_VERSION}")
    project = manifest.get("project")
    if not isinstance(project, dict) or not _text(project.get("id")):
        raise ValueError("project.id must be a non-empty string")

    checks = _source_checks(manifest.get("source"))
    gates = manifest.get("gates") if isinstance(manifest.get("gates"), dict) else {}
    for gate_id, description in GATES:
        item = gates.get(gate_id)
        if not isinstance(item, dict):
            status, diagnostic, message = "NOT_VERIFIED", "WP9001", "Gate evidence missing."
            evidence_ref = None
        else:
            state = item.get("status")
            evidence_ref = item.get("evidenceRef")
            if state not in {"PASS", "WARN", "FAIL", "NOT_VERIFIED"}:
                status, diagnostic, message = "NOT_VERIFIED", "WP9002", "Gate status invalid or missing."
            elif state == "PASS" and not _text(evidence_ref):
                status, diagnostic, message = "NOT_VERIFIED", "WP9003", "PASS requires evidence reference."
            elif state == "PASS":
                status, diagnostic, message = "PASS", None, "Evidence reference supplied."
            elif state == "FAIL":
                status, diagnostic, message = "FAIL", "WP9004", "Gate explicitly failed."
            elif state == "WARN":
                status, diagnostic, message = "WARN", "WP9005", "Unresolved warning."
            else:
                status, diagnostic, message = "NOT_VERIFIED", "WP9006", "Gate not verified."
        checks.append({
            "id": gate_id,
            "description": description,
            "status": status,
            "diagnostic": diagnostic,
            "message": message,
            "evidenceRef": evidence_ref if _text(evidence_ref) else None,
        })

    acceptance = manifest.get("acceptance") if isinstance(manifest.get("acceptance"), dict) else {}
    for key, code in (("maxCriticalDefects", "ACC-001"), ("maxHighDefects", "ACC-002")):
        value = acceptance.get(key)
        valid = isinstance(value, int) and not isinstance(value, bool) and value >= 0
        status = "PASS" if valid and value == 0 else "FAIL" if valid else "NOT_VERIFIED"
        checks.append({
            "id": code,
            "status": status,
            "message": f"{key}={value}" if valid else f"{key} must be an explicit non-negative integer.",
        })
    for key, code in (("rtoMinutes", "ACC-003"), ("rpoMinutes", "ACC-004")):
        value = acceptance.get(key)
        valid = (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value >= 0
        )
        checks.append({
            "id": code,
            "status": "PASS" if valid else "NOT_VERIFIED",
            "message": f"{key} declared." if valid else f"{key} must be finite and non-negative.",
        })

    counts = {state: sum(check["status"] == state for check in checks)
              for state in ("PASS", "WARN", "FAIL", "NOT_VERIFIED")}
    qualified = all(counts[state] == 0 for state in ("WARN", "FAIL", "NOT_VERIFIED"))
    status = (
        "QUALIFIED" if qualified else "BLOCKED" if counts["FAIL"]
        else "CONDITIONAL" if counts["WARN"] else "INCOMPLETE"
    )
    return {
        "reportVersion": REPORT_VERSION,
        "project": {"id": project["id"], "name": project.get("name")},
        "inputSha256": _digest(manifest),
        "status": status,
        "summary": {"total": len(checks), **counts},
        "checks": checks,
        "productionQualification": {
            "eligible": qualified,
            "rule": "All source intake checks, twelve WP9 gates, zero critical/high defects, and explicit RTO/RPO must PASS.",
            "authorization": "Advisory evidence only; not production change approval or independent evidence verification.",
        },
        "limitations": [
            "Artifact hashes are format-checked but not recomputed from files by this assessor.",
            "Evidence references and gate statuses are supplied assertions, not independently witnessed evidence.",
            "Synthetic fixtures validate the assessor contract only; they cannot qualify a real APEX application.",
            "Real source exports, consistent Oracle snapshots, target pilot, witnessed rehearsals, and owner approvals are required.",
        ],
    }


def assess_pilot_file(input_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    manifest = json.loads(Path(input_path).read_text(encoding="utf-8"))
    report = assess_pilot(manifest)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Assess WP9 APEX pilot qualification evidence.")
    parser.add_argument("manifest")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        report = assess_pilot_file(args.manifest, args.output)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"pilot qualification error: {error}", file=sys.stderr)
        return 2
    print(json.dumps({
        "status": report["status"],
        "summary": report["summary"],
        "output": args.output,
    }, sort_keys=True))
    return {"QUALIFIED": 0, "BLOCKED": 1, "CONDITIONAL": 3, "INCOMPLETE": 4}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
