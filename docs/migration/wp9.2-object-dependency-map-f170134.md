# WP9.2 — Object Dependency Map: Demo Permintaan Barang (170134)

Basis: static references in the uploaded APEX SQL export and generated install.sql. This is not a live ALL_DEPENDENCIES query.

## Relational edges

| Dependent | Prerequisite | Relationship |
|---|---|---|
| USER_ROLES | ROLES | FK ROLE_CODE |
| DOC_TYPES | ROLES | FKs APPROVER1_ROLE, APPROVER2_ROLE |
| APPROVALS | DOC_TYPES | FK DOC_TYPE |
| REQUESTS | DEPARTMENTS | FK DEPARTMENT_ID (ALTER TABLE) |
| REQUEST_LINES | REQUESTS | FK REQUEST_ID, ON DELETE CASCADE |
| REQUEST_LINES | ITEMS | FK ITEM_ID |

## View edges

| View | Direct sources | Additional behavior |
|---|---|---|
| USER_ROLES_V | USER_ROLES, ROLES | Role display join |
| APPROVALS_V | APPROVALS, DOC_TYPES | Calls APPROVAL_PKG.CAN_ACT_YN |
| DEPARTMENTS_V | DEPARTMENTS | Projection |
| ITEMS_V | ITEMS | Projection |
| REQUESTS_V | REQUESTS, DEPARTMENTS | Scalar department display lookup |
| REQUEST_LINES_V | REQUEST_LINES, REQUESTS, ITEMS | Scalar request/item display lookups |
| DASH_KPI_V | APPROVALS_V, REQUESTS | CAN_ACT_YN filter; Oracle DUAL |
| DASH_C1_S1_V | REQUESTS | Group by status |
| DASH_C2_S1_V | REQUEST_SUMMARY_V | Sum by department |
| REQUEST_SUMMARY_V | REQUESTS, DEPARTMENTS, REQUEST_LINES | Correlated line count and NVL(SUM(...),0) |

## Package and trigger edges

| Source | Static dependencies | Dynamic/contextual dependencies |
|---|---|---|
| SEC_PKG | USER_ROLES | APEX session context; DB session user |
| DOC_PKG | DOC_TYPES, DOC_SEQ | Period/clock policy |
| APPROVAL_PKG | DOC_TYPES, APPROVALS, SEC_PKG | Configured table/columns, AMOUNT_EXPR, VALIDATE_PROC |
| REQUEST_PKG | REQUEST_LINES | Invoked via DOC_TYPES.VALIDATE_PROC |
| USER_ROLES_TRG | USER_ROLES, SEC_PKG | Principal and clock |
| DEPARTMENTS_TRG | DEPARTMENTS, SEC_PKG | Principal and clock |
| ITEMS_TRG | ITEMS, SEC_PKG | Principal and clock |
| REQUESTS_TRG | REQUESTS, APPROVAL_PKG, DOC_PKG, SEC_PKG | Numbering and bypass state |
| REQUEST_LINES_TRG | REQUEST_LINES, REQUESTS, APPROVAL_PKG, SEC_PKG | Parent-state guard and ORA-04091 cascade handling |

## APEX consumers

- Dashboard 00100: DASH_KPI_V, DASH_C1_S1_V, DASH_C2_S1_V.
- Approval 00190/00191: APPROVALS_V, APPROVAL_PKG; SEC_PKG through authorization.
- Departments 00200/00201: DEPARTMENTS_V, DEPARTMENTS, DEPARTMENTS_TRG.
- Items 00210/00211: ITEMS_V, ITEMS, ITEMS_TRG.
- Requests 00300/00301: REQUESTS_V, REQUESTS, DEPARTMENTS, REQUESTS_TRG.
- Detail request 00302: REQUESTS, REQUESTS_V, REQUEST_LINES_V, REQUEST_LINES_TRG; page absent from APEXLang.
- Request lines 00310/00311: REQUEST_LINES_V, REQUEST_LINES, ITEMS, REQUESTS.
- Summary 00400: REQUEST_SUMMARY_V.
- User roles 00500/00501: USER_ROLES, USER_ROLES_V, ROLES.
- Document types 00510/00511: DOC_TYPES.
- Shared LOVs: departments, items, requests, request lines, roles and status lookup sources.
- Five authorization schemes call SEC_PKG.

## Suggested migration order

1. ROLES, DEPARTMENTS, ITEMS.
2. USER_ROLES, DOC_TYPES, DOC_SEQ.
3. REQUESTS, REQUEST_LINES, APPROVALS after identity/generated-column/FK decisions.
4. SEC_PKG redesign; DOC_PKG atomic numbering; REQUEST_PKG validation.
5. APPROVAL_PKG as a domain workflow service, not a line-by-line package port.
6. Trigger behavior as explicit target invariants.
7. Base views, summary/report views and dashboard aggregates.
8. APEX page/API/UI conversion after page 00302 and critical journeys are resolved.

The DOC_TYPES→DOC_SEQ relation is a logical numbering dependency, not a declared FK. Dynamic AMOUNT_EXPR and VALIDATE_PROC edges are configuration-derived. See the full WP9.2 report for limitations.
