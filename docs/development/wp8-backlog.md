# WP8 — Functional Migration & Runtime Integration Backlog

WP8 is phased and remains in progress. See the [phase plan](../migration/wp8-functional-migration.md).

| ID | Work package | Status |
|---|---|---|
| WP8.1 | Conservative Oracle CREATE TABLE to PostgreSQL DDL draft | Implemented; CI-verified |
| WP8.2 | Read-only Oracle metadata extraction and dictionary reconciliation | Implemented baseline; CI-verified |
| WP8.3 | Restartable chunked data migration engine | Implemented offline baseline; CI pending |
| WP8.4 | Data reconciliation and integrity report | Planned |
| WP8.5 | PL/SQL conversion workbench and rule registry | Planned |
| WP8.6 | Runtime repositories, services, APIs, and PostgreSQL integration | Planned |
| WP8.7 | APEX-to-target functional parity test harness | Planned |
| WP8.8 | Security mapping, rehearsal, rollback, and cutover readiness | Planned |

## WP8.3 checklist

- [x] Deterministic bounded JSONL chunk manifest with unique ordered key contract.
- [x] Per-chunk row counts, key boundaries, and SHA-256 checksums.
- [x] Durable SQLite checkpoint ledger with pending/running/loaded/failed states.
- [x] Retry/resume behavior and skip of durable loaded chunks.
- [x] Target sink idempotency contract for commit/checkpoint crash windows.
- [x] Checksum and row-count verification before target load.
- [x] Synthetic tests for restart, retry, failure recovery, tampering, and partial-load rejection.
- [x] Oracle keyset extraction template and operational/security guidance.
- [ ] Validate snapshot SCN, keyset SQL plans, type fidelity, and throughput on a sanitized representative Oracle schema and disposable PostgreSQL target.
- [ ] Implement and test a real PostgreSQL adapter after database integration design and credentials are explicitly approved.

## WP8 global quality gates

- No production connection or credential use without explicit approval.
- No generated SQL executes automatically; unsupported semantics are never silently dropped.
- Data migration must be restartable and idempotent.
- Reconciliation must cover counts, keys, aggregates, chunk hashes, LOBs, and referential integrity.
- Functional parity requires representative sanitized APEX exports and source-side behavior evidence.
- WP8 is not complete until all eight work packages pass their acceptance gates.
