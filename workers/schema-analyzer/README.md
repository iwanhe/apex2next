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
