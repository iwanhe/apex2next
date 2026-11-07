# Oracle Schema Analyzer — POC

Static Oracle metadata inventory and conservative PostgreSQL conversion. The tools are offline: they do not connect to Oracle or PostgreSQL and never execute source or generated SQL.

## WP8.3 — Restartable chunked data migration

WP8.3 defines a file-based extraction/load contract, not a live database connector.

1. Extract rows from a consistent Oracle snapshot using a unique, non-null key and keyset pagination. Use explicit column lists, bound values, deterministic ORDER BY, and a stable SCN where Flashback Query is available. The SQL template is in [sql/keyset_extract_template.sql](sql/keyset_extract_template.sql).
2. Stream the rows in key order into bounded JSONL chunks. The manifest records owner/table, key fields, chunk ordinal, row count, first/last key, and SHA-256.
3. Run the loader with a durable SQLite checkpoint ledger. A loaded chunk is skipped after restart; a failed chunk can be retried.
4. Implement the target adapter so each chunk is applied atomically and idempotently by migration ID + chunk ID + checksum. A retry after target commit but before checkpoint commit must be a no-op at the target.

Example offline manifest generation:

```python
from pathlib import Path
from apex2next_schema_analyzer.data_migration import build_chunk_manifest

manifest = build_chunk_manifest(
    rows, Path("build/orders"), migration_id="orders-2026-01",
    source_owner="APP", source_table="ORDERS", key_fields=["ORDER_ID"],
    chunk_size=5000, created_at="2026-11-07T10:00:00+07:00",
)
```

The checkpoint database is local operational state and must be backed up with the migration workspace. Protect it as operational data. The JSONL chunks can contain sensitive business data: encrypt at rest and in transit, restrict access, set retention/deletion policy, and never commit real exports to Git.

The `IdempotentTargetSink` protocol is the PostgreSQL adapter boundary. It must atomically register the migration/chunk/checksum and load the chunk in one transaction, rejecting the same chunk ID with a different checksum. The current repository includes a fake sink for tests only; no PostgreSQL driver or live adapter is implemented.

## WP8.2 — Read-only metadata extraction

The SQL scripts in sql/ use owner-scoped ALL_* views. Run with SQLcl (recommended for CLOB spooling) or compatible SQL*Plus. CSV outputs cover objects/status, columns, constraints, indexes, dependencies, partitions, grants, and synonyms. The DDL script uses DBMS_METADATA.GET_DDL for a documented object-type allowlist. Verify CLOB completeness, quoting, per-object errors, and object-type support on the actual Oracle release.

The offline manifest normalizer records object keys, status, last DDL time, extraction status, and SHA-256 for available DDL. Reconciliation checks object keys and per-type counts. Use a dedicated read-only account; do not use SYS/SYSTEM or broad dictionary/table privileges solely for this workflow. Keep credentials, wallets, connection strings, and production extracts out of Git.

## WP8.1 — Conservative Oracle DDL conversion

```bash
PYTHONPATH=workers/schema-analyzer/src python -m apex2next_schema_analyzer.ddl_conversion schema-export.sql --target-schema app --output build/schema-conversion.json --sql-output build/postgres-schema.sql
```

The initial allowlist covers CREATE TABLE, conservative scalar datatypes, PK/UNIQUE constraints, and in-snapshot FKs. Unknown datatypes and identity/generated semantics block affected tables. Unsupported defaults, CHECK constraints, and external FK targets produce diagnostics. Review generated SQL before execution.


## WP8.4 — Offline data reconciliation and integrity report

WP8.4 compares normalized evidence exported independently from the source and target. It is
offline-first: it has no Oracle/PostgreSQL driver, does not execute SQL, and does not infer
missing evidence. The public API is `reconcile_snapshots(source, target, ...)` from
`apex2next_schema_analyzer.data_reconciliation`.

Each snapshot is JSON with a `tables` array. A table entry can contain:
- `table` and `rowCount`;
- `primaryKey: {columns: [...], keys: [...]}` (a composite key is represented as an array);
- `aggregates: {COLUMN: {count, sum, min, max, tolerance?}}`;
- `foreignKeys: [{name, violationCount}]`;
- `lobs: {COLUMN: {rowCount, totalBytes, sha256}}`.

Optional chunk evidence uses the WP8.3 manifest plus target receipts:
`chunkManifest.chunks[].chunk_id/checksum/row_count` and
`targetChunkReceipts[].chunkId/checksum/rowCount`. The target receipt must be generated
only after the target adapter verifies the exact chunk identity/checksum.

CLI input example (the actual snapshot JSON can be much larger):

```json
{
  "source": {"snapshotId": "oracle-scn-123", "tables": []},
  "target": {"snapshotId": "pg-copy-123", "tables": []},
  "chunkManifest": {"chunks": []},
  "targetChunkReceipts": []
}
```

Run with:
```bash
PYTHONPATH=workers/schema-analyzer/src python -m apex2next_schema_analyzer.data_reconciliation input.json --output build/reconciliation.json
```

Status policy: FAIL for row-count/key/aggregate/LOB/chunk mismatch or increased target FK
violations; WARN when evidence is absent/incomplete or the source FK baseline already has
violations; PASS only when all supplied evidence matches and no warning remains. Aggregate
tolerance applies to SUM only; counts/min/max remain exact. PK evidence compares canonical
scalar key values, including composite keys.

LOB hashes must use the same documented canonical byte representation on both sides.
Chunk hashes prove transfer-byte identity, not logical row equivalence. Large key lists may
make reports large; production-scale implementations should stream/summarize key differences
without weakening exact coverage checks.

The report is deterministic and machine-readable, with diagnostic codes, counts, coverage
percentage, per-table/per-domain statuses, snapshot IDs, and explicit limitations. A PASS
does not certify APEX behavior, SQL semantics, timezone/collation, Oracle empty-string behavior,
or business-rule equivalence. Validate source queries, target receipts, LOB canonicalization,
and performance against sanitized representative data before production use.
