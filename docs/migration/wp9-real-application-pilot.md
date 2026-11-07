# WP9 — Real APEX Application Pilot & Production Qualification

## Objective and honest status

WP9 qualifies the complete WP1–WP8 pipeline against one representative, sanitized Oracle APEX application and consistent Oracle evidence. The repository currently has synthetic APEXLang fixtures only; no real sanitized application export or witnessed pilot evidence is present. This delivery establishes intake contracts, an offline qualification assessor, evidence gates, and an execution runbook. It does not claim a real pilot was executed or production-qualified.

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

\`\`\`bash
PYTHONPATH=workers/schema-analyzer/src python -m apex2next_schema_analyzer.pilot_qualification \\
  tests/fixtures/wp9/synthetic-pilot.json \\
  --output /tmp/wp9-qualification-report.json
\`\`\`

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

A sanitized real APEX export and runtime version; matching Oracle dictionary/DDL/PLSQL/data evidence; disposable PostgreSQL target and target build; approved critical journeys and role matrix; witnessed rehearsal/restore/rollback/performance; formal owner approvals.

## Safety

This WP9 assessor uses no production credentials or connections. Do not commit real source exports or data. Live Oracle extraction, data movement, Playwright execution against real source/target, and production changes require separate approval and security design.
