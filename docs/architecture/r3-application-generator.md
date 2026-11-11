# R3 — Application generator

Status: done on 2026-11-11. Acceptance: the pilot application 170134 is regenerated and passes the same tests
(API 63/63, runtime-web 3/3, e2e 12/12, parity journeys J-01…J-05 with 0 state differences and 0 message mismatches).

The generator removes the largest block of hand typing that the pilot needed: region and LOV queries, routes and the
pages of the common APEX patterns. It does **not** convert business logic. What it cannot do safely is listed as a
TODO with the reason; nothing is guessed.

## Commands

| Command | Result |
|---|---|
| `tools/apex2next catalog --database-url URL --out APP/db/target-catalog.json` | Column types of the migrated PostgreSQL schema |
| `tools/apex2next generate APP --init-map` | Proposed `ui/app-map.json` (routes, region keys, form names) for review |
| `tools/apex2next generate APP` | Generated sources and `ui/generation-report.json` / `.md` |
| `tools/apex2next generate APP --check` | Exit 1 when a generated file is stale or orphaned; writes nothing |
| `tools/apex2next queries --out DIR --plan PLAN` | Data snapshot query for SQL Workshop, written from the schema plan |

## Inputs and outputs

| Input (in the application directory) | Origin |
|---|---|
| `ui/apex-page-inventory.json` | `apex2next inventory` (APEX SQL export) |
| `db/schema-plan.json` | `apex2next schema-plan` (known objects, column types, function mappings) |
| `db/target-catalog.json` | `apex2next catalog`; optional, needed for column types of classic report and Cards regions |
| `ui/app-map.json` | **Reviewed by a person.** Names the export does not decide |

| Output | Content |
|---|---|
| `apps/api/src/pages/app-sources.generated.ts` | `REGION_SOURCES`, `LOV_SOURCES`, `FORM_SOURCES` |
| `apps/web/lib/app-routes.generated.ts` | `PAGE_ROUTES`, `IR_DOWNLOADS` |
| `apps/web/app/(app)/**/page.tsx` | One page per supported pattern; form pages get `[param]` (edit) and `new` (create) |
| `ui/generation-report.json`, `.md` | Per page, region and LOV: generated, provided, or manual with the reason |

Output is deterministic. Generated pages start with a `GENERATED` comment; a generated page that the generator no
longer produces is removed, a hand-written page is never touched.

## Page patterns

| Pattern | Recognized by | Generated page |
|---|---|---|
| `IR_PAGE` | Normal page, exactly one Interactive Report region, no items | `IrPage`: search, sort, paging, download, detail link, CREATE |
| `FACETED_REPORT` | Faceted Search region and one classic report | `FacetedPage` kind `CLASSIC`: facets, search, column links, CREATE |
| `FACETED_CARDS` | Faceted Search region and one Cards region | `FacetedPage` kind `CARDS`: facets, search, card link, "Load more" |
| `FORM_DIALOG` | One form region with one primary key item | `FormDialog`: edit page, and create page when the form allows insert |
| `LOGIN` | Alias `LOGIN` or username and password items | Not generated: sign-in is part of the application shell |
| `MANUAL` | Anything else | Not generated; listed as `GEN001` with the region types found |

Derivations worth knowing:

- **Links** are read from `f?p=` targets. A link is generated only when it goes to a generated form page and passes
  its primary key. Other links are reported (`GEN005`).
- **Create mode values**: items that another page passes when it opens a form without the primary key are forwarded
  as query parameters (pilot: `request_id` from page 302 to page 311).
- **Extra items**: visible items without a database source (`ALWAYS_NULL`) are posted with the form (pilot: `P191_NOTE`).
- **Facets** come from items with `source_type = FACET_COLUMN`, in item sequence.
- **Cards**: a column that only feeds a link and is not shown is hidden from row search.
- **Rows per page**: 50 for an Interactive Report (APEX default, assumption A-01 confirmed in J-04), the region's
  `query_num_rows` for a classic report, 50 per batch for Cards.

## Region and LOV SQL translation

Module `apex2next_schema_analyzer.region_sql`, built on the WP9.3 token-level expression converter. Only registered
rewrites are applied. Each rewrite is a finding with a disposition.

| Rule | Disposition | Rewrite |
|---|---|---|
| RGN001 | AUTOMATIC | `:BIND` becomes `$n`; the server supplies the value |
| RGN002 | ASSISTED | `TO_NUMBER(:BIND)` becomes `$n`; the type comes from the compared column |
| RGN003 | AUTOMATIC | `V('ITEM')`, `NV('ITEM')` become `$n` |
| RGN004 | ASSISTED | `NVL2` becomes `CASE WHEN … IS NOT NULL` |
| RGN005 | ASSISTED | `DECODE` becomes `CASE` with `IS NOT DISTINCT FROM` (NULL equals NULL, as in DECODE) |
| RGN006 | AUTOMATIC | Objects after FROM/JOIN get the target schema |
| RGN007–RGN013 | MANUAL | Not a single SELECT, untokenizable text, LOV shape problems, `&ITEM.` in a string literal |

`EXP` rules of the schema plan still apply (`NVL`, `SYSDATE`, `FROM DUAL`, outer join `(+)`, hierarchical queries,
unknown functions and so on). A query with any MANUAL or UNSUPPORTED finding is reported and **not emitted**, so an
unsafe translation never runs.

Two shapes are emitted:

- a **plain column list on one object** keeps the reviewed structure `view` + `select` + `where`;
- **any other query** is emitted as translated SQL and runs as a derived table.

A LOV keeps its translated query without `ORDER BY`. The runtime orders by the display or return column with binary
collation, as `NLS_SORT=BINARY` does. LOVs with bind variables (cascading LOVs) are reported as manual.

While building this, one defect of the WP9.3 converter was fixed: `EXTRACT(… FROM col)`, `TRIM(… FROM col)` and
`IS DISTINCT FROM` no longer report the column as an unresolved table (`EXP020`).

## Snapshot query

`apex2next_schema_analyzer.snapshot_query` writes the read-only SQL Workshop snapshot of WP9.6 from the schema plan:
session facts, row counts, identity state, every table row and every view row. Row keys come from the primary key.
A view uses its first column unless `viewKeys` in the reviewed config names another key. For the pilot the generated
query has the same 38 branches and the same session block as the hand-written query that produced S0…S4.

## Generator finding codes

| Code | Disposition | Meaning |
|---|---|---|
| GEN001 | MANUAL | Page matches no supported pattern |
| GEN002 | MANUAL | Region type has no generator (charts, metric cards, …) |
| GEN003 | MANUAL | Region or LOV query could not be translated safely |
| GEN004 | ASSISTED | No catalog entry: columns of a classic report or Cards region are treated as text |
| GEN005 | MANUAL | Link target is not a generated form page |
| GEN006–GEN009 | MANUAL | PL/SQL process, validation, server-side condition, form DML to wire to a service |
| GEN010 | MANUAL | Authorization scheme to implement |
| GEN011, GEN012 | ASSISTED | Dynamic action to review; static content region not rendered |
| GEN013, GEN014 | MANUAL | `SELECT *`; Interactive Report column without a definition in the export |

## Result on the pilot (170134)

| | Generated | Provided | Manual |
|---|---|---|---|
| Pages (19, one is the global page) | 15 | 1 (login) | 2 (dashboard 100, master-detail 302) |
| Report regions | 11 | – | 3 (two charts, one metric card region) |
| LOVs | 5 dynamic | 3 static (read from the UI spec) | 0 |

Open items in the report: 32 manual (business logic, conditions, authorization, the two pages) and 19 to review.

## What is still by hand

- The project skeleton (workspace, `app.module`, shell, login, component wrappers) is copied from the example.
  A `convert` command that creates it is roadmap R5.
- Page services and controllers: form DML, PL/SQL processes, validations, conditions.
- Authorization schemes.
- Pages outside the four patterns, Interactive Grid, charts, uploads, PDF, e-mail, REST sources, jobs.

## Tests

- `tests/test_r3_region_sql.py`: translator rules and refusals.
- `tests/test_r3_app_generator.py`: the pilot's generated files are current, summary and shapes, synthetic
  applications (join query, untranslatable query, missing catalog, cascading LOV, stale and orphan files), snapshot
  query equals the proven query.
- `tests/test_toolkit_cli.py`: new-application flow from export and DDL to generated sources.
- `examples/f170134-target/apps/api/test/migrations.integration.test.js`: `target-catalog.json` equals the migrated
  schema.
