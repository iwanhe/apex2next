# WP9.1 — Candidate Pilot Intake: Demo Permintaan Barang

**Assessment date:** 2026-11-07  
**Status:** Static intake completed; pilot qualification incomplete  
**Source handling:** Read-only archive inspection. No SQL, PL/SQL, JavaScript, or deployment script was executed. No database connection was made.

## 1. Candidate source packages

| Package | Observed format | Archive SHA-256 | Files | Uncompressed bytes |
|---|---|---|---:|---:|
| `f170134.zip` | Oracle APEX SQL export | `7c2cc3dcc0304bf12946bafb1684c03db8083b25d40f5c82908fb805faa135bb` | 69 | 340,473 |
| `demo-apexlang(1).zip` | APEXLang source directory | `8d8fb07e2b21674075136d348cd214ca8a4d17984e6d4cc758867f6f4e7832bf` | 38 | 189,625 |

The SQL archive contains SQL text files only. The APEXLang archive contains 30 `.apx` files, 5 PNG assets, 1 JavaScript file and 2 JSON metadata files. A separate combined database install script, `install.sql`, was subsequently supplied and inspected as text. It is not the APEX application export. None of the uploaded source files or archives has been copied into this repository; source artifacts remain outside Git.

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

These are source references from the APEX export. The subsequently supplied `install.sql` provides a combined generated database-install script containing definitions for a subset of these objects; it is static source evidence, not an Oracle dictionary inventory or proof that the script was installed successfully. See section 10 for its exact inventory and remaining gaps.

## 6. Existing parser coverage against this candidate

The current SQL-export parser is a single-text-file static scanner. It is not ZIP-aware and does not follow the `@@` include directives in the APEX export install entry point. The separate database `install.sql` was inspected with read-only text/regex inventory only; it was not passed through the APEX application parser and was not executed.

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
| WP9-004 Oracle schema/metadata | INCOMPLETE | A combined generated DDL script is now supplied; owner-scoped Oracle dictionary inventory, installed-object/status reconciliation, grants and snapshot metadata are still absent. |
| WP9-005 PL/SQL/dependencies | INCOMPLETE | Four package specs/bodies and five trigger sources are present in `install.sql`; dependency reconciliation, semantic review and runtime evidence remain outstanding. |
| WP9-006 Target schema/runtime | NOT VERIFIED | No application-specific target schema or runtime generated. |
| WP9-007 Data migration/reconciliation | NOT VERIFIED | No data snapshot or migration rehearsal. |
| WP9-008 Functional parity | NOT VERIFIED | No approved journeys or paired source/target evidence. |
| WP9-009 Security parity | NOT VERIFIED | Source role schemes are visible, but package implementation and role tests are absent. |
| WP9-010 Performance/operations | NOT VERIFIED | No workload profile or performance evidence. |
| WP9-011 Restore/rollback | NOT VERIFIED | No witnessed restore or rollback evidence. |
| WP9-012 Owner acceptance | NOT VERIFIED | No formal owner approvals supplied. |

**Overall result: INCOMPLETE / NOT QUALIFIED.** The additional database install script materially improves source coverage, but it is not an Oracle dictionary snapshot and does not provide data evidence or runtime behavior. This remains a static source intake, not a completed real-application pilot or production qualification.

## 8. Required evidence to proceed

1. Confirm that both archives are approved for this pilot and provide a sanitization attestation. The basic static scan is not a substitute for security review.
2. Confirm the actual Oracle APEX instance release/build, application ID, parsing schema, and whether the two archives are intended to represent the same application snapshot.
3. Reconcile the supplied `install.sql` against an owner-scoped Oracle dictionary inventory and obtain missing DDL for any referenced object not defined in the script.
4. Confirm whether `install.sql` is the approved source of truth and provide a consistent snapshot identifier; reconcile package, trigger, view and table definitions with the actual source schema.
5. Provide grants/role inventory and approved data snapshot evidence; no credentials are needed for offline intake.
6. Resolve page 00302 and provide the approved critical-journey catalogue, role matrix and expected outcomes.

## 9. Safety and boundaries

- No archive script or embedded SQL/PLSQL/JavaScript was executed.
- No Oracle or PostgreSQL connection was made.
- No credentials, production data, or source archive was committed to Git.
- The archive hashes above identify the exact uploaded packages inspected in this intake.
- The WP9 qualification assessor still requires evidence references and owner approvals; this report does not mark any production gate PASS.


## 10. Supporting database install script — `install.sql`

**Artifact:** user-supplied `install.sql`  
**Size:** 38,098 bytes  
**SHA-256:** `7c71e9c56b76d5fe893d2f357e692b9e7c458adc37791784379842ec1712d66d`  
**Inspection:** read-only static text inventory; no SQL or PL/SQL execution.

The file identifies itself as a generated combined installation script from a Pandawa APEXLang generator. It contains these database definitions:

| Object type | Count | Inventory |
|---|---:|---|
| Tables | 9 | `APX_DEMO_ROLES`, `APX_DEMO_USER_ROLES`, `APX_DEMO_DOC_TYPES`, `APX_DEMO_DOC_SEQ`, `APX_DEMO_APPROVALS`, `APX_DEMO_DEPARTMENTS`, `APX_DEMO_ITEMS`, `APX_DEMO_REQUESTS`, `APX_DEMO_REQUEST_LINES` |
| Views | 10 | `APX_DEMO_APPROVALS_V`, `APX_DEMO_USER_ROLES_V`, `APX_DEMO_DEPARTMENTS_V`, `APX_DEMO_ITEMS_V`, `APX_DEMO_REQUESTS_V`, `APX_DEMO_REQUEST_LINES_V`, `APX_DEMO_DASH_KPI_V`, `APX_DEMO_DASH_C1_S1_V`, `APX_DEMO_DASH_C2_S1_V`, `APX_DEMO_REQUEST_SUMMARY_V` |
| Package specifications | 4 | `APX_DEMO_SEC_PKG`, `APX_DEMO_DOC_PKG`, `APX_DEMO_APPROVAL_PKG`, `APX_DEMO_REQUEST_PKG` |
| Package bodies | 4 | Bodies for the four packages above |
| Triggers | 5 | `APX_DEMO_USER_ROLES_TRG`, `APX_DEMO_DEPARTMENTS_TRG`, `APX_DEMO_ITEMS_TRG`, `APX_DEMO_REQUESTS_TRG`, `APX_DEMO_REQUEST_LINES_TRG` |
| Explicit indexes | 4 | Approval, request department, request-line request, request-line item indexes |
| ALTER TABLE statements | 3 | Request department FK; request-line request FK with cascade; request-line item FK |
| Seed/config DML | 12 INSERT and 7 MERGE statements | Includes role/document configuration and demo data sections |

The nine tables contain 79 declared columns by a conservative line-based inventory. The source includes primary keys, unique constraints, check constraints and foreign keys. There is no standalone `CREATE SEQUENCE` statement; document numbering appears to use the `APX_DEMO_DOC_SEQ` table. The file includes two explicit `COMMIT` statements in its seed/demo-data sections.

### PL/SQL and review flags

- The script contains package specifications and bodies for security, document numbering, approval workflow and request business rules. This directly supplies source bodies that were previously missing from the intake.
- Four `EXECUTE IMMEDIATE` occurrences were detected in the package implementation. These require manual review of dynamic SQL construction, identifier validation, injection exposure and target-language redesign. One call uses `DBMS_ASSERT.QUALIFIED_SQL_NAME` around a configured validation procedure name; this is a useful guard but is not by itself proof of safe semantic equivalence.
- Trigger logic is present and must be mapped to explicit target write-path behavior. Do not blindly translate Oracle trigger side effects into PostgreSQL triggers or application services without business-rule review.
- Views use `CREATE OR REPLACE FORCE VIEW`; compile status and dependency validity are not proven by static source inspection.
- The install script contains configuration/demo DML. Do not execute it against a production schema. Confirm that all seed values are synthetic and review every DML statement before any isolated installation rehearsal.

### Coverage and remaining gaps

The supplied script is valuable DDL/PLSQL source, but it is not equivalent to a live `ALL_OBJECTS`/`ALL_TAB_COLUMNS`/constraints/dependencies/grants inventory. It does not prove that these objects exist, are valid, or match the APEX application's actual parsing schema. It also does not supply production/sanitized business data, source runtime observations, grants/privileges, synonyms, scheduler jobs, database links, or a consistent SCN/snapshot.

Next, compare every APEX-referenced object against this script and an owner-scoped Oracle dictionary export. Review all package and trigger logic, then feed the table DDL through the schema-conversion analyzer and record every unsupported datatype/default/constraint as a diagnostic. No converted DDL should be executed before review.

## 11. Updated intake gate position

- WP9-004 is no longer blocked for lack of all DDL: a generated database install script is available. It remains INCOMPLETE pending dictionary and installed-object reconciliation.
- WP9-005 now has package and trigger source to analyze. It remains INCOMPLETE pending dependency mapping, dynamic-SQL review and semantic validation.
- WP9-003 remains NOT VERIFIED because no archive-aware APEX parser/IR reconciliation has been run.
- WP9-007 remains NOT VERIFIED because no consistent data snapshot or migration rehearsal was supplied.
- Overall WP9 remains NOT QUALIFIED.
