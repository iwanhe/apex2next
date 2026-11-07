from copy import deepcopy

import pytest

from apex2next_extractor.parity import compare_parity


def _manifest():
    return {
        "manifestVersion": "apex2next.functional-parity-input.v1",
        "application": {"id": "orders-demo", "sourceSnapshot": "source-001", "targetBuild": "build-001"},
        "checks": [
            {
                "id": "FUNC-001", "category": "FUNCTIONAL", "description": "Required validation",
                "comparator": "EXACT",
                "source": {"value": {"valid": False, "error": "Required"}, "evidenceRef": "source#1"},
                "target": {"value": {"valid": False, "error": "Required"}, "evidenceRef": "target#1"},
            },
            {
                "id": "API-001", "category": "API", "description": "Status",
                "comparator": "EXACT",
                "source": {"value": 200, "evidenceRef": "source#2"},
                "target": {"value": 500, "evidenceRef": "target#2"},
            },
            {
                "id": "SEC-001", "category": "SECURITY", "description": "Access denied",
                "comparator": "EXACT",
                "source": {"value": 403, "evidenceRef": "source#3"},
                "target": None,
            },
        ],
    }


def test_parity_report_is_deterministic_and_non_mutating():
    manifest = _manifest()
    before = deepcopy(manifest)
    first = compare_parity(manifest)
    assert first == compare_parity(manifest)
    assert manifest == before
    assert first["status"] == "FAIL"
    assert first["summary"] == {"total": 3, "PASS": 1, "FAIL": 1, "NOT_VERIFIED": 1}
    assert first["acceptance"]["eligible"] is False
    assert first["categories"]["FUNCTIONAL"]["status"] == "PASS"
    assert first["categories"]["API"]["status"] == "FAIL"
    assert first["categories"]["SECURITY"]["status"] == "NOT_VERIFIED"


def test_missing_source_or_target_evidence_never_passes():
    manifest = _manifest()
    manifest["checks"][0]["source"] = None
    manifest["checks"][1]["target"] = {"value": 200}
    report = compare_parity(manifest)
    assert report["checks"][0]["status"] == "NOT_VERIFIED"
    assert report["checks"][1]["status"] == "NOT_VERIFIED"


def test_numeric_tolerance_requires_explicit_finite_nonnegative_tolerance():
    manifest = _manifest()
    check = manifest["checks"][0]
    check.update(comparator="NUMERIC_TOLERANCE", tolerance=0.01)
    check["source"]["value"] = 10.0
    check["target"]["value"] = 10.005
    assert compare_parity(manifest)["checks"][0]["status"] == "PASS"
    check["tolerance"] = -1
    with pytest.raises(ValueError):
        compare_parity(manifest)


def test_unordered_set_comparator_and_exact_ordered_comparison():
    manifest = _manifest()
    check = manifest["checks"][0]
    check.update(comparator="UNORDERED_SET")
    check["source"]["value"] = ["a", "b"]
    check["target"]["value"] = ["b", "a"]
    assert compare_parity(manifest)["checks"][0]["status"] == "PASS"
    check.update(comparator="EXACT")
    assert compare_parity(manifest)["checks"][0]["status"] == "FAIL"


def test_duplicate_ids_and_unsupported_comparator_are_rejected():
    manifest = _manifest()
    manifest["checks"][1]["id"] = manifest["checks"][0]["id"]
    with pytest.raises(ValueError, match="duplicate"):
        compare_parity(manifest)
    manifest = _manifest()
    manifest["checks"][0]["comparator"] = "EXECUTE_SQL"
    with pytest.raises(ValueError, match="comparator"):
        compare_parity(manifest)


def test_numeric_values_reject_nan_and_boolean_coercion():
    manifest = _manifest()
    check = manifest["checks"][0]
    check.update(comparator="NUMERIC_TOLERANCE", tolerance=0)
    check["source"]["value"] = True
    check["target"]["value"] = 1
    assert compare_parity(manifest)["checks"][0]["status"] == "FAIL"


def test_empty_checks_are_rejected():
    manifest = _manifest()
    manifest["checks"] = []
    with pytest.raises(ValueError, match="non-empty"):
        compare_parity(manifest)
