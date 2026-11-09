# WP9.6 data migration report — snapshot-s3.csv

Snapshot SHA-256 `1cd4d4394ff01a847540035404ccd681a82aa918eeabeb41969d17ea3132d548`; Oracle session: user `APEX_PUBLIC_USER`, APP_USER `IWAN.HERDIAN@KCSI-ID.COM`, sysdate `2026-11-09T11:10:19`, DB charset `AL32UTF8`.

**Committed:** yes

| Check | Result |
|---|---|
| SNP-001 | PASS |
| SNP-002 | PASS |
| SNP-003 | PASS |
| LOD-001 | PASS |
| LOD-002 | PASS |
| IDN-001 | PASS |
| TBL-001 | PASS |
| VIW-001 | PASS |

## Load (foreign-key order)

| Table | Source rows | Loaded |
|---|---|---|
| apx_demo_departments | 3 | 3 |
| apx_demo_doc_seq | 1 | 1 |
| apx_demo_items | 5 | 5 |
| apx_demo_roles | 5 | 5 |
| apx_demo_doc_types | 1 | 1 |
| apx_demo_requests | 4 | 4 |
| apx_demo_user_roles | 7 | 7 |
| apx_demo_approvals | 4 | 4 |
| apx_demo_request_lines | 7 | 7 |

## Identity alignment

| Column | Max key | Oracle LAST_NUMBER | Next value |
|---|---|---|---|
| apx_demo_user_roles.user_role_id | 47 | 81 | 81 |
| apx_demo_approvals.approval_id | 23 | 41 | 41 |
| apx_demo_departments.department_id | 3 | 41 | 41 |
| apx_demo_items.item_id | 5 | 41 | 41 |
| apx_demo_requests.request_id | 41 | 61 | 61 |
| apx_demo_request_lines.line_id | 41 | 61 | 61 |

## Reconciliation (views evaluated as `IWAN.HERDIAN@KCSI-ID.COM`)

| Object | Rows | Differences |
|---|---|---|
| apx_demo_roles | 5 | 0 |
| apx_demo_user_roles | 7 | 0 |
| apx_demo_doc_types | 1 | 0 |
| apx_demo_doc_seq | 1 | 0 |
| apx_demo_approvals | 4 | 0 |
| apx_demo_departments | 3 | 0 |
| apx_demo_items | 5 | 0 |
| apx_demo_requests | 4 | 0 |
| apx_demo_request_lines | 7 | 0 |
| apx_demo_user_roles_v | 7 | 0 |
| apx_demo_departments_v | 3 | 0 |
| apx_demo_items_v | 5 | 0 |
| apx_demo_requests_v | 4 | 0 |
| apx_demo_request_lines_v | 7 | 0 |
| apx_demo_request_summary_v | 4 | 0 |
| apx_demo_approvals_v | 4 | 0 |
| apx_demo_dash_c1_s1_v | 3 | 0 |
| apx_demo_dash_c2_s1_v | 2 | 0 |
| apx_demo_dash_kpi_v | 3 | 0 |
