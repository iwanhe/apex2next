# R2 — Shared Runtime

**Status:** Foundation implemented; adapter integration and APEX parity remain in progress.  
**Branch:** `feat/r2-shared-runtime`

## Objective

Extract the runtime behavior proven in the WP9 pilot into reusable, framework-neutral contracts and helpers so multiple generated applications do not need to reimplement APEX semantics independently.

## Runtime layers

| Layer | Responsibility | Dependency rule |
|---|---|---|
| Runtime contracts | Application/page/item/region/button/report/principal/message/event metadata | No framework or database dependency |
| Policy engine | Authorization and button/page access decisions | Consumes contracts; fail closed |
| Validation engine | Item normalization, required/type/range/length validation | Pure functions; no database access |
| Region engine | Report query validation, pagination, sorting, facets | Produces plans; adapter owns SQL |
| Session adapter | Cookie/session lifecycle and identity-provider integration | NestJS/API boundary |
| Database adapter | Transactions, LOV queries, report execution, lost-update checks | Database-specific |
| UI adapter | Next.js forms, reports, facets, messages and navigation | React/Next boundary |
| Event adapter | Dynamic action event dispatch and supported actions | Explicit allowlist; no expression eval |

## Implemented slices

### R2.1 — Framework-neutral foundation

Package `@apex2next/shared-runtime` currently provides:
- TypeScript contracts for runtime application, page, item, region, button, authorization, principal, report, messages and event actions.
- Pure item normalization/validation with read-only submission rejection.
- Fail-closed authorization evaluation.
- Validated report request planning with sortable-column allowlists and page-size bounds.
- Node test suite for the above behavior.

## Security invariants

1. Missing or unauthenticated principal is denied.
2. Missing authorization policy is denied.
3. A submitted item not declared writable is rejected.
4. User input never becomes SQL identifiers or executable source expressions.
5. Sort columns must come from the report definition allowlist.
6. Dynamic actions are data contracts only; source expressions are never evaluated.
7. Business transactions remain owned by the target application use case layer.

### R2.2 — NestJS adapter

Package `@apex2next/nestjs-adapter` currently provides:
- `RuntimePolicyGuard` with explicit public-route opt-in and fail-closed behavior when policy metadata is absent.
- `RequireRuntimePolicy` and `PublicRuntimeRoute` decorators.
- Resolver port for central policy lookup; consuming applications supply a trusted policy provider.
- `RuntimePageItemsPipe` to normalize/validate form payloads and return structured HTTP 400 validation responses.

### R2.3 — Next.js/React adapter

Package `@apex2next/nextjs-adapter` currently provides:
- Server-component-compatible `RuntimeForm` for text, textarea, number, date, select, radio, checkbox, display, hidden, file and password item types.
- Inline validation messages, required markers, help text and LOV options.
- `RuntimeReportTable` with hidden-column filtering, row rendering and empty state.
- Server rendering tests using React DOM; no client-side state or direct database access.

### R2.4 — LOV, navigation and declarative events

The shared runtime now also provides:
- Static LOV filtering/deduplication and registered-provider resolution with bounded results; callers cannot submit SQL.
- Navigation visibility filtered through authorization policies, stable ordering, and application-relative URL validation.
- Declarative event-action planning with supported event/action allowlists, known-target validation and deterministic sequence ordering. No source JavaScript is evaluated.

### R2.5 — Session, transaction and lost-update contracts

The shared runtime now defines:
- Session claims, max-age/clock-skew policy, and a session-store port for create/read/revoke/revoke-all.
- Session-claim validation after cryptographic verification by the consuming authentication adapter. The shared package does not sign or verify tokens.
- Database-agnostic transaction and transaction-runner ports; the application adapter owns connection lifecycle and commit/rollback.
- Opaque version-token comparison that fails closed for missing or stale values (`LOST_UPDATE`).

## R2 completion plan

| Slice | Scope | Acceptance evidence |
|---|---|---|
| R2.1 | Shared contracts and pure validation/policy/report planning | Package build, strict typecheck, unit tests |
| R2.2 | NestJS adapter integration and common error/message contracts | API integration tests |
| R2.3 | Next.js form/report/facet adapter integration | Browser tests |
| R2.4 | LOV, navigation, dynamic-action allowlist and event dispatch | Unit + E2E tests |
| R2.5 | Generic session, transaction and lost-update adapter contracts | Security + concurrency tests |
| R2.6 | Extract WP9 pilot implementations into shared package without behavior drift | Pilot parity journeys unchanged |
| R2.7 | Multi-app fixture proving reuse independent of f170134 | CI build + parity tests |
| R2.8 | Versioned runtime contract and migration compatibility policy | Documentation + CI compatibility checks |

## Non-goals

- Replacing NestJS, Next.js, or PostgreSQL.
- Executing arbitrary APEX PL/SQL, SQL, JavaScript, or condition expressions.
- Claiming universal APEX feature parity before per-feature evidence exists.
- Moving application-specific business rules into the shared runtime.
