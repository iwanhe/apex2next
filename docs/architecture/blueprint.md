# APEX2NEXT — Application Architecture Blueprint

## 1. Purpose

Build a reusable migration platform and use it to pilot migrations from Oracle APEX + Oracle Database to Next.js + NestJS + PostgreSQL. The platform must inventory source assets, assess complexity, convert supported constructs, migrate data, generate target code, and prove functional/data parity.

The scope covers application-owned schemas and objects, APEX metadata and application assets, application data, PL/SQL, integrations, security rules, and deployment artifacts. Oracle APEX internal platform schemas are out of scope.

## 2. Confirmed architecture decisions

| Concern | Decision |
|---|---|
| Product outcome | Reusable converter and pilot migration |
| Source | Oracle APEX and Oracle Database |
| Target UI | Next.js App Router + TypeScript |
| Target API | NestJS + TypeScript + OpenAPI |
| Target database | PostgreSQL |
| PL/SQL | Migrate all in-scope logic; no Oracle runtime dependency after cutover |
| Automation | Full automation as a target, with explicit diagnostics/review for uncertain constructs |
| Deployment | Local and cloud |
| Data | All in-scope data and database objects |

## 3. Architecture principles

- **Semantic parity over syntactic translation:** preserve behavior, authorization, transaction boundaries, calculations, and data meaning.
- **Traceability:** every target artifact links to source objects, conversion rule versions, and diagnostics.
- **Repeatability:** jobs are idempotent where possible and can resume safely.
- **Fail closed:** unknown authorization behavior and unsupported critical constructs block promotion.
- **No silent loss:** every inventoried source object must be converted, intentionally excluded with rationale, or marked blocked.
- **Separation of concerns:** UI, API/business orchestration, data integrity, and migration control plane remain distinct.
- **Security by default:** least privilege, secret isolation, parameterized SQL, auditability, and secure session handling.

## 4. Logical architecture

### 4.1 Control plane
Next.js migration dashboard for project setup, source registration, inventory, complexity reports, conversion review, run monitoring, reconciliation, approvals, and release readiness.

### 4.2 Execution plane
NestJS orchestration API and workers:
- Python workers: parsing, metadata extraction, static analysis, dependency analysis, and selected conversion tasks.
- TypeScript workers: code generation, target project assembly, API generation, and test scaffolding.
- Data worker: chunked Oracle extraction, transformation, PostgreSQL loading, retries, and reconciliation.
- Validation worker: schema, data, behavior, security, and performance checks.

Long-running workers must not rely on short-lived serverless request lifetimes.

### 4.3 Target runtime
Generated Next.js application, NestJS API, PostgreSQL database, identity provider, background jobs, object storage (when required), observability, and backup/restore.

## 5. Repository topology

```text
apex2next/
├── apps/
│   ├── migration-dashboard/       # Next.js control-plane UI
│   ├── migration-api/             # NestJS orchestration API
│   └── generated-app/             # output workspace/template
├── packages/
│   ├── shared-contracts/
│   ├── apex-parser/
│   ├── oracle-analyzer/
│   ├── schema-converter/
│   ├── plsql-converter/
│   ├── apex-ui-converter/
│   ├── api-generator/
│   ├── data-migrator/
│   ├── test-generator/
│   ├── validation-engine/
│   └── code-generator/
├── workers/
│   ├── extraction-worker/
│   ├── conversion-worker/
│   ├── data-worker/
│   └── validation-worker/
├── templates/{nextjs,nestjs,postgresql,github-actions}/
├── infrastructure/{docker,local,cloud}/
├── examples/sample-apex-app/
├── tests/{fixtures,regression,e2e}/
└── docs/{architecture,data,migration,adr,development,runbooks}/
```

## 6. Migration pipeline

1. Create migration project and define scope.
2. Register Oracle source connection or upload APEX export.
3. Extract APEX metadata, application files, and database inventory.
4. Normalize source metadata into an intermediate representation (IR).
5. Build dependency graph and complexity/risk assessment.
6. Convert database schema and supporting objects.
7. Convert PL/SQL and classify semantic uncertainty.
8. Convert APEX pages, components, processes, validations, navigation, and authorization.
9. Generate NestJS APIs and Next.js UI.
10. Migrate data using snapshot/chunking strategy.
11. Generate and execute regression, reconciliation, security, and E2E tests.
12. Resolve diagnostics and rerun impacted stages.
13. Deploy target, perform cutover rehearsal, and approve production cutover.

## 7. Conversion disposition

Every source object receives exactly one current disposition:
- `AUTO`: deterministic conversion with known semantics.
- `AUTO_TEST`: generated automatically but requires passing targeted parity tests.
- `REVIEW`: human decision or manual adjustment required.
- `BLOCKED`: unsupported or unsafe to convert until resolved.
- `ERROR`: extraction/conversion execution failed.

A conversion run cannot be marked successful while any in-scope object is silently missing or any critical object remains BLOCKED/ERROR.

## 8. Business logic placement

| Logic | Preferred target |
|---|---|
| Presentation and client interaction | Next.js |
| Authorization enforcement and orchestration | NestJS |
| Business services and integration workflows | NestJS |
| Constraints, set-based transformations, data integrity | PostgreSQL |
| Scheduled/background workloads | Worker/job service |
| Audit trail and durable business events | PostgreSQL + application service |

Do not move logic to the browser merely because it was represented by an APEX Dynamic Action.

## 9. Deployment topology

### Local
Docker Compose for PostgreSQL and supporting services; Next.js, NestJS, and workers run in containers or developer processes. Oracle source connectivity remains private and read-only for extraction.

### Cloud
Next.js dashboard may run on Vercel. NestJS and Python workers run on a container platform suitable for durable jobs. PostgreSQL uses a managed service. Artifacts and large exports use private object storage. Secrets are injected at runtime.

## 10. Quality gates

- Inventory completeness: 100% of scoped objects classified.
- Conversion traceability: 100% generated artifacts linked to source/rule metadata.
- Data reconciliation: row counts, key aggregates, constraints, and LOB checks pass.
- Functional parity: agreed critical user journeys pass.
- Security: no critical/high unresolved findings; authorization defaults to deny.
- Operational readiness: backup restore, monitoring, rollback rehearsal, and owner sign-off complete.

## 11. Delivery milestones

1. Foundation and source ingestion.
2. Schema inventory, dependency graph, and deterministic DDL conversion.
3. Repeatable data migration and reconciliation.
4. PL/SQL parser/IR and supported conversion rules.
5. APEX UI/API generation.
6. End-to-end parity, security, performance, and cutover certification.
