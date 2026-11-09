-- APEX2NEXT WP9.6 — read-only data snapshot of application 170134 (Demo Permintaan Barang)
-- Run in APEX SQL Workshop > SQL Commands as the parsing schema (WKSP_KCSI), then Download as CSV.
-- One SELECT = one read-consistent snapshot. Nothing is written. No bind variables or substitutions.
--
-- Columns: SECTION, OBJ, PK, DOC (JSON text), SHA256 (of DOC, computed in Oracle to detect transport damage)
--   SNAPSHOT  session/NLS/time facts, APP_USER as the source packages see it
--   COUNT     row count per table and view
--   IDENTITY  identity sequence state (high-water mark for post-load alignment)
--   ROW       every row of the 9 tables (JSON_OBJECT(*), NULL ON NULL)
--   VIEW      every row of the 10 views, for parity of view logic on the migrated data
select section, obj, pk, doc, lower(rawtohex(standard_hash(doc, 'SHA256'))) sha256
  from (
select 'SNAPSHOT' section, 'SESSION' obj, '-' pk,
       json_object(
         'db_user'           value user,
         'apex_app_user'     value sys_context('APEX$SESSION', 'APP_USER'),
         'pkg_app_user'      value apx_demo_sec_pkg.app_user,
         'sysdate'           value to_char(sysdate, 'YYYY-MM-DD"T"HH24:MI:SS'),
         'systimestamp'      value to_char(systimestamp, 'YYYY-MM-DD"T"HH24:MI:SS.FF6TZH:TZM'),
         'dbtimezone'        value dbtimezone,
         'sessiontimezone'   value sessiontimezone,
         'nls_date_format'   value (select value from nls_session_parameters where parameter = 'NLS_DATE_FORMAT'),
         'nls_numeric_chars' value (select value from nls_session_parameters where parameter = 'NLS_NUMERIC_CHARACTERS'),
         'nls_sort'          value (select value from nls_session_parameters where parameter = 'NLS_SORT'),
         'nls_language'      value (select value from nls_session_parameters where parameter = 'NLS_LANGUAGE'),
         'db_charset'        value (select value from nls_database_parameters where parameter = 'NLS_CHARACTERSET')
         null on null returning varchar2(4000)) doc
  from dual
-- row counts -------------------------------------------------------------------------------
union all select 'COUNT', 'APX_DEMO_ROLES', '-', to_char(count(*)) from apx_demo_roles
union all select 'COUNT', 'APX_DEMO_USER_ROLES', '-', to_char(count(*)) from apx_demo_user_roles
union all select 'COUNT', 'APX_DEMO_DOC_TYPES', '-', to_char(count(*)) from apx_demo_doc_types
union all select 'COUNT', 'APX_DEMO_DOC_SEQ', '-', to_char(count(*)) from apx_demo_doc_seq
union all select 'COUNT', 'APX_DEMO_APPROVALS', '-', to_char(count(*)) from apx_demo_approvals
union all select 'COUNT', 'APX_DEMO_DEPARTMENTS', '-', to_char(count(*)) from apx_demo_departments
union all select 'COUNT', 'APX_DEMO_ITEMS', '-', to_char(count(*)) from apx_demo_items
union all select 'COUNT', 'APX_DEMO_REQUESTS', '-', to_char(count(*)) from apx_demo_requests
union all select 'COUNT', 'APX_DEMO_REQUEST_LINES', '-', to_char(count(*)) from apx_demo_request_lines
union all select 'COUNT', 'APX_DEMO_USER_ROLES_V', '-', to_char(count(*)) from apx_demo_user_roles_v
union all select 'COUNT', 'APX_DEMO_DEPARTMENTS_V', '-', to_char(count(*)) from apx_demo_departments_v
union all select 'COUNT', 'APX_DEMO_ITEMS_V', '-', to_char(count(*)) from apx_demo_items_v
union all select 'COUNT', 'APX_DEMO_REQUESTS_V', '-', to_char(count(*)) from apx_demo_requests_v
union all select 'COUNT', 'APX_DEMO_REQUEST_LINES_V', '-', to_char(count(*)) from apx_demo_request_lines_v
union all select 'COUNT', 'APX_DEMO_REQUEST_SUMMARY_V', '-', to_char(count(*)) from apx_demo_request_summary_v
union all select 'COUNT', 'APX_DEMO_APPROVALS_V', '-', to_char(count(*)) from apx_demo_approvals_v
union all select 'COUNT', 'APX_DEMO_DASH_C1_S1_V', '-', to_char(count(*)) from apx_demo_dash_c1_s1_v
union all select 'COUNT', 'APX_DEMO_DASH_C2_S1_V', '-', to_char(count(*)) from apx_demo_dash_c2_s1_v
union all select 'COUNT', 'APX_DEMO_DASH_KPI_V', '-', to_char(count(*)) from apx_demo_dash_kpi_v
-- identity sequences ------------------------------------------------------------------------
union all
select 'IDENTITY', c.table_name, c.column_name,
       json_object('sequence' value c.sequence_name, 'last_number' value s.last_number,
                   'increment_by' value s.increment_by, 'cache_size' value s.cache_size,
                   'generation_type' value c.generation_type null on null returning varchar2(4000))
  from user_tab_identity_cols c
  join user_sequences s on s.sequence_name = c.sequence_name
 where c.table_name like 'APX\_DEMO\_%' escape '\'
-- table rows --------------------------------------------------------------------------------
union all select 'ROW', 'APX_DEMO_ROLES', role_code, json_object(* null on null returning varchar2(4000)) from apx_demo_roles
union all select 'ROW', 'APX_DEMO_USER_ROLES', to_char(user_role_id), json_object(* null on null returning varchar2(4000)) from apx_demo_user_roles
union all select 'ROW', 'APX_DEMO_DOC_TYPES', doc_type, json_object(* null on null returning varchar2(4000)) from apx_demo_doc_types
union all select 'ROW', 'APX_DEMO_DOC_SEQ', doc_type || '|' || period, json_object(* null on null returning varchar2(4000)) from apx_demo_doc_seq
union all select 'ROW', 'APX_DEMO_APPROVALS', to_char(approval_id), json_object(* null on null returning varchar2(4000)) from apx_demo_approvals
union all select 'ROW', 'APX_DEMO_DEPARTMENTS', to_char(department_id), json_object(* null on null returning varchar2(4000)) from apx_demo_departments
union all select 'ROW', 'APX_DEMO_ITEMS', to_char(item_id), json_object(* null on null returning varchar2(4000)) from apx_demo_items
union all select 'ROW', 'APX_DEMO_REQUESTS', to_char(request_id), json_object(* null on null returning varchar2(4000)) from apx_demo_requests
union all select 'ROW', 'APX_DEMO_REQUEST_LINES', to_char(line_id), json_object(* null on null returning varchar2(4000)) from apx_demo_request_lines
-- view rows (as seen by the APP_USER in SNAPSHOT) -------------------------------------------
union all select 'VIEW', 'APX_DEMO_USER_ROLES_V', to_char(user_role_id), json_object(* null on null returning varchar2(4000)) from apx_demo_user_roles_v
union all select 'VIEW', 'APX_DEMO_DEPARTMENTS_V', to_char(department_id), json_object(* null on null returning varchar2(4000)) from apx_demo_departments_v
union all select 'VIEW', 'APX_DEMO_ITEMS_V', to_char(item_id), json_object(* null on null returning varchar2(4000)) from apx_demo_items_v
union all select 'VIEW', 'APX_DEMO_REQUESTS_V', to_char(request_id), json_object(* null on null returning varchar2(4000)) from apx_demo_requests_v
union all select 'VIEW', 'APX_DEMO_REQUEST_LINES_V', to_char(line_id), json_object(* null on null returning varchar2(4000)) from apx_demo_request_lines_v
union all select 'VIEW', 'APX_DEMO_REQUEST_SUMMARY_V', request_no, json_object(* null on null returning varchar2(4000)) from apx_demo_request_summary_v
union all select 'VIEW', 'APX_DEMO_APPROVALS_V', to_char(approval_id), json_object(* null on null returning varchar2(4000)) from apx_demo_approvals_v
union all select 'VIEW', 'APX_DEMO_DASH_C1_S1_V', label, json_object(* null on null returning varchar2(4000)) from apx_demo_dash_c1_s1_v
union all select 'VIEW', 'APX_DEMO_DASH_C2_S1_V', label, json_object(* null on null returning varchar2(4000)) from apx_demo_dash_c2_s1_v
union all select 'VIEW', 'APX_DEMO_DASH_KPI_V', to_char(seq), json_object(* null on null returning varchar2(4000)) from apx_demo_dash_kpi_v
)
 order by section, obj, pk
