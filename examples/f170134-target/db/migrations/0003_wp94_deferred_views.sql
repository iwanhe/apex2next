-- APEX2NEXT deferred view migration (generated DRAFT; review required)
-- Source: install.sql sha256:7c71e9c56b76d5fe893d2f357e692b9e7c458adc37791784379842ec1712d66d
-- Requires the reviewed target functions below to exist before this migration runs:
--   apx_demo_approval_pkg.can_act_yn -> app.can_act_yn  (provided by 0002_wp94_business_functions.sql)

SET LOCAL search_path TO app;

CREATE VIEW app.apx_demo_approvals_v AS
select a.approval_id
      ,a.doc_type
      ,d.doc_name
      ,a.doc_id
      ,a.doc_no
      ,a.approval_level
      ,a.approver_role
      ,a.amount
      ,a.requested_by
      ,a.requested_on
      ,a.status
      ,a.acted_by
      ,a.acted_on
      ,a.note
      ,app.can_act_yn(a.approval_id) can_act_yn
  from apx_demo_approvals a
  join apx_demo_doc_types d on d.doc_type = a.doc_type;
CREATE VIEW app.apx_demo_dash_kpi_v AS
select 1 seq
      ,'fa-check-square-o' icon
      ,'Approval Menunggu Anda' label
      ,(select count(*) from apx_demo_approvals_v where status = 'PENDING' and can_act_yn = 'Y') metric_value

union all
select 2 seq
      ,'fa-file-o' icon
      ,'Permintaan Draft' label
      ,(select count(*) from apx_demo_requests where status = 'DRAFT') metric_value

union all
select 3 seq
      ,'fa-clock-o' icon
      ,'Menunggu Approval' label
      ,(select count(*) from apx_demo_requests where status = 'SUBMITTED') metric_value;
