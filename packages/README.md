# Shared Packages

## Available (R2)

| Package | What it is |
|---|---|
| [`runtime-api`](runtime-api/README.md) | Shared NestJS runtime: PostgreSQL access, local accounts, Oracle-style error mapping, access log, report engine, form helpers |
| [`runtime-web`](runtime-web/README.md) | Shared Next.js runtime: session/guard, APEX-style formatting, forms, reports, facets, charts, shell |
| `ir-schema` | IR JSON schema |

Both runtime packages were extracted from the pilot app 170134 without changing behaviour. They are used through the pilot's own pnpm workspace (`examples/f170134-target/pnpm-workspace.yaml`). The root workspace excludes them, so the root install does not need the Next.js/NestJS toolchain.

## Planned

- shared-contracts
- apex-parser
- oracle-analyzer
- schema-converter
- plsql-converter
- apex-ui-converter
- api-generator
- data-migrator
- test-generator
- validation-engine
- code-generator

Each package should own a narrow responsibility, public contracts, unit tests and conversion fixtures. Avoid circular dependencies. `shared-contracts` is the lowest-level contract package.
