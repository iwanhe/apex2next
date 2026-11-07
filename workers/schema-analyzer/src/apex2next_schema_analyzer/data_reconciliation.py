"""Offline reconciliation of normalized source/target migration evidence."""
from __future__ import annotations
import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

FORMAT = "apex2next.data-reconciliation.v1"


def _diag(code: str, severity: str, message: str, table: str | None = None,
          subject: str | None = None) -> dict[str, Any]:
    item = {"code": code, "severity": severity, "message": message}
    if table is not None:
        item["table"] = table
    if subject is not None:
        item["subject"] = subject
    return item


def _count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _token(value: Any) -> str:
    parts = value if isinstance(value, list) else [value]
    if not parts or any(x is None or isinstance(x, (dict, list)) for x in parts):
        raise ValueError("Primary keys must contain non-null scalar values")
    return json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _equal(left: Any, right: Any, tolerance: Any = 0) -> bool:
    try:
        if left is None or right is None or isinstance(left, bool) or isinstance(right, bool):
            raise InvalidOperation
        return abs(Decimal(str(left)) - Decimal(str(right))) <= Decimal(str(tolerance))
    except (InvalidOperation, ValueError):
        return left == right


def _tables(snapshot: dict[str, Any], label: str) -> dict[str, dict[str, Any]]:
    entries = snapshot.get("tables")
    if not isinstance(entries, list):
        raise ValueError(f"{label}.tables must be an array")
    result = {}
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("table"), str) or not item["table"].strip():
            raise ValueError(f"Every {label} table entry must contain a table name")
        name = item["table"].upper()
        if name in result:
            raise ValueError(f"Duplicate {label} table entry: {name}")
        result[name] = item
    return result


def _keys(table: str, src: dict[str, Any], tgt: dict[str, Any], diags: list) -> dict | None:
    a, b = src.get("primaryKey"), tgt.get("primaryKey")
    if not isinstance(a, dict) or not isinstance(b, dict):
        diags.append(_diag("REC003", "WARNING", "Primary-key evidence is missing.", table))
        return None
    if a.get("columns") != b.get("columns"):
        diags.append(_diag("REC004", "FAIL", "Primary-key column definitions differ.", table))
        return {"status": "FAIL", "sourceColumns": a.get("columns"), "targetColumns": b.get("columns")}
    if not isinstance(a.get("keys"), list) or not isinstance(b.get("keys"), list):
        diags.append(_diag("REC005", "WARNING", "Primary-key key lists are missing.", table))
        return None
    try:
        sk, tk = [_token(x) for x in a["keys"]], [_token(x) for x in b["keys"]]
    except (TypeError, ValueError):
        diags.append(_diag("REC006", "FAIL", "Primary-key evidence contains invalid values.", table))
        return {"status": "FAIL"}
    ss, ts = set(sk), set(tk)
    missing, extra = sorted(ss - ts), sorted(ts - ss)
    sd, td = len(sk) - len(ss), len(tk) - len(ts)
    count_mismatch = ((_count(src.get("rowCount")) and len(sk) != src["rowCount"]) or
                      (_count(tgt.get("rowCount")) and len(tk) != tgt["rowCount"]))
    status = "FAIL" if missing or extra or sd or td or count_mismatch else "PASS"
    if missing or extra or sd or td:
        diags.append(_diag("REC007", "FAIL", "Primary-key coverage has duplicates, missing, or extra keys.", table))
    if count_mismatch:
        diags.append(_diag("REC023", "FAIL",
            "Primary-key evidence must include exactly one key per table row.", table))
    matched = len(ss & ts)
    return {"status": status, "sourceKeyCount": len(sk), "targetKeyCount": len(tk),
            "sourceDuplicateCount": sd, "targetDuplicateCount": td,
            "missingInTarget": missing, "extraInTarget": extra, "matchedUniqueKeys": matched,
            "coveragePercent": round(matched / len(ss) * 100, 6) if ss else 100.0,
            "keyEvidenceCountMismatch": bool(count_mismatch)}


def _aggregates(table: str, src: dict, tgt: dict, diags: list) -> dict | None:
    a, b = src.get("aggregates"), tgt.get("aggregates")
    if not isinstance(a, dict) or not isinstance(b, dict):
        diags.append(_diag("REC008", "WARNING", "Aggregate evidence is missing.", table))
        return None
    results = []
    for col in sorted(set(a) | set(b)):
        if col not in a or col not in b or not isinstance(a.get(col), dict) or not isinstance(b.get(col), dict):
            diags.append(_diag("REC009", "WARNING", f"Aggregate evidence is incomplete for {col}.", table, col))
            results.append({"column": col, "status": "WARN"})
            continue
        left, right = a[col], b[col]
        fields = [x for x in ("count", "sum", "min", "max") if x in left or x in right]
        mismatches = [x for x in fields if x not in left or x not in right or
                      not _equal(left[x], right[x], left.get("tolerance", 0) if x == "sum" else 0)]
        status = "FAIL" if mismatches else ("PASS" if fields else "WARN")
        if mismatches:
            diags.append(_diag("REC010", "FAIL", f"Aggregate mismatch for {col}: {', '.join(mismatches)}.", table, col))
        results.append({"column": col, "status": status, "comparedFields": fields, "mismatchedFields": mismatches})
    overall = "FAIL" if any(x["status"] == "FAIL" for x in results) else (
        "WARN" if any(x["status"] == "WARN" for x in results) else "PASS")
    return {"status": overall, "columns": results}


def _foreign_keys(table: str, src: dict, tgt: dict, diags: list) -> dict | None:
    a, b = src.get("foreignKeys"), tgt.get("foreignKeys")
    if not isinstance(a, list) or not isinstance(b, list):
        diags.append(_diag("REC011", "WARNING", "Foreign-key validation evidence is missing.", table))
        return None
    left = {str(x.get("name", "")).upper(): x for x in a if isinstance(x, dict)}
    right = {str(x.get("name", "")).upper(): x for x in b if isinstance(x, dict)}
    results = []
    for name in sorted(set(left) | set(right)):
        x, y = left.get(name), right.get(name)
        if x is None or y is None:
            status, av, bv = "FAIL", None if x is None else x.get("violationCount"), None if y is None else y.get("violationCount")
            diags.append(_diag("REC012", "FAIL", f"FK validation entry {name} is missing.", table, name))
        else:
            av, bv = x.get("violationCount"), y.get("violationCount")
            if not _count(av) or not _count(bv):
                status = "WARN"
                diags.append(_diag("REC013", "WARNING", f"Invalid FK violation count for {name}.", table, name))
            elif av == bv == 0:
                status = "PASS"
            elif bv > av:
                status = "FAIL"
                diags.append(_diag("REC014", "FAIL", f"Target FK violations increased for {name}.", table, name))
            else:
                status = "WARN"
                diags.append(_diag("REC015", "WARNING", f"FK violation baseline differs for {name}.", table, name))
        results.append({"name": name, "sourceViolations": av, "targetViolations": bv, "status": status})
    overall = "FAIL" if any(x["status"] == "FAIL" for x in results) else (
        "WARN" if any(x["status"] == "WARN" for x in results) else "PASS")
    return {"status": overall, "constraints": results}


def _lobs(table: str, src: dict, tgt: dict, diags: list) -> dict | None:
    a, b = src.get("lobs"), tgt.get("lobs")
    if not isinstance(a, dict) or not isinstance(b, dict):
        diags.append(_diag("REC016", "WARNING", "LOB length/hash evidence is missing.", table))
        return None
    results = []
    for col in sorted(set(a) | set(b)):
        x, y = a.get(col), b.get(col)
        if not isinstance(x, dict) or not isinstance(y, dict):
            status = "WARN"
            diags.append(_diag("REC017", "WARNING", f"LOB evidence is incomplete for {col}.", table, col))
        else:
            fields = ("rowCount", "totalBytes", "sha256")
            missing = [f for f in fields if f not in x or f not in y]
            mismatch = [f for f in fields if f in x and f in y and x[f] != y[f]]
            status = "FAIL" if mismatch else ("WARN" if missing else "PASS")
            if mismatch:
                diags.append(_diag("REC018", "FAIL", f"LOB mismatch for {col}: {', '.join(mismatch)}.", table, col))
            elif missing:
                diags.append(_diag("REC019", "WARNING", f"LOB evidence fields missing for {col}.", table, col))
        results.append({"column": col, "status": status})
    overall = "FAIL" if any(x["status"] == "FAIL" for x in results) else (
        "WARN" if any(x["status"] == "WARN" for x in results) else "PASS")
    return {"status": overall, "columns": results}


def _chunks(manifest: dict | None, receipts: list | None, diags: list) -> dict | None:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("chunks"), list) or not isinstance(receipts, list):
        diags.append(_diag("REC020", "WARNING", "Chunk manifest or target receipts are missing."))
        return None
    src = {str(x.get("chunk_id")): x for x in manifest["chunks"] if isinstance(x, dict)}
    tgt = {str(x.get("chunkId")): x for x in receipts if isinstance(x, dict)}
    results = []
    for chunk_id in sorted(set(src) | set(tgt)):
        a, b = src.get(chunk_id), tgt.get(chunk_id)
        status = "PASS" if a is not None and b is not None and (
            a.get("checksum") == b.get("checksum") and a.get("row_count") == b.get("rowCount")) else "FAIL"
        if status == "FAIL":
            diags.append(_diag("REC021", "FAIL", f"Chunk receipt missing or checksum/row-count mismatch: {chunk_id}.",
                               subject=chunk_id))
        results.append({"chunkId": chunk_id, "status": status})
    return {"status": "FAIL" if any(x["status"] == "FAIL" for x in results) else "PASS",
            "chunkCount": len(src), "receipts": results}


def reconcile_snapshots(source: dict[str, Any], target: dict[str, Any], *,
                        chunk_manifest: dict[str, Any] | None = None,
                        target_chunk_receipts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Compare normalized evidence; see README for the JSON input contract."""
    if not isinstance(source, dict) or not isinstance(target, dict):
        raise ValueError("source and target snapshots must be JSON objects")
    src, tgt = _tables(source, "source"), _tables(target, "target")
    diags, results = [], []
    for name in sorted(set(src) | set(tgt)):
        a, b = src.get(name), tgt.get(name)
        if a is None or b is None:
            diags.append(_diag("REC001", "FAIL", f"Table {name} is missing from one snapshot.", name))
            results.append({"table": name, "status": "FAIL"})
            continue
        ac, bc = a.get("rowCount"), b.get("rowCount")
        if not _count(ac) or not _count(bc):
            row_status = "WARN"
            diags.append(_diag("REC002", "WARNING", "Row-count evidence is missing or invalid.", name))
        else:
            row_status = "PASS" if ac == bc else "FAIL"
            if row_status == "FAIL":
                diags.append(_diag("REC022", "FAIL", f"Row count differs: source={ac}, target={bc}.", name))
        pk, agg = _keys(name, a, b, diags), _aggregates(name, a, b, diags)
        fk, lob = _foreign_keys(name, a, b, diags), _lobs(name, a, b, diags)
        parts = [row_status] + [x["status"] for x in (pk, agg, fk, lob) if x is not None]
        status = "FAIL" if "FAIL" in parts else ("WARN" if "WARN" in parts else "PASS")
        results.append({"table": name, "status": status, "rowCount": {
            "source": ac, "target": bc, "delta": bc - ac if _count(ac) and _count(bc) else None},
            "primaryKey": pk, "aggregates": agg, "foreignKeys": fk, "lobs": lob})
    chunk_report = _chunks(chunk_manifest, target_chunk_receipts, diags)
    statuses = [x["status"] for x in results] + ([chunk_report["status"]] if chunk_report else [])
    if any(x == "FAIL" for x in statuses):
        status = "FAIL"
    elif any(x == "WARN" for x in statuses) or any(x["severity"] == "WARNING" for x in diags):
        status = "WARN"
    else:
        status = "PASS"
    diags.sort(key=lambda x: (x.get("table", ""), x["code"], x.get("subject", ""), x["message"]))
    return {"format": FORMAT, "status": status,
        "sourceSnapshotId": source.get("snapshotId"), "targetSnapshotId": target.get("snapshotId"),
        "tables": results, "chunks": chunk_report,
        "summary": {"tableCount": len(results), "passedTables": sum(x["status"] == "PASS" for x in results),
            "warnedTables": sum(x["status"] == "WARN" for x in results),
            "failedTables": sum(x["status"] == "FAIL" for x in results),
            "diagnosticCount": len(diags), "failCount": sum(x["severity"] == "FAIL" for x in diags),
            "warningCount": sum(x["severity"] == "WARNING" for x in diags)},
        "diagnostics": diags,
        "limitations": [
            "Compares supplied snapshot evidence only; no Oracle or PostgreSQL connection is made.",
            "PK lists and aggregates must come from separately reviewed source/target queries.",
            "Chunk checksums prove transfer-byte identity only when target receipts attest to the same checksum.",
            "LOB SHA-256 requires the same documented canonical byte representation on both sides.",
            "PASS does not prove application behavior, timezone, collation, empty-string, or business-semantic equivalence."]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile normalized source/target snapshots")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    report = reconcile_snapshots(payload["source"], payload["target"],
        chunk_manifest=payload.get("chunkManifest"), target_chunk_receipts=payload.get("targetChunkReceipts"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
