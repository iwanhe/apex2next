# WP8 — Functional Migration & Runtime Integration Backlog

WP8 is phased and remains in progress. See [WP8 phase plan](../migration/wp8-functional-migration.md).

| ID | Work package | Status |
|---|---|---|
| WP8.1 | Conservative Oracle CREATE TABLE to PostgreSQL DDL draft | Implemented baseline; CI pending |
| WP8.2 | Read-only Oracle metadata extraction and dictionary reconciliation | Planned |
| WP8.3 | Restartable chunked data migration engine | Planned |
| WP8.4 | Data reconciliation and integrity report | Planned |
| WP8.5 | PL/SQL conversion workbench and rule registry | Planned |
| WP8.6 | Runtime repositories, services, APIs, and PostgreSQL integration | Planned |
| WP8.7 | APEX-to-target functional parity test harness | Planned |
| WP8.8 | Security mapping, rehearsal, rollback, and cutover readiness | Planned |

## WP8.1 implementation checklist

- [x] Add offline Oracle CREATE TABLE parser subset.
- [x] Add conservative scalar datatype mapping.
- [x] Convert table-level primary keys, unique constraints, and in-snapshot foreign keys.
- [x] Generate deterministic PostgreSQL DDL draft and JSON diagnostics report.
- [x] Block tables with unknown datatype, identity/generated columns, or inline REFERENCES.
- [x] Report unsupported CHECK constraints, defaults, and external foreign keys.
- [x] Validate target schema identifier and quote source identifiers.
- [x] Add regression tests for comments, strings, quoted identifiers, constraints, unsupported features, and deterministic output.
- [x] Document offline/read-only execution and limitations.
- [x] CI verification on final WP8.1 commit (85 pytest passed; all 4 CI jobs passed).
- [ ] Compare a sanitized representative DDL export with Oracle dictionary metadata.

## WP8.1 CI evidence

Final verified commit: `fcd73ee71dcd65d93ba579177d26855545bbe2d5`. Run: [42363415407](https://github.com/iwanhe/apex2next/actions/runs/42363415407).

## WP8 global quality gates

- No production connection or credential use without explicit approval.
- No generated SQL executes automatically.
- No unsupported data types or business semantics are silently dropped.
- Every conversion has a stable rule ID/version, diagnostic, and test fixture.
- Data migration must be restartable and idempotent.
- Reconciliation must cover counts, keys, aggregates, chunk hashes, LOBs, and referential integrity.
- Functional parity requires representative sanitized APEX exports and source-side behavior evidence.
- No claim of WP8 completion until all eight work packages pass their acceptance gates.