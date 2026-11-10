# WP9 pilot closure — app 170134 as proof and template

**Decision (owner, 2026-11-10):** the pilot with app 170134 "Demo Permintaan Barang" is a **proof and template**. It will not go live. The next step is a real PANDAWA application. Because nothing goes live, the formal sign-offs WP9-012, the witnessed rehearsal and the RTO/RPO approval are not needed for this app. They return as real gates for the next one.

## 1. What the pilot proved

| Area | Result | Evidence |
|---|---|---|
| Source analysis | 19 pages, 269 components, 9 tables, 10 views, 4 packages, 5 triggers inventoried and reconciled with the Oracle dictionary | WP9.1–WP9.3 |
| Schema and data | 5 read-consistent Oracle snapshots migrate with every check PASS; identities aligned to Oracle `LAST_NUMBER` | WP9.6 §2 |
| Business logic | PL/SQL replaced by NestJS services with the same Oracle error codes and texts | WP9.4 |
| UI | All 19 pages rebuilt in Next.js from a generated UI spec | WP9.5 |
| Behavior | 5 journeys (52 messages/observations, every table and view) identical on APEX and on the target | WP9.6 J-01…J-05 |
| Operations | Migration with retry and rollback, backup/restore with verification, light performance test, access log | WP9.7 |
| Sign-in | Local accounts with forced change, expiry, lockout, rate limit, revocation and audit | WP9-009 |

The proof covers a small application on a free APEX instance. It does not show the effort or risk for a 200-page production application.

## 2. What is reusable as is

- **Evidence method:**
  - the snapshot query run in SQL Workshop (per-row SHA-256);
  - the migration with checks SNP/LOD/IDN/TBL/VIW;
  - state and view comparison;
  - journey replay on the target and comparison of observed APEX texts.
- **Tooling:** dictionary reconciliation, schema plan, DDL conversion, page inventory, UI-spec generator, coverage matrix, rehearsal (`rehearse.py`), performance test (`perf.py`) and the qualification assessor.
- **Runtime patterns:**
  - APEX authorization schemes per page, button and navigation entry;
  - APEX messages and validations;
  - lost-update checksum;
  - IR/faceted reports;
  - local accounts;
  - access log.

## 3. What was app-specific and must become generic before the next app

These lessons come from the pilot:

1. **The snapshot query** was written by hand for 9 tables and 10 views. It should be generated from the schema plan.
2. **Report definitions** (SQL per region) and **form definitions** were written by hand. They should be generated from the page inventory, with hand overrides only where needed.
3. **Business services** replaced 4 packages by hand. For a large application, the PL/SQL workbench must say early which packages convert mechanically and which need hand work, so the effort can be estimated.
4. **The page inventory missed component authorization** (`p_security_scheme`) until J-05 found it. Every component attribute that affects behavior must be reconciled against the export before the UI is built.
5. **Parity journeys** were scripted by hand. A journey catalogue with expected texts (from APEX observation) should drive both runs.
6. **View performance:** views converted 1:1 with one scalar subquery per row are slow in PostgreSQL. The conversion should flag them and propose joins.
7. **Evidence through the owner's browser and SQL Workshop works, but it is slow.** For a production application, read-only database access (SQLcl/SQL*Net to a non-production copy) saves most of that time.

## 4. Choosing the next application

Criteria: a real business process with 2–4 roles and an approval or status flow; 20–60 pages; a non-production copy available; manageable PL/SQL; no hard go-live deadline during the migration.

| Candidate | Fit |
|---|---|
| **FRITS** (IT request system, app 216180) | Good: request and approval workflow like the pilot, so the template carries over; real users and data. Recommended. |
| SIPP (violation reporting, app 211068) | Medium: confidential data and DBMS_CRYPTO encryption with keys in the APEX session need their own design (key management in the target). |
| OOPS KDK (app 35340, ~226 pages) | Not yet: too large for the second step, business-critical, with its own enhancement go-live. A good third step once the generic tooling exists. |

## 5. Needed from the owner to start the next application

1. The choice of application.
2. The APEX export (SQL, split files) and the schema DDL/install script, from a non-production environment.
3. Read-only access to a non-production database copy, or the generated snapshot and dictionary queries run in SQL Workshop as in this pilot.
4. A list of 3–5 critical journeys and the roles and test users to run them.
5. A statement on data classification (personal or confidential data present?) before any data leaves Oracle.
