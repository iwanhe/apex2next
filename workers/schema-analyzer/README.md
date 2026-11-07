# Oracle Schema Analyzer — POC

Static Oracle metadata inventory and conservative PostgreSQL conversion. All tools are offline: they do not connect to Oracle or PostgreSQL and never execute source or generated SQL.

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
