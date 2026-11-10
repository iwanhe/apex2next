# WP9.7 — Rehearsal, performance, operations and qualification gates: app 170134

**Status:** The engineering rehearsal is done. Migration with retry, backup and restore pass, a light performance test ran on synthetic volume, and access logging was added. The twelve-gate assessment is now **CONDITIONAL** (10 checks PASS, 7 WARN, 5 NOT VERIFIED, 0 FAIL). The assessor reports CONDITIONAL as soon as nothing fails, even while checks are still NOT VERIFIED. It was BLOCKED until local accounts were built for WP9-009 (see [WP9-009](wp9-009-local-accounts-f170134.md)). The pilot is **not qualified for go-live** yet. The open items are owner decisions and sign-offs, listed in §6.

Evidence is in [`wp9.7/f170134/`](wp9.7/f170134/): `rehearsal.json`, `perf.json`, `perf-1user.json`, `pilot-input.json` (gate manifest) and `qualification.json` (assessor output). Everything ran on a disposable PostgreSQL 16 database in a cloud sandbox with 2 vCPU. Nothing was written to Oracle.

## 1. Migration rehearsal (WP9-007, WP9-011)

The rehearsal uses `rehearsal/rehearse.py` with snapshot S4 (`report_6.csv`, SHA-256 `9fe1721f…`, 38 rows).

| Step | What it proves | Result | Time |
|---|---|---|---:|
| R1 | Clean target; apply the reviewed migrations 0001–0005 | PASS | 260 ms |
| R2 | Load S4 in one transaction; every check (SNP, LOD, IDN, TBL, VIW) passes | PASS | 44 ms |
| R3 | Rerun on a loaded target fails closed (LOD-001) and changes nothing | PASS | 53 ms |
| R4 | Injected mid-load failure (FK violation in the last table): LOD-002, whole load rolled back, 0 rows left | PASS | 167 ms |
| R5 | Retry after the failure: every check PASS; then a local account (DEMO_ADMIN) is created | PASS | 409 ms |
| R6 | Backup with `pg_dump -Fc -n app -n iam` (40,360 bytes; kept outside Git) | PASS | 115 ms |
| R7 | Simulated loss: `DROP SCHEMA app`, `DROP SCHEMA iam` | PASS | 24 ms |
| R8 | `pg_restore`, then 9/9 tables and 10/10 views equal to S4, identity next values ≥ Oracle `LAST_NUMBER`, and API smoke with `AUTH_MODE=local` (`/health/ready`, sign-in with the temporary password, forced change, report rows) | PASS | 1,593 ms |

**Retry and resume.** The load is all-or-nothing, so "resume" means rerun from an empty target. R3–R5 show that this is safe.

**Measured RTO.** Restore plus verification (R7 → R8) took **1.6 s** at demo volume; most of it is the API start and one password hash. At production volume the rehearsal must be repeated, because the time grows with data size. **RPO** equals the age of the last backup. At cutover it is 0, because APEX is frozen before the final snapshot.

The rehearsal was run by the engineer. **It was not witnessed**, and RTO/RPO targets have not been approved.

### Cutover and rollback procedure (proposal)

1. Announce the window and make APEX app 170134 unavailable. Use the application availability setting, so APEX data stops changing.
2. Take the final snapshot with the SQL Workshop query. Record its SHA-256.
3. Apply the migrations, load the snapshot (all checks PASS), take a `pg_dump`, then start API and web.
4. Smoke-test as each role: J-04 read-only and one J-01 cycle on a test request. Then switch users to the target.
5. **Rollback before the first business write on the target:** make APEX available again. Oracle is unchanged, so nothing is lost.
6. **Rollback after business writes:** there is no reverse migration from PostgreSQL to Oracle. The owner must choose one of these:
   - limit the rollback window to the smoke test;
   - re-enter target-side changes in APEX by hand, using the request numbers;
   - commission a reverse sync before go-live.

## 2. Performance (WP9-010)

The test uses `rehearsal/perf.py` on a disposable database: S4 plus **synthetic** volume of 20,005 requests, 60,007 lines and 13,337 approval steps. The synthetic rows are marked `SYN-…` / `SYNTHETIC`. The API ran with `AUTH_MODE=dev`, before local accounts existed. Local accounts add one indexed account lookup per request and about 0.3 s of scrypt per sign-in. Each scenario was called 200 times (30 for the single-user run) after 5 warm-up calls. Latency was measured at the client. API and database share the same 2 vCPU.

| Scenario (page) | 1 user p50 / p95 | 10 users p50 / p95 | Errors |
|---|---:|---:|---:|
| S1 dashboard KPI + charts (100) | 199 / 209 ms | 1,059 / 1,160 ms | 0 |
| S2 requests + facets (300) | 52 / 64 ms | 288 / 348 ms | 0 |
| S3 facet DRAFT + search (300) | 104 / 117 ms | 590 / 649 ms | 0 |
| S4 lines IR first page (310) | 5 / 5 ms | 22 / 35 ms | 0 |
| S5 lines IR search + sort (310) | 376 / 417 ms | 2,064 / 2,660 ms | 0 |
| S6 lines IR last page (310) | 125 / 165 ms | 743 / 885 ms | 0 |
| S7 summary IR sort by total (400) | 47 / 52 ms | 266 / 313 ms | 0 |
| S8 approval inbox (190) | 4 / 7 ms | 29 / 44 ms | 0 |
| S9 create request (301) | 3 / 5 ms | 20 / 52 ms | 0 |

**Change made:** the API pool now sets `jit=off`. PostgreSQL's JIT compilation doubled the cost of the report queries (S5 went from 3.8 s to 2.1 s p50 at 10 users). `PG_JIT=on` restores the server default.

**Hot spots.** S5, S6 and S1 scan whole views:
- `apx_demo_request_lines_v` computes its display columns with one scalar subquery per row. This is a faithful conversion of the Oracle view, where Oracle's scalar-subquery caching hides the cost.
- An IR search matches every column, so no index can be used. APEX behaves the same.
- The dashboard aggregates over all requests.

At 10 concurrent users on 2 vCPU the work queues on the CPU, so latency is roughly five times the single-user value. Options for later, if the owner's targets need them:
- rewrite the views as joins (a WP9.3 override, needs review);
- give the database its own CPU;
- cache the dashboard.

**Proposed targets (for owner approval):**
- with 1 user, every page p95 < 1 s;
- with 10 concurrent users at this volume, p95 < 3 s;
- 0 errors.

The measurements meet these targets. There is no APEX baseline at this volume, so the numbers are indicative, not a capacity test.

## 3. Operations (WP9-010)

| Item | State |
|---|---|
| Health | `GET /health` (process) and `GET /health/ready` (database) |
| Access log | **New:** one JSON line per request on stdout with time, request id, method, path, status, ms and user. The path is logged without the query string, so search terms stay out. A valid `x-request-id` header is reused, otherwise a new id is generated and echoed. `ACCESS_LOG=off` disables the log. A unit test covers it. |
| Error log | Unexpected errors are logged with stack trace; the user only sees "Terjadi kesalahan pada server." |
| Backup | `pg_dump -Fc -n app`; restore is rehearsed in R6–R8 |
| Security audit | `iam.account_events`: account created, sign-in ok/failed, locked, unlocked, password changed/reset, Sign Out, sessions revoked, deactivated/activated (no passwords) |
| Missing | Monitoring and alerting (uptime, error rate, latency), log shipping and retention, an operations runbook (start/stop, configuration, secrets, backup schedule), and a defect workflow |

## 4. Defects

All defects found in WP9.6/9.7 are fixed and covered by tests or the parity journeys:
- WP9.6 J-01/J-02: messages and texts;
- J-04: report sort, CSV format;
- J-05: button authorization schemes, the page security message;
- WP9.7: JIT latency.

**Open critical/high defects: 0.** The identity provider is a gate (WP9-009), not a defect.

## 5. Twelve-gate assessment

The assessment was produced with `pilot_qualification` from [`pilot-input.json`](wp9.7/f170134/pilot-input.json). Result: **CONDITIONAL** (exit code 3; BLOCKED before WP9-009). Only all-PASS gives QUALIFIED. Gate statuses are the engineer's assessment; they become evidence only with the sign-offs in §6.

| Gate | Status | Evidence | Needed to PASS |
|---|---|---|---|
| WP9-001 Package intake | NOT VERIFIED | [WP9.1](wp9.1-pilot-intake-f170134.md) hashes and inventory | Owner attestation that the package is sanitized (it holds demo users and the owner's account name) and a chain-of-custody record |
| WP9-002 Runtime, scope | PASS | [WP9.6 §1](wp9.6-data-parity-f170134.md): APEX 26.2.1, app 170134, snapshots S0–S4 | — |
| WP9-003 Extraction, IR | WARN | [WP9.5](wp9.5-ui-f170134.md): 269/269 components; J-05 found that `p_security_scheme` of components was dropped (fixed) | Owner accepts the SQL export as the source (D-003) and the extractor review |
| WP9-004 Oracle schema | WARN | [WP9.3](wp9.3-source-validation-schema-f170134.md): REC/DEP 12/12 | Decisions on WP9.3 §6 (ON NULL identity, NUMBER precision, empty strings, `\|\| NULL`) |
| WP9-005 PL/SQL dispositions | WARN | [WP9.4](wp9.4-business-logic-f170134.md) | Final sign-off on DEV-01…06 and F-01…05 (now "accepted for now") |
| WP9-006 Target build | PASS | CI on the feature branch: build, migrations, API/web/e2e | — |
| WP9-007 Data rehearsal | PASS | 5 snapshot migrations, `rehearsal.json` R1–R5 | Repeat at production volume before cutover |
| WP9-008 Journey parity | WARN | [WP9.6](wp9.6-data-parity-f170134.md): J-01…J-05 identical | Business approval of the journeys and results |
| WP9-009 Identity, access | WARN | [WP9-009 local accounts](wp9-009-local-accounts-f170134.md): scrypt, forced change, expiring temporary passwords, lockout, throttling, revocation, audit trail; J-05 negative paths; F-04 and e-mail handover decided | Security review and sign-off |
| WP9-010 Performance, operations | WARN | §2–§3, `perf.json` | Approved targets; monitoring and alerting; runbook |
| WP9-011 Restore, rollback | WARN | `rehearsal.json` R6–R8 | Approved RTO/RPO; a witnessed rehearsal; rollback option chosen (§1) |
| WP9-012 Sign-off | NOT VERIFIED | — | Business, application, security and operations sign-off |

The source checks also report SRC-002 (sanitization attestation) as NOT VERIFIED. RTO and RPO (ACC-003/004) are NOT VERIFIED until they are approved. ACC-001/002 (0 critical, 0 high defects) PASS.

## 6. Owner decisions needed

1. Sanitization attestation and chain of custody for the package (WP9-001).
2. RTO/RPO and the rollback option after first write (§1).
3. Performance targets (§2).
4. Approval of journeys J-01…J-05 and their results (WP9-008).
5. ~~WP9-009 decisions~~: local accounts built; F-04 kept as in the source; temporary passwords by e-mail with 72 h expiry (2026-11-10). Security review and sign-off remain.
6. Remaining open items: D-UI-01…04, the WP9.3 §6 type decisions, and final sign-off on DEV/F/G.
7. Names for the four sign-offs (business, application, security, operations) and a date for a witnessed rehearsal.

## 7. Re-run

From `examples/f170134-target` after `pnpm build`, with a disposable database:

```bash
DATABASE_URL=postgresql://…/f170134_pilot python3 rehearsal/rehearse.py --snapshot snapshot-s4.csv \
  --backup-dir /tmp/wp97 --output ../../docs/migration/wp9.7/f170134/rehearsal.json
DATABASE_URL=postgresql://…/f170134_perf python3 rehearsal/perf.py --snapshot snapshot-s4.csv \
  --output ../../docs/migration/wp9.7/f170134/perf.json            # add --users 1 --iterations 30 for perf-1user.json
PYTHONPATH=../../workers/schema-analyzer/src python3 -m apex2next_schema_analyzer.pilot_qualification \
  ../../docs/migration/wp9.7/f170134/pilot-input.json --output ../../docs/migration/wp9.7/f170134/qualification.json
```

Both scripts drop schema `app` in the database they are given; never point them at a database that holds data you need.
