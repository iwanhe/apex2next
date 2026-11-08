# Oracle Schema Analyzer — POC

Static Oracle metadata inventory and conservative PostgreSQL conversion. All tools are offline: they do not connect to Oracle or PostgreSQL and never execute source or generated SQL.

## WP9.3 — schema plan (Oracle install script → PostgreSQL schema draft)

`schema_plan` supersedes the WP8.1 `ddl_conversion` subset for application schemas; WP8.1 is unchanged as baseline evidence. It covers identity (incl. `ON NULL` and DBMS_METADATA options), virtual → stored generated columns, CHECK/PK/UNIQUE/FK (inline, out-of-line, `ALTER TABLE`, states), indexes, sequences, comments and views (dependency ordered). It also produces a trigger/PL/SQL behavior inventory, twelve dependency checks, an expected catalog and a load plan. See [the design](../../docs/architecture/wp9.3-schema-conversion-engine.md).

\`\`\`bash
PYTHONPATH=workers/schema-analyzer/src:workers/extraction-worker/src \
  python -m apex2next_schema_analyzer.schema_plan install.sql --apex-export f170134/application \
  --output build/schema-plan.json --sql-output build/0001_schema.sql --post-load-output build/post-load.sql
python -m apex2next_schema_analyzer.schema_report build/schema-plan.json --output build/report.md
\`\`\`

Exit code 1 means at least one DEP check failed. Generated SQL is a draft for disposable PostgreSQL environments only. Integration tests: `APEX2NEXT_TEST_DATABASE_URL=<disposable db> python -m pytest -m postgres`.

## WP8.5 — PL/SQL conversion workbench

This is a bounded lexical analysis and rule-registry baseline, not a complete PL/SQL parser or transpiler.

Usage:

\`\`\`python
from apex2next_schema_analyzer.plsql_workbench import analyze_plsql, rule_registry
report = analyze_plsql("BEGIN v_total := NVL(v_amount, 0); END;", source_name="orders.sql")
print(report["status"], report["diagnostics"])
print(rule_registry()["version"])
\`\`\`

CLI:

\`\`\`bash
PYTHONPATH=workers/schema-analyzer/src python -m apex2next_schema_analyzer.plsql_workbench procedure.sql --output build/plsql-analysis.json
\`\`\`

Registry version 2026.11.1 assigns recognized constructs an explicit disposition:
- ASSISTED: candidate mapping exists but needs semantic review (NVL to possible COALESCE).
- MANUAL: explicit target design/rewrite required (DECODE, SYSDATE, anchored types, dynamic SQL, exception handling).
- UNSUPPORTED: no safe baseline mapping (CONNECT BY, autonomous transactions, selected DBMS/UTL integrations, pipelined functions).

The report includes source SHA-256, source locations, statement inventory, diagnostics, and unchanged candidateSource. No rewrite is applied; rewriteCount is zero and no rule is AUTOMATIC. Comments and quoted literals are masked before matching. Input is bounded to 1,000,000 characters.

A clean report means only that no current lexical rule matched. It does not prove syntax validity, semantic equivalence, dependency completeness, or migration readiness. Package state, privileges, transaction boundaries, NLS/timezone behavior, triggers, database links, and external integrations need separate analysis.

## Prior WP8 capabilities

WP8.1 converts a conservative CREATE TABLE subset into PostgreSQL DDL drafts. WP8.2 provides read-only Oracle dictionary SQL and offline manifest reconciliation. WP8.3 provides bounded JSONL chunks and a restartable SQLite checkpoint contract; no live PostgreSQL adapter is included. WP8.4 compares normalized source/target evidence offline, including counts, keys, aggregates, FK, LOB and chunk receipts.

WP8.4 CI verification: commit 1ba9c65e7ceed123f56f6780eeec639ef856cd7a; run 42366139624 passed all four jobs; Ruff passed and pytest reported 111 passed. This verifies the offline baseline only, not production qualification.
