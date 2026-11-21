# R4a Interactive Grid — row-security qualification gate

Status: **design/test gate; implementation not yet qualified**.

## Source evidence from F170134 pilot

- The generated report runtime authorizes the application and page scheme, but it does not automatically enforce per-row ownership/department visibility.
- The pilot's authorization schemes are role based: `APP_USERS`, `REQUESTER`, `WAREHOUSE`, `MASTER_DATA`, and `ADMIN_RIGHTS`. The `REQUESTER` scheme allows REQUESTER and MANAGER roles.
- Request headers carry `department_id` and `created_by`; request lines reference their parent through `request_id`.
- The source service locks a request parent and enforces DRAFT/REJECTED line mutation rules. This is business-state protection, not a proof of read isolation.
- No evidence found in the inspected pilot service code establishes a per-user or per-department row visibility rule for the request master list. Do not invent one during conversion.

## Required boundary

1. Authentication/application/page authorization must be evaluated on the server for every read and mutation.
2. A browser-supplied request ID, department ID, tenant ID, ownership value, or parent key is a filter—not authorization evidence.
3. Detail/child reads must verify access to the parent before returning children, and the child query must include a server-derived parent predicate.
4. List/report SELECTs need an explicit, reviewed row-access policy; role-only authorization must not be represented as row-level isolation.
5. If the source app's intended visibility semantics are unknown, preserve the report only for an explicitly authorized broad audience or block generation and emit a diagnostic requiring owner review. Never guess.
6. Grid DML policy does not qualify SELECT/read isolation. The existing DML scope primitive is not a substitute for a scoped report/query runtime.

## Parent-child acceptance tests (request header → request lines)

| Scenario | Expected |
|---|---|
| Authenticated user has page access; parent is authorized | Header and its lines returned |
| User can access page but parent access policy denies selected parent | Not-found/denied response; no header or child data |
| Client substitutes another parent ID | Denied; no cross-parent rows |
| Child endpoint receives a parent ID with no server-side authorization evidence | Fail closed |
| Child query is executed with verified parent scope | SQL predicate limits rows to that parent |
| Parent is deleted / does not exist | No child data; consistent not-found |
| Role is insufficient | Denied before data is returned |
| Policy is missing/ambiguous in source metadata | Diagnostic/blocker; do not generate permissive fallback |

## Follow-up implementation slices

- **R4a-S1:** establish source owner decision for REQUESTER/MANAGER/WAREHOUSE visibility (user, department, all requests, or role-based broad visibility).
- **R4a-S2:** add a policy contract for SELECT reports separate from DML; server resolver receives trusted principal and verified parent context only.
- **R4a-S3:** implement scoped request-line/detail reads and cross-parent regression tests in PostgreSQL integration.
- **R4a-S4:** extend generator diagnostics and scorecard so unresolved row-access semantics cannot be counted as safely converted.
- **R4a-S5:** test read visibility with multiple principals and seeded departments/requests; verify no cross-scope leakage through list, detail, export, pagination, or aggregate paths.

## Exit criteria

This gate is not complete until policy semantics are backed by source evidence or an owner decision, tests demonstrate denial of cross-scope reads, and CI runs against the implementation. Documentation-only completion must not be presented as security implementation or production readiness.
