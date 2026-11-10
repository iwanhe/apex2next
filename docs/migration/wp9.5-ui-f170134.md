# WP9.5 — Pages & Features: Demo Permintaan Barang (170134)

**Status:** Implemented on branch `feat/foundation-and-architecture-docs`. All 19 pages of the APEX SQL export (page 0 and pages 100–9999) are mapped to Next.js routes and NestJS endpoints. The work is verified on PostgreSQL 16 with API integration tests and Chromium end-to-end journeys. WP9.6 compared five journeys with the running APEX application (identical data, messages and reports, see [WP9.6](wp9.6-data-parity-f170134.md)); A-01…A-03 are confirmed there. The deviation DEV-06, the UI differences D-UI-01…04 and the gaps G-01…G-03 need owner review.

## 1. Source of truth (D-003)

The two received exports disagree. The **SQL export** is authoritative for WP9.5 because it matches the installed database (WP9.3b), and the APEXLang archive is a stale snapshot:

| Difference | APEXLang | SQL export |
|---|---|---|
| Page 302 "Detail Permintaan" (master-detail) | missing | present, with a navigation entry and a breadcrumb |
| Page 210 Items | IR | faceted search + Cards |
| Page 300 Permintaan Barang | IR | faceted search + classic report |
| Page 100 KPI region | `kpi_1..3` columns | `seq, icon, label, metric_value` (matches the redefined view, WP9.3b D-001) |
| Items present only in the SQL export | — | P210_ACTIVE_YN, P210_CATEGORY, P210_SEARCH, P300_DEPARTMENT_ID_DSP, P300_SEARCH, P300_STATUS, P302_REQUEST_ID |

This resolves the page 00302 question from WP9.1/9.2: the page is implemented from the SQL export.

## 2. Page inventory and coverage

`apex2next_extractor.page_inventory` builds a deterministic inventory from the unpacked SQL export (`examples/f170134-target/ui/apex-page-inventory.json`, format `apex2next.apex-page-inventory.v1`). The inventory contains 19 pages and 269 components with stable keys `P<page>:<KIND>:<name>` (regions, report regions, items, buttons, processes, validations, dynamic actions with their actions, IR/report/region columns, cards, charts), plus authorization schemes (page and component level, `p_security_scheme`), LOVs (including static values), the navigation menu and bar, breadcrumbs and application formats. Only derived metadata is committed; the export itself is not (chain-of-custody policy).

```bash
PYTHONPATH=workers/extraction-worker/src python -m apex2next_extractor.page_inventory \
  /path/to/f170134 --output examples/f170134-target/ui/apex-page-inventory.json
cd examples/f170134-target && node scripts/generate-ui-spec.mjs   # typed UI spec for api + web
```

`ui/coverage.json` maps **every** component key once: 227 IMPLEMENTED, 41 ADAPTED (each with a note), 1 NOT_APPLICABLE (login "Clear Page(s) Cache"), 0 unmapped. A test fails if a key is missing or extra, if the inventory hash changed without review, or if a referenced file does not exist.

Labels, prompts, required flags, LOV null texts, inline help, button labels, confirm texts, success and error messages, column headings, format masks, sort orders and rows-per-page values come from the generated spec (`ui-spec.generated.ts`), not from retyped strings. Region and LOV SQL are allowlisted constants in the API; a drift test proves that they equal the region source in the inventory.

| APEX page | Mode / scheme | Target route | API |
|---|---|---|---|
| 9999 Login | public | `/login` | `POST /auth/login` |
| 100 Home | APP_USERS | `/` | `GET /pages/100` |
| 190 Approval Inbox | APP_USERS | `/approvals` | `GET /regions/approvalInbox` |
| 191 Approval | modal, APP_USERS | `/approvals/[id]` | `GET /forms/approval/:id`, `POST …/approve`, `POST …/reject` |
| 200 Departments | APP_USERS | `/departments` | `GET /regions/departments` |
| 201 Department | modal, MASTER_DATA | `/departments/new`, `/departments/[id]` | `GET/POST/PUT/DELETE /forms/department` |
| 210 Items | APP_USERS | `/items` | `GET /regions/items` (cards + facets) |
| 211 Item | modal, MASTER_DATA | `/items/new`, `/items/[id]` | `…/forms/item` |
| 300 Permintaan Barang | APP_USERS | `/requests` | `GET /regions/requests` (classic + facets) |
| 301 Permintaan Barang | modal, REQUESTER | `/requests/new`, `/requests/[id]` | `…/forms/request`, `POST /forms/request/:id/submit` |
| 302 Detail Permintaan | APP_USERS | `/requests/detail?id=` | `GET /pages/302` |
| 310 Baris Permintaan | APP_USERS | `/request-lines` | `GET /regions/requestLines` |
| 311 Baris Permintaan | modal, REQUESTER | `/request-lines/new`, `/request-lines/[id]` | `…/forms/requestLine` |
| 400 Rekap Permintaan | APP_USERS | `/reports/requests` | `GET /regions/requestSummary` |
| 500 Users & Roles | ADMIN_RIGHTS | `/admin/users` | `GET /regions/userRoles` |
| 501 User Role | modal, ADMIN_RIGHTS | `/admin/users/new`, `/admin/users/[id]` | `…/forms/userRole` |
| 510 Document Types & Approval | ADMIN_RIGHTS | `/admin/document-types` | `GET /regions/docTypes` |
| 511 Document Type | modal, ADMIN_RIGHTS, update only | `/admin/document-types/[docType]` | `GET/PUT /forms/docType/:id` |
| 0 Global Page | — | — (no components) | — |

## 3. Architecture (ADR-0003)

- **Next.js 15 (App Router, React 19, no UI library)** renders pages on the server. The browser never calls the API. Server components and server actions call it with the session token from an httpOnly cookie.
- **NestJS page layer** (`apps/api/src/pages`): one method per APEX page action, one transaction per page submit (APEX commits once per submit). It authorizes the application scheme and then the page scheme from the export, evaluates the button and read-only conditions, runs the item and page validations, checks lost updates, and calls the WP9.4 business services.
- **PostgreSQL** keeps the views, `app.can_act_yn` and the principal setting `app.username` from WP9.3/9.4.

### Authentication (replaces "Oracle APEX Accounts")

The production identity provider is decided in WP9-009. Until then only `AUTH_MODE=dev` exists, and it fails closed:

- The API refuses to start when `AUTH_MODE` is unset, when it runs with `NODE_ENV=production`, when `SESSION_SECRET` has fewer than 32 characters, or when `DEV_LOGIN_PASSWORD` has fewer than 12.
- Any username signs in with the shared dev password, as a workspace account would. `APP_USER` is the upper-cased username, and the APEX schemes then decide access. A user without roles is refused by APP_USERS with the source message.
- The session is an HMAC-SHA256 signed token (8 h, like the APEX session maximum). It is stored in an httpOnly SameSite=Lax cookie (Secure in production). Every API route requires it unless it is marked public (`/auth/login`, `/health`).
- A failed login shows the APEX message `Invalid Login Credentials`. Sign Out is a POST that clears the cookie.

### Behavior kept from APEX

| Area | Behavior |
|---|---|
| Authorization | APP_USERS for every page, then the page scheme. The navigation entries "Administration" etc. are filtered by their scheme. Messages are verbatim. |
| Item validations | Value required (`#LABEL# must have some value.`), number (`#LABEL# must be a number greater than or equal to 0.` for the `min_value 0` items, otherwise `#LABEL# must be Numeric.`) and date (`#LABEL# does not match format DD-MON-YYYY.`) are reported together, inline per item, with the "n errors have occurred" notification. Read-only items are not validated. |
| Page validation | `NEED_DATE_AFTER_REQUEST_DATE` on SAVE/CREATE/SUBMIT, using the database value of read-only items. |
| Text items | `trim_spaces=BOTH`. An empty value is NULL. |
| Read-only items | P301 DEPARTMENT_ID/NEED_DATE/PURPOSE (not DRAFT/REJECTED) and STATUS (not APPROVED/FULFILLED/CLOSED) are not submitted and keep their database value. REQUEST_NO and LINE_AMOUNT are query-only. |
| Buttons | Conditions are evaluated by the API (P301 by status, P191 by `can_act_yn`, P302 CREATE_REQUEST_LINES by an EXISTS on DRAFT/REJECTED, forms by PK). Labels, hot flags, positions and confirm texts come from the export. The delete confirm uses the APEX default text because the app defines no `DELETE_MSG`. |
| Page 301 SUBMIT | SAVE_REQUESTS (UPDATE) and then CALL_SUBMIT_REQUESTS run in **one** transaction. Success message: "Dokumen diajukan untuk approval." |
| Page 191 | `P191_NOTE` is trimmed. REJECT requires a note (-20108), and the SoD/role checks keep their order. Success messages: "Dokumen disetujui." / "Dokumen ditolak." |
| Lost update (`VALUES`) | A checksum over the loaded form values; a mismatch on UPDATE/DELETE gives the APEX message "Current version of data in database has changed since user initiated update process." |
| DB constraint errors | 23505/23503/23514/23502 map to ORA-00001/02291/02292/02290/01400 texts with the (identical) constraint name. |
| Reports | IR row search (case-insensitive, dates as DD-MON-YYYY), single-column sort, binary collation (`COLLATE "C"`, NLS_SORT=BINARY), Oracle null ordering, "x - y of z" pagination, detail-link column, CSV/HTML download of all filtered rows with labels and formatted values. Classic reports use their static ORDER BY and 15 rows. |
| Faceted search | Search + checkbox facets: OR within a facet, AND across facets. Counts are computed with the other facets applied, zero counts are hidden, values are ordered by count, and "Show more" appears after 7. |
| LOVs | The 5 dynamic LOVs run as allowlisted SQL ordered with binary collation. The 3 static LOVs come from the export. `display_extra=YES`, so stored values outside the LOV are shown as in APEX and are not rejected. |
| Formats | Application date format DD-MON-YYYY. Number masks `999G999G999G999G990` and `999G999G999G990D99` (NLS AMERICAN: `,` group, `.` decimal). |
| Charts / metric cards | Page 100 pie "Permintaan per Status", bar "Nilai per Department", and metric cards from `apx_demo_dash_kpi_v` ordered by SEQ. |

## 4. Deviation, UI differences, assumptions, gaps (need review)

**DEV-06 — button conditions are enforced on submit.** APEX renders a button only when its condition is true, but a crafted request can still run the page processes. The target refuses such actions with `ACTION_NOT_AVAILABLE` (409). For example, DELETE on a request that is not DRAFT is refused. Together with the query-only REQUEST_NO, this narrows findings **F-02** (request_no cannot be changed through the UI) and **F-03** (the UI deletes only DRAFT requests). The API-level behavior of WP9.4 is unchanged.

| ID | Difference |
|---|---|
| D-UI-01 | Modal pages are routed dialogs over the application shell. Closing a dialog redirects to the parent page, which re-renders all regions (APEX refreshes one region through a dynamic action), and the success message is shown there. |
| D-UI-02 | Date pickers are native browser date inputs, so the browser locale controls the display format. Reports and display items use DD-MON-YYYY. |
| D-UI-03 | Charts are static SVG, not Oracle JET (no zoom, animations or legend toggling). |
| D-UI-04 | Universal Theme and Font APEX icons are not reproduced. The theme is a neutral stylesheet. |

| ID | Assumption to confirm against the running source (WP9.7) |
|---|---|
| A-01 | IR rows per page = 50 (the export stores no value; this is the IR runtime default). **Confirmed on APEX in WP9.6 J-04.** |
| A-02 | The APEX built-in texts above are those of APEX 26.2 in language `en`. **WP9.6 confirmed** "Invalid Login Credentials", the delete confirm, "n error(s) has/have occurred", "Row created/updated/deleted." and the number range message; the required, date and lost-update texts are not observed yet. |
| A-03 | **Resolved in WP9.6:** oracleapex.com shows `P9999_REMEMBER`; set `LOGIN_REMEMBER_USERNAME=true` for parity (default off). |

| ID | Gap (not implemented) |
|---|---|
| G-01 | The IR Actions menu: column chooser, filters, highlight, control break, aggregate, compute, chart, group by, pivot, saved/private reports, subscriptions, flashback, reset. |
| G-02 | The XLSX, PDF and email downloads of the IR (CSV and HTML are implemented). |
| G-03 | Facet charts (`p_fc_show_chart`). |

Open security items for WP9-009: the production identity provider, login throttling, row-level ownership (F-04), and session revocation (the tokens are stateless).

## 5. Verification

| Evidence | Result |
|---|---|
| `pnpm typecheck` (api + web, strict) | pass |
| API tests (`node --test`, PostgreSQL 16) | **56/56**: 38 WP9.4 tests, 13 WP9.5 HTTP tests (12 scenarios: auth, schemes, every form, reports, facets, LOVs, DB error mapping, lost update) and 5 drift guards (generated spec current, region/LOV SQL = export, scheme messages, complete coverage) |
| Web unit tests (formats, pagination label) | 3/3 |
| E2E (Python Playwright, Chromium, real API + web + PostgreSQL 16) | **11/11** journeys: login/role navigation, no-role refusal, page scheme messages, request create with validations, master-detail line + submit with confirm, approval reject-needs-note + approve, status after approval + lost update across two users, departments/items incl. ORA-00001 and facets, report search/sort/CSV, admin forms, home charts + sign out |
| Python (inventory builder, synthetic export + committed-inventory shape; regeneration from the real export when `APEX2NEXT_F170134_SQL_EXPORT_DIR` is set) | 4/4 locally, incl. byte-equal regeneration |
| CI | `pilot-f170134-api` (spec check, api + web tests, no skips) and the new `pilot-f170134-e2e` (build, Chromium, no skips) |

Run locally (disposable database; schema `app` is dropped):

```bash
cd examples/f170134-target
pnpm install --frozen-lockfile && pnpm build
DATABASE_URL=postgresql://…/disposable pnpm test
DATABASE_URL=postgresql://…/disposable python -m pytest e2e -p no:cacheprovider   # needs: pip install pytest playwright; playwright install chromium
```

## 6. Not done yet

- **Parity with the running APEX application (WP9.6/9.7):** the same journeys must be run on oracleapex.com and the screens, messages and data compared. A-01…A-03 must be confirmed.
- **Owner decisions:** DEV-06, D-UI-01…04, G-01…G-03 (accept, or implement before go-live), plus the open WP9.4 items DEV-01…05 and F-01…F-05, and the WP9.3 §6 decisions.
- **WP9-009:** identity provider, throttling, row-level ownership, session revocation.
