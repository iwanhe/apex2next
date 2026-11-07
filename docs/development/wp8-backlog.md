# WP8 — Functional Migration & Runtime Integration Backlog

WP8 is phased and remains in progress. See the [phase plan](../migration/wp8-functional-migration.md).

| ID | Work package | Status |
|---|---|---|
| WP8.1 | Conservative Oracle CREATE TABLE to PostgreSQL DDL draft | Implemented; CI-verified |
| WP8.2 | Read-only Oracle metadata extraction and dictionary reconciliation | Implemented baseline; CI-verified |
| WP8.3 | Restartable chunked data migration engine | Implemented offline baseline; CI-verified |
| WP8.4 | Data reconciliation and integrity report | Implemented offline baseline; CI pending |
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
- [ ] Validate snapshot SCN, keyset SQL plans, type fidelity, and throughput on sanitized Oracle/PostgreSQL environments.
- [ ] Implement and test a real PostgreSQL adapter after database integration design and credentials are explicitly approved.

## WP8.4 checklist

- [x] Compare source/target row counts and report deltas.
- [x] Compare single/composite primary-key coverage, missing/extra keys, and duplicates.
- [x] Compare configured COUNT/SUM/MIN/MAX aggregates with explicit SUM tolerance.
- [x] Verify WP8.3 chunk IDs, checksums, and row counts against target receipts.
- [x] Compare FK violation baselines and flag increased target violations.
- [x] Compare LOB row counts, byte lengths, and canonical SHA-256 evidence.
- [x] Emit deterministic JSON, PASS/WARN/FAIL status, and stable diagnostics.
- [x] Add synthetic regression tests for mismatches, missing evidence, determinism, and immutability.
- [ ] Validate query recipes, target receipts, LOB canonicalization, and scale on sanitized representative data.
- [ ] Add streaming/external-sort key comparison for very large tables if measured report size or memory requires it.

## WP8 global quality gates

- No production connection or credential use without explicit approval.
- No generated SQL executes automatically; unsupported semantics are never silently dropped.
- Data migration must be restartable and idempotent.
- Reconciliation must cover counts, keys, aggregates, chunk hashes, LOBs, and referential integrity.
- Functional parity requires representative sanitized APEX exports and source-side behavior evidence.
- WP8 is not complete until all eight work packages pass their acceptance gates.
