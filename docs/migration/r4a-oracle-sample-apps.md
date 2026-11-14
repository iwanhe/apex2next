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

## Step 2: runnable project, native form DML, authorization rules (2026-11-12)

| Addition | What it does |
|---|---|
| `apex2next new APP --oracle-schema S` | Copies `templates/app` (the pilot shell without anything of the pilot) into the application directory: sign-in with local accounts, generic page layer, components, migrations of the accounts schema. The runtime packages are packed into `vendor/` with a content hash in the file name, so the application depends on a fixed copy and not on this checkout. Existing files are never overwritten |
| Native form DML | A form on a table with a native DML process, no PL/SQL process after submit and no unconverted trigger on its table is created, updated and deleted by the runtime (`insertRow`, `updateRow`, `deleteRow` with the lost-update checksum). Otherwise `GEN009` stays and says why |
| Authorization schemes | `security-schemes.generated.ts` proposes a rule per scheme: `return true` -> allow; "is in role or group" -> roles in `iam.account_roles` (granted with `accounts.mjs grant`); "rows returned" with only `:APP_USER` -> translated SQL. Any other scheme denies access until a developer writes its rule in `security.ts` (`GEN010`) |
| Login and home page | The login page items and button come from the export (`LOGIN_PAGE`); the home page is the application's home URL; when it is not generated, a placeholder lists the menu |
| Key default `TO_NUMBER(SYS_GUID(), 'X...X')` | New rule `EXP022`: `guid_number()`, a random 128-bit integer, created by the migration that uses it (8 of the 27 applications) |
| Yes/No, radio group, popup LOV items | Shown as select lists with the same values (`GEN024`, to review); file upload and other item types are reported (`GEN023`) |
| `apex2next smoke APP --database-url URL` | Signs in with a fresh local account, changes the temporary password, opens every generated page and runs one create / edit / delete through a form |

Result on **Forms Patterns** (7310), converted outside the repository with only toolkit commands: the four
tables and their data model migrate automatically, 6 of 11 pages are generated (5 pages need their own work:
the advanced form, the attachment form with its PL/SQL, the content-row report, the editable grid, the file page),
and `apex2next smoke` passes 9 of 9 checks, including a category created, edited and deleted through the generated
form.

Across the 27 applications: 7 of 28 generated forms run on native DML (the rest wait on trigger conversion, the
next step), and 14 of 18 authorization schemes get a rule. Pages: 196 of 740; composed pages that compute their
content before display are now honestly left manual. Table: [r4a/scoreboard-step2.md](r4a/scoreboard-step2.md).

## Step 3: trigger conversion (2026-11-12)

All 60 triggers in the 27 applications are BEFORE ROW insert/update triggers. Most of them stamp audit columns,
fill a key, count a row version or upper-case a code. `schema-plan --convert-triggers` now writes those as
PL/pgSQL trigger functions in the schema migration (module `trigger_conversion`); the switch is off by default, so
an application whose trigger logic was rebuilt by hand (the pilot, WP9.4) keeps its plan unchanged.

| Part | Rule |
|---|---|
| Converted subset | `BEFORE ... FOR EACH ROW [WHEN (...)]`, body `BEGIN ... END` without DECLARE/EXCEPTION, made of `:NEW.col := expr`, `SELECT expr INTO :NEW.col FROM [SYS.]DUAL`, `IF/ELSIF/ELSE`, `NULL`, `RETURN`, `RAISE_APPLICATION_ERROR(-20nnn, msg)`. Expressions go through the registered expression rewrites; any MANUAL finding (package call, Oracle-only function, other bind, package variable) keeps the whole trigger manual (`TRC006` with the reason) |
| APEX user | `V('APP_USER')`, `SYS_CONTEXT('APEX$SESSION','APP_USER')`, `APEX_APPLICATION.G_USER`, `WWV_FLOW.G_USER`, `:APP_USER` -> `apex_app_user()`, which reads `app.username`, set by the runtime per transaction (`TRC002`). Oracle `USER` -> `upper(current_user)` (`TRC003`) |
| Errors | `RAISE_APPLICATION_ERROR` -> `RAISE EXCEPTION` (SQLSTATE P0001, DETAIL `ORA-20nnn`); the runtime shows `ORA-20nnn: message` (`TRC005`; the exact APEX text is to be confirmed in the parity journeys) |
| Data migration | Every generated trigger returns at once while `apex2next.loading` is `on`; `load-data` / the snapshot loader set it, so migrated rows keep their source keys and audit values |
| Native form DML | Only tables with an unconverted trigger block it; converted tables are written by the runtime and the trigger does the rest |

Result: 45 of 60 triggers converted (15 stay manual: package calls such as `DBMS_LOB`, `APEX_MARKDOWN`,
`DBMS_RANDOM`, `TO_CHAR` with Oracle formats, a DECLARE block, sequences of objects that are not emitted). Every
generated migration still applies on PostgreSQL 16 (27/27), and each converted trigger was fired once on a scratch
copy (40 ran; 5 inserts hit CHECK constraints of the synthetic test row, not the trigger). Forms on native DML:
**17 of 28** (was 7).

Found and fixed while running **Sample Master Detail** (7860) end to end:
- `guid_number()` returned a numeric with 16 decimal places (`...178.0000000000000000`); it now returns scale 0,
  so keys look like the Oracle NUMBER keys.
- LOVs ordered by a column they do not show (`order by display_order`) were manual (`RGN011`); with the target
  catalog they are now generated (`orderBy: 'o'`, the order columns carried in the derived table). LOVs 86/125.
- A form page with a select item whose LOV is still manual crashed when opened; it is now left manual (`GEN025`)
  and not linked to. Pages 192/740: the four pages that would have failed are no longer counted.
- `apex2next new` reports a migration copy that differs from the current schema plan instead of silently keeping it.

Sample Master Detail on PostgreSQL: `apex2next smoke` 14/14 (all generated pages open); through the API a project
and a task are created, the project edited and deleted (its tasks cascade), with keys, `CREATED_BY` / `UPDATED_BY`
and upper-cased status codes set by the converted triggers; the STATUS LOV lists in `display_order`.
Forms Patterns stays at smoke 9/9. Table: [r4a/scoreboard-step3.md](r4a/scoreboard-step3.md).

## Applications chosen for installation and full conversion

| Application | Pages | Why |
|---|---|---|
| Sample Master Detail (7860) | 33 | Forms, master-detail with Interactive Grid, classic reports: the patterns of a request application |
| Forms Patterns (7310) | 11 | Forms, file attachment, editable grid; small enough to convert completely |

Brookstrut (48 pages) was the first proposal but is mostly reports and charts. It stays a candidate for the
performance test because it generates its own data.

Object names do not clash with the pilot (`EBA_DEMO_MD_*`, `SFM_*` against `APX_DEMO_*`).
Installed 2026-11-12 from the App Gallery of oracleapex.com, workspace KCSI (schema WKSP_KCSI), with the
supporting objects and sample data (checked read-only in SQL Commands):

| Application | App ID in KCSI | Pages | Sample data |
|---|---|---|---|
| Oracle APEX Forms Patterns | 26200 | 12 | SFM_EXPENSE_CATEGORIES 6, SFM_EXPENSE_REPORTS 7, SFM_EXPENSE_REPORT_LINES 16, SFM_EXPENSE_RECEIPTS 4 |
| Sample Master Detail | 204850 | 34 | EBA_DEMO_MD_PROJECTS 5, _TASKS 45, _MILESTONES 12, _TEAM_MEMBERS 12, _COMMENTS 11, _TASK_TODOS 9, _TASK_LINKS 7, _STATUS 3 |

## Consolidation of draft PRs #2 and #3 (2026-11-12)

The R2 shared-runtime and R3 UI-generator drafts were reviewed against this branch; the pieces it lacked
(trim_spaces handling, safe report paging, hidden-column sort refusal, session issue-time and lifetime checks)
are now in `@apex2next/runtime-api`. Details and what was not ported: [r4a/pr2-pr3-consolidation.md](r4a/pr2-pr3-consolidation.md).


## Step 4a: read-only Interactive Grid (initial safe slice)

The composer now supports a deliberately narrow Interactive Grid pattern:

- The export must explicitly mark the grid non-editable (`is_editable=false` / `N`). Missing editability is treated as editable.
- The source must be a table-backed query (`query_type=TABLE` with a known `query_table`). SQL-backed grids remain manual until a reviewed projection can be proven equivalent.
- Every region column must explicitly declare visibility. Only visible columns with a simple identifier `source_expression` are selected; hidden columns are not sent to the browser. Missing visibility or a computed expression keeps the query manual (`GEN013`).
- The generated read-only grid reuses the runtime paginated report table. It does not generate row editing, row actions, bulk changes, or client-controlled DML.
- Table names must be simple identifiers present in the converted schema plan. IG `query_where` predicates are currently rejected rather than interpolated; add a reviewed predicate translator before supporting them. Missing/unknown visibility, computed expressions, invalid ordering, or a grid with no visible columns now fail closed; the generator never widens these cases to `SELECT *`.

This increment is covered by synthetic regression tests for visible-column projection and fail-closed handling of editable/unspecified grids. It is not yet counted as increased sample-app coverage until the Oracle APEX 26.2 Interactive Grids export fixtures are run through the full scoreboard and parity smoke tests.

## Step 4b: editable Interactive Grid metadata foundation

The page inventory now retains additional source metadata needed for a later, reviewable editable-grid conversion:

- Region-column primary-key, query-only, read-only, required, display, and data-type attributes.
- DML process attributes and the owning region reference when the export supplies one.
- Existing region-level edit operations and lost-update settings remain preserved.

This is **extraction only**. It does not infer missing metadata, grant write permissions, or generate an editable grid. A future generator must reconcile the region's allowed operations with a recognized native IG DML process, a known primary key, column writeability, page/process authorization, row-level authorization, validations, and lost-update behavior. Any missing or unsupported condition must keep the region manual.


## Step 4c: editable Interactive Grid eligibility analysis

A separate, deterministic analyzer now evaluates the editable-grid metadata without enabling DML generation. It reports one of:

- `MANUAL`: export metadata is incomplete or contradictory (source, key, visibility, writeability, operation list, or DML process association).
- `REVIEW_REQUIRED`: the export proves the narrow structural prerequisites, but security and parity gates still require explicit implementation and review.

The analyzer checks table-backed source identifiers, explicit visibility and read-only/query-only flags, one simple primary key, at least one visible writable column, supported operation flags (`i`, `u`, `d`), and exactly one native IG DML process associated with the same region.

It always emits `auto_generate: false`. Even a structurally complete grid remains blocked by three mandatory findings: page/process and row-level authorization; validation and server-side condition parity; and lost-update/concurrency equivalence. This is intentional: source metadata alone cannot prove that a client row may be changed or that APEX's server-side behavior is preserved.

Regression tests cover complete metadata, missing visibility/writeability, unsupported operations, absent key/source/process, and read-only or unspecified editability. Run it after inventory with `tools/apex2next ig-analyze APP/ui/apex-page-inventory.json --out APP/ui/editable-ig-analysis.json`. This analyzer is a planning/reporting foundation only; it does not change the existing read-only grid generator.
