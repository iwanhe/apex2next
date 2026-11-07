# WP8 — Functional Migration and Runtime Integration

**Delivery model:** phased; each phase has an independent acceptance gate.  
**Current implementation:** WP8.1 conservative Oracle DDL conversion baseline.  
**Status:** WP8 in progress; WP8 is not complete.

## Scope

WP8 moves APEX2NEXT from target-project scaffolding toward validated schema, data, business logic, runtime security, and functional parity. Conversion is not complete merely because generated SQL compiles or data loads.

## Work packages

| ID | Scope | Main deliverables | Acceptance evidence | Status |
|---|---|---|---|---|
| WP8.1 | Oracle schema conversion | DDL parser subset, datatype mapping, constraints, PostgreSQL SQL draft, diagnostics | deterministic tests; unsupported constructs blocked/reported | Implemented baseline; CI pending |
| WP8.2 | Source schema extraction | Read-only DBMS_METADATA export guidance/scripts, object inventory reconciliation | object counts and DDL hashes reconcile with Oracle dictionary | Planned |
| WP8.3 | Data migration engine | Chunk manifest, typed extraction contract, resumable checkpoints, retry-safe PostgreSQL load | restart/retry tests and row/key coverage | Planned |
| WP8.4 | Data reconciliation | counts, PK coverage, aggregates, chunk hashes, LOB length/hash, FK validation | source/target reconciliation report | Planned |
| WP8.5 | PL/SQL conversion workbench | rule registry, parse/diagnose supported SQL/PLSQL subset, manual-review stubs | golden fixtures and no false AUTO classification | Planned |
| WP8.6 | Runtime integration | generated repositories/services/API contracts and DB integration tests | integration tests against disposable PostgreSQL | Planned |
| WP8.7 | APEX functional parity | source-to-target test case model, Playwright journeys, server-side assertions | representative sanitized APEX and target journeys | Planned |
| WP8.8 | Security and cutover | identity/policy mapping, rehearsal, rollback, cutover checklist | security review, rehearsal evidence, sign-off | Planned |

## WP8.1 — Implemented baseline

### Inputs and outputs

Input is an offline Oracle DDL text export. Output is a JSON conversion report and a PostgreSQL SQL draft. The converter does not connect to either database and does not execute input or output SQL.

Command: `PYTHONPATH=workers/schema-analyzer/src python -m apex2next_schema_analyzer.ddl_conversion schema-export.sql --target-schema app --output build/schema-conversion.json --sql-output build/postgres-schema.sql`

### Initial conversion allowlist

- CREATE TABLE, simple unquoted and quoted identifiers.
- NUMBER precision/scale to SMALLINT, INTEGER, BIGINT, or NUMERIC.
- VARCHAR2/NVARCHAR2/VARCHAR and CHAR/NCHAR with explicit simple length.
- CLOB/NCLOB to TEXT; BLOB and bounded RAW to BYTEA.
- Oracle DATE to TIMESTAMP(0) WITHOUT TIME ZONE.
- TIMESTAMP with supported precision, BINARY_FLOAT, BINARY_DOUBLE, FLOAT.
- Table-level PRIMARY KEY, UNIQUE, and FOREIGN KEY when the referenced table is included in the same input.
- Simple numeric/string/NULL defaults and reviewed timestamp defaults.

### Safety rules

- Unknown datatype blocks the whole table, not just the column.
- Identity/generated columns and inline REFERENCES block the table pending explicit design.
- CHECK expressions are diagnosed and omitted; they are never copied as executable target SQL.
- Unsupported defaults are diagnosed and omitted.
- Foreign keys to missing or blocked tables are omitted with explicit diagnostics.
- Identifiers are quoted; target schema is validated as a simple PostgreSQL identifier.
- Input comments and string literals are masked for DDL boundary detection.
- Stable ordering and source SHA-256 are included in the report.
- No data, indexes, views, sequences, triggers, grants, partitions, or PL/SQL are migrated in WP8.1.

## WP8.1 acceptance criteria

1. Supported DDL fixtures produce deterministic PostgreSQL SQL.
2. Unsupported datatype/identity semantics block affected tables.
3. Unsupported constraints/defaults produce explicit diagnostics.
4. No SQL is executed and no live database connection is attempted.
5. Target schema identifier injection is rejected.
6. CI runs the complete Python suite including DDL conversion tests.

## Production qualification boundary

WP8.1 is a converter foundation, not an Oracle schema migration utility certified for production. A representative sanitized DDL corpus and dictionary-level inventory comparison are required. Datatype mappings require business-owner review for precision, timezone, character semantics, collation, and Oracle empty-string behavior.

## Next implementation step

WP8.2 should add a read-only Oracle metadata extraction contract and inventory reconciliation before expanding datatype/constraint coverage. WP8.3 must follow with restartable chunked data movement, then WP8.4 reconciliation. Do not connect migration workers to production systems until credentials, network boundaries, least-privilege accounts, and disposable target testing are explicitly approved.