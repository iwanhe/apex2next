"""Offline security mapping and migration cutover readiness assessment.

Consumes reviewed evidence only. It does not connect to databases, identity
providers, cloud control planes, or deployment environments and never performs
a cutover or rollback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

INPUT_VERSION = "apex2next.cutover-readiness-input.v1"
REPORT_VERSION = "apex2next.cutover-readiness.v1"

SECURITY_CONTROLS = {
    "SEC-001": ("Identity and role mappings reviewed", "identityMappings"),
    "SEC-002": ("Privileged human accounts use MFA", "privilegedMfa"),
    "SEC-003": ("Service identities are non-interactive and scoped", "serviceIdentities"),
    "SEC-004": ("Secrets are externalized from source and artifacts", "secretsExternalized"),
    "SEC-005": ("Transport encryption is enforced", "transportEncryption"),
    "SEC-006": ("Security and administrative audit logging is enabled", "auditLogging"),
    "SEC-007": ("Least-privilege grants are reviewed", "leastPrivilege"),
    "SEC-008": ("Role and row-level access tests are evidenced", "accessTests"),
}
CUTOVER_CONTROLS = {
    "CUT-001": ("Backup restore has been verified", "backupRestoreVerified"),
    "CUT-002": ("End-to-end migration rehearsal completed", "rehearsalCompleted"),
    "CUT-003": ("Data reconciliation report is PASS", "dataReconciliation"),
    "CUT-004": ("Functional parity report is PASS", "functionalParity"),
    "CUT-005": ("Rollback rehearsal completed successfully", "rollbackTested"),
    "CUT-006": ("Monitoring, alerting, and on-call coverage are ready", "monitoringReady"),
    "CUT-007": ("Change freeze and cutover window are approved", "changeWindowApproved"),
    "CUT-008": ("Operational runbook and communications are approved", "runbookApproved"),
}
APPROVAL_ROLES = {"BUSINESS_OWNER", "APPLICATION_OWNER", "SECURITY_OWNER", "OPERATIONS_OWNER"}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _evidence_check(
    control_id: str, description: str, item: Any, *, boolean: bool = True
) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"id": control_id, "description": description, "status": "NOT_VERIFIED",
                "diagnostic": "CUT001", "message": "Control evidence is missing."}
    evidence_ref = item.get("evidenceRef")
    if not _nonempty(evidence_ref):
        return {"id": control_id, "description": description, "status": "NOT_VERIFIED",
                "diagnostic": "CUT002", "message": "Evidence reference is missing."}
    value = item.get("value")
    if boolean and not isinstance(value, bool):
        return {"id": control_id, "description": description, "status": "NOT_VERIFIED",
                "diagnostic": "CUT003", "message": "Control value must be an explicit boolean."}
    if boolean and value is False:
        return {"id": control_id, "description": description, "status": "FAIL",
                "diagnostic": "CUT004", "message": "Control is explicitly not satisfied.",
                "evidenceRef": evidence_ref}
    return {"id": control_id, "description": description, "status": "PASS",
            "diagnostic": None, "message": "Control evidence supplied.",
            "evidenceRef": evidence_ref}


def _identity_mapping_checks(mappings: Any) -> list[dict[str, Any]]:
    if not isinstance(mappings, list) or not mappings:
        return [{"id": "SEC-001", "description": SECURITY_CONTROLS["SEC-001"][0],
                 "status": "NOT_VERIFIED", "diagnostic": "SEC001",
                 "message": "No reviewed source-to-target identity mappings supplied."}]
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, mapping in enumerate(mappings):
        if not isinstance(mapping, dict):
            results.append({"id": f"SEC-001-{index + 1}", "description": "Identity mapping",
                            "status": "NOT_VERIFIED", "diagnostic": "SEC002",
                            "message": "Mapping entry must be an object."})
            continue
        source_role, target_role = mapping.get("sourceRole"), mapping.get("targetRole")
        permissions, target_permissions = mapping.get("sourcePermissions"), mapping.get("targetPermissions")
        evidence_ref = mapping.get("evidenceRef")
        key = str(source_role)
        if not _nonempty(source_role) or not _nonempty(target_role) or key in seen:
            status, code, message = "FAIL", "SEC003", "Role mapping is incomplete or duplicated."
        elif not isinstance(permissions, list) or not isinstance(target_permissions, list):
            status, code, message = "NOT_VERIFIED", "SEC004", "Permission sets are missing or malformed."
        elif any(not _nonempty(p) for p in permissions + target_permissions):
            status, code, message = "FAIL", "SEC005", "Permission sets contain invalid entries."
        elif not set(target_permissions).issubset(set(permissions)):
            status, code, message = "FAIL", "SEC006", "Target permissions exceed the declared source permission set."
        elif mapping.get("reviewed") is not True or not _nonempty(evidence_ref):
            status, code, message = "NOT_VERIFIED", "SEC007", "Mapping review or evidence reference is missing."
        else:
            status, code, message = "PASS", None, "Reviewed mapping does not expand declared permissions."
        seen.add(key)
        results.append({"id": f"SEC-001-{index + 1}", "description": f"{source_role} → {target_role}",
                        "status": status, "diagnostic": code, "message": message,
                        "evidenceRef": evidence_ref if _nonempty(evidence_ref) else None})
    if any(x["status"] != "PASS" for x in results):
        overall = "FAIL" if any(x["status"] == "FAIL" for x in results) else "NOT_VERIFIED"
    else:
        overall = "PASS"
    return [{"id": "SEC-001", "description": SECURITY_CONTROLS["SEC-001"][0],
             "status": overall, "diagnostic": None if overall == "PASS" else "SEC008",
             "message": "Identity mapping aggregate.", "details": results}]


def _approval_checks(approvals: Any) -> list[dict[str, Any]]:
    if not isinstance(approvals, list):
        approvals = []
    by_role: dict[str, dict[str, Any]] = {}
    duplicate: set[str] = set()
    for approval in approvals:
        if isinstance(approval, dict) and _nonempty(approval.get("role")):
            role = approval["role"]
            if role in by_role:
                duplicate.add(role)
            by_role[role] = approval
    results = []
    for role in sorted(APPROVAL_ROLES):
        item = by_role.get(role)
        if role in duplicate:
            status, code, message = "FAIL", "APR001", "Duplicate approval entries are not accepted."
        elif not isinstance(item, dict):
            status, code, message = "NOT_VERIFIED", "APR002", "Required approval is missing."
        elif item.get("approved") is not True or not _nonempty(item.get("evidenceRef")):
            status, code, message = "NOT_VERIFIED", "APR003", "Approval or its evidence reference is missing."
        else:
            status, code, message = "PASS", None, "Approval evidence supplied."
        results.append({"id": f"APP-{role}", "description": f"{role} sign-off",
                        "status": status, "diagnostic": code, "message": message,
                        "evidenceRef": item.get("evidenceRef") if isinstance(item, dict) else None})
    return results


def assess_cutover_readiness(manifest: dict[str, Any]) -> dict[str, Any]:
    """Evaluate security, rehearsal, rollback, cutover controls, and approvals."""
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    if manifest.get("manifestVersion") != INPUT_VERSION:
        raise ValueError(f"manifestVersion must be {INPUT_VERSION}")
    project = manifest.get("project")
    if not isinstance(project, dict) or not _nonempty(project.get("id")):
        raise ValueError("project.id must be a non-empty string")

    controls = manifest.get("controls")
    if not isinstance(controls, dict):
        controls = {}
    results: list[dict[str, Any]] = []
    for control_id, (description, key) in SECURITY_CONTROLS.items():
        if control_id == "SEC-001":
            results.extend(_identity_mapping_checks(controls.get(key)))
        else:
            results.append(_evidence_check(control_id, description, controls.get(key)))
    for control_id, (description, key) in CUTOVER_CONTROLS.items():
        item = controls.get(key)
        if control_id in {"CUT-003", "CUT-004"} and isinstance(item, dict):
            expected = "PASS"
            actual = item.get("value")
            if actual in {"FAIL", "NOT_VERIFIED", "WARN"}:
                item = {**item, "value": False}
            elif actual != expected:
                item = {**item, "value": None}
        results.append(_evidence_check(control_id, description, item))
    results.extend(_approval_checks(manifest.get("approvals")))

    rollback = manifest.get("rollback")
    if not isinstance(rollback, dict):
        rollback = {}
    for field in ("rtoMinutes", "rpoMinutes"):
        value = rollback.get(field)
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0
        results.append({
            "id": "RBK-" + field.upper(),
            "description": f"Approved rollback {field}",
            "status": "PASS" if valid and _nonempty(rollback.get("evidenceRef")) else "NOT_VERIFIED",
            "diagnostic": None if valid and _nonempty(rollback.get("evidenceRef")) else "RBK001",
            "message": "Rollback objective is explicit and evidenced." if valid and _nonempty(rollback.get("evidenceRef")) else "A finite non-negative objective and rollback evidence reference are required.",
            "evidenceRef": rollback.get("evidenceRef") if _nonempty(rollback.get("evidenceRef")) else None,
            "value": value if valid else None,
        })

    counts = {status: sum(item["status"] == status for item in results)
              for status in ("PASS", "FAIL", "NOT_VERIFIED")}
    status = "BLOCKED" if counts["FAIL"] or counts["NOT_VERIFIED"] else "READY"
    categories = {
        "SECURITY": [x for x in results if x["id"].startswith("SEC-")],
        "CUTOVER": [x for x in results if x["id"].startswith("CUT-")],
        "APPROVALS": [x for x in results if x["id"].startswith("APP-")],
        "ROLLBACK": [x for x in results if x["id"].startswith("RBK-")],
    }
    return {
        "reportVersion": REPORT_VERSION,
        "project": {"id": project["id"], "sourceSnapshot": project.get("sourceSnapshot"),
                    "targetRelease": project.get("targetRelease")},
        "inputSha256": _sha256(manifest),
        "status": status,
        "summary": {"total": len(results), **counts},
        "categories": {name: {"status": "FAIL" if any(x["status"] == "FAIL" for x in items)
                              else "NOT_VERIFIED" if any(x["status"] == "NOT_VERIFIED" for x in items)
                              else "PASS",
                              "checks": items} for name, items in categories.items()},
        "checks": results,
        "cutoverAuthorization": {
            "eligible": status == "READY",
            "rule": "All security, cutover, rollback, and four owner-approval checks must PASS.",
            "authorization": "This report is advisory evidence only; a separately authorized change process must execute cutover.",
        },
        "limitations": [
            "The assessor validates declared evidence references and supplied values; it does not independently verify evidence authenticity.",
            "No live identity provider, database, cloud, backup, deployment, monitoring, or ticketing system is accessed.",
            "A READY result is not permission to execute a production change; change authority and business acceptance remain external.",
            "Rollback feasibility depends on the actual cutover strategy, write freeze, reverse data path, and tested recovery objectives.",
        ],
    }


def assess_cutover_file(input_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    manifest = json.loads(Path(input_path).read_text(encoding="utf-8"))
    report = assess_cutover_readiness(manifest)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2,
                                      allow_nan=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Assess offline APEX2NEXT security and cutover readiness.")
    parser.add_argument("manifest", help="Path to cutover-readiness-input.v1 JSON")
    parser.add_argument("--output", required=True, help="Path to readiness report JSON")
    args = parser.parse_args()
    try:
        report = assess_cutover_file(args.manifest, args.output)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"cutover readiness error: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"status": report["status"], "summary": report["summary"],
                      "output": args.output}, sort_keys=True))
    return 0 if report["status"] == "READY" else 3 if report["status"] == "BLOCKED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
