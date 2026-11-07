# WP7 — Target Code Generation

**Status:** Initial generator implementation | **Generator:** 0.1.0

## Purpose

WP7 consumes schema-valid Normalized IR plus WP5 dependency analysis and WP6 semantic plans. It creates a deterministic target workspace containing a Next.js App Router application, NestJS API scaffold, PostgreSQL migration baseline, and auditable conversion reports.

## Public API and CLI

```python
from apex2next_extractor import generate_project
result = generate_project(ir_document, "build/generated-target")
```

```bash
PYTHONPATH=workers/extraction-worker/src python -m apex2next_extractor.generator_cli \
  build/application-ir.json --output build/generated-target
```

The output directory must be empty or absent. The explicit `overwrite=True` / `--overwrite` option allows writing into a non-empty directory; use it only when the directory is dedicated to generated output.

## Generated workspace

| Path | Responsibility |
|---|---|
| apps/web | Next.js 15 App Router + React 19 + TypeScript |
| apps/web/app/page.tsx | Application landing page and extracted page links |
| apps/web/app/pages/* | Stable page routes keyed by source object identity |
| apps/api | NestJS 11 API application |
| apps/api/src/health.controller.ts | Health endpoint scaffold |
| db/migrations/0001_baseline.sql | PostgreSQL app schema and migration ledger |
| migration-report/source-ir.json | Full input IR snapshot |
| migration-report/semantic-analysis.json | WP6 classifications and transformation plans |
| migration-report/dependency-graph.json | WP5 dependency order and cycles |
| migration-report/manual-review.md | Manual/unsupported objects and diagnostics |
| migration-report/summary.json | Compact counts and generated-scope statement |
| generation-manifest.json | SHA-256 for each generated artifact |

## Generation rules and safety

- Validate the source document against the shared IR JSON Schema before writing any files.
- Derive stable URL segments from page names plus a hash of canonical object identity; sanitize route segments and HTML text.
- Never execute source expressions or copy raw SQL/PLSQL into executable target files.
- Keep source IR and semantic reports in the generated output for traceability.
- Never infer PostgreSQL business tables from page items, regions, or display columns.
- Generate only a baseline schema/migration ledger until a validated database schema inventory is available.
- Generate structural page shells, not functional clones of APEX pages.
- Include dependency graph and WP6 diagnostics; do not silently drop MANUAL or UNSUPPORTED objects.
- Refuse non-empty output by default to avoid overwriting user work.
- Use stable ordering, stable route IDs, and a content-hash manifest for reproducibility.

## Acceptance tests

The Python suite verifies schema rejection, expected workspace files, route generation, source-expression non-execution, manual-review preservation, deterministic file contents, manifest hashes, and safe refusal to overwrite. CI also generates a project from the committed synthetic APEXLang fixture and runs target workspace install/build/test/typecheck.

## Current limits

This WP7 baseline is not a full converter. It does not yet emit business DTOs, repository methods, database entities, REST endpoints for APEX processes, login/authorization flows, interactive grids/reports, dynamic action behavior, PL/SQL rewrites, data migration pipelines, or end-to-end parity tests. Those require additional semantic rules and source artifacts. A sanitized real APEX application plus database DDL/data dictionary is required before production qualification.
