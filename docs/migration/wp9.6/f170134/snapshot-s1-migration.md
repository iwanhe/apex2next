# WP9.6 data migration report — snapshot-s1.csv

Snapshot SHA-256 `8ee82921b06e83918b8e459db6fd6f243a4e621c02cca1579f256cf6d6e21352`; Oracle session: user `APEX_PUBLIC_USER`, APP_USER `IWAN.HERDIAN@KCSI-ID.COM`, sysdate `2026-11-09T09:36:31`, DB charset `AL32UTF8`.

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
| apx_demo_requests | 3 | 3 |
| apx_demo_user_roles | 7 | 7 |
| apx_demo_approvals | 2 | 2 |
| apx_demo_request_lines | 6 | 6 |

## Identity alignment

| Column | Max key | Oracle LAST_NUMBER | Next value |
|---|---|---|---|
| apx_demo_user_roles.user_role_id | 47 | 61 | 61 |
| apx_demo_approvals.approval_id | 21 | 41 | 41 |
| apx_demo_departments.department_id | 3 | 21 | 21 |
| apx_demo_items.item_id | 5 | 21 | 21 |
| apx_demo_requests.request_id | 21 | 41 | 41 |
| apx_demo_request_lines.line_id | 22 | 41 | 41 |

## Reconciliation (views evaluated as `IWAN.HERDIAN@KCSI-ID.COM`)

| Object | Rows | Differences |
|---|---|---|
| apx_demo_roles | 5 | 0 |
| apx_demo_user_roles | 7 | 0 |
| apx_demo_doc_types | 1 | 0 |
| apx_demo_doc_seq | 1 | 0 |
| apx_demo_approvals | 2 | 0 |
| apx_demo_departments | 3 | 0 |
| apx_demo_items | 5 | 0 |
| apx_demo_requests | 3 | 0 |
| apx_demo_request_lines | 6 | 0 |
| apx_demo_user_roles_v | 7 | 0 |
| apx_demo_departments_v | 3 | 0 |
| apx_demo_items_v | 5 | 0 |
| apx_demo_requests_v | 3 | 0 |
| apx_demo_request_lines_v | 6 | 0 |
| apx_demo_request_summary_v | 3 | 0 |
| apx_demo_approvals_v | 2 | 0 |
| apx_demo_dash_c1_s1_v | 2 | 0 |
| apx_demo_dash_c2_s1_v | 2 | 0 |
| apx_demo_dash_kpi_v | 3 | 0 |
