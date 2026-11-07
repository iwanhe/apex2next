# Oracle Schema Analyzer — POC

Static Oracle DDL inventory and conservative PostgreSQL conversion. The tools are offline: they do not connect to Oracle or PostgreSQL and never execute source or generated SQL.

## WP8.2 — Read-only metadata extraction

The SQL scripts in sql/ use owner-scoped ALL_* dictionary views. Run with SQLcl (recommended for CLOB spooling) or compatible SQL*Plus:

```sql
define OWNER = 'APP_OWNER'
@workers/schema-analyzer/sql/dictionary_inventory.sql
@workers/schema-analyzer/sql/ddl_export.sql
```

CSV outputs cover objects/status, columns, constraints, indexes, dependencies, partitions, grants, and synonyms. The DDL script uses DBMS_METADATA.GET_DDL for a documented object-type allowlist. Verify CLOB completeness, quoting, per-object errors, and object-type support on the actual Oracle release.

Normalize dictionary_objects.csv. DDL_FILE is optional and must be relative to the DDL directory:

```bash
PYTHONPATH=workers/schema-analyzer/src python -m apex2next_schema_analyzer.metadata_manifest build dictionary_objects.csv --ddl-dir ./ddl --owner APP_OWNER --extracted-at 2026-11-07T10:00:00+07:00 --output build/oracle-metadata-manifest.json
PYTHONPATH=workers/schema-analyzer/src python -m apex2next_schema_analyzer.metadata_manifest reconcile build/oracle-metadata-manifest.json dictionary_objects.csv --output build/oracle-metadata-reconciliation.json
```

The manifest includes owner/type/name keys, object status, last DDL time, extraction status, and SHA-256 for available DDL. Missing DDL, duplicate rows, and unsafe paths are explicit diagnostics. Reconciliation checks object keys and per-type counts against a dictionary snapshot.

Security: use a dedicated read-only owner-scoped account and ALL_* visibility. Do not use SYS/SYSTEM, broad DBA roles, SELECT ANY DICTIONARY, or SELECT ANY TABLE solely for this workflow. Keep credentials, wallets, connection strings, and production extracts out of Git. Exact grants depend on Oracle version and organizational policy.

Limitations: ALL_DEPENDENCIES does not reveal dynamic SQL or every runtime dependency. Partition NUM_ROWS and LAST_ANALYZED are optimizer statistics, not exact live row counts. DBMS_METADATA support varies by object type and privilege. Missing DDL is an extraction gap, not proof that an object is absent.

## WP8.1 — Conservative Oracle DDL conversion

```bash
PYTHONPATH=workers/schema-analyzer/src python -m apex2next_schema_analyzer.ddl_conversion schema-export.sql --target-schema app --output build/schema-conversion.json --sql-output build/postgres-schema.sql
```

The initial allowlist covers CREATE TABLE, conservative scalar datatypes, PK/UNIQUE constraints, and in-snapshot FKs. Unknown datatypes and identity/generated semantics block affected tables. Unsupported defaults, CHECK constraints, and external FK targets produce diagnostics. Review generated SQL before execution.
