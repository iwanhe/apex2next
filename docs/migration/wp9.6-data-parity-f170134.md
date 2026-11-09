# WP9.6 — Data Migration & Functional Parity: Demo Permintaan Barang (170134)

**Status:** One end-to-end parity journey (J-01) has been executed on both the source and the target, and **the two sides are identical**:

- **Source:** Oracle APEX 26.2.1 on oracleapex.com, workspace KCSI, schema WKSP_KCSI.
- **Target:** Next.js + NestJS + PostgreSQL 16.
- **Data and messages compared:** 9/9 tables, 10/10 views and 12/12 user-visible messages.

The data migration of two read-consistent Oracle snapshots passes every check.

This is evidence for one journey on demo-sized data. It is **not** pilot qualification (WP9.7).

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
| S1 `report_3.csv` | `8ee82921b06e83918b8e459db6fd6f243a4e621c02cca1579f256cf6d6e21352` |

## 2. Data migration

| Check | S0 | S1 |
|---|---|---|
| SNP-001 every DOC matches its Oracle SHA-256 | PASS | PASS |
| SNP-002 counts equal the rows received | PASS | PASS |
| SNP-003 session facts, all objects, unique keys, valid JSON | PASS | PASS |
| LOD-001 empty target / LOD-002 loaded = source (FK order, one transaction) | PASS | PASS |
| IDN-001 identity next value ≥ max(key)+1 and ≥ Oracle LAST_NUMBER | PASS | PASS |
| TBL-001 every column of every row equal (incl. the generated `line_amount`) | PASS (28 rows) | PASS (33 rows) |
| VIW-001 every view row equal under the snapshot APP_USER | PASS (10 views) | PASS (10 views; incl. 2 approval steps and `can_act_yn`) |

Reports: [`snapshot-s0-migration.md`](wp9.6/f170134/snapshot-s0-migration.md) and [`snapshot-s1-migration.md`](wp9.6/f170134/snapshot-s1-migration.md), with JSON versions alongside.

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

## 4. Changes made in the target from the observations

Before J-01 the target differed from APEX in these points. Each was fixed and is covered by tests.

- **DML success messages.** APEX shows "Row created.", "Row updated." and "Row deleted."; "Row updated." appears only when a value changed. When a submit also runs a process, APEX joins the messages in process order.
- **Number field ranges.** All number items have `min_value 0`, so APEX shows "#LABEL# must be a number greater than or equal to 0." instead of "must be Numeric". The page inventory now keeps item plug-in attributes.
- **Errors from `RAISE_APPLICATION_ERROR`.** These keep their `ORA-2xxxx:` prefix. The error notification lists every message under "n error(s) has/have occurred".
- **Application title.** `&APP_TITLE.` and the header logo use the logo text "DEMO" ("DEMO - Log In"). Browser titles are the page step titles.
- **Pagination labels.** Classic report: "row(s) x - y of z". Interactive Report: "x - y". There is no total row count text.

This confirms WP9.5 assumption A-02 for the texts seen: "Invalid Login Credentials", "Would you like to perform this delete action?", "n error(s) …" and "Row …". It also settles A-03: oracleapex.com shows "Remember username", so set `LOGIN_REMEMBER_USERNAME=true` for parity. A-01 (IR rows per page 50) is still unconfirmed, because no report had more than 3 rows.

## 5. Differences that remain (need owner decision)

| ID | APEX | Target |
|---|---|---|
| D-UI-05 | Page 300 does not refresh its report and facets after a dialog closes. Page 302 refreshes only the header and lines; the master list and the "Tambah" button keep the state from before Submit. | The parent page re-renders completely, so lists, facets and buttons are always current. |
| D-UI-06 | Confirmations use `apex.confirm` with the button label as the OK action (e.g. [Cancel / Submit for Approval]). | The browser `confirm()` dialog with OK/Cancel and the same text. |

## 6. Not covered yet (WP9.7 input)

- **Other pages on APEX:** master data and admin pages (201/211/501/511), IR search, sort and download, facet filtering, lost update between two sessions, negative authorization paths, and the two-level approval above `LEVEL2_LIMIT` (DIRECTOR).
- **Data volume and performance:** the data is demo-sized (≤ 33 rows).
- **Test data left in the source:** REQ-2026-0003 ("WP96 parity A rev", FULFILLED), its two lines and two approval steps, and the counter `REQ/2026 = 4`. Removing them requires DML on the source and the owner's decision.

## 7. Re-run

```bash
cd examples/f170134-target && pnpm install --frozen-lockfile && pnpm build
DATABASE_URL=postgresql://…/disposable python parity/journey.py \
  --s0 snapshot-s0.csv --s1 snapshot-s1.csv \
  --apex-observations parity/apex-observations-j01.json --output build/parity-j01.json
```

The script drops schema `app`, migrates, loads S0 (all checks must pass), starts API and web on free ports, runs J-01 and writes the comparison. The request date of J-01 is "today" in UTC, so the target run must happen on the same UTC date as the APEX run, or the dates in S1 must be shifted.
