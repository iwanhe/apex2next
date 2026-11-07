# WP8 — Functional Migration & Runtime Integration Backlog

WP8 is phased and remains in progress. See the phase plan in ../migration/wp8-functional-migration.md.

| ID | Work package | Status |
|---|---|---|
| WP8.1 | Conservative Oracle CREATE TABLE to PostgreSQL DDL draft | Implemented; CI-verified |
| WP8.2 | Read-only Oracle metadata extraction and dictionary reconciliation | Implemented baseline; CI-verified |
| WP8.3 | Restartable chunked data migration engine | Implemented offline baseline; CI-verified |
| WP8.4 | Data reconciliation and integrity report | Implemented offline baseline; CI-verified |
| WP8.5 | PL/SQL conversion workbench and rule registry | Implemented offline baseline; CI-verified |
| WP8.6 | Runtime repositories, services, APIs, and PostgreSQL integration | Implemented generated runtime baseline; CI-verified |
| WP8.7 | APEX-to-target functional parity test harness | Planned |
| WP8.8 | Security mapping, rehearsal, rollback, and cutover readiness | Planned |

## WP8.5 checklist

- [x] Versioned deterministic rule registry with ASSISTED/MANUAL/UNSUPPORTED dispositions.
- [x] Bounded lexical masking for comments and quoted literals; source offsets retained.
- [x] Inventory selected SQL, transaction, cursor, and exception statements.
- [x] Source-located diagnostics, source fingerprint, and deterministic JSON report.
- [x] Preserve source exactly; no generated rewrite and no AUTOMATIC classification.
- [x] Golden regression tests for lexical patterns, comments/literals, and unsupported constructs.
- [ ] Grammar-backed parsing and validation against sanitized representative PL/SQL corpus.
- [ ] Target-specific semantic adapters after behavior tests and explicit review.

## WP8 global quality gates

- No production connection or credential use without explicit approval.
- No generated SQL executes automatically; unsupported semantics are never silently dropped.
- Data migration must be restartable and idempotent.
- Reconciliation covers counts, keys, aggregates, chunk hashes, LOBs, and referential integrity.
- Functional parity requires representative sanitized APEX exports and source-side behavior evidence.
- WP8 is not complete until all eight work packages pass their acceptance gates.


## WP8.6 checklist

- [x] PostgreSQL Pool configuration with bounded pool size and connection timeouts.
- [x] NestJS database module and graceful pool shutdown.
- [x] Liveness and database-readiness endpoints backed by a NestJS health service.
- [x] Parameterized repository primitives with strict table/column allowlists.
- [x] Transaction helper with BEGIN/COMMIT/ROLLBACK and guaranteed client release.
- [x] Target-owned SQL migration runner with advisory lock and per-file transaction.
- [x] PostgreSQL integration test for CRUD, injection resistance, allowlist rejection, and rollback.
- [x] CI verifies migration idempotency by applying the migration runner twice.
- [ ] Sanitized application-specific repositories/services/DTOs after WP8.1 schema and domain review.
- [ ] Production pool sizing, TLS, secrets management, observability, and load tests.
