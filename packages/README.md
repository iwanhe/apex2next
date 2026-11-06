# Shared Packages

Planned packages:
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

Each package should own a narrow responsibility, public contracts, unit tests, and conversion fixtures. Avoid circular dependencies; shared-contracts is the lowest-level contract package.
