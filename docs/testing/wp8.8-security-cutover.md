# WP8.8 — Security mapping, rehearsal, rollback, and cutover readiness

## Objective

Establish a fail-closed, evidence-driven gate for a migration rehearsal and a future production cutover. This package supplies an offline assessment engine and operational runbook template. It does not connect to source/target systems and does not execute cutover or rollback.

## Delivered offline baseline

- Versioned input manifest: \`apex2next.cutover-readiness-input.v1\`.
- Security controls for identity/role mapping, privileged MFA, non-interactive service identities, secret externalization, transport encryption, audit logging, least privilege, and access tests.
- Role permission comparison: target permission set must be a subset of the declared source permission set; mappings must be reviewed and evidenced.
- Cutover controls for restore verification, full rehearsal, data reconciliation PASS, functional parity PASS, rollback test, monitoring/on-call readiness, approved change window, and approved runbook.
- Four mandatory approvals: BUSINESS_OWNER, APPLICATION_OWNER, SECURITY_OWNER, OPERATIONS_OWNER.
- Explicit rollback RTO/RPO objectives and evidence reference.
- Deterministic JSON report with per-control status, category summary, input SHA-256, and fail-closed authorization eligibility.
- CLI exit codes: 0 READY, 3 BLOCKED, 2 invalid input/I/O.

## Run

\`\`\`bash
PYTHONPATH=workers/schema-analyzer/src python -m apex2next_schema_analyzer.cutover_readiness \\
  tests/fixtures/cutover/synthetic-ready.json \\
  --output /tmp/cutover-readiness-report.json
\`\`\`

The checked-in synthetic fixture demonstrates the manifest contract only. It is not real security review, restore, rehearsal, reconciliation, parity, rollback, or approval evidence.

## Security mapping rules

1. Inventory source users, roles, responsibilities, privileges, row-level policies, service accounts, and integration identities from approved read-only extracts.
2. Map each source role to a named target role and explicit permission set. Do not infer missing grants.
3. Target permissions must not exceed the declared source permission set without a separately approved business/security exception.
4. Review privileged roles separately; require MFA for human privileged access and non-interactive scoped credentials for services.
5. Externalize secrets to an approved secret manager; prohibit credentials in repository files, generated artifacts, test reports, and migration bundles.
6. Enforce TLS for network paths and audit authentication, authorization changes, privileged operations, and data export.
7. Test positive and negative authorization cases, including row-level boundaries and tenant/company separation where applicable.
8. Retain source inventory, mapping diff, reviewer identity, approval record, and test evidence references.

The subset comparison is a conservative guardrail, not a complete authorization equivalence proof. Source and target permission vocabularies must be normalized and reviewed before comparing.

## Rehearsal runbook

### Pre-rehearsal gates
- Approved source snapshot/SCN and extraction scope.
- Target environment isolated, disposable, and access-controlled.
- Sanitized data and synthetic identities; no production credentials in logs or artifacts.
- Schema conversion reviewed; unsupported objects explicitly dispositioned.
- Target migration plan, dependency order, and repeatability confirmed.
- Backup and restore procedure tested on the target recovery boundary.
- Monitoring dashboards, alert routing, operator roster, and incident contacts ready.

### Rehearsal sequence
1. Record source snapshot identifier, target release/build, environment, operator, and change record.
2. Capture baseline counts, keys, aggregates, LOB checksums, and referential integrity evidence.
3. Execute the approved extraction and chunk load in the isolated rehearsal environment.
4. Resume/retry a deliberately interrupted chunk and prove target-side idempotency.
5. Run full data reconciliation; investigate all WARN/FAIL outcomes.
6. Run source/target functional journeys and role access tests using the same test identities and synthetic data.
7. Measure elapsed time, throughput, error rate, resource use, and operator interventions.
8. Exercise rollback to the declared recovery point; verify RTO/RPO and data consistency.
9. Capture evidence references, deviations, defects, corrective actions, and owner sign-offs.
10. Repeat until exit criteria are met; never waive unresolved critical security or data-integrity failures.

## Rollback strategy and safety boundaries

- Define the rollback decision authority, trigger thresholds, latest safe rollback time, and communication protocol before the change window.
- Record explicit RTO and RPO objectives and test them, not merely document them.
- Freeze source writes or use a separately designed and tested reverse-change/data-capture strategy. Do not assume that restoring an old database automatically preserves writes made after cutover.
- Preserve source environment and backup until formal acceptance and retention expiry.
- Keep target writes disabled or controlled until the rollback window closes, according to the approved business continuity design.
- A database restore alone is not application rollback: include DNS/routing, application release, identity configuration, secrets, integrations, scheduled jobs, and queued messages.
- Avoid split-brain writes. Establish one authoritative write system at each phase and define reconciliation for any permitted dual-write interval.
- This repository does not automate rollback. Any actual restore, routing change, or deployment reversal requires a separately approved operational runbook and authorized operator.

## Cutover checklist

### T-7 to T-1 days
- [ ] Security mapping signed by application and security owners.
- [ ] Critical functional journeys and role matrix approved.
- [ ] Full rehearsal completed with measured duration and no unresolved critical defects.
- [ ] Data reconciliation PASS for the approved consistent snapshots.
- [ ] Functional parity PASS for all mandatory journeys.
- [ ] Backup restore and rollback rehearsal meet approved RTO/RPO.
- [ ] Target monitoring, alerts, on-call, support, and communications verified.
- [ ] Change ticket, cutover window, freeze, and go/no-go authority approved.

### T-0
- [ ] Confirm source snapshot and write-freeze/CDC boundary.
- [ ] Confirm target release checksum, schema version, configuration, secrets, and integrations.
- [ ] Execute approved final delta/data load and reconciliation.
- [ ] Run smoke tests, access tests, business-critical transactions, and queue/scheduler checks.
- [ ] Obtain explicit go/no-go from business, application, security, and operations owners.
- [ ] Record decision time, operator, evidence, and any accepted residual risk.

### T+1 to T+N
- [ ] Monitor business KPIs, errors, latency, authorization denials, data drift, and integrations.
- [ ] Reconcile agreed control totals and transaction samples.
- [ ] Keep rollback capability and source retention until acceptance criteria are met.
- [ ] Close incident/deviation log and obtain formal business acceptance.

## Readiness semantics

- \`READY\`: every required control, rollback objective, and four approvals has PASS evidence.
- \`BLOCKED\`: any explicit failure or missing/unverifiable evidence exists.
- The report is advisory and cannot authorize production changes. A READY report is necessary evidence, not a substitute for the organization's formal change authority.

## Production qualification inputs

- Approved source identity/role/privilege inventory and target authorization model.
- Real evidence references from identity, security testing, backup/restore, rehearsal, parity, reconciliation, and change-management systems.
- Documented data freeze/CDC/reverse-data strategy and application/integration rollback plan.
- Business-approved RTO/RPO and residual-risk acceptance.
- Security, operations, application, and business owner sign-off.
