# WP9.1 — Candidate Pilot Intake: Demo Permintaan Barang

**Assessment date:** 2026-11-07  
**Status:** Static intake completed; pilot qualification incomplete  
**Source handling:** Read-only archive inspection. No SQL, PL/SQL, JavaScript, or deployment script was executed. No database connection was made.

## 1. Candidate source packages

| Package | Observed format | Archive SHA-256 | Files | Uncompressed bytes |
|---|---|---|---:|---:|
| `f170134.zip` | Oracle APEX SQL export | `7c2cc3dcc0304bf12946bafb1684c03db8083b25d40f5c82908fb805faa135bb` | 69 | 340,473 |
| `demo-apexlang(1).zip` | APEXLang source directory | `8d8fb07e2b21674075136d348cd214ca8a4d17984e6d4cc758867f6f4e7832bf` | 38 | 189,625 |

The SQL archive contains SQL text files only. The APEXLang archive contains 30 `.apx` files, 5 PNG assets, 1 JavaScript file and 2 JSON metadata files. Neither archive has been copied into this repository; source archives and their contents remain outside Git.

## 2. Application identity and version evidence

| Attribute | Evidence |
|---|---|
| Application ID | `170134` |
| Application name | Demo Permintaan Barang |
| Application alias | `DEMO` |
| Export release | `26.2.1` |
| Export build date metadata | `2026.04.07` |
| Compatibility mode | `26.1` |
| Parsing schema owner in export default | `WKSP_KCSI` |
| APEXLang `mmdVersion` | `26.2.0+3479` |

The APEX SQL export declares release `26.2.1`. This is source-export metadata; confirm the actual source instance runtime/build and parsing schema with the application owner before treating it as authoritative runtime evidence. APEXLang `mmdVersion` is metadata for the APEXLang source format and is not itself proof of the source instance runtime.

## 3. Page inventory

The SQL export contains 19 page files, including Global Page and Login Page. The APEXLang archive contains 18 page definitions.

| Page | Name |
|---:|---|
| 00000 | Global Page |
| 00100 | Home |
| 00190 | Approval Inbox |
| 00191 | Approval |
| 00200 | Departments |
| 00201 | Department |
| 00210 | Items |
| 00211 | Item |
| 00300 | Permintaan Barang |
| 00301 | Permintaan Barang |
| 00302 | Detail Permintaan |
| 00310 | Baris Permintaan |
| 00311 | Baris Permintaan |
| 00400 | Rekap Permintaan |
| 00500 | Users & Roles |
| 00501 | User Role |
| 00510 | Document Types & Approval |
| 00511 | Document Type |
| 09999 | Login Page |

**Cross-format discrepancy:** page `00302` (`Detail Permintaan`) exists in the SQL export but is absent from the supplied APEXLang archive. The page inventories must not be treated as equivalent until this difference is explained and reconciled. The other 18 page IDs match.

## 4. Static component inventory

Counts below are occurrences of APEX export API calls across the SQL files. They are useful inventory evidence, not proof that every component's full properties, relationships or behavior have been understood.

| Component/API family | Calls |
|---|---:|
| Pages | 19 |
| Regions | 39 |
| Page items | 54 |
| Buttons | 34 |
| Processes | 27 |
| Dynamic-action events | 17 |
| Dynamic-action actions | 17 |
| Validations | 1 |
| Interactive worksheets | 6 |
| Worksheet columns | 46 |
| Report regions | 1 |
| Report columns | 25 |
| JET charts | 2 |
| JET chart series | 2 |
| JET chart axes | 2 |
| Cards | 1 |
| Card actions | 1 |
| Shared LOV definitions (`create_list_of_values`) | 8 |
| Static LOV data calls | 12 |
| Authorization schemes (`create_security_scheme`) | 5 |
| Authentication schemes | 1 |
| Application static files | 6 |
| Page groups | 5 |
| Lists | 2 |
| List entries | 17 |

The export includes an Oracle APEX Accounts authentication scheme and five PL/SQL-function authorization schemes: `ADMIN_RIGHTS`, `APP_USERS`, `MASTER_DATA`, `REQUESTER`, and `WAREHOUSE`. These call functions in `APX_DEMO_SEC_PKG`; their effective authorization semantics cannot be established from the APEX export alone.

## 5. Database and PL/SQL dependency candidates

The application source references the following database identifiers:

- Tables or table-like objects: `APX_DEMO_DEPARTMENTS`, `APX_DEMO_ITEMS`, `APX_DEMO_REQUESTS`, `APX_DEMO_REQUEST_LINES`, `APX_DEMO_ROLES`, `APX_DEMO_USER_ROLES`, `APX_DEMO_DOC_TYPES`.
- Views or view-like objects: `APX_DEMO_DASH_C1_S1_V`, `APX_DEMO_DASH_C2_S1_V`, `APX_DEMO_DASH_KPI_V`, `APX_DEMO_APPROVALS_V`, `APX_DEMO_DEPARTMENTS_V`, `APX_DEMO_ITEMS_V`, `APX_DEMO_REQUESTS_V`, `APX_DEMO_REQUEST_LINES_V`, `APX_DEMO_REQUEST_SUMMARY_V`, `APX_DEMO_USER_ROLES_V`.
- PL/SQL package candidates: `APX_DEMO_APPROVAL_PKG`, `APX_DEMO_SEC_PKG`.
- Trigger-name candidates also appear in source references, including `APX_DEMO_DEPARTMENTS_TRG`, `APX_DEMO_ITEMS_TRG`, `APX_DEMO_REQUEST_LINES_TRG`, and `APX_DEMO_REQUESTS_TRG`.

These are source references, not a verified Oracle object inventory. The archive contains **zero CREATE TABLE/VIEW/PACKAGE/PROCEDURE/FUNCTION/TRIGGER/SEQUENCE/TYPE DDL statements** and no supporting-object DDL package. Package bodies, table definitions, view definitions, triggers, constraints, indexes, sequences, grants and data are therefore not available for conversion or reconciliation.

## 6. Existing parser coverage against this candidate

The current SQL-export parser is a single-text-file static scanner. It is not ZIP-aware and does not follow the `@@` include directives in `install.sql`. The archive was therefore inventoried without claiming an end-to-end parser execution.

A source-level routine inventory found 42 distinct `wwv_flow_imp*` routine names. The current `OBJECT_TYPES` map recognizes 12 routine names that occur in this export, including page, region, item, button, process, dynamic-action, validation, list/list-entry, authentication and theme declarations. Important encountered calls are not yet modeled, including:

- `create_security_scheme` (5)
- `create_list_of_values` (8)
- `create_worksheet` (6) and `create_worksheet_column` (46)
- `create_report_region` (1) and `create_report_columns` (25)
- `create_jet_chart` / series / axis
- `create_card` / `create_card_action`
- `create_page_group`, `create_plugin_setting`, `create_static_lov_data`, `create_app_static_file`, and other shared-component routines.

The parser's current call prefix also does not include the export's `wwv_imp_workspace.create_flow` application declaration. Generic helpers such as `wwv_flow_imp.id`, `g_varchar2_table`, and `component_begin` are not application components and must not be counted as semantic coverage. A raw ratio of mapped calls to all lexical calls would be misleading.

**WP9.1 parser conclusion:** the current parser can recognize a useful subset of page-level declarations, but the archive intake adapter, complete shared-component taxonomy, page/region/process relationships, security-scheme extraction and parser-vs-source reconciliation need further implementation. No semantic conversion or parity claim is made.

## 7. Intake gate assessment

| Gate | Current assessment | Reason |
|---|---|---|
| WP9-001 Source package intake/integrity | INCOMPLETE | Archive hashes and inventories recorded; formal sanitization attestation and chain-of-custody approval not supplied. |
| WP9-002 Runtime/version/scope | INCOMPLETE | Export metadata identifies app and release; actual instance runtime, owner and scope need confirmation. |
| WP9-003 Extraction/IR | NOT VERIFIED | No archive-aware parser execution or IR reconciliation yet. |
| WP9-004 Oracle schema/metadata | BLOCKED | No Oracle dictionary inventory or DDL supplied. |
| WP9-005 PL/SQL/dependencies | BLOCKED | Package and trigger implementations are missing. |
| WP9-006 Target schema/runtime | NOT VERIFIED | No application-specific target schema or runtime generated. |
| WP9-007 Data migration/reconciliation | NOT VERIFIED | No data snapshot or migration rehearsal. |
| WP9-008 Functional parity | NOT VERIFIED | No approved journeys or paired source/target evidence. |
| WP9-009 Security parity | NOT VERIFIED | Source role schemes are visible, but package implementation and role tests are absent. |
| WP9-010 Performance/operations | NOT VERIFIED | No workload profile or performance evidence. |
| WP9-011 Restore/rollback | NOT VERIFIED | No witnessed restore or rollback evidence. |
| WP9-012 Owner acceptance | NOT VERIFIED | No formal owner approvals supplied. |

**Overall result: INCOMPLETE / NOT QUALIFIED.** This is a candidate source intake and static inventory, not a completed real-application pilot or production qualification.

## 8. Required evidence to proceed

1. Confirm that both archives are approved for this pilot and provide a sanitization attestation. The basic static scan is not a substitute for security review.
2. Confirm the actual Oracle APEX instance release/build, application ID, parsing schema, and whether the two archives are intended to represent the same application snapshot.
3. Supply a reviewed schema-only DDL export or `DBMS_METADATA.GET_DDL` output for all referenced tables, views, packages, triggers, sequences, constraints and indexes.
4. Supply package specs/bodies for `APX_DEMO_APPROVAL_PKG` and `APX_DEMO_SEC_PKG`, plus the actual trigger and view definitions.
5. Supply owner-scoped Oracle dictionary inventory and a consistent snapshot identifier. No credentials are needed for offline intake.
6. Resolve page 00302 and provide the approved critical-journey catalogue, role matrix and expected outcomes.

## 9. Safety and boundaries

- No archive script or embedded SQL/PLSQL/JavaScript was executed.
- No Oracle or PostgreSQL connection was made.
- No credentials, production data, or source archive was committed to Git.
- The archive hashes above identify the exact uploaded packages inspected in this intake.
- The WP9 qualification assessor still requires evidence references and owner approvals; this report does not mark any production gate PASS.
