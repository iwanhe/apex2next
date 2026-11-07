# WP8 — Functional Migration and Runtime Integration

**Delivery model:** phased; each phase has an independent acceptance gate.  
**Current implementation:** WP8.1 schema conversion, WP8.2 metadata extraction, WP8.3 offline chunk migration, WP8.4 offline reconciliation, WP8.5 PL/SQL workbench, and WP8.6 generated PostgreSQL runtime baseline.  
**Status:** WP8 remains in progress; offline foundations are not production-qualified.

## Work packages

| ID | Scope | Main deliverables | Acceptance evidence | Status |
|---|---|---|---|---|
| WP8.1 | Oracle schema conversion | DDL parser subset, datatype mapping, PostgreSQL SQL draft, diagnostics | deterministic tests; unsupported constructs blocked/reported | Implemented; CI-verified |
| WP8.2 | Source schema extraction | Read-only dictionary scripts, DBMS_METADATA DDL export, stable manifest | synthetic tests; sanitized Oracle validation pending | Implemented baseline; CI-verified |
| WP8.3 | Data migration engine | Bounded chunks, typed JSONL contract, durable checkpoints, retries | restart/retry/tamper tests; live adapters pending | Implemented offline baseline; CI-verified |
| WP8.4 | Data reconciliation | Counts, PK coverage, aggregates, chunk hashes, LOB, FK validation | deterministic tests; sanitized source/target validation pending | Implemented offline baseline; CI-verified |
| WP8.5 | PL/SQL conversion workbench | Versioned rule registry, lexical analysis, source diagnostics, unchanged candidate source | golden fixtures; no false AUTO classification | Implemented offline baseline; CI-verified |
| WP8.6 | Runtime integration | PostgreSQL pool, generic repository, transaction helper, NestJS database/health services, API readiness, migration runner | disposable PostgreSQL integration tests, idempotent migrations, build/test/typecheck | Implemented generated runtime baseline; CI-verified |
| WP8.7 | APEX functional parity | Paired evidence model, deterministic comparator, Playwright capture contract | synthetic comparator tests; real source/target journeys pending | Implemented offline baseline; CI-verified |
| WP8.8 | Security and cutover | Identity/policy mapping, rehearsal, rollback, cutover checklist | security review, rehearsal evidence, sign-off | Planned |

## WP8.5 — PL/SQL conversion workbench baseline

The plsql_workbench module exposes rule_registry() and analyze_plsql(source, source_name=...). Registry version 2026.11.1 identifies Oracle constructs that need assisted, manual, or unsupported handling. The analyzer masks comments and quoted literals, records source locations and a SHA-256 fingerprint, and inventories selected statement keywords.

Candidate source is returned unchanged. No SQL/PLSQL is executed, no rewrite is emitted, and no rule is marked AUTOMATIC. This is lexical analysis—not a complete grammar, syntax validator, or semantic equivalence checker. A clean report means only that no current lexical rule matched.

Sanitized real PL/SQL corpus validation, grammar-backed parsing, package/global-state analysis, dependency resolution, and target-specific semantic adapters remain future gates.

## Production qualification boundary

WP8.1–WP8.5 are offline foundations; WP8.6 is verified against a disposable PostgreSQL target in CI, not production-certified migration utilities. A representative sanitized DDL/metadata/PLSQL/data corpus and disposable PostgreSQL target are required. Datatype mappings need business-owner review for precision, timezone, character semantics, collation, and Oracle empty-string behavior. Reconciliation PASS does not prove application or business-semantic parity.

## Next step

WP8.7 introduces the APEX-to-target functional parity test harness. Production connectivity still requires separate approval of credentials, network boundaries, least-privilege accounts, and target adapter design.


## WP8.6 — Generated PostgreSQL runtime baseline

The target generator now emits a PostgreSQL runtime foundation:
- pg Pool provider with required DATABASE_URL, bounded DB_POOL_MAX, connection timeout, and application name.
- NestJS global database module, database health service, and graceful pool shutdown.
- /health liveness endpoint and /health/ready database readiness probe.
- Generic repository primitives for find/insert/update/delete. Dynamic values use bind parameters; table and column identifiers are restricted to reviewed lowercase identifiers and writable-column allowlists.
- Explicit transaction helper with BEGIN/COMMIT/ROLLBACK and guaranteed client release.
- API-package migration runner with a PostgreSQL advisory lock, migration ledger, deterministic file order, and one transaction per migration.
- Disposable PostgreSQL integration test for CRUD, malicious-value parameterization, identifier/column rejection, and transaction rollback.
- CI applies migrations twice to verify runner idempotency.

No application-specific business table, entity, repository, process endpoint, or business service is inferred from APEX UI metadata. Those require reviewed WP8.1 schema output, source dependencies, and business semantics. The runtime is a generated baseline, not a production-ready deployment: TLS, secret management, observability, pool sizing, retry policy, load testing, and real-source integration remain qualification tasks.


## WP8.7 — Functional parity harness baseline

The offline parity engine consumes paired source/target observations and produces a deterministic report. It supports FUNCTIONAL, API, DATA, WORKFLOW, SECURITY, and UI checks with EXACT, NUMERIC_TOLERANCE, and UNORDERED_SET comparators. Missing evidence is NOT_VERIFIED; any mismatch is FAIL; only complete supplied evidence with all checks passing produces PASS. The CLI uses distinct exit codes for PASS, FAIL, invalid input, and NOT_VERIFIED.

Playwright is specified as the source/target capture adapter, not falsely reported as already running. Execution is gated on a sanitized source APEX environment, a target pilot, an approved journey catalogue, equivalent test identities, and safe synthetic data. CI validates the deterministic comparator using synthetic evidence only (132 Python tests; all four CI jobs passed). It does not establish real application parity.
