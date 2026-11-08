-- APEX2NEXT WP9.3b — read-only dictionary inventory for APEX SQL Workshop (no SQL*Plus commands).
-- Use when the schema is only reachable through APEX (e.g. oracleapex.com, no SQL*Net/SQLcl).
-- Run as the application parsing schema in SQL Workshop > SQL Commands with "Rows" set to 5000,
-- then copy the whole result grid (header included) into a text file, or download it if offered.
-- Requires Oracle 23ai+ (DATA_DEFAULT_VC, SEARCH_CONDITION_VC). Change the prefix if needed.
with p as (select 'APX\_DEMO\_%' prefix from dual)
select section, obj, item, c1, c2, c3, c4, c5
  from (
select 1 ord, 'SNAPSHOT' section, sys_context('USERENV', 'CURRENT_SCHEMA') obj,
       to_char(systimestamp, 'YYYY-MM-DD"T"HH24:MI:SS.FF3TZH:TZM') item,
       (select max(version_full) from product_component_version) c1,
       sys_context('USERENV', 'DB_NAME') c2, sys_context('USERENV', 'CON_NAME') c3,
       (select to_char(count(*)) from user_objects) c4, null c5, 0 n
  from dual
union all
select 2, 'OBJECT_COUNT', object_type, null, to_char(count(*)),
       to_char(sum(case when object_name like (select prefix from p) escape '\' then 1 else 0 end)),
       to_char(sum(case when status <> 'VALID' then 1 else 0 end)), null, null, 0
  from user_objects group by object_type
union all
select 3, 'OBJECT', object_type, object_name, status,
       to_char(created, 'YYYY-MM-DD"T"HH24:MI:SS'), to_char(last_ddl_time, 'YYYY-MM-DD"T"HH24:MI:SS'),
       generated, null, 0
  from user_objects where object_name like (select prefix from p) escape '\'
union all
select 4, 'COLUMN', table_name, column_name, data_type,
       data_length || ',' || data_precision || ',' || data_scale || ',' || char_used || ',' || char_length,
       nullable || '/' || virtual_column || '/' || identity_column || '/' || default_on_null,
       substr(data_default_vc, 1, 4000), to_char(column_id), column_id
  from user_tab_cols where table_name like (select prefix from p) escape '\' and hidden_column = 'NO'
union all
select 5, 'IDENTITY', table_name, column_name, generation_type, substr(identity_options, 1, 4000),
       null, null, null, 0
  from user_tab_identity_cols where table_name like (select prefix from p) escape '\'
union all
select 6, 'CONSTRAINT', table_name, constraint_name, constraint_type,
       status || '/' || validated || '/' || deferrable || '/' || deferred || '/' || generated,
       r_constraint_name, delete_rule, substr(search_condition_vc, 1, 4000), 0
  from user_constraints where table_name like (select prefix from p) escape '\'
union all
select 7, 'CONS_COLUMN', table_name, constraint_name, column_name, to_char(position), null, null, null, position
  from user_cons_columns where table_name like (select prefix from p) escape '\'
union all
select 8, 'INDEX', table_name, index_name, index_type, uniqueness, status, generated, null, 0
  from user_indexes where table_name like (select prefix from p) escape '\'
union all
select 9, 'IND_COLUMN', table_name, index_name, column_name, to_char(column_position), descend, null, null,
       column_position
  from user_ind_columns where table_name like (select prefix from p) escape '\'
union all
select 10, 'TRIGGER', table_name, trigger_name, trigger_type, triggering_event, status, base_object_type, null, 0
  from user_triggers where table_name like (select prefix from p) escape '\'
union all
select 11, 'DEPENDENCY', type, name, referenced_type, referenced_owner || '.' || referenced_name,
       dependency_type, null, null, 0
  from user_dependencies where name like (select prefix from p) escape '\'
union all
select 12, 'ERROR', type, name, to_char(line) || ':' || to_char(position), attribute,
       substr(text, 1, 4000), null, null, sequence
  from user_errors where name like (select prefix from p) escape '\'
union all
select 13, 'GRANT', type, table_name, grantee, privilege, grantor, grantable, null, 0
  from user_tab_privs where table_name like (select prefix from p) escape '\'
union all
select 14, 'SOURCE_LINES', type, name, to_char(count(*)), to_char(sum(length(text))), null, null, null, 0
  from user_source where name like (select prefix from p) escape '\' group by type, name
)
order by ord, obj, item, n;
