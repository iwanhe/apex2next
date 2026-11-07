-- Read-only, owner-scoped Oracle inventory for SQLcl / SQL*Plus.
-- Usage: define OWNER = 'APP_OWNER'; @dictionary_inventory.sql
-- ALL_* views expose only metadata visible to the current session.

set echo off
set feedback off
set heading on
set pagesize 50000
set linesize 32767
set trimspool on
set verify off
set markup csv on delimiter , quote on

spool dictionary_objects.csv
select owner, object_type, object_name, status,
       to_char(last_ddl_time, 'YYYY-MM-DD"T"HH24:MI:SS') last_ddl_time,
       cast(null as varchar2(512)) ddl_file
from all_objects
where owner = upper('&&OWNER')
order by owner, object_type, object_name;
spool off

spool dictionary_columns.csv
select owner, table_name, column_id, column_name, data_type, data_length,
       data_precision, data_scale, nullable, char_length, char_used,
       data_default, virtual_column, identity_column
from all_tab_columns where owner = upper('&&OWNER')
order by owner, table_name, column_id;
spool off

spool dictionary_constraints.csv
select owner, table_name, constraint_name, constraint_type, status,
       validated, deferrable, deferred, delete_rule, r_owner, r_constraint_name
from all_constraints where owner = upper('&&OWNER')
order by owner, table_name, constraint_name;
spool off

spool dictionary_indexes.csv
select owner, index_name, table_owner, table_name, uniqueness, status,
       index_type, tablespace_name, partitioned
from all_indexes where owner = upper('&&OWNER')
order by owner, table_name, index_name;
spool off

spool dictionary_dependencies.csv
select owner, name, type, referenced_owner, referenced_name, referenced_type, dependency_type
from all_dependencies where owner = upper('&&OWNER')
order by owner, name, type, referenced_owner, referenced_name;
spool off

spool dictionary_partitions.csv
select table_owner owner, table_name, partition_name, partition_position,
       tablespace_name, num_rows, last_analyzed
from all_tab_partitions where table_owner = upper('&&OWNER')
order by table_owner, table_name, partition_position;
spool off

spool dictionary_grants.csv
select owner, table_name, grantee, privilege, grantable, type
from all_tab_privs where owner = upper('&&OWNER')
order by owner, table_name, grantee, privilege;
spool off

spool dictionary_synonyms.csv
select owner, synonym_name, table_owner, table_name, db_link
from all_synonyms where owner = upper('&&OWNER')
order by owner, synonym_name;
spool off

set markup csv off
undefine OWNER
