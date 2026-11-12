# WP9.6 — Data Migration & Functional Parity: Demo Permintaan Barang (170134)

**Status:** Five end-to-end parity journeys (J-01 transactions/approval, J-02 master data/administration, J-03 two-level approval, J-04 reports, J-05 authorization and lost update) have been executed on both the source and the target, and **the two sides are identical**:

- **Source:** Oracle APEX 26.2.1 on oracleapex.com, workspace KCSI, schema WKSP_KCSI.
- **Target:** Next.js + NestJS + PostgreSQL 16.
- **Data and messages compared:** J-01: 9/9 tables, 10/10 views, 12/12 user-visible messages. J-02: 9/9 tables, 10/10 views, 11/11 messages. J-03: 9/9 tables, 10/10 views, 7/7 messages and button states. J-04 (read-only): 14/14 report observations (rows, order, pagination, CSV, facets). J-05: 9/9 tables, 10/10 views, 8/8 messages and button states.

The data migration of five read-consistent Oracle snapshots passes every check.

This is evidence for five journeys on demo-sized data. It is **not** pilot qualification (WP9.7).

## 1. Method

1. **S0, source snapshot before the journey** (2026-11-09 07:13 UTC). The owner ran [`extract_snapshot_apex_workshop.sql`](../../examples/f170134-target/migration/oracle/extract_snapshot_apex_workshop.sql) in SQL Workshop and downloaded the CSV.
   - The query is a single read-only SELECT, so the snapshot is read-consistent.
   - It returns every row of the 9 tables and 10 views as `JSON_OBJECT(*)`, the counts, the identity high-water marks and the session/NLS facts.
   - Each row carries the SHA-256 computed in Oracle.
2. **S0 migrated into PostgreSQL** with `apex2next_schema_analyzer.snapshot_migration`. It verifies, loads, aligns identities and reconciles, and commits only if every check passes.
3. **J-01 on APEX.** Claude ran J-01 in the owner's built-in browser. The owner signed in as `DEMO_REQ` and `DEMO_MGR`; no password passed through Claude. Claude drove the real pages through the APEX client API (dialog iframe, `apex.item().setValue`, button clicks, `apex.confirm`) and recorded every message: [`parity/apex-observations-j01.json`](../../examples/f170134-target/parity/apex-observations-j01.json).
4. **S1, source snapshot after the journey** (2026-11-09 09:36 UTC).
5. **J-01 on the target** from the same S0, with the same users and inputs, using [`parity/journey.py`](../../examples/f170134-target/parity/journey.py) (Playwright/Chromium). Then two comparisons:
   - **Target database vs S1** (`compare_state`, `compare_views_after`): rows are matched by natural keys. Surrogate keys and clock columns are excluded; every other column must be equal.
   - **Messages vs the APEX observations.**

Snapshots (not committed; owner demo data, hashes recorded):

| Snapshot | SHA-256 of the CSV |
|---|---|
| S0 `report_2.csv` | `3b847e22b21c69da6a32882eb3c7ae4bb2c03faf3458234d611bf71fc5727b81` |
| S1 `report_3.csv` (after J-01, before J-02) | `8ee82921b06e83918b8e459db6fd6f243a4e621c02cca1579f256cf6d6e21352` |
| S2 `report_4.csv` (after J-02, 2026-11-09 10:47 UTC) | `eb1a21493a7e09efb69bcc23e4d89508006325d40f6f3cd1e2ae1a38e9c4f674` |
| S3 `report_5.csv` (after J-03, 2026-11-09 11:10 UTC; J-04 ran read-only on this state) | `1cd4d4394ff01a847540035404ccd681a82aa918eeabeb41969d17ea3132d548` |
| S4 `report_6.csv` (after J-05, 2026-11-10 08:03 UTC) | `9fe1721fa1d5b83d259681a9b6a3e89367e8dbc4b75ca949fbe3805036f079a7` |

## 2. Data migration

| Check | S0 | S1 | S2 | S3 | S4 |
|---|---|---|---|---|---|
| SNP-001 every DOC matches its Oracle SHA-256 | PASS | PASS | PASS | PASS | PASS |
| SNP-002 counts equal the rows received | PASS | PASS | PASS | PASS | PASS |
| SNP-003 session facts, all objects, unique keys, valid JSON | PASS | PASS | PASS | PASS | PASS |
| LOD-001 empty target / LOD-002 loaded = source (FK order, one transaction) | PASS | PASS | PASS | PASS | PASS |
| IDN-001 identity next value ≥ max(key)+1 and ≥ Oracle LAST_NUMBER | PASS | PASS | PASS | PASS | PASS |
| TBL-001 every column of every row equal (incl. the generated `line_amount`) | PASS (28 rows) | PASS (33 rows) | PASS (33 rows) | PASS (37 rows) | PASS (38 rows) |
| VIW-001 every view row equal under the snapshot APP_USER | PASS (10 views) | PASS (10 views; incl. 2 approval steps and `can_act_yn`) | PASS (10 views) | PASS (10 views; incl. the DIRECTOR step) | PASS (10 views) |

Reports: [`snapshot-s0-migration.md`](wp9.6/f170134/snapshot-s0-migration.md), [`snapshot-s1-migration.md`](wp9.6/f170134/snapshot-s1-migration.md), [`snapshot-s2-migration.md`](wp9.6/f170134/snapshot-s2-migration.md) [`snapshot-s3-migration.md`](wp9.6/f170134/snapshot-s3-migration.md) and [`snapshot-s4-migration.md`](wp9.6/f170134/snapshot-s4-migration.md), with JSON versions alongside.

Facts established from the source snapshots:
- **Clock.** Oracle `sysdate` and `systimestamp` run in UTC (session zone +00:00; DBTIMEZONE -05:00 does not affect DATE). The target clock policy `APP_TIME_ZONE=UTC` therefore matches, which is evidence for the WP9.3 §6 timezone decision.
- **Locale.** NLS: `NLS_SORT=BINARY`, `NLS_NUMERIC_CHARACTERS=.,`, language AMERICAN, character set AL32UTF8. These match the target choices from WP9.5 (`COLLATE "C"`, number masks).
- **Identity values.** Identity columns use CACHE 20, so Oracle handed out REQUEST_ID 21 after LAST_NUMBER 21. The target alignment (next = max(max+1, LAST_NUMBER)) also produced 21. Oracle then lost part of its approval cache (APPROVAL_ID 1, then 21), while the target gave 1, then 2. Surrogate values can differ and nothing user-visible depends on them; they are excluded from parity.

## 3. Journey J-01 (users DEMO_REQ, DEMO_MGR)

| Step | Action | APEX = target |
|---|---|---|
| J1 | DEMO_REQ creates a request with a need date before the request date, then a valid one (REQ-2026-0003) | "1 error has occurred" + "Tanggal dibutuhkan tidak boleh sebelum tanggal permintaan." / "Row created." |
| J2 | Two lines via page 302, the first one with Qty "abc" | "Qty must be a number greater than or equal to 0." / "Row created." ×2 |
| J3 | Submit from the header dialog (confirm) | "Dokumen diajukan untuk approval." |
| J4 | Create REQ-2026-0004 and delete it (DRAFT, confirm) | "Row deleted." (number 0004 stays consumed in both) |
| J5 | DEMO_MGR rejects without a note, then with "WP96 revisi" | "1 error has occurred" + "ORA-20108: Alasan penolakan wajib diisi." / "Dokumen ditolak." |
| J6 | DEMO_REQ revises Keperluan and resubmits | "Row updated. Dokumen diajukan untuk approval." |
| J7 | DEMO_MGR approves ("WP96 ok") | "Dokumen disetujui." |
| J8 | DEMO_MGR sets status FULFILLED | "Row updated." |

Result ([`parity-j01.json`](wp9.6/f170134/parity-j01.json)): **PASS**.
- **Tables:** 9/9 equal, including the document counter `LAST_NO=4`, both approval steps with actor, note and amount, the audit actors and the final request state.
- **Views:** 10/10 equal.
- **Messages:** 12/12 identical.

### Journey J-02 (users DEMO_WH, DEMO_ADMIN; S1 → S2)

| Step | Action | APEX = target |
|---|---|---|
| A1 | DEMO_WH creates department "wp96" | "Row created." (stored as WP96) |
| A2 | Creates department "ops" (duplicate) | "1 error has occurred" + `ORA-00001: unique constraint (WKSP_KCSI.APX_DEMO_DEPARTMENTS_U1) violated on table WKSP_KCSI.APX_DEMO_DEPARTMENTS columns (DEPT_CODE)` |
| A3 | Item "wp96-01" with price -5, then 1000 | "Harga Standar must be a number greater than or equal to 0." / "Row created." (WP96-01, UOM PCS) |
| A4 | Changes the item price to 1500 | "Row updated." |
| A5 | Deletes the item and the department (confirm) | "Row deleted." ×2 |
| B1 | DEMO_ADMIN opens a new user role | `P501_USERNAME` defaults to DEMO_ADMIN (`:APP_USER`) |
| B2 | Creates "wp96.user" / REQUESTER, then deletes it | "Row created." (WP96.USER) / "Row deleted." |
| B3 | Document type REQ: Apply Changes without a change | No message; the row is unchanged |

Result ([`parity-j02.json`](wp9.6/f170134/parity-j02.json)): **PASS**: 9/9 tables, 10/10 views and 11/11 messages.

J-02 deletes everything it creates, so the state comparison mainly proves two things: nothing else changed, and the configuration row stayed the same after a save without changes. The messages are the main evidence for J-02. The planned delete of department OPS (expected ORA-02292) was **not** executed on the source: the session's safety check refused it, because it would delete a real record if the foreign key did not hold. That case is covered only on the target (API test).

### Journey J-03 (users DEMO_REQ, DEMO_MGR, DEMO_DIR; S2 → S3)

Two-level approval: the amount (12,500,000) is above `LEVEL2_LIMIT` (10,000,000) of document type REQ.

| Step | Action | APEX = target |
|---|---|---|
| C1 | DEMO_REQ creates REQ-2026-0005 (IT, "WP96 parity C") and adds IT-001, qty 1, price 12,500,000 | "Row created." ×2 |
| C2 | Submits from the header dialog (confirm) | "Dokumen diajukan untuk approval." |
| C3 | DEMO_MGR approves level 1 ("WP96 L1 ok") | "Dokumen disetujui."; a level-2 DIRECTOR step is created, `REQUESTED_ON` = level-1 `ACTED_ON` |
| C4 | DEMO_MGR opens the level-2 step | No Approve/Reject button (`can_act_yn = 'N'`); only Close |
| C5 | DEMO_DIR opens it and approves ("WP96 L2 ok") | Approve and Reject shown / "Dokumen disetujui."; request APPROVED, `UPDATED_BY` DEMO_DIR |

Result ([`parity-j03.json`](wp9.6/f170134/parity-j03.json)): **PASS**: 9/9 tables, 10/10 views and 7/7 messages and button states. The target passed on the first run; no target change was needed.

Observation on APEX: after Submit the "Tambah" button on page 302 stays visible until the page is reloaded. The button condition (status DRAFT/REJECTED) is evaluated at render time, and the dialog-closed action refreshes only the header region. This is the D-UI-05 behaviour already accepted; the target hides the button at once.

### Journey J-04 (user DEMO_ADMIN; read-only on S3)

| Step | Action | APEX = target |
|---|---|---|
| D1 | Page 310 Interactive Report, default | 7 rows in `LINE_ID` order, "1 - 7" |
| D2 | Search "laptop" (all columns, case-insensitive), then sort Jumlah descending | 3 rows (one matched through the request purpose), 25,000,000 / 12,500,000 / 300,000 |
| D3 | CSV download of that report | File "Baris Permintaan.csv", header = column labels, formatted values (`"12,500,000"`), search and sort applied, UTF-8 without BOM, LF |
| D4 | Page 400: sort Total ascending, then search "OPERATIONS"; CSV | 315,000 < 1,250,000 < 12,500,000 < 25,300,000; 2 rows; "Rekap Permintaan.csv" |
| D5 | Page 300 faceted search: Status = DRAFT, then search "laptop" | Rows, "row(s) x - y of z" and facet counts (a facet ignores its own selection; zero counts hidden) |
| D6 | Page 210 faceted search with cards: Kategori = IT; search "toner" | Cards and counts, e.g. "Alat Tulis Kantor 2, Perangkat IT 2, Consumables 1" |

Result ([`parity-j04.json`](wp9.6/f170134/parity-j04.json)): **PASS**, 14/14 observations identical, database unchanged. **A-01 is confirmed**: Interactive Reports show 50 rows per page (Actions > Rows Per Page has 50 selected).

### Journey J-05 (user DEMO_REQ; S3 → S4)

| Step | Action | APEX = target |
|---|---|---|
| E1 | DEMO_REQ opens Users & Roles (500) and Document Types (510) | "Akses ditolak: hanya untuk role ADMIN." + "Access denied by Page security check" |
| E2 | DEMO_REQ opens Departments (200) and Items (210) | Lists readable (3 rows, 5 cards); **no Create button** (button scheme MASTER_DATA) |
| E3 | Creates REQ-2026-0006 ("WP96 parity D") | "Row created." |
| E4 | Two tabs on the same version: tab A saves the purpose, then tab B saves its stale form | "Row updated." / "1 error has occurred" + "Current version of data in database has changed since user initiated update process." |

Result ([`parity-j05.json`](wp9.6/f170134/parity-j05.json)): **PASS**: 9/9 tables, 10/10 views, 8/8 messages and button states. The stale save changed nothing (`NOTES` stays empty). On APEX the second tab was a hidden frame in the same session; its first save closed the open dialog, and that extra save is replayed on the target so both sides end in the same state.

## 4. Changes made in the target from the observations

Before J-01 the target differed from APEX in these points. Each was fixed and is covered by tests.

- **DML success messages.** APEX shows "Row created.", "Row updated." and "Row deleted."; "Row updated." appears only when a value changed. When a submit also runs a process, APEX joins the messages in process order.
- **Number field ranges.** All number items have `min_value 0`, so APEX shows "#LABEL# must be a number greater than or equal to 0." instead of "must be Numeric". The page inventory now keeps item plug-in attributes.
- **Errors from `RAISE_APPLICATION_ERROR`.** These keep their `ORA-2xxxx:` prefix. The error notification lists every message under "n error(s) has/have occurred".
- **Application title.** `&APP_TITLE.` and the header logo use the logo text "DEMO" ("DEMO - Log In"). Browser titles are the page step titles.
- **Pagination labels.** Classic report: "row(s) x - y of z". Interactive Report: "x - y". There is no total row count text.
- **Report sort (J-04).** Numbers and dates sorted as text (the ORDER BY resolved to the text-cast output column), so 300,000 came before 25,000,000 and the default `LINE_ID` order was 1, 2, 21, 22, 3. The sort now uses the source column; strings keep byte order (`NLS_SORT=BINARY`).
- **CSV download (J-04).** File named after the region title (`Baris Permintaan.csv`, with `filename*`), UTF-8 without BOM, LF line ends; it was `requestLines.csv` with BOM and CRLF.
- **Button authorization schemes (J-05).** Six buttons carry their own scheme in the export (CREATE on 200/210: MASTER_DATA; CREATE on 300/310 and EDIT_HEADER/CREATE_REQUEST_LINES on 302: REQUESTER). The page inventory dropped `p_security_scheme` of components; it now keeps it, and the target hides those buttons unless the scheme passes. The target pages still enforce their own schemes.
- **Page security message (J-05).** A failed page scheme shows the scheme message and "Access denied by Page security check".
- **Constraint error text (J-02).** Oracle 23ai names the schema, the table and the columns, e.g. `ORA-00001: unique constraint (WKSP_KCSI.X) violated on table WKSP_KCSI.T columns (C)`. The target uses the same form, with the schema label from `DB_ERROR_SCHEMA` (default WKSP_KCSI). The ORA-02292/02290/01400 texts carry the schema prefix but are not observed yet.

This confirms WP9.5 assumption A-02 for the texts seen: "Invalid Login Credentials", "Would you like to perform this delete action?", "n error(s) …" and "Row …". It also settles A-03: oracleapex.com shows "Remember username", so set `LOGIN_REMEMBER_USERNAME=true` for parity. A-01 (IR rows per page 50) is confirmed by J-04.

## 5. Differences that remain (need owner decision)

| ID | APEX | Target |
|---|---|---|
| D-UI-05 | Page 300 does not refresh its report and facets after a dialog closes. Page 302 refreshes only the header and lines; the master list and the "Tambah" button keep the state from before Submit. | The parent page re-renders completely, so lists, facets and buttons are always current. |
| D-UI-06 | Confirmations use `apex.confirm` with the button label as the OK action (e.g. [Cancel / Submit for Approval]). | The browser `confirm()` dialog with OK/Cancel and the same text. |

## 6. Not covered yet (WP9.7 input)

- **Other paths on APEX:** ORA-02292 on a referenced department (refused by the session safety check, see J-02), XLSX/PDF download, IR saved reports, control breaks, charts and the other Actions-menu features (recorded WP9.5 gaps), and dialog pages opened directly by a user without the scheme. Two separate users editing at once were not tested; J-05 used two tabs of one session, which APEX checks the same way.
- **Data volume and performance:** the data is demo-sized (≤ 33 rows).
- **Test data left in the source (owner decision 2026-11-09: keep):** REQ-2026-0003 ("WP96 parity A rev", FULFILLED), REQ-2026-0005 ("WP96 parity C", APPROVED) and REQ-2026-0006 ("WP96 parity D tab A", DRAFT), with their lines and approval steps, and the counter `REQ/2026 = 6`.

## 7. Re-run

```bash
cd examples/f170134-target && pnpm install --frozen-lockfile && pnpm build
DATABASE_URL=postgresql://…/disposable python parity/journey.py --journey J-01 \
  --s0 snapshot-s0.csv --s1 snapshot-s1.csv \
  --apex-observations parity/apex-observations-j01.json --output build/parity-j01.json
```

For J-02 use `--journey J-02 --s0 snapshot-s1.csv --s1 snapshot-s2.csv --apex-observations parity/apex-observations-j02.json`; for J-03 `--journey J-03 --s0 snapshot-s2.csv --s1 snapshot-s3.csv --apex-observations parity/apex-observations-j03.json`; for J-04 `--journey J-04 --s0 snapshot-s3.csv --s1 snapshot-s3.csv` (read-only); for J-05 `--journey J-05 --s0 snapshot-s3.csv --s1 snapshot-s4.csv`, each with its `apex-observations-j0N.json`. The script drops schema `app`, migrates, loads S0 (all checks must pass), starts API and web on free ports, runs J-01 and writes the comparison. The request date of J-01 is "today" in UTC, so the target run must happen on the same UTC date as the APEX run, or the dates in S1 must be shifted.
