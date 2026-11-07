# WP8 — Functional Migration & Runtime Integration Backlog

WP8 is phased and remains in progress. See the [phase plan](../migration/wp8-functional-migration.md).

| ID | Work package | Status |
|---|---|---|
| WP8.1 | Conservative Oracle CREATE TABLE to PostgreSQL DDL draft | Implemented; CI-verified |
| WP8.2 | Read-only Oracle metadata extraction and dictionary reconciliation | Implemented baseline; CI pending |
| WP8.3 | Restartable chunked data migration engine | Planned |
| WP8.4 | Data reconciliation and integrity report | Planned |
| WP8.5 | PL/SQL conversion workbench and rule registry | Planned |
| WP8.6 | Runtime repositories, services, APIs, and PostgreSQL integration | Planned |
| WP8.7 | APEX-to-target functional parity test harness | Planned |
| WP8.8 | Security mapping, rehearsal, rollback, and cutover readiness | Planned |

## WP8.2 checklist

- [x] SQLcl/SQL*Plus read-only inventory scripts using owner-scoped ALL_* views.
- [x] Export objects, columns, constraints, indexes, dependencies, partitions, grants, and synonyms.
- [x] DBMS_METADATA DDL export script with explicit object allowlist.
- [x] Stable JSON manifest, explicit timestamp, and SHA-256 for extracted DDL.
- [x] Missing DDL, duplicate rows, and path traversal diagnostics.
- [x] Object-key and per-type count reconciliation.
- [x] Synthetic regression tests and security/coverage documentation.
- [ ] Validate SQLcl/SQL*Plus output and DBMS_METADATA coverage against a sanitized representative Oracle schema.

## WP8 global quality gates

- No production connection or credential use without explicit approval.
- No generated SQL executes automatically; unsupported semantics are never silently dropped.
- Data migration must be restartable and idempotent.
- Reconciliation must cover counts, keys, aggregates, chunk hashes, LOBs, and referential integrity.
- Functional parity requires representative sanitized APEX exports and source-side behavior evidence.
- WP8 is not complete until all eight work packages pass their acceptance gates.
