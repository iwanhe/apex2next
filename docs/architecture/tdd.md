# APEX2NEXT — Technical Design Document

## 1. Design overview

Use a three-plane architecture: control plane, execution plane, and generated target runtime. Keep migration orchestration separate from generated business applications.

## 2. Technology baseline

| Layer | Baseline |
|---|---|
| Dashboard | Next.js App Router, React, TypeScript |
| UI | Tailwind CSS, shadcn/ui; TanStack Table for data grids |
| Forms | React Hook Form + Zod |
| API | NestJS, TypeScript, OpenAPI |
| Database | PostgreSQL |
| Parsing | Python, ANTLR grammars where available and maintained |
| Generation | TypeScript/Python generators with versioned templates |
| Data movement | Oracle driver/extractor, streaming chunks, PostgreSQL COPY |
| Tests | pytest, Vitest/Jest, Supertest, Playwright |
| Runtime | Node.js 22+, Python 3.12+, PostgreSQL 17 baseline |
| Local orchestration | Docker Compose |
| CI | GitHub Actions |

Versions are initial baselines and must be pinned and security-reviewed before release.

## 3. Service boundaries

### migration-dashboard
Project configuration, source registration, inventory browsing, conversion review, run monitoring, diagnostics, reports, and approvals. It must not connect directly to Oracle or PostgreSQL using browser-held credentials.

### migration-api
NestJS API for project lifecycle, orchestration, task state, artifacts, audit, and authorization. Long-running work is delegated to durable workers.

### workers
- extraction-worker: APEX export parsing and Oracle metadata extraction.
- conversion-worker: AST/IR transformations and code generation.
- data-worker: chunked extract-transform-load, checkpoints, and reconciliation.
- validation-worker: test execution and validation evidence.

### shared-contracts
Versioned DTOs, event contracts, diagnostic codes, status enums, and IR schemas shared across services.

## 4. Converter pipeline

`Source input → parser → AST → normalized IR → dependency graph → rule engine → target generators → diagnostics/tests`

- Parser owns syntax recognition and source locations.
- IR owns normalized semantics and references to source objects.
- Rule engine applies versioned transformations.
- Generator emits target files deterministically.
- Diagnostics explain unsupported or uncertain semantics.
- Test generator creates targeted tests from source behavior and mapping rules.

Do not use regular expressions as the primary parser for nested PL/SQL or SQL grammar. Regex may support narrow lexical preprocessing only.

## 5. Data migration design

1. Inspect source metadata and choose a consistent snapshot strategy.
2. Extract in bounded chunks using stable keys or safe pagination.
3. Transform values with explicit type/time/character-set rules.
4. Load using PostgreSQL COPY for bulk paths or parameterized batches.
5. Persist checkpoints and chunk state.
6. Retry failed chunks safely; quarantine irrecoverable rows.
7. Reconcile row counts, primary keys, null/distinct counts, aggregates, hashes, LOB lengths/hashes, and FK orphans.
8. Synchronize sequences/identity generators after load.

Initial offline migration is the first delivery target. CDC is a later capability and must use a real log-based or vendor-supported change capture mechanism.

## 6. Persistence model

Use PostgreSQL schemas to separate framework domains:
- `platform`: users, projects, project configuration.
- `source`: source applications and extracted objects.
- `analysis`: inventory, dependencies, complexity findings.
- `conversion`: rules, results, generated artifacts, diagnostics.
- `migration`: runs, tasks, data transfer checkpoints.
- `validation`: test executions, reconciliation results.
- `deployment`: environments and releases.
- `audit`: append-only activity history.

Use UUID primary keys, TIMESTAMPTZ timestamps, explicit foreign keys, and JSONB only for variable structured payloads—not as a substitute for relational integrity.

## 7. Security design

- Oracle extraction account is read-only and limited to required dictionary/application objects.
- Store credentials in a secret manager; never expose them to dashboard/browser.
- TLS for network traffic and encryption at rest for stored artifacts.
- Use parameterized SQL and allowlisted identifiers for generated dynamic SQL.
- Enforce authorization in NestJS; frontend visibility is not an authorization control.
- Prefer secure, HTTP-only, SameSite cookies for browser sessions.
- Audit privileged actions, source access, conversion approvals, and cutover.
- Review PostgreSQL RLS carefully with connection pooling, role ownership, and BYPASSRLS behavior.

Identity provider choice (Keycloak vs Better Auth) remains an implementation decision; it must support role/permission mapping and secure session lifecycle.

## 8. API conventions

- Version APIs under `/api/v1`.
- Use DTO validation at ingress.
- Return stable error envelopes with machine-readable codes and correlation IDs.
- Use pagination for inventory and diagnostic collections.
- Make orchestration endpoints return task/run identifiers; poll or subscribe for progress.
- Document APIs through OpenAPI.

## 9. Reliability and observability

- Durable task state, idempotency keys, bounded retries, and dead-letter handling.
- Structured JSON logs with project_id, run_id, task_id, source_object_id, and correlation_id.
- Metrics for throughput, retry count, queue age, conversion status, and reconciliation deltas.
- Artifact retention and redaction policy for source exports and logs.
- Health/readiness endpoints for API and workers.

## 10. CI quality gates

Pull requests must run formatting, lint, typecheck, unit tests, Python static checks, conversion fixture regression, and dependency/security scanning. Integration and E2E jobs run when infrastructure is available. No production deployment from an unreviewed or failing branch.
