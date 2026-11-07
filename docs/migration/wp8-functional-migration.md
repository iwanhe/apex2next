# WP8 — Functional Migration and Runtime Integration

**Delivery model:** phased; each phase has an independent acceptance gate.  
**Current implementation:** WP8.1 schema conversion, WP8.2 metadata extraction, WP8.3 offline chunk migration, WP8.4 offline reconciliation, and WP8.5 offline PL/SQL workbench baseline.  
**Status:** WP8 remains in progress; offline foundations are not production-qualified.

## Work packages

| ID | Scope | Main deliverables | Acceptance evidence | Status |
|---|---|---|---|---|
| WP8.1 | Oracle schema conversion | DDL parser subset, datatype mapping, PostgreSQL SQL draft, diagnostics | deterministic tests; unsupported constructs blocked/reported | Implemented; CI-verified |
| WP8.2 | Source schema extraction | Read-only dictionary scripts, DBMS_METADATA DDL export, stable manifest | synthetic tests; sanitized Oracle validation pending | Implemented baseline; CI-verified |
| WP8.3 | Data migration engine | Bounded chunks, typed JSONL contract, durable checkpoints, retries | restart/retry/tamper tests; live adapters pending | Implemented offline baseline; CI-verified |
| WP8.4 | Data reconciliation | Counts, PK coverage, aggregates, chunk hashes, LOB, FK validation | deterministic tests; sanitized source/target validation pending | Implemented offline baseline; CI-verified |
| WP8.5 | PL/SQL conversion workbench | Versioned rule registry, lexical analysis, source diagnostics, unchanged candidate source | golden fixtures; no false AUTO classification | Implemented offline baseline; CI pending |
| WP8.6 | Runtime integration | Generated repositories/services/API contracts and DB integration tests | disposable PostgreSQL integration tests | Planned |
| WP8.7 | APEX functional parity | Source-to-target test model, Playwright journeys, server assertions | representative sanitized APEX and target journeys | Planned |
| WP8.8 | Security and cutover | Identity/policy mapping, rehearsal, rollback, cutover checklist | security review, rehearsal evidence, sign-off | Planned |

## WP8.5 — PL/SQL conversion workbench baseline

The plsql_workbench module exposes rule_registry() and analyze_plsql(source, source_name=...). Registry version 2026.11.1 identifies Oracle constructs that need assisted, manual, or unsupported handling. The analyzer masks comments and quoted literals, records source locations and a SHA-256 fingerprint, and inventories selected statement keywords.

Candidate source is returned unchanged. No SQL/PLSQL is executed, no rewrite is emitted, and no rule is marked AUTOMATIC. This is lexical analysis—not a complete grammar, syntax validator, or semantic equivalence checker. A clean report means only that no current lexical rule matched.

Sanitized real PL/SQL corpus validation, grammar-backed parsing, package/global-state analysis, dependency resolution, and target-specific semantic adapters remain future gates.

## Production qualification boundary

WP8.1–WP8.5 are offline foundations, not production-certified migration utilities. A representative sanitized DDL/metadata/PLSQL/data corpus and disposable PostgreSQL target are required. Datatype mappings need business-owner review for precision, timezone, character semantics, collation, and Oracle empty-string behavior. Reconciliation PASS does not prove application or business-semantic parity.

## Next step

WP8.6 introduces runtime repositories, services, API contracts, and PostgreSQL integration tests. Production connectivity requires separate approval of credentials, network boundaries, least-privilege accounts, and target adapter design.
