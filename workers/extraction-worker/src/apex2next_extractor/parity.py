"""Evidence-based functional parity comparison for APEX-to-target migrations.

Evidence is treated as inert JSON data. This module never executes source SQL,
PL/SQL, JavaScript, HTTP requests, browser scripts, or generated application code.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

PARITY_REPORT_VERSION = "apex2next.functional-parity.v1"
CATEGORIES = {"FUNCTIONAL", "API", "DATA", "WORKFLOW", "SECURITY", "UI"}
COMPARATORS = {"EXACT", "NUMERIC_TOLERANCE", "UNORDERED_SET"}
STATUSES = {"PASS", "FAIL", "NOT_VERIFIED"}


def canonical_json(value: Any) -> str:
    """Serialize JSON-compatible evidence deterministically."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _validate_check(check: Any, index: int) -> None:
    prefix = f"checks[{index}]"
    if not isinstance(check, dict):
        raise ValueError(f"{prefix} must be an object")
    for field in ("id", "category", "description", "comparator"):
        if not isinstance(check.get(field), str) or not check[field].strip():
            raise ValueError(f"{prefix}.{field} must be a non-empty string")
    if check["category"] not in CATEGORIES:
        raise ValueError(f"{prefix}.category is unsupported")
    if check["comparator"] not in COMPARATORS:
        raise ValueError(f"{prefix}.comparator is unsupported")
    if check["comparator"] == "NUMERIC_TOLERANCE":
        tolerance = check.get("tolerance")
        if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
            raise ValueError(f"{prefix}.tolerance must be a finite non-negative number")
        if not math.isfinite(tolerance) or tolerance < 0:
            raise ValueError(f"{prefix}.tolerance must be a finite non-negative number")
    for side in ("source", "target"):
        evidence = check.get(side)
        if evidence is not None and not isinstance(evidence, dict):
            raise ValueError(f"{prefix}.{side} must be an object or null")
        if isinstance(evidence, dict):
            reference = evidence.get("evidenceRef")
            if reference is not None and (not isinstance(reference, str) or not reference.strip()):
                raise ValueError(f"{prefix}.{side}.evidenceRef must be a non-empty string")


def _compare_values(check: dict[str, Any]) -> tuple[str, str]:
    source = check["source"]["value"]
    target = check["target"]["value"]
    comparator = check["comparator"]

    if comparator == "EXACT":
        passed = canonical_json(source) == canonical_json(target)
        return ("PASS" if passed else "FAIL", "Values are exactly equal." if passed else "Source and target values differ.")

    if comparator == "NUMERIC_TOLERANCE":
        if (
            isinstance(source, bool) or not isinstance(source, (int, float))
            or isinstance(target, bool) or not isinstance(target, (int, float))
        ):
            return "FAIL", "Numeric comparator received a non-numeric value."
        passed = abs(float(source) - float(target)) <= float(check["tolerance"])
        return (
            "PASS" if passed else "FAIL",
            "Numeric difference is within tolerance." if passed else "Numeric difference exceeds tolerance.",
        )

    if not isinstance(source, list) or not isinstance(target, list):
        return "FAIL", "Unordered-set comparator requires arrays on both sides."
    try:
        source_items = sorted(canonical_json(item) for item in source)
        target_items = sorted(canonical_json(item) for item in target)
    except (TypeError, ValueError):
        return "FAIL", "Evidence contains values that are not valid JSON."
    passed = source_items == target_items
    return (
        "PASS" if passed else "FAIL",
        "Unordered collections are equal." if passed else "Unordered collections differ.",
    )


def compare_parity(manifest: dict[str, Any]) -> dict[str, Any]:
    """Compare paired source/target observations and return a stable report."""
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    if manifest.get("manifestVersion") != "apex2next.functional-parity-input.v1":
        raise ValueError("manifestVersion must be apex2next.functional-parity-input.v1")
    application = manifest.get("application")
    if not isinstance(application, dict) or not isinstance(application.get("id"), str) or not application["id"].strip():
        raise ValueError("application.id must be a non-empty string")
    checks = manifest.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError("checks must be a non-empty array")

    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for index, check in enumerate(checks):
        _validate_check(check, index)
        if check["id"] in seen:
            raise ValueError(f"duplicate check id: {check['id']}")
        seen.add(check["id"])

        source = check.get("source")
        target = check.get("target")
        result: dict[str, Any] = {
            "id": check["id"],
            "category": check["category"],
            "description": check["description"],
            "comparator": check["comparator"],
            "sourceEvidenceRef": source.get("evidenceRef") if isinstance(source, dict) else None,
            "targetEvidenceRef": target.get("evidenceRef") if isinstance(target, dict) else None,
        }
        if not isinstance(source, dict) or "value" not in source or not source.get("evidenceRef"):
            result.update(status="NOT_VERIFIED", diagnostic="PARITY001", message="Source observation or evidence reference is missing.")
        elif not isinstance(target, dict) or "value" not in target or not target.get("evidenceRef"):
            result.update(status="NOT_VERIFIED", diagnostic="PARITY002", message="Target observation or evidence reference is missing.")
        else:
            status, message = _compare_values(check)
            result.update(status=status, diagnostic=None if status == "PASS" else "PARITY003", message=message)
        results.append(result)

    counts = {status: sum(item["status"] == status for item in results) for status in STATUSES}
    overall = "FAIL" if counts["FAIL"] else (
        "NOT_VERIFIED" if counts["NOT_VERIFIED"] else "PASS"
    )
    categories: dict[str, dict[str, int | str]] = {}
    for category in sorted(CATEGORIES):
        members = [item for item in results if item["category"] == category]
        if not members:
            continue
        category_counts = {
            status: sum(item["status"] == status for item in members) for status in STATUSES
        }
        category_status = "FAIL" if category_counts["FAIL"] else (
            "NOT_VERIFIED" if category_counts["NOT_VERIFIED"] else "PASS"
        )
        categories[category] = {"status": category_status, **category_counts}

    report = {
        "reportVersion": PARITY_REPORT_VERSION,
        "application": {
            "id": application["id"],
            "sourceSnapshot": application.get("sourceSnapshot"),
            "targetBuild": application.get("targetBuild"),
        },
        "inputSha256": "sha256:" + sha256_json(manifest),
        "status": overall,
        "summary": {"total": len(results), **counts},
        "categories": categories,
        "checks": results,
        "acceptance": {
            "eligible": overall == "PASS",
            "rule": "All supplied checks must PASS; missing evidence is NOT_VERIFIED and any mismatch is FAIL.",
            "limitations": [
                "Only supplied observations are compared; the harness does not execute or capture source/target applications.",
                "A PASS does not establish coverage of unlisted workflows, production readiness, or business-owner acceptance.",
                "Evidence authenticity, snapshot consistency, test identity, and artifact retention require external controls.",
            ],
        },
    }
    return report


def compare_parity_files(input_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    """Read a JSON manifest and write a deterministic JSON report."""
    manifest = json.loads(Path(input_path).read_text(encoding="utf-8"))
    report = compare_parity(manifest)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report
