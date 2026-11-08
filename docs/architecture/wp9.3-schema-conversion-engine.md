# WP9.3 — Oracle → PostgreSQL Schema Conversion Engine (schema-plan 0.3.0)

## Purpose

Convert an Oracle install script or DBMS_METADATA DDL into a reviewed PostgreSQL schema draft. Every source statement must leave with an explicit disposition and stable findings. The engine never executes source SQL.

It supersedes the WP8.1 `ddl_conversion` subset for application schema work. That module is left unchanged as recorded WP8 baseline evidence.

## Modules (`workers/schema-analyzer/src/apex2next_schema_analyzer/`)

| Module | Responsibility |
|---|---|
| `sql_tokens` | Lossless tokenizer: strings, `q'[..]'`, `N'..'`, quoted identifiers, binds, comments. SQL*Plus script splitter: `;` SQL, `/`-terminated PL/SQL, PROMPT/SET/@ lines. Statement classification. |
| `sql_expression` | Token-level rewrites with a rule registry (`EXP001`–`EXP020`): NVL→COALESCE, SYSDATE/SYSTIMESTAMP, TRUNC(SYSDATE), FROM DUAL, MINUS→EXCEPT, owner prefixes. Detects Oracle-only constructs, PL/SQL calls, unknown functions and unresolved FROM/JOIN objects. |
| `schema_conversion` | Parses CREATE TABLE, ALTER TABLE ADD, CREATE INDEX, COMMENT and CREATE SEQUENCE. Maps datatypes, identity (incl. `ON NULL` and DBMS_METADATA options), virtual columns, defaults, inline and out-of-line constraints and constraint states (ENABLE/DISABLE/NOVALIDATE/DEFERRABLE/USING INDEX). Rule registry `SCH001`–`SCH035`. |
| `view_conversion` | View header/options (FORCE, column list, READ ONLY, CHECK OPTION), body conversion, select-list output columns, per-view target design (`VIW001`–`VIW007`). |
| `trigger_analysis` | Lexical behavior inventory: events, `:NEW` writes classified (audit-clock, audit-principal, normalization, derived-by-call, field-lock, forced-literal), guards and error codes, called members, cross-table reads, ORA-04091 and bypass flags. Never converted (`TRG001`–`TRG005`). |
| `apex_references` | APEX consumer references from parsed export calls: table-backed regions and their item/IG columns, SQL sources (regions, charts, IR, LOVs), and `package.member` calls (processes, authorization plugin attributes). |
| `schema_plan` | Orchestration: constraint attachment, deterministic names, FK resolution and type alignment, index coverage, view topological order and blocking propagation, dependency checks, SQL/post-load emission, expected catalog, load plan, CLI. |
| `schema_report` | Deterministic Markdown review report generated from the plan. |

## Disposition model

`AUTOMATIC` < `ASSISTED` < `MANUAL` < `UNSUPPORTED`. An object's disposition is the worst disposition among its findings. An object that is not emitted is never AUTOMATIC or ASSISTED, with one exception: an index that is covered by an equivalent constraint. Business logic (triggers, PL/SQL) and data DML are always MANUAL in WP9.3.

Structural problems block the owning object: an unknown datatype, an unparsed element, an unsupported identity option, or an out-of-subset generated expression. Non-structural problems omit only that element and record it: an unsupported CHECK, default or index. Every omission appears in three places: the object's `omitted` list, an `-- OMITTED` line next to the CREATE TABLE in the migration, and the "Not emitted" trailer.

## Dependency validation

| Check | Rule |
|---|---|
| DEP-001 | FK targets are defined in the input |
| DEP-002 | FK references an emitted PRIMARY KEY/UNIQUE key on exactly those columns, and that key is not DEFERRABLE (PostgreSQL requirement; found by integration test) |
| DEP-003 | FK column types compatible after alignment (unconstrained NUMBER child → referenced integer type) |
| DEP-004 | View dependencies resolve; topological order; cycles fail |
| DEP-005 | ALTER/INDEX/TRIGGER/COMMENT targets exist |
| DEP-006 | Trigger `:NEW`/`:OLD`/`UPDATE OF` columns exist; no trigger writes a generated column |
| DEP-007 | PL/SQL calls from views/triggers resolve to members declared in the package spec |
| DEP-008 | No PostgreSQL relation-namespace collisions (tables, views, indexes, key indexes, sequences) |
| DEP-009 | Identifiers ≤ 63 bytes; no case-fold collisions |
| DEP-010 | The independent WP8 inventory parser agrees on object counts |
| DEP-011 | Every statement has a disposition |
| DEP-012 | APEX consumer objects, columns and package members resolve (when an export is supplied) |

## Emission contract

- Lower-case identifiers, quoted only when required (reserved words are flagged with SCH028).
- One transaction: `CREATE SCHEMA IF NOT EXISTS`, `SET LOCAL search_path`, sequences, tables (columns, PK, UNIQUE, CHECK), FKs and NOT VALID constraints via `ALTER TABLE`, indexes, views in dependency order, comments.
- A re-apply fails atomically. Version tracking belongs to the migration runner.
- Post-load identity alignment is a separate script. `loadPlan` lists the insertable columns, the excluded generated columns, and the identity override mode.
- `expectedCatalog` uses `format_type()` spelling. The integration tests compare it for equality with `pg_catalog`.

## Limitations

The tokenizer is lexical, not an Oracle SQL grammar. Unfamiliar syntax therefore blocks the object or produces a finding; it is never converted by guesswork. Compound triggers, partitioning, IOTs, domain indexes, temporary tables and `CREATE TABLE AS` are blocked. View output columns are derived lexically and are verified only by the integration tests. Static conversion is not evidence of Oracle installation state. Dictionary reconciliation is required.
