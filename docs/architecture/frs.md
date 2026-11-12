# APEX2NEXT — Functional Requirements Specification

## 1. Scope and actors

The platform migrates one or more Oracle APEX applications and their application-owned Oracle database assets to a PostgreSQL-backed Next.js/NestJS solution.

Actors:
- **Platform Administrator:** manages users, projects, environments, and global conversion rules.
- **Migration Lead:** configures scope, source/target, runs, and release gates.
- **Technical Analyst:** reviews inventory, dependencies, diagnostics, and conversion output.
- **Developer:** repairs generated code and extends target implementation.
- **Data Owner:** approves data mapping and reconciliation.
- **Business Owner/UAT Tester:** validates business journeys and signs off parity.

## 2. Functional modules

### FRS-001 Project management
- Create, update, archive, and list migration projects.
- Store source/target platform versions, scope, owners, environments, and project status.
- Support multiple applications per project.
- Preserve immutable run history and configuration snapshots.

### FRS-002 Source connector and ingestion
- Accept APEX application export files.
- Support read-only Oracle source connections for metadata and data extraction.
- Validate connection, privileges, version, and source reachability.
- Store source credentials only in a secret store; never persist plaintext secrets in project records or logs.
- Calculate file hashes and preserve original export artifacts.

### FRS-003 APEX extractor
Extract and normalize:
- Applications, pages, page groups, regions, items, buttons, branches.
- Computations, validations, processes, dynamic actions, LOVs.
- Navigation menus, breadcrumbs, lists, shared components.
- Authentication schemes, authorization schemes, build options.
- Plug-ins, web services, REST data sources, static files, themes/templates.
- Relevant application settings and session-state behavior.

### FRS-004 Oracle schema analyzer
Inventory tables, columns, constraints, indexes, sequences, views, materialized views, triggers, procedures, functions, packages, types, synonyms, grants, database links, scheduler jobs, partitions, LOBs, and dependencies. Identify unsupported or environment-bound features.

### FRS-005 Dependency and complexity analysis
- Build object-level dependency graph.
- Detect cycles, dynamic SQL, external dependencies, and cross-schema references.
- Calculate complexity/risk indicators with explainable rules.
- Allow analyst annotations and scope exclusions with rationale and approval.

### FRS-006 Schema converter
- Convert supported DDL and data types to PostgreSQL.
- Preserve constraints, indexes, defaults, identity/sequence behavior, and comments where possible.
- Emit deterministic scripts and diagnostics.
- Detect naming collisions, reserved words, precision loss, and semantic differences.

### FRS-007 PL/SQL converter
- Parse source into AST/IR before transformation.
- Convert supported SQL/PLSQL constructs to PL/pgSQL or TypeScript services.
- Preserve exception, transaction, and package-state semantics or emit blocking diagnostics.
- Parameterize dynamic SQL and reject unsafe string-concatenated SQL by default.
- Generate targeted tests for converted routines.

### FRS-008 APEX UI converter
- Map pages to Next.js routes and regions to React components.
- Convert forms, reports, grids, LOVs, validations, branches, dynamic actions, charts, and navigation.
- Map APEX authorization to explicit server-side permissions.
- Record manual review where plugins, custom JavaScript, or session-state dependencies cannot be safely inferred.

### FRS-009 API and code generator
- Generate NestJS controllers, services, DTOs, repositories, OpenAPI definitions, and tests.
- Generate Next.js route/page/component scaffolding.
- Support template/version selection and deterministic regeneration.
- Preserve user-owned extensions outside generated regions.

### FRS-010 Data migration
- Support initial offline migration and initial-plus-delta strategy.
- Provide chunking, checkpoints, retry, resume, throttling, and error quarantine.
- Handle LOB/binary data, character sets, date/time semantics, and sequence synchronization.
- Support a CDC adapter interface; do not label polling as CDC.
- Produce row counts, checksums, aggregate comparisons, and orphan checks.

### FRS-011 Test generation and validation
- Generate schema, routine, API, and UI regression test scaffolding.
- Validate data reconciliation and referential integrity.
- Execute functional journeys and security checks.
- Track evidence and test environment/version.

### FRS-012 Deployment and cutover
- Generate environment templates and deployment manifests.
- Support local and cloud targets.
- Provide cutover checklist, read-only/freeze steps, final delta, validation, DNS/traffic switch, monitoring, and rollback runbook.
- Require explicit business/technical approval before production cutover.

## 3. Core business rules

1. All in-scope source objects must have a disposition.
2. Exclusions require owner, reason, timestamp, and approval.
3. Unknown authorization rules must deny access and block release.
4. A conversion result must include source hash, rule-set version, target artifact reference, diagnostics, and test evidence.
5. A migration task must be idempotent or document why it is not; retries must not duplicate committed data.
6. A successful data task requires reconciliation, not just successful inserts.
7. A successful PL/SQL conversion requires semantic tests for critical routines; compilation alone is insufficient.
8. Cutover is prohibited while critical diagnostics, reconciliation failures, or mandatory UAT tests remain unresolved.

## 4. Non-functional requirements

- **Security:** least privilege, TLS, secret isolation, parameterized SQL, audit logging, secure cookies, server-side authorization.
- **Reliability:** resumable jobs, durable task state, bounded retries, dead-letter/error quarantine.
- **Scalability:** streaming and chunked processing; no requirement to load entire source tables into worker memory.
- **Observability:** structured logs, correlation IDs, metrics, per-object diagnostics.
- **Performance:** initial targets to be baselined using representative workloads; API p95 <500 ms and dashboard initial load <3 s are provisional targets, not universal guarantees.
- **Maintainability:** versioned conversion rules, fixtures, deterministic generators, modular packages.
- **Portability:** local Docker Compose and cloud deployment patterns.

## 5. Acceptance criteria

- Project can ingest an APEX export and register an Oracle source.
- Inventory report covers every scoped object category and identifies extraction gaps.
- Dependency graph and risk report are reproducible.
- Schema/data conversion produces traceable output and reconciliation evidence.
- Unsupported PL/SQL/APEX features are reported, never silently omitted.
- Generated app passes agreed critical CRUD and business workflows.
- Authorization tests prove deny-by-default behavior.
- Backup restore and cutover/rollback rehearsal pass before production approval.

## 6. Out of scope

- Migrating Oracle APEX internal schemas or recreating the APEX runtime.
- Automatic conversion guarantees for arbitrary third-party plugins, proprietary packages, or undocumented external integrations.
- Replacing business-owner decisions about changed workflows or data retention.
