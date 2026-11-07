# Oracle Schema Analyzer — POC

A conservative static inventory scanner for Oracle DDL text. It identifies common `CREATE` object headers and high-confidence `REFERENCES` dependencies, returning JSON inventory and explicit limitations.

## Input preparation
Export application-owned DDL from Oracle using a privilege-appropriate DBMS_METADATA workflow. Keep the extraction account read-only and exclude Oracle-maintained/internal schemas.

## Run

```bash
PYTHONPATH=workers/schema-analyzer/src \
  python -m apex2next_schema_analyzer schema-export.sql --output build/oracle-inventory.json
```

## Initial inventory categories
Tables, views, materialized views, indexes, sequences, synonyms, procedures, functions, packages/package bodies, types/type bodies, triggers, database links, contexts, jobs, and users.

## Safety and limitations
- Input is treated as text; no DDL is executed.
- This is a first-pass object-header inventory, not a full Oracle SQL/PLSQL grammar.
- Dynamic SQL and dependencies hidden in PL/SQL bodies are not resolved.
- Column-level metadata, constraints, indexes, grants, partitions, scheduler settings, and object source must be extracted and modeled in later increments.
- Review diagnostics and reconcile the inventory against Oracle dictionary views before treating it as complete.


## WP8.1 — Conservative Oracle DDL conversion

Create a PostgreSQL DDL draft and JSON review report from an Oracle DDL text export:

```bash
PYTHONPATH=workers/schema-analyzer/src \
  python -m apex2next_schema_analyzer.ddl_conversion schema-export.sql \
  --target-schema app \
  --output build/schema-conversion.json \
  --sql-output build/postgres-schema.sql
```

Python API:

```python
from apex2next_schema_analyzer import convert_oracle_ddl

result = convert_oracle_ddl(oracle_ddl_text, target_schema="app")
print(result["sql"])
print(result["diagnostics"])
```

The first conversion allowlist covers CREATE TABLE, a conservative set of scalar datatypes, primary keys, unique constraints, and table-level foreign keys when both tables are in the same input. Unknown datatypes block the entire table. Unsupported defaults, CHECK constraints, and external FK targets produce review diagnostics. Oracle identity/generated columns and inline REFERENCES are blocked rather than silently weakened.

The tool is offline and read-only: it treats DDL as text, never connects to Oracle/PostgreSQL, and never executes generated SQL. It does not yet convert indexes, views, sequences, triggers, grants, partitions, virtual columns, PL/SQL, or data. Always reconcile the source inventory with Oracle dictionary metadata and review generated SQL before execution.
