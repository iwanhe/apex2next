from pathlib import Path
import pytest
from apex2next_schema_analyzer.metadata_manifest import build_manifest, reconcile_manifest


def write_csv(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_manifest_hashes_and_sorts_ddl_files(tmp_path: Path) -> None:
    ddl = tmp_path / "ddl"
    ddl.mkdir()
    (ddl / "z.sql").write_text("CREATE VIEW V_Z AS SELECT 1 X FROM DUAL;")
    (ddl / "a.sql").write_text("CREATE TABLE T_A (ID NUMBER);")
    csv = write_csv(tmp_path / "objects.csv",
        "OWNER,OBJECT_TYPE,OBJECT_NAME,STATUS,LAST_DDL_TIME,DDL_FILE\n"
        "APP,VIEW,V_Z,VALID,2026-11-01,z.sql\nAPP,TABLE,T_A,VALID,2026-11-01,a.sql\n")
    result = build_manifest(csv, ddl, extracted_at="2026-11-07T10:00:00+07:00")
    assert [x["objectName"] for x in result["objects"]] == ["T_A", "V_Z"]
    assert result["summary"]["ddlExtracted"] == 2
    assert result["objects"][0]["ddl"]["sha256"].startswith("sha256:")
    assert build_manifest(csv, ddl, extracted_at="2026-11-07T10:00:00+07:00") == result


def test_missing_duplicate_and_path_traversal_are_diagnostics(tmp_path: Path) -> None:
    ddl = tmp_path / "ddl"
    ddl.mkdir()
    csv = write_csv(tmp_path / "objects.csv",
        "OWNER,OBJECT_TYPE,OBJECT_NAME,DDL_FILE\n"
        "APP,TABLE,T_A,missing.sql\nAPP,TABLE,T_A,../secret.sql\n")
    result = build_manifest(csv, ddl, extracted_at="2026-11-07T10:00:00Z")
    assert result["summary"]["ddlMissing"] == 1
    assert {x["code"] for x in result["diagnostics"]} == {"ORA_META002", "ORA_META004"}


def test_reconciliation_detects_missing_and_unexpected_objects(tmp_path: Path) -> None:
    ddl = tmp_path / "ddl"
    ddl.mkdir()
    csv = write_csv(tmp_path / "objects.csv",
        "OWNER,OBJECT_TYPE,OBJECT_NAME,STATUS\nAPP,TABLE,T_A,VALID\nAPP,VIEW,V_A,VALID\n")
    manifest = build_manifest(csv, ddl, extracted_at="2026-11-07T10:00:00Z")
    manifest["objects"].pop()
    manifest["objects"].append({"owner": "APP", "objectType": "SEQUENCE", "objectName": "S_X"})
    report = reconcile_manifest(manifest, csv)
    assert report["status"] == "MISMATCH"
    assert report["missingFromManifest"] == [["APP", "VIEW", "V_A"]]
    assert report["unexpectedInManifest"] == [["APP", "SEQUENCE", "S_X"]]


def test_reconciliation_passes_matching_inventory(tmp_path: Path) -> None:
    ddl = tmp_path / "ddl"
    ddl.mkdir()
    csv = write_csv(tmp_path / "objects.csv", "OWNER,OBJECT_TYPE,OBJECT_NAME\nAPP,TABLE,T_A\n")
    report = reconcile_manifest(build_manifest(csv, ddl, extracted_at="2026-11-07T10:00:00Z"), csv)
    assert report["status"] == "PASS"
    assert report["byObjectType"][0]["matches"] is True


def test_timestamp_is_required(tmp_path: Path) -> None:
    ddl = tmp_path / "ddl"
    ddl.mkdir()
    csv = write_csv(tmp_path / "objects.csv", "OWNER,OBJECT_TYPE,OBJECT_NAME\n")
    with pytest.raises(ValueError):
        build_manifest(csv, ddl, extracted_at="")
