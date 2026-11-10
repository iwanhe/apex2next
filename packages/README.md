# Shared Packages

Planned and implemented packages:
- `shared-runtime` — framework-neutral runtime contracts, validation, fail-closed authorization, and report planning (R2 foundation).
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
