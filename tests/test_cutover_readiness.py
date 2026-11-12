from copy import deepcopy

import pytest

from apex2next_schema_analyzer.cutover_readiness import (
    INPUT_VERSION,
    assess_cutover_readiness,
)


def complete_manifest():
    controls = {
        "identityMappings": [{
            "sourceRole": "ORDER_CLERK", "targetRole": "orders.clerk",
            "sourcePermissions": ["orders:read", "orders:create"],
            "targetPermissions": ["orders:read", "orders:create"],
            "reviewed": True, "evidenceRef": "security/role-map#1",
        }],
    }
    for key in (
        "privilegedMfa", "serviceIdentities", "secretsExternalized", "transportEncryption",
        "auditLogging", "leastPrivilege", "accessTests", "backupRestoreVerified",
        "rehearsalCompleted", "monitoringReady", "rollbackTested", "changeWindowApproved",
        "runbookApproved",
    ):
        controls[key] = {"value": True, "evidenceRef": f"evidence/{key}"}
    controls["dataReconciliation"] = {"value": "PASS", "evidenceRef": "recon/report.json"}
    controls["functionalParity"] = {"value": "PASS", "evidenceRef": "parity/report.json"}
    return {
        "manifestVersion": INPUT_VERSION,
        "project": {"id": "orders-pilot", "sourceSnapshot": "oracle-scn:123", "targetRelease": "release-42"},
        "controls": controls,
        "rollback": {"rtoMinutes": 60, "rpoMinutes": 15, "evidenceRef": "rehearsal/rollback#1"},
        "approvals": [
            {"role": role, "approved": True, "evidenceRef": f"approval/{role}"}
            for role in ("BUSINESS_OWNER", "APPLICATION_OWNER", "SECURITY_OWNER", "OPERATIONS_OWNER")
        ],
    }


def test_complete_evidence_is_ready_and_deterministic():
    manifest = complete_manifest()
    before = deepcopy(manifest)
    first = assess_cutover_readiness(manifest)
    assert first == assess_cutover_readiness(manifest)
    assert manifest == before
    assert first["status"] == "READY"
    assert first["cutoverAuthorization"]["eligible"] is True
    assert first["summary"]["FAIL"] == 0
    assert first["summary"]["NOT_VERIFIED"] == 0


def test_missing_evidence_blocks_cutover_not_false_pass():
    manifest = complete_manifest()
    del manifest["controls"]["backupRestoreVerified"]
    report = assess_cutover_readiness(manifest)
    assert report["status"] == "BLOCKED"
    check = next(x for x in report["checks"] if x["id"] == "CUT-001")
    assert check["status"] == "NOT_VERIFIED"


def test_explicit_failed_security_control_blocks_cutover():
    manifest = complete_manifest()
    manifest["controls"]["privilegedMfa"]["value"] = False
    report = assess_cutover_readiness(manifest)
    assert report["status"] == "BLOCKED"
    assert next(x for x in report["checks"] if x["id"] == "SEC-002")["status"] == "FAIL"


def test_permission_expansion_fails_identity_mapping():
    manifest = complete_manifest()
    manifest["controls"]["identityMappings"][0]["targetPermissions"].append("users:admin")
    report = assess_cutover_readiness(manifest)
    assert report["status"] == "BLOCKED"
    assert report["categories"]["SECURITY"]["status"] == "FAIL"


def test_unreviewed_mapping_is_not_verified():
    manifest = complete_manifest()
    manifest["controls"]["identityMappings"][0]["reviewed"] = False
    report = assess_cutover_readiness(manifest)
    assert report["categories"]["SECURITY"]["status"] == "NOT_VERIFIED"


def test_non_pass_reconciliation_and_parity_block_cutover():
    manifest = complete_manifest()
    manifest["controls"]["dataReconciliation"]["value"] = "WARN"
    report = assess_cutover_readiness(manifest)
    assert report["status"] == "BLOCKED"
    assert next(x for x in report["checks"] if x["id"] == "CUT-003")["status"] == "FAIL"


def test_all_four_approvals_are_required():
    manifest = complete_manifest()
    manifest["approvals"] = manifest["approvals"][:-1]
    report = assess_cutover_readiness(manifest)
    assert report["status"] == "BLOCKED"
    assert report["categories"]["APPROVALS"]["status"] == "NOT_VERIFIED"


def test_rollback_objectives_must_be_finite_nonnegative_and_evidenced():
    manifest = complete_manifest()
    manifest["rollback"]["rtoMinutes"] = -1
    report = assess_cutover_readiness(manifest)
    assert report["status"] == "BLOCKED"
    assert next(x for x in report["checks"] if x["id"] == "RBK-RTOMINUTES")["status"] == "NOT_VERIFIED"


def test_duplicate_approvals_are_rejected():
    manifest = complete_manifest()
    manifest["approvals"].append(dict(manifest["approvals"][0]))
    report = assess_cutover_readiness(manifest)
    assert report["status"] == "BLOCKED"
    assert report["categories"]["APPROVALS"]["status"] == "FAIL"


def test_wrong_manifest_version_and_project_id_are_rejected():
    manifest = complete_manifest()
    manifest["manifestVersion"] = "unknown"
    with pytest.raises(ValueError, match="manifestVersion"):
        assess_cutover_readiness(manifest)
    manifest = complete_manifest()
    manifest["project"]["id"] = ""
    with pytest.raises(ValueError, match="project.id"):
        assess_cutover_readiness(manifest)


def test_identity_mapping_duplicate_role_and_invalid_permission_fail():
    manifest = complete_manifest()
    duplicate = dict(manifest["controls"]["identityMappings"][0])
    manifest["controls"]["identityMappings"].append(duplicate)
    report = assess_cutover_readiness(manifest)
    assert report["categories"]["SECURITY"]["status"] == "FAIL"
    manifest = complete_manifest()
    manifest["controls"]["identityMappings"][0]["targetPermissions"] = [" "]
    assert assess_cutover_readiness(manifest)["categories"]["SECURITY"]["status"] == "FAIL"
