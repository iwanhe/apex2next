# WP9 — Real APEX Application Pilot & Production Qualification

## Objective and honest status

WP9 qualifies the complete WP1–WP8 pipeline against one representative, sanitized Oracle APEX application and consistent Oracle evidence. A candidate Oracle APEX SQL export and a companion APEXLang archive have now been received and statically inventoried in WP9.1. Formal sanitization attestation, Oracle dictionary/DDL/PLSQL/data evidence, target pilot execution, witnessed test evidence and owner approvals are still missing. The candidate is therefore not yet a qualified pilot. This delivery establishes intake contracts, an offline qualification assessor, evidence gates, and an execution runbook; it does not claim production qualification.

## WP9.1 candidate intake

The 2026-11-07 static intake report is [WP9.1 — Candidate Pilot Intake: Demo Permintaan Barang](wp9.1-pilot-intake-f170134.md). It records the uploaded archive hashes, app ID 170134, export release metadata 26.2.1, page/component inventory, cross-format discrepancy (page 00302 is missing from the APEXLang archive), parser coverage gaps, database/PLSQL dependencies and the current fail-closed gate assessment. A separate user-supplied generated `install.sql` has since been inspected: it contains 9 tables, 10 views, 4 package specifications and bodies, 5 triggers, indexes, constraints and demo/config DML. This advances schema/PLSQL source intake but does not replace Oracle dictionary reconciliation or data/runtime evidence.

The inspection was read-only. No archive source was executed and no database connection was made. The archives were not committed to Git. The report's basic source scan is not a sanitization attestation.

## WP9.2 — static source/database analysis

The offline analysis is recorded in [WP9.2 static analysis](wp9.2-static-analysis-f170134.md), with a [dependency map](wp9.2-object-dependency-map-f170134.md), [conversion disposition matrix](wp9.2-conversion-disposition-f170134.md), [partial PostgreSQL DDL draft](wp9.2-postgresql-ddl-draft.sql) and [machine-readable report](wp9.2-analysis-f170134.json).

The analysis reconciles the APEX SQL export and generated install script at source level, confirms that APEXLang omits page 00302, maps 9 tables/10 views/4 packages/5 triggers, and identifies security, dynamic SQL, transaction and concurrency risks. Only three tables are included in the partial PostgreSQL DDL; six identity-bearing tables and the virtual generated column remain blocked. No source SQL was executed and no Oracle connection was made.

WP9.2 is complete as an offline analysis deliverable. It does not establish installed-object validity, dictionary/grant parity, functional parity, or production qualification. WP9-004/005 remain incomplete pending live owner-scoped dictionary and semantic evidence.

## WP9.3 — source validation & PostgreSQL target schema (offline part)

Recorded in [WP9.3 source validation & target schema](wp9.3-source-validation-schema-f170134.md), using the [schema conversion engine](../architecture/wp9.3-schema-conversion-engine.md) (schema-plan 0.3.0). The source `install.sql` hash matches WP9.2. The generated migration emits all 9 tables, with every PK, FK, UNIQUE and CHECK, the 4 indexes, 6 identity columns and the stored generated column. 8 of the 10 views are emitted; the 2 views that depend on PL/SQL have a target design. The migration is verified on PostgreSQL 16: the catalog equals the plan, behavior tests pass, re-apply is atomic, and output is deterministic. Twelve dependency checks run, including APEX consumer references. The only failure is source finding SRC-001: the page 100 KPI region selects columns that `APX_DEMO_DASH_KPI_V` does not define in `install.sql`.

WP9-004 advances to "reviewed target DDL draft". WP9.3b dictionary reconciliation (2026-11-08) confirms that all 49 installed objects are VALID and that tables, constraints, indexes, identity, triggers and PL/SQL source match the script. There is one view drift: `APX_DEMO_DASH_KPI_V` was redefined after install, which explains SRC-001. WP9-004 stays open until that view text is captured and the plan is regenerated. Page 00302 is still unresolved. Triggers and packages are inventoried for WP9.4 and are not converted.

## Pilot selection

Select one bounded but representative application with a named business/application owner, 3–5 critical journeys, at least two roles, privileged and negative authorization paths, representative pages/items/regions/validations/dynamic actions/processes/LOVs/reports/APIs/PLSQL/database objects, and relevant integrations/jobs. Avoid a trivial read-only application. Use non-production and synthetic or approved anonymized data.

## Intake requirements

Manifest version: apex2next.wp9-pilot-input.v1.

Declare source format APEX_SQL_EXPORT or APEXLANG_DIRECTORY, sanitization attestation, application ID, actual APEX runtime version, consistent snapshot identifier, and artifact relative paths/byte sizes/SHA-256. Include approved Oracle dictionary/DDL and PL/SQL inventory, business journey catalogue, role matrix, and data classification as evidence.

Never place production passwords, tokens, private keys, session cookies, PII, or unapproved exports in Git. Sanitization is a human/security attestation, not inferred from filenames. The assessor validates hash format only; intake operators must calculate hashes from actual files.

## Twelve qualification gates

| Gate | Required evidence |
|---|---|
| WP9-001 | Sanitized package inventory, checksums, scope, chain of custody |
| WP9-002 | Actual APEX runtime version, app ID, owner, source snapshot |
| WP9-003 | Extraction logs, IR validation, unresolved reference/dependency report |
| WP9-004 | Oracle dictionary/DDL reconciliation and reviewed target DDL |
| WP9-005 | PL/SQL inventory, dependency map, unsupported/manual dispositions |
| WP9-006 | Generated Next.js/NestJS build, PostgreSQL migrations, target schema review |
| WP9-007 | Consistent-snapshot migration rehearsal, retry/resume, data reconciliation |
| WP9-008 | Business-approved source/target critical journey parity |
| WP9-009 | Identity/role mapping, positive/negative access and row-level security |
| WP9-010 | Load/performance, observability, operations and defect acceptance |
| WP9-011 | Witnessed backup restore and rollback meeting approved RTO/RPO |
| WP9-012 | Business, application, security and operations sign-off |

PASS requires an evidence reference. WARN is conditional, FAIL blocks, and missing/NOT_VERIFIED evidence is incomplete. Only all-PASS intake and gates, zero critical/high defects, and explicit RTO/RPO produce QUALIFIED.

## Run assessor

```bash
PYTHONPATH=workers/schema-analyzer/src python -m apex2next_schema_analyzer.pilot_qualification \
  tests/fixtures/wp9/synthetic-pilot.json \
  --output /tmp/wp9-qualification-report.json
```

Exit codes: 0 QUALIFIED, 1 BLOCKED, 3 CONDITIONAL, 4 INCOMPLETE, 2 invalid input/I/O. The checked-in fixture is synthetic and validates only the assessor contract.

## Execution sequence

1. Agree pilot scope, owner, journeys, roles, data classification and acceptance criteria.
2. Export APEX using approved tooling; extract Oracle dictionary/DDL and source evidence from a consistent snapshot.
3. Sanitize and inspect package outside Git; calculate checksums and record chain of custody.
4. Run extraction, parser, normalized IR validation, dependency analysis, schema conversion, PL/SQL workbench and target generation.
5. Review every unsupported, assisted, manual, unresolved and warning diagnostic; no silent drops.
6. Provision isolated disposable PostgreSQL target; apply reviewed migrations and load approved sanitized data.
7. Reconcile counts, keys, aggregates, LOBs and referential integrity.
8. Implement/review target APIs, workflows, authorization and UI for approved journeys.
9. Capture equivalent source/target evidence; run parity and negative access tests.
10. Run performance/load, restore, migration rehearsal, rollback rehearsal and operational review.
11. Resolve defects, rerun affected evidence, obtain four owner sign-offs.
12. Produce qualification report and go/no-go recommendation. Production change remains separately authorized.

## Exit criteria

- No unresolved critical/high defects.
- Every in-scope source object has explicit disposition.
- Data reconciliation PASS for approved consistent snapshots.
- All mandatory journeys and role tests PASS.
- Security, performance, backup/restore, rollback, monitoring and operations gates PASS.
- RTO/RPO measured in a witnessed rehearsal.
- Business/application/security/operations sign-off recorded.

## Current blockers

Formal sanitization attestation and source scope; confirmed actual runtime/snapshot; Oracle dictionary reconciliation and any missing object/grant evidence; archive-aware extraction and parser coverage; review of dynamic SQL and trigger/package semantics; consistent data evidence; disposable PostgreSQL target and target build; approved critical journeys and role matrix; witnessed rehearsal/restore/rollback/performance; formal owner approvals.

## Safety

This WP9 assessor uses no production credentials or connections. Do not commit real source exports or data. Live Oracle extraction, data movement, Playwright execution against real source/target, and production changes require separate approval and security design.
