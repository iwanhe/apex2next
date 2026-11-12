# APEX2NEXT

**Oracle APEX + Oracle Database to Next.js + PostgreSQL Migration Platform**

APEX2NEXT is a migration platform intended to inventory, analyze, convert, migrate, validate, and operationalize applications built with Oracle APEX and Oracle Database into a target stack based on Next.js, NestJS, and PostgreSQL.

> **Important:** Full automation is the engineering goal, not a guarantee that every Oracle/APEX construct can be translated without review. The platform must never silently discard data or behavior. Every source object must receive an explicit disposition, diagnostics, and validation evidence.

## Current status: assistive toolkit

APEX2NEXT is currently used as an **assistive toolkit**, not a one-click converter. Inventory, schema conversion,
dictionary reconciliation, PL/SQL triage, data loading with verification and readiness assessment are automated.
Pages of the common patterns are generated; other pages and all business logic are built by developers and proven
equal to APEX by parity tests. The pilot (app 170134) shows the full method end to end; see the [pilot closure](docs/migration/wp9-pilot-closure-f170134.md).

- **User guide (Bahasa Indonesia):** [docs/panduan/README.md](docs/panduan/README.md): plain-language usage, capability scope and roadmap
- **Shared runtime (R2):** [`packages/runtime-api`](packages/runtime-api/README.md) (NestJS) and [`packages/runtime-web`](packages/runtime-web/README.md) (Next.js), so a converted app only writes its own pages, report definitions and business logic
- **Generators (R3):** `tools/apex2next generate` writes region and LOV SQL (Oracle → PostgreSQL), routes and the pages of the common APEX patterns, with a report of what is left to do by hand; see [R3 application generator](docs/architecture/r3-application-generator.md)
- **Runnable project (R4a):** `tools/apex2next new` creates a Next.js + NestJS application around the generated sources; `tools/apex2next smoke` signs in and exercises it. Tested on the Oracle APEX 26.2 sample applications: see [R4a](docs/migration/r4a-oracle-sample-apps.md)
- **One entry point:** `tools/apex2next` (`doctor`, `queries`, `inventory`, `supporting-objects`, `schema-plan`, `dictionary-check`, `plsql`, `load-data`, `catalog`, `new`, `generate`, `smoke`, `scoreboard`, `assess`)

```bash
tools/apex2next doctor
tools/apex2next inventory path/to/f123 --out work/inventory
tools/apex2next schema-plan path/to/install.sql --apex-export path/to/f123/application --out work/schema
```

## Target architecture

- **Frontend:** Next.js App Router + TypeScript
- **Backend:** NestJS + TypeScript + OpenAPI
- **Target database:** PostgreSQL
- **Parser/conversion workers:** Python (ANTLR-based parsing where appropriate) and TypeScript generators
- **Data migration:** streaming extraction, chunked transfer, PostgreSQL COPY/batched writes, reconciliation
- **Testing:** unit, conversion regression, integration, Playwright E2E
- **Deployment:** Docker Compose for local use; cloud deployment with managed PostgreSQL and container workers

## Repository status

This repository is the foundation for the reusable converter and pilot migration. Detailed scope and design decisions are documented under [docs/](docs/).

- [WP6 Semantic Analysis](docs/architecture/wp6-semantic-analysis.md)
- [WP7 Target Code Generation](docs/architecture/wp7-target-code-generation.md)
- [WP8 Functional Migration — Phase Plan](docs/migration/wp8-functional-migration.md)

## Documentation

- [Architecture Blueprint](docs/architecture/blueprint.md)
- [Functional Requirements Specification](docs/architecture/frs.md)
- [Technical Design](docs/architecture/tdd.md)
- [ERD](docs/data/erd.md)
- [Data Dictionary](docs/data/data-dictionary.md)
- [Migration and Conversion Rules](docs/migration/migration-rules.md)
- [Architecture Decision Records](docs/adr/README.md)
- [Development Setup](docs/development/setup.md)

## Non-negotiable migration principles

1. No silent data loss.
2. No silent functionality loss.
3. No false-positive conversion or validation success.
4. Preserve business semantics, not merely syntax.
5. Make every conversion repeatable, traceable, and reviewable.
6. Keep Oracle as a source system only during migration; PostgreSQL is the sole operational database after cutover.

## Initial implementation sequence

1. Repository foundation and engineering standards.
2. APEX export ingestion and Oracle schema inventory.
3. Normalized source model and dependency graph.
4. PostgreSQL schema conversion and data migration.
5. PL/SQL conversion and compatibility diagnostics.
6. APEX UI conversion and API generation.
7. Functional parity, reconciliation, security, and cutover validation.

## License

License has not yet been selected. Do not assume this repository is open source for redistribution until a license is added.
