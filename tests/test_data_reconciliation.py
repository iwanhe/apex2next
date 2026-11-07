from copy import deepcopy
import pytest
from apex2next_schema_analyzer.data_reconciliation import reconcile_snapshots


def table(name="ORDERS", rows=2, keys=None, amount_sum=10, fk=0, lob_hash="abc"):
    return {"table": name, "rowCount": rows,
        "primaryKey": {"columns": ["ID"], "keys": keys if keys is not None else [1, 2]},
        "aggregates": {"AMOUNT": {"count": 2, "sum": amount_sum, "min": 2, "max": 8}},
        "foreignKeys": [{"name": "FK_CUSTOMER", "violationCount": fk}],
        "lobs": {"DOCUMENT": {"rowCount": 2, "totalBytes": 100, "sha256": lob_hash}}}


def snapshots(a=None, b=None):
    return ({"snapshotId": "oracle-scn-123", "tables": [a or table()]},
            {"snapshotId": "pg-copy-123", "tables": [b or table()]})


def evidence():
    return ({"chunks": [{"chunk_id": "c1", "checksum": "sha256:one", "row_count": 2}]},
            [{"chunkId": "c1", "checksum": "sha256:one", "rowCount": 2}])


def test_matching_complete_evidence_passes():
    src, tgt = snapshots()
    manifest, receipts = evidence()
    report = reconcile_snapshots(src, tgt, chunk_manifest=manifest, target_chunk_receipts=receipts)
    assert report["status"] == "PASS"
    assert report["tables"][0]["primaryKey"]["coveragePercent"] == 100.0


def test_row_count_mismatch_fails():
    src, tgt = snapshots(b=table(rows=3))
    report = reconcile_snapshots(src, tgt)
    assert report["status"] == "FAIL"
    assert any(x["code"] == "REC022" for x in report["diagnostics"])


def test_missing_extra_and_duplicate_keys_fail():
    src, tgt = snapshots(b=table(keys=[1, 3]))
    report = reconcile_snapshots(src, tgt)
    assert report["tables"][0]["primaryKey"]["missingInTarget"]
    assert report["tables"][0]["primaryKey"]["extraInTarget"]
    src, tgt = snapshots(a=table(keys=[1, 1]))
    assert reconcile_snapshots(src, tgt)["status"] == "FAIL"


def test_composite_keys_supported():
    src, tgt = snapshots(table(keys=[[1, "A"], [2, "B"]]), table(keys=[[1, "A"], [2, "B"]]))
    assert reconcile_snapshots(src, tgt)["tables"][0]["primaryKey"]["status"] == "PASS"


def test_aggregate_mismatch_and_tolerance():
    src, tgt = snapshots(b=table(amount_sum=11))
    assert reconcile_snapshots(src, tgt)["tables"][0]["aggregates"]["status"] == "FAIL"
    a, b = table(), table(amount_sum=10.001)
    a["aggregates"]["AMOUNT"]["tolerance"] = 0.01
    src, tgt = snapshots(a, b)
    assert reconcile_snapshots(src, tgt)["tables"][0]["aggregates"]["status"] == "PASS"


def test_fk_increase_fails_and_baseline_difference_warns():
    src, tgt = snapshots(b=table(fk=1))
    assert reconcile_snapshots(src, tgt)["tables"][0]["foreignKeys"]["status"] == "FAIL"
    src, tgt = snapshots(table(fk=2), table(fk=1))
    assert reconcile_snapshots(src, tgt)["tables"][0]["foreignKeys"]["status"] == "WARN"


def test_lob_hash_mismatch_fails():
    src, tgt = snapshots(b=table(lob_hash="different"))
    assert reconcile_snapshots(src, tgt)["tables"][0]["lobs"]["status"] == "FAIL"


def test_chunk_checksum_and_count_verified():
    src, tgt = snapshots()
    manifest, receipts = evidence()
    receipts[0]["checksum"] = "sha256:tampered"
    report = reconcile_snapshots(src, tgt, chunk_manifest=manifest, target_chunk_receipts=receipts)
    assert report["chunks"]["status"] == "FAIL"
    assert report["status"] == "FAIL"


def test_missing_evidence_is_warning_not_false_pass():
    src, tgt = snapshots()
    assert reconcile_snapshots(src, tgt)["status"] == "WARN"


def test_missing_table_fails():
    src, tgt = snapshots()
    tgt["tables"] = []
    assert reconcile_snapshots(src, tgt)["status"] == "FAIL"


def test_report_is_deterministic_and_inputs_are_immutable():
    src, tgt = snapshots()
    before = deepcopy((src, tgt))
    assert reconcile_snapshots(src, tgt) == reconcile_snapshots(src, tgt)
    assert (src, tgt) == before


def test_duplicate_table_names_rejected():
    src, tgt = snapshots()
    src["tables"].append(table())
    with pytest.raises(ValueError, match="Duplicate source table"):
        reconcile_snapshots(src, tgt)


def test_missing_chunk_receipts_prevent_pass():
    src, tgt = snapshots()
    report = reconcile_snapshots(src, tgt)
    assert report["status"] == "WARN"
    assert any(x["code"] == "REC020" for x in report["diagnostics"])
