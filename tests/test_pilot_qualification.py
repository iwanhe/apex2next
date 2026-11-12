from copy import deepcopy

import pytest

from apex2next_schema_analyzer.pilot_qualification import INPUT_VERSION, assess_pilot


def fixture():
    gate_ids = [f"WP9-{index:03d}" for index in range(1, 13)]
    return {
        "manifestVersion": INPUT_VERSION,
        "project": {"id": "orders-pilot", "name": "Synthetic Orders"},
        "source": {
            "format": "APEX_SQL_EXPORT",
            "sanitized": True,
            "applicationId": "100",
            "apexRuntimeVersion": "24.2",
            "snapshotId": "fixture:scn-123",
            "artifacts": [{
                "path": "f100.sql",
                "sizeBytes": 1024,
                "sha256": "sha256:" + "a" * 64,
            }],
        },
        "gates": {
            gate_id: {"status": "PASS", "evidenceRef": f"fixture:{gate_id}"}
            for gate_id in gate_ids
        },
        "acceptance": {
            "maxCriticalDefects": 0,
            "maxHighDefects": 0,
            "rtoMinutes": 60,
            "rpoMinutes": 15,
        },
    }


def test_all_pass_is_qualified_and_deterministic():
    data = fixture()
    original = deepcopy(data)
    report = assess_pilot(data)
    assert report == assess_pilot(data)
    assert data == original
    assert report["status"] == "QUALIFIED"
    assert report["productionQualification"]["eligible"] is True


def test_missing_gate_is_incomplete():
    data = fixture()
    del data["gates"]["WP9-008"]
    report = assess_pilot(data)
    assert report["status"] == "INCOMPLETE"
    check = next(item for item in report["checks"] if item["id"] == "WP9-008")
    assert check["status"] == "NOT_VERIFIED"


def test_warn_is_conditional_and_fail_is_blocked():
    data = fixture()
    data["gates"]["WP9-010"]["status"] = "WARN"
    assert assess_pilot(data)["status"] == "CONDITIONAL"
    data["gates"]["WP9-010"]["status"] = "FAIL"
    assert assess_pilot(data)["status"] == "BLOCKED"


def test_pass_requires_evidence():
    data = fixture()
    del data["gates"]["WP9-003"]["evidenceRef"]
    assert assess_pilot(data)["status"] == "INCOMPLETE"


@pytest.mark.parametrize(
    "change",
    [
        lambda data: data["source"].update(sanitized=False),
        lambda data: data["source"].update(format="UNKNOWN"),
        lambda data: data["source"]["artifacts"][0].update(path="../secret.env"),
        lambda data: data["source"]["artifacts"][0].update(sha256="bad"),
        lambda data: data["source"]["artifacts"][0].update(sizeBytes=True),
        lambda data: data["acceptance"].update(maxCriticalDefects=1),
        lambda data: data["acceptance"].update(maxHighDefects=True),
        lambda data: data["acceptance"].update(rtoMinutes=-1),
    ],
)
def test_invalid_source_or_acceptance_blocks_or_incompletes(change):
    data = fixture()
    change(data)
    assert assess_pilot(data)["status"] in {"BLOCKED", "INCOMPLETE"}


def test_runtime_version_is_required():
    data = fixture()
    data["source"]["apexRuntimeVersion"] = ""
    assert assess_pilot(data)["status"] == "INCOMPLETE"


def test_duplicate_artifact_paths_fail():
    data = fixture()
    data["source"]["artifacts"].append(dict(data["source"]["artifacts"][0]))
    assert assess_pilot(data)["status"] == "BLOCKED"


def test_invalid_manifest_and_project_rejected():
    data = fixture()
    data["manifestVersion"] = "unknown"
    with pytest.raises(ValueError, match="manifestVersion"):
        assess_pilot(data)
    data = fixture()
    data["project"]["id"] = ""
    with pytest.raises(ValueError, match="project.id"):
        assess_pilot(data)
