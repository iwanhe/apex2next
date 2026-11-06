# Engineering Standards

## 1. General principles
Apply KISS, YAGNI, DRY, SOLID, secure-by-default, and explicit ownership. Prefer readable code and small modules over speculative abstractions. Every feature must include observable behavior, validation, and tests appropriate to risk.

## 2. Repository and dependency boundaries
- `apps/` contains deployable applications; `packages/` contains reusable libraries; `workers/` contains durable background processes.
- Keep dependency direction inward: apps/workers may depend on packages; low-level packages must not import apps.
- Avoid circular dependencies. Shared contracts must not depend on framework-specific implementations.
- Pin runtime/toolchain versions and review dependency licenses, maintenance, and vulnerabilities.
- Do not add a dependency for trivial functionality that can be implemented safely with the platform.

## 3. TypeScript and Node.js
- Enable strict TypeScript; do not introduce `any` without a documented boundary justification.
- Validate all external input at runtime (DTO/Zod/class-validator); TypeScript types alone do not validate requests.
- Use async/await, explicit error handling, and structured logs. Never swallow errors.
- Keep controllers thin; business rules belong in services/domain modules.
- Use dependency injection where it improves testability; avoid service-locator patterns.
- Do not expose secrets, SQL, stack traces, or source credentials in API responses/logs.

## 4. Python workers
- Use type hints for public interfaces and small, testable functions.
- Use structured logging and explicit exception classes.
- Stream large files/rows; never load an unbounded export or table into memory.
- Make task handlers idempotent or persist a checkpoint/compensation strategy.
- Separate parsing, transformation, I/O, and orchestration.

## 5. Database and SQL
- PostgreSQL DDL migrations are versioned and reviewed; do not rely on ORM auto-sync in shared environments.
- Use explicit schemas, lower_snake_case identifiers, primary/foreign keys, unique/check constraints, and appropriate indexes.
- Use TIMESTAMPTZ for instants and document timezone assumptions.
- Parameterize values; identifiers must come from allowlists/validated metadata.
- Transactions must be explicit; document isolation/locking requirements for critical workflows.
- Avoid destructive schema/data changes without a reviewed migration and rollback/recovery plan.
- Store source/target identifiers and diagnostics with stable references; JSONB is not a substitute for relational constraints.

## 6. Migration/converter rules
- Parse nested SQL/PLSQL using grammar/parser technology, not regex-only translation.
- Preserve source locations, source hashes, dependency links, and rule-set versions.
- Every rule has fixtures for positive, negative, and edge cases.
- Conversion statuses are AUTO, AUTO_TEST, REVIEW, BLOCKED, ERROR.
- Unsupported or ambiguous semantics must produce stable diagnostics; never silently omit.
- Generated output must be deterministic for identical input, rules, and template versions.
- Regeneration must preserve user-owned extension points.
- Compilation is not proof of semantic parity.

## 7. Security and privacy
- Least privilege for Oracle extraction and PostgreSQL runtime identities.
- Secrets are stored in a secret manager or local untracked environment file; never commit them.
- TLS in transit and encryption at rest for sensitive artifacts.
- Server-side authorization is mandatory; UI hiding is not access control.
- Default deny for unknown authorization mappings.
- Parameterized SQL; validate/allowlist dynamic identifiers.
- Redact credentials, tokens, personal data, and business-sensitive payloads from logs.
- Use synthetic/sanitized fixtures only. Define artifact retention and deletion policy.

## 8. API conventions
- Version public APIs under `/api/v1`.
- Validate request DTOs at ingress and return stable error codes plus correlation IDs.
- Paginate inventory, diagnostics, and execution history.
- Long-running work returns a run/task ID and executes in durable workers.
- Publish OpenAPI and test authorization on every protected route.

## 9. Testing policy
- Unit tests for domain logic, parsers, mapping rules, and transformations.
- Regression fixtures for every converter rule and fixed semantic defect.
- Integration tests for database, task persistence, and retry/idempotency behavior.
- Playwright E2E tests for critical dashboard and generated-app journeys.
- Security tests for authentication, authorization, tenant/project isolation, injection, and secret leakage.
- Critical PL/SQL/business routines require source-vs-target semantic parity tests.
- Tests must be deterministic and must not depend on production systems/data.

## 10. Pull request and release quality gates
A PR should have a clear scope, linked issue/decision, tests, migration impact, security impact, and operational notes. CI must pass format, lint, typecheck, unit/regression tests, and applicable security checks. Breaking schema/API changes require migration/versioning notes. Production promotion requires data reconciliation, UAT, backup restore evidence, monitoring, and rollback rehearsal.
