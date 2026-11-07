# WP8 — Functional Migration and Runtime Integration

**Delivery model:** phased; each phase has an independent acceptance gate.  
**Current implementation:** WP8.1 conservative Oracle DDL conversion and WP8.2 read-only metadata extraction baseline.  
**Status:** WP8 remains in progress; WP8.1/WP8.2 offline baselines are implemented, not production-qualified.

## Work packages

| ID | Scope | Main deliverables | Acceptance evidence | Status |
|---|---|---|---|---|
| WP8.1 | Oracle schema conversion | DDL parser subset, datatype mapping, PostgreSQL SQL draft, diagnostics | deterministic tests; unsupported constructs blocked/reported | Implemented; CI-verified |
| WP8.2 | Source schema extraction | Read-only dictionary scripts, DBMS_METADATA DDL export, stable manifest, reconciliation | synthetic tests; sanitized Oracle validation pending | Implemented baseline |
| WP8.3 | Data migration engine | Chunk manifest, typed extraction contract, resumable checkpoints, retry-safe PostgreSQL load | restart/retry tests and row/key coverage | Planned |
| WP8.4 | Data reconciliation | Counts, PK coverage, aggregates, chunk hashes, LOB length/hash, FK validation | source/target reconciliation report | Planned |
| WP8.5 | PL/SQL conversion workbench | Rule registry, parse/diagnose supported SQL/PLSQL subset, manual-review stubs | golden fixtures and no false AUTO classification | Planned |
| WP8.6 | Runtime integration | Generated repositories/services/API contracts and DB integration tests | disposable PostgreSQL integration tests | Planned |
| WP8.7 | APEX functional parity | Source-to-target test model, Playwright journeys, server assertions | representative sanitized APEX and target journeys | Planned |
| WP8.8 | Security and cutover | Identity/policy mapping, rehearsal, rollback, cutover checklist | security review, rehearsal evidence, sign-off | Planned |

## WP8.2 — Read-only metadata extraction

Owner-scoped SQLcl/SQL*Plus scripts use ALL_* dictionary views to export object status, columns, constraints, indexes, declared dependencies, partitions, grants, and synonyms. A separate DBMS_METADATA.GET_DDL script exports a defined set of object types. SQLcl is recommended for CLOB output; verify CLOB completeness, quoting, and per-object errors on the source Oracle release.

The offline manifest normalizer records owner/type/name, status, last DDL time, DDL extraction state, relative filename, and SHA-256. The operator supplies the extraction timestamp. Duplicate dictionary rows, missing DDL, and path traversal are explicit diagnostics. Reconciliation compares manifest object keys and per-type counts with a dictionary CSV snapshot.

Security boundary: use a dedicated read-only account and ALL_* visibility. Do not use SYS/SYSTEM or broad dictionary/table privileges solely for this workflow. No credentials or production extracts belong in Git. Partition NUM_ROWS/LAST_ANALYZED are optimizer statistics, not authoritative live row counts. ALL_DEPENDENCIES does not expose dynamic SQL or every runtime dependency. Missing DDL is an extraction gap, not proof of object absence.

## Production qualification boundary

WP8.1/WP8.2 are offline foundations, not production-certified migration utilities. A representative sanitized DDL/metadata corpus and dictionary comparison remain required. Datatype mappings need business-owner review for precision, timezone, character semantics, collation, and Oracle empty-string behavior.

## Next step

WP8.3 should add a typed, restartable chunked data extraction/load contract with durable checkpoints and retry-safe behavior. WP8.4 must reconcile counts, keys, aggregates, chunk hashes, LOBs, and referential integrity. Production connectivity requires separate explicit approval of credentials, network boundaries, least-privilege accounts, and disposable-target testing.
