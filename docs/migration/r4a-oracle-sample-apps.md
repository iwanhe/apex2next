# R4a — Toolkit breadth test on the Oracle APEX 26.2 sample applications

Status: in progress (started 2026-11-12). Owner decision 2026-11-12: use the official sample applications to test the
toolkit before the first real application (FRITS, R4), and install 1–2 of them in the KCSI workspace on
oracleapex.com for parity tests.

## Why

The pilot (170134) proved the method on one small application. The sample applications are 29 real APEX 26.2
applications written by Oracle, in the same split SQL export format, with their DDL and sample data carried as
supporting objects. They need no owner input and contain no company data, so they show where the toolkit breaks
before a real application does.

They do **not** replace FRITS: they have no real business rules, no real data volume and no owner sign-off.

## Source

| | |
|---|---|
| Repository | `oracle/apex`, branch `26.2`, folder `sample-apps` |
| Commit | `244dd3691fa5c2897a069fc912b149b9c2853679` (2026-10-24) |
| Format used | `sql/<app>.zip` (split SQL export); the APEXlang folders are not used yet |
| Applications | 29; 27 carry supporting objects (`apex-pwa-reference` and `ux-pattern-catalog` do not) |

The exports are kept outside this repository, like every other source export.

## Procedure (per application)

```bash
tools/apex2next inventory          EXPORT/fNNNN --out APP/ui
tools/apex2next supporting-objects EXPORT/fNNNN --out WORK/so          # new in R4a
tools/apex2next schema-plan        WORK/so/install.sql --apex-export EXPORT/fNNNN/application --out APP/db
psql -f APP/db/0001_schema.sql ; psql -f APP/db/0003_deferred_views.sql  # disposable database
tools/apex2next catalog            --database-url URL --out APP/db/target-catalog.json
tools/apex2next generate           APP --init-map ; tools/apex2next generate APP
tools/apex2next scoreboard         APPS/* --out scoreboard.md            # new in R4a
```

## Baseline (2026-11-12, generator as of R3)

Every step ran on all 27 applications without a crash:
- supporting objects decoded in 27 of 27;
- schema plan written in 27 of 27, and the migrations applied on PostgreSQL 16 in 27 of 27 (after the fix below);
- `generate` ran in 27 of 27.

| | Result |
|---|---|
| Tables converted | 167 of 175 (the rest use Oracle-only types: `SDO_GEOMETRY`, `VECTOR`, JSON duality) |
| Pages generated or provided | 65 of 740 (9%) |
| Report regions generated | 92 of 1,135 (8%) |
| LOVs generated or provided | 82 of 125 |

Full table: [r4a/scoreboard-baseline.md](r4a/scoreboard-baseline.md).

The pilot had 79% of its pages generated. The sample applications are feature showcases, so this baseline is
pessimistic for a business application. The order of the gaps is still the useful result:

| Gap | Size in the 27 applications |
|---|---|
| Region type without a generator | 830 regions. The most common are lists (126 pages), display selectors (125), Interactive Grid (61), charts (40), calendars (25) and content rows (49) |
| Page with static content only | 130 pages |
| Classic report or Cards outside a faceted search | 35 and 20 pages with only that region |
| Query not translated safely | 189 regions. Main causes: calls to PL/SQL packages (`EXP009`, `EXP010`), objects outside the plan such as APEX views and collections (`EXP020`), `SELECT *` (`GEN013`), PL/SQL function body returning SQL (`RGN007`) |
| Data and business logic in PL/SQL | sample data packages and audit triggers in almost every application; these remain WP9.4-style service work |

## Defects found and fixed

| Defect | Fix |
|---|---|
| The DDL of an application inside its supporting objects could not be read | New `supporting-objects` command. It decodes the install scripts (string literals, `wwv_flow.LF`, `UNISTR(...)` over concatenations) without executing anything, in install order, with conditions and hashes |
| `COMMENT ON VIEW` was written for a view that is not emitted, so the migration failed (`image-support-rte`) | A comment now goes with the migration that creates its object; none for a view that is not emitted |

## Step 1: page composer (2026-11-12)

The R3 generator only knew whole-page patterns. Most sample pages instead combine a few simple regions, so the
generator now also **composes a page region by region**:

| Region | Rendered as |
|---|---|
| Static content | Text and an allowlist of tags (paragraphs, lists, headings, tables, links). Scripts, frames, images and all attributes are dropped; links go only to generated pages or to `https://` |
| List (shared component) | Linked list with descriptions; a link to a page that is not generated is shown as text |
| Classic report, Interactive Report, Cards | The R3 region sources, now also for regions on a table (`query_type` TABLE) |
| Display selector, breadcrumb | Not rendered (the shell shows the breadcrumb) |
| Region condition "item is null / not null" | Rendered conditionally |
| Button that opens a page | Link, with its condition and authorization scheme |

Rules that keep this safe:
- A region the composer cannot render, or with any other display condition, keeps the **whole page manual**.
- A button that needs server logic is **left out and reported**; the page is then `PARTIAL`.
- A query may bind only **hidden items of its own page** (sent as `item.<NAME>`, as APEX sets them from the URL) and
  `APP_USER` (always the signed-in user). Any other bind keeps the region manual (`GEN016`).
- The generator **never overwrites a hand-written page**. A page can be kept manual with `"manual": true` in
  `ui/app-map.json`; the pilot marks pages 100 and 302 this way.

| | Baseline | After step 1 |
|---|---|---|
| Pages generated or provided | 65 of 740 (9%) | 199 of 740 (27%) |
| Report regions generated | 92 of 1,135 (8%) | 208 of 1,135 (18%) |

Full table: [r4a/scoreboard-composer.md](r4a/scoreboard-composer.md). The pilot is unchanged: tests 63/63,
e2e 12/12, J-01…J-05 PASS.

## Applications chosen for installation and full conversion

| Application | Pages | Why |
|---|---|---|
| Sample Master Detail (7860) | 33 | Forms, master-detail with Interactive Grid, classic reports: the patterns of a request application |
| Forms Patterns (7310) | 11 | Forms, file attachment, editable grid; small enough to convert completely |

Brookstrut (48 pages) was the first proposal but is mostly reports and charts. It stays a candidate for the
performance test because it generates its own data.

Object names do not clash with the pilot (`EBA_DEMO_MD_*`, `SFM_*` against `APX_DEMO_*`).
Installation status: waiting for the browser connection, or for the owner to install them from the App Gallery.
