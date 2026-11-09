# WP9.4 — Business Logic Migration: Demo Permintaan Barang (170134)

**Status:** Implemented and tested on PostgreSQL 16. Functional parity against a running Oracle/APEX instance is **not** established yet (WP9.6). Deviations DEV-01…DEV-05 and findings F-01…F-05 need owner sign-off.
**Date:** 2026-11-09
**Source:** `install.sql` `sha256:7c71e9c5…2d66d` (reconciled with the Oracle dictionary in WP9.3b), APEX export f170134 (processes, authorization schemes, page `p_required_role`).
**Target:** [`examples/f170134-target`](../../examples/f170134-target/README.md): NestJS 11 business services, reviewed PostgreSQL functions, and generated migrations.

## 1. Scope and placement (ADR-0003)

| Source unit | Target | Where |
|---|---|---|
| `APX_DEMO_SEC_PKG` (app_user, bootstrap_mode, has_role[_yn], has_any_role, set_test_user) | `app.current_username/has_role/has_role_yn/has_any_role` SQL functions; `SecurityService`; `Principal` | `0002_wp94_business_functions.sql`, `business/security.service.ts`, `business/context.ts` |
| `APX_DEMO_DOC_PKG.NEXT_NO` | `NumberingService.nextNo` (same transaction as the insert) | `business/numbering.service.ts` |
| `APX_DEMO_APPROVAL_PKG` (submit, approve, reject, can_act_yn, doc_amount, bypass, get_type/get_doc/set_doc_status/create_step) | `ApprovalService`, `DocumentTypeRegistry` with reviewed `DocumentAdapter`s, and `app.can_act_yn` SQL function | `business/approval.service.ts`, `business/document-types.ts`, `0002` |
| `APX_DEMO_REQUEST_PKG.CHECK_SUBMIT` | `requestDocument.validate` | `business/document-types.ts` |
| `APX_DEMO_REQUESTS_TRG`, `APX_DEMO_REQUEST_LINES_TRG` | `RequestService` write paths | `business/request.service.ts` |
| `APX_DEMO_USER_ROLES_TRG`, `_DEPARTMENTS_TRG`, `_ITEMS_TRG` | `MasterDataService` | `business/master-data.service.ts` |
| APEX authorization schemes + page `p_required_role`; page processes `CALL_SUBMIT_REQUESTS` (301), `CALL_APPROVE`/`CALL_REJECT` (191) | `PermintaanBarangService` (one transaction per use case; scheme checked first) | `business/permintaan-barang.service.ts` |
| Views `APX_DEMO_APPROVALS_V`, `APX_DEMO_DASH_KPI_V` (held in WP9.3) | Generated in `0003_wp94_deferred_views.sql` via the reviewed function mapping `APX_DEMO_APPROVAL_PKG.CAN_ACT_YN → app.can_act_yn` | `db/function-mappings.json` |

**Identity.** `APP_USER` is replaced by an authenticated `Principal`. `BusinessDatabase.run` opens one transaction per use case and publishes the username with `set_config('app.username', $1, true)` (transaction-local, so it never leaks across pooled connections; this is tested). The SQL functions and the approvals view read it. With no principal, every check fails closed. Building the `Principal` from a verified identity provider is WP9-009; the HTTP controllers are WP9.5.

**Clock.** Every `SYSDATE` is replaced by one transaction clock in `APP_TIME_ZONE`. The default is `UTC`, because the source database reports `+00:00`. This follows the open WP9.3 decision 3.

## 2. Business rule catalog

Source lines refer to `install.sql`. Every rule has at least one integration test (`apps/api/test/*.integration.test.js`).

| Rule | Source | Behavior | Error (Oracle code) |
|---|---|---|---|
| BR-SEC-01 | SEC_PKG.APP_USER 243-249 | Principal = upper-cased authenticated username; test override not migrated | `UNAUTHENTICATED` |
| BR-SEC-02 | HAS_ROLE 262-279 | Role or ADMIN, case-insensitive username | — |
| BR-SEC-03/04 | HAS_ROLE_YN, HAS_ANY_ROLE 281-305 | Y/N form; registered with any role | — |
| BR-SEC-05 | APEX schemes + `p_required_role` | ADMIN_RIGHTS (500–511), APP_USERS (100,190,191,200,210,300,302,310,400), MASTER_DATA (201,211), REQUESTER = REQUESTER or MANAGER (301,311), WAREHOUSE; messages verbatim | `FORBIDDEN` |
| BR-DOC-01 | NEXT_NO 348-378 | `PREFIX-YYYY-NNNN`; period = year of the transaction clock (not `request_date`) | `NOT_FOUND` (-1403) for an unknown type |
| BR-DOC-02 | MERGE + UPDATE … RETURNING | Counter in the caller's transaction: gapless, serialized, rollback releases the number | — |
| BR-DOC-03 | `LPAD(l_no, 4, '0')` | See DEV-04 | `NUMBERING_CAPACITY_EXCEEDED` |
| BR-APR-01 | GET_TYPE 489-503 | Unknown document type | `UNKNOWN_DOC_TYPE` (-20100) |
| BR-APR-02 | dynamic SQL 505-561 | Configuration must match the reviewed adapter (DEV-05) | `DOC_TYPE_CONFIG_DRIFT` |
| BR-APR-03 | SUBMIT 598-624 | Only DRAFT/REJECTED; no approver1 → APPROVED, else SUBMITTED + level-1 step requested by the principal | `DOC_NOT_SUBMITTABLE` (-20101) |
| BR-APR-04 | VALIDATE_PROC → CHECK_SUBMIT 993-1006 | At least one line | `REQUEST_WITHOUT_LINES` (-20201) |
| BR-APR-05/06 | GET_DOC / SET_DOC_STATUS | Read doc number/status; internal status change (source `g_bypass`) with audit stamps | `NOT_FOUND` (-1403) |
| BR-APR-07 | DOC_AMOUNT / CREATE_STEP 542-596 | Amount = Σ `line_amount` (NVL 0); PENDING step with current doc number | — |
| BR-APR-08 | CAN_ACT_YN 626-645 | `'Y'` iff PENDING, not requested by the principal, and the principal has the approver role/ADMIN; unknown → `'N'` | — |
| BR-APR-09 | ASSERT_CAN_ACT 647-661 | Checks in source order | -20105, -20106, -20107 |
| BR-APR-10 | APPROVE 663-694 | Level 1 with `amount > level2_limit` (strict) and approver2 → level-2 step for the original requester; else document APPROVED | as BR-APR-09; `NOT_FOUND` (-1403) |
| BR-APR-11 | REJECT 696-721 | Note mandatory (`''` counts as NULL); step and document REJECTED; re-submit allowed | `REJECT_NOTE_REQUIRED` (-20108) |
| BR-REQ-01/02/03 | REQUESTS_TRG insert 783-789 + defaults | Status forced DRAFT; `request_no` from NEXT_NO('REQ') when empty; `request_date` = today | — |
| BR-REQ-04 | 791-793 | SUBMITTED cannot be updated | `REQUEST_LOCKED_SUBMITTED` (-20110) |
| BR-REQ-05 | 794-796 | CANCELLED/CLOSED are final | `REQUEST_FINAL` (-20111) |
| BR-REQ-06 | 797-801 | User status changes only APPROVED/FULFILLED/CLOSED → FULFILLED/CLOSED | `REQUEST_STATUS_TRANSITION` (-20112) |
| BR-REQ-07 | 803-807 | After submit, `department_id`, `purpose`, `need_date` keep their values silently; the target also reports them in `ignored` | — |
| BR-REQ-08 | (no delete trigger) | Delete in any status; lines cascade (see F-03) | — |
| BR-LIN-01 | REQUEST_LINES_TRG 826-840 | Lines change only while the parent is DRAFT/REJECTED; cascade delete exempt | `REQUEST_LINES_LOCKED` (-20121) |
| BR-MD-01 | USER_ROLES/DEPARTMENTS/ITEMS_TRG | Codes upper-cased (username, role_code, dept_code, item_code, uom) | — |
| BR-AUD-01 | all triggers | `created_*` on insert, `updated_*` on every write, from principal + clock | — |

Error responses carry `{code, oracleCode, rule, message}`. Message texts are the Oracle texts, including the Oracle behavior of concatenating NULL as an empty string. HTTP status is mapped per code.

## 3. Deviations from the source (deliberate; need sign-off)

| ID | Source behavior | Target behavior | Why |
|---|---|---|---|
| DEV-01 | `BOOTSTRAP_MODE`: while no ADMIN exists, **every** role check passes (WP9.2 SEC-001) | Not reproduced; the first ADMIN is provisioned explicitly (seed/migration) | Fail-open authorization |
| DEV-02 | SUBMIT reads the document without a lock; concurrent submits can both create steps, and a line can change during submit | Document row `FOR UPDATE` in submit/approve; line changes lock the parent | WP9.2 race finding; tested with parallel submits and a line-versus-submit race |
| DEV-03 | Line update checks only the **new** parent, so a line can be moved out of a SUBMITTED request | Both old and new parent must be open | Integrity of submitted amounts |
| DEV-04 | `LPAD(10000,4,'0')` = `'1000'`, giving a duplicate number and then ORA-00001 | Explicit `NUMBERING_CAPACITY_EXCEEDED` at number 10000; counter rolled back | Same failure, explicit cause |
| DEV-05 | `AMOUNT_EXPR` and `VALIDATE_PROC` from `apx_demo_doc_types` are executed as SQL/PLSQL | Configuration is compared with the reviewed adapter and never executed; drift fails closed | Code injection through configuration data |

The first-of-period numbering race (MERGE then PK violation) is removed by `INSERT … ON CONFLICT`. This is a strict improvement with the same numbers.

## 4. Findings (source behavior kept for parity; owner decision)

- **F-01** Status `CANCELLED` is unreachable. BR-REQ-06 forbids DRAFT → CANCELLED, and no package sets it.
- **F-02** `request_no` is not protected by any trigger and can be changed by an update. WP9.5: page 301 shows it as a query-only item, so the UI cannot change it; the service-level behavior is unchanged.
- **F-03** Requests can be deleted in any status, including APPROVED, and their lines cascade. Approval steps (no FK) remain as orphans. WP9.5: the page 301 DELETE button exists only for DRAFT, and the page layer enforces that (DEV-06).
- **F-04** There is no row-level ownership: any REQUESTER/MANAGER can edit any request (page 301). This is input for WP9-009.
- **F-05** Approval steps record `doc_no`/`amount` at creation; later edits after REJECTED do not update historical steps. Correct behavior, noted for reporting.

## 5. Verification

| Evidence | Result |
|---|---|
| `apps/api` typecheck (`tsc --noEmit`, strict) | pass |
| 38 Node tests (6 unit + 32 integration on PostgreSQL 16.15) | 38/38. Five consecutive runs were stable. CI job `pilot-f170134-api` fails if any test is skipped |
| Migrations through the real runner (`migrate.mjs`): 0001 → 0002 → 0003, re-run is a no-op | pass. Catalog equals `expectedCatalog` incl. 10 views and 5 functions |
| `app.can_act_yn` = approvals view = `ApprovalService.assertCanAct` for 6 principals | pass |
| Concurrency: 20 parallel creates give gapless unique numbers; 5 parallel submits create one step; line versus submit keeps amount equal to the lines | pass |
| Python engine tests (function mappings, deferred views, runner format, pilot artifact pinning, byte-identical regeneration) | 238 pass locally |

## 6. Not done yet

- **Functional parity with Oracle (WP9.6).** The same scenarios must be executed against APEX/Oracle (oracleapex.com) and compared.
- ~~HTTP controllers and pages (WP9.5)~~ done, see [WP9.5](wp9.5-ui-f170134.md). Still open: **identity provider/principal mapping and row-level security (WP9-009)** and **seed/configuration data migration (WP9.6)**.
- **Owner decisions from WP9.3 §6** (types, timezone, empty strings) are still open; the services follow the draft schema.
