# WP8 — Functional Migration and Runtime Integration

**Delivery model:** phased; each phase has an independent acceptance gate.  
**Current implementation:** WP8.1 schema conversion, WP8.2 metadata extraction, WP8.3 offline chunk migration, and WP8.4 offline reconciliation baseline.  
**Status:** WP8 remains in progress; offline foundations are not production-qualified.

## Work packages

| ID | Scope | Main deliverables | Acceptance evidence | Status |
|---|---|---|---|---|
| WP8.1 | Oracle schema conversion | DDL parser subset, datatype mapping, PostgreSQL SQL draft, diagnostics | deterministic tests; unsupported constructs blocked/reported | Implemented; CI-verified |
| WP8.2 | Source schema extraction | Read-only dictionary scripts, DBMS_METADATA DDL export, stable manifest, reconciliation | synthetic tests; sanitized Oracle validation pending | Implemented baseline; CI-verified |
| WP8.3 | Data migration engine | Bounded chunks, typed JSONL contract, durable checkpoints, retries, idempotent sink contract | restart/retry/tamper tests; live adapters pending | Implemented offline baseline; CI-verified |
| WP8.4 | Data reconciliation | Counts, PK coverage, aggregates, chunk hashes, LOB length/hash, FK validation | deterministic offline tests; sanitized source/target validation pending | Implemented offline baseline; CI pending |
| WP8.5 | PL/SQL conversion workbench | Rule registry, parse/diagnose supported SQL/PLSQL subset, manual-review stubs | golden fixtures and no false AUTO classification | Planned |
| WP8.6 | Runtime integration | Generated repositories/services/API contracts and DB integration tests | disposable PostgreSQL integration tests | Planned |
| WP8.7 | APEX functional parity | Source-to-target test model, Playwright journeys, server assertions | representative sanitized APEX and target journeys | Planned |
| WP8.8 | Security and cutover | Identity/policy mapping, rehearsal, rollback, cutover checklist | security review, rehearsal evidence, sign-off | Planned |

## WP8.3 — Offline chunk migration baseline

The offline engine accepts rows already extracted by an approved source-side process. It writes deterministic bounded JSONL chunks and a manifest with key boundaries, row counts, and SHA-256. Input rows must be strictly ordered by a unique, non-null key. Extraction must use explicit columns and a consistent Oracle snapshot; the supplied keyset SQL is a reviewed template, not an executed query.

A SQLite checkpoint ledger persists chunk status and retry attempts. On restart, chunks marked LOADED are skipped. Failed chunks can be retried. Before loading, the engine verifies chunk checksum and row count. The target sink contract requires atomic, idempotent application keyed by migration ID/chunk ID/checksum, which covers the failure window where the target commits but the local checkpoint does not.

No live Oracle reader, PostgreSQL sink, CDC, parallel worker coordination, LOB streaming, or reconciliation was implemented in WP8.3. The fake sink exists only in tests. The checkpoint store is designed for one worker; do not share it across concurrent workers.

Operational safeguards: secure/encrypt chunk files and checkpoint database, restrict access, keep exports out of Git, and define retention/deletion. The source snapshot SCN, keyset query plan, and datatype fidelity require representative validation before a real migration.

## WP8.4 — Offline data reconciliation baseline

The `reconcile_snapshots(source, target, ...)` API consumes normalized JSON evidence. For each table it compares row counts and deltas; exact single/composite primary-key coverage (including duplicate, missing, and extra keys); configured COUNT/SUM/MIN/MAX aggregates; FK violation baselines; and LOB row counts, byte lengths, and SHA-256. Optional WP8.3 chunk manifests are compared with target chunk receipts by ID, checksum, and row count.

The report is deterministic JSON with table/domain statuses, coverage percentage, diagnostic codes, and a summary. FAIL is used for data mismatches and target integrity regressions. WARN is used when evidence is missing/incomplete or source-side FK violations already exist. Missing evidence is never silently treated as PASS. SUM tolerance is explicit and applies only to SUM; counts, MIN, and MAX are exact.

No live database reader, source query runner, target receipt writer, streaming key-diff engine, or LOB byte reader is included. Source/target evidence must be produced by separately reviewed, consistent-snapshot queries. Target receipts must be emitted only after atomic target-side verification. LOB hashes require identical canonical byte representation. Large key lists can produce large reports and require scale validation.

## Production qualification boundary

WP8.1–WP8.4 are offline foundations, not production-certified migration utilities. A representative sanitized DDL/metadata/data corpus and a disposable PostgreSQL target are required. Datatype mappings need business-owner review for precision, timezone, character semantics, collation, and Oracle empty-string behavior. Reconciliation PASS proves only that supplied evidence matches under the configured comparison contract; it does not prove application or business-semantic parity.

## Next step

WP8.5 adds the PL/SQL conversion workbench. Production connectivity requires separate explicit approval of credentials, network boundaries, least-privilege accounts, and target adapter design.
