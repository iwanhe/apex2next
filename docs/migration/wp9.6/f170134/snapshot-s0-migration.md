# WP9.6 data migration report — snapshot-s0.csv

Snapshot SHA-256 `3b847e22b21c69da6a32882eb3c7ae4bb2c03faf3458234d611bf71fc5727b81`; Oracle session: user `APEX_PUBLIC_USER`, APP_USER `IWAN.HERDIAN@KCSI-ID.COM`, sysdate `2026-11-09T07:13:06`, DB charset `AL32UTF8`.

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
| apx_demo_requests | 2 | 2 |
| apx_demo_user_roles | 7 | 7 |
| apx_demo_approvals | 0 | 0 |
| apx_demo_request_lines | 4 | 4 |

## Identity alignment

| Column | Max key | Oracle LAST_NUMBER | Next value |
|---|---|---|---|
| apx_demo_user_roles.user_role_id | 47 | 61 | 61 |
| apx_demo_approvals.approval_id | 0 | 1 | 1 |
| apx_demo_departments.department_id | 3 | 21 | 21 |
| apx_demo_items.item_id | 5 | 21 | 21 |
| apx_demo_requests.request_id | 2 | 21 | 21 |
| apx_demo_request_lines.line_id | 4 | 21 | 21 |

## Reconciliation (views evaluated as `IWAN.HERDIAN@KCSI-ID.COM`)

| Object | Rows | Differences |
|---|---|---|
| apx_demo_roles | 5 | 0 |
| apx_demo_user_roles | 7 | 0 |
| apx_demo_doc_types | 1 | 0 |
| apx_demo_doc_seq | 1 | 0 |
| apx_demo_approvals | 0 | 0 |
| apx_demo_departments | 3 | 0 |
| apx_demo_items | 5 | 0 |
| apx_demo_requests | 2 | 0 |
| apx_demo_request_lines | 4 | 0 |
| apx_demo_user_roles_v | 7 | 0 |
| apx_demo_departments_v | 3 | 0 |
| apx_demo_items_v | 5 | 0 |
| apx_demo_requests_v | 2 | 0 |
| apx_demo_request_lines_v | 4 | 0 |
| apx_demo_request_summary_v | 2 | 0 |
| apx_demo_approvals_v | 0 | 0 |
| apx_demo_dash_c1_s1_v | 1 | 0 |
| apx_demo_dash_c2_s1_v | 2 | 0 |
| apx_demo_dash_kpi_v | 3 | 0 |
