-- DBMS_METADATA DDL export. SQLcl is recommended for CLOB spooling.
-- Usage: define OWNER = 'APP_OWNER'; @ddl_export.sql
-- Output is data only. Never execute exported DDL automatically.

set echo off
set feedback off
set heading off
set pagesize 0
set linesize 32767
set long 100000000
set longchunksize 32767
set trimspool on
set verify off
set markup csv on delimiter , quote on

spool object_ddl.csv
select owner, object_type, object_name,
       dbms_metadata.get_ddl(
         case object_type
           when 'PACKAGE BODY' then 'PACKAGE_BODY'
           when 'TYPE BODY' then 'TYPE_BODY'
           else replace(object_type, ' ', '_')
         end, object_name, owner) ddl_text
from all_objects
where owner = upper('&&OWNER')
  and object_type in ('TABLE','VIEW','MATERIALIZED VIEW','INDEX','SEQUENCE','SYNONYM',
                      'TRIGGER','PROCEDURE','FUNCTION','PACKAGE','PACKAGE BODY','TYPE','TYPE BODY')
order by object_type, object_name;
spool off

set markup csv off
undefine OWNER
