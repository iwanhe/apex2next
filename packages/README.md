# Shared Packages

Planned and implemented packages:
- `shared-runtime` — framework-neutral runtime contracts, validation, fail-closed authorization, and report planning (R2 foundation).
- `nestjs-adapter` — NestJS authorization guard and page-item validation pipe (R2.2).
- `nextjs-adapter` — reusable server-rendered React form and report components (R2.3).
- `shared-contracts`
- `apex-parser`
- `oracle-analyzer`
- `schema-converter`
- `plsql-converter`
- `apex-ui-converter`
- `api-generator`
- `data-migrator`
- `test-generator`
- `validation-engine`
- `code-generator`

Each package should own a narrow responsibility, public contracts, unit tests, and conversion fixtures. Avoid circular dependencies; shared-runtime is framework-neutral and must not depend on generated application code.
