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
| WP8.7 | APEX-to-target functional parity test harness | Implemented offline baseline; CI-verified |
| WP8.8 | Security mapping, rehearsal, rollback, and cutover readiness | Implemented offline baseline; CI-verified on PR head 6fdde26; real rehearsal/sign-off pending |
| WP9.1 | Candidate pilot archive intake and static source assessment | Completed; qualification incomplete |
| WP9.2 | Real pilot source/database dependency analysis and partial PostgreSQL DDL draft | Completed offline/static; live reconciliation incomplete |
| WP9.3 | Oracle schema conversion plan, PostgreSQL 16 integration and dictionary reconciliation | Offline conversion/integration CI-verified; unresolved installed-view drift and snapshot consistency remain |

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

## WP8.7 checklist

- [x] Versioned paired source/target evidence manifest and deterministic parity report.
- [x] Functional, API, data, workflow, security, and UI comparison domains.
- [x] Exact, explicit numeric-tolerance, and unordered-set comparators.
- [x] Missing evidence is NOT_VERIFIED; mismatches are FAIL; no silent PASS.
- [x] CLI exit codes and stable diagnostic codes.
- [x] Golden synthetic fixtures and negative tests.
- [x] Playwright source/target capture contract documented.
- [ ] Playwright execution against representative sanitized APEX and target pilot.
- [ ] Business-approved critical journeys, role matrix, API contracts, and data canonicalization.
- [ ] Evidence retention, redaction, and business-owner sign-off.

## WP8.8 checklist

- [x] Versioned cutover-readiness manifest and deterministic offline assessment report.
- [x] Identity/role mapping with reviewed target permission non-expansion check.
- [x] MFA, service identity, secrets, TLS, audit, least privilege, and access-test controls.
- [x] Restore, rehearsal, reconciliation, parity, rollback, monitoring, change-window, and runbook controls.
- [x] Four mandatory owner approvals and explicit RTO/RPO evidence.
- [x] Fail-closed status semantics and synthetic positive/negative tests.
- [x] Security mapping, rehearsal, rollback, and cutover runbook documented.
- [ ] Validate mapping against real approved source/target identity inventories.
- [ ] Execute representative restore, migration rehearsal, parity, and rollback in isolated pilot.
- [ ] Obtain formal security, business, application, and operations sign-off.
- [ ] Production change authority and actual cutover remain outside this offline tool.

## WP9 — Real APEX application pilot & production qualification

- [x] Versioned pilot intake and qualification manifest.
- [x] Source format, sanitization attestation, runtime, snapshot, artifact path/size/hash structure checks.
- [x] Twelve fail-closed qualification gates spanning WP1–WP8, data, parity, security, performance, rollback and sign-off.
- [x] Critical/high defect thresholds and explicit RTO/RPO acceptance.
- [x] Deterministic report, CLI exit codes, synthetic fixture and negative tests.
- [x] Pilot selection, intake, execution, evidence and exit-criteria runbook.
- [x] Receive and statically inventory candidate Oracle APEX SQL export and companion APEXLang archive; record archive hashes and page/component inventories.
- [x] Compare cross-format page inventories and identify the missing APEXLang page 00302.
- [ ] Obtain formal sanitization attestation and confirm source instance runtime/snapshot.
- [ ] Implement archive-aware intake and expand SQL-export parser coverage for shared components and security schemes.
- [x] Receive and statically inventory generated combined database install script containing table/view DDL, package specs/bodies and triggers.
- [ ] Reconcile supplied install script against Oracle dictionary, installed object validity, grants and consistent data evidence.
- [ ] Execute full WP1–WP8 pipeline against real source and consistent Oracle evidence.
- [ ] Validate target against business-approved journeys.
- [ ] Complete witnessed rehearsal, performance, restore, rollback and owner sign-off.
- [ ] Production qualification and production cutover authorization.

See [WP9.1 candidate intake report](wp9.1-pilot-intake-f170134.md) for source evidence and blockers.


## WP9.2 — Candidate application source/database analysis (offline complete)

- Reconcile the 19-page Oracle APEX SQL export against the 18-page APEXLang archive; identify page 00302 as missing from APEXLang.
- Reconcile actual APEX SQL database references against the generated combined install script; mask comments/literals to avoid false unresolved references.
- Inventory 9 tables, 10 views, 4 package specs/bodies, 5 triggers, 4 explicit indexes and declared constraints.
- Map relational, view, package, trigger and APEX page dependencies; mark configuration/dynamic SQL edges explicitly.
- Review security bootstrap behavior, package bypass state, dynamic SQL, transaction ownership, submit race and document-number concurrency.
- Produce PostgreSQL conversion disposition matrix and partial DDL draft for 3/9 tables; six identity/generated-column tables remain blocked.
- Preserve source artifacts outside Git; analysis is static only, no database connection or source execution.

Deliverables:
- [WP9.2 static analysis](../migration/wp9.2-static-analysis-f170134.md)
- [Object dependency map](../migration/wp9.2-object-dependency-map-f170134.md)
- [Conversion dispositions](../migration/wp9.2-conversion-disposition-f170134.md)
- [Partial PostgreSQL DDL draft](../migration/wp9.2-postgresql-ddl-draft.sql)
- [Machine-readable analysis report](../migration/wp9.2-analysis-f170134.json)

WP9.2 closes the offline analysis slice, not WP9 production qualification. WP9-004/005 remain incomplete until Oracle dictionary/installed-object reconciliation and semantic validation; WP9-006/008/009 remain not verified until target build, approved journeys and security evidence exist.
