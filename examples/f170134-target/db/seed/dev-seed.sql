-- Development / test seed (NOT production data). Mirrors the configuration of install.sql 06_config_seed
-- (roles, REQ document type) plus test users and two departments/items. Applied through direct DML, the
-- reviewed data-migration path, so audit columns stay empty as they would after a raw load.
INSERT INTO app.apx_demo_roles (role_code, role_name) VALUES
  ('REQUESTER','Requester'), ('MANAGER','Department Manager'), ('DIRECTOR','Director'),
  ('WAREHOUSE','Warehouse'), ('ADMIN','Administrator');
INSERT INTO app.apx_demo_doc_types (doc_type, doc_name, prefix, table_name, pk_column, number_column,
  status_column, amount_expr, validate_proc, approver1_role, approver2_role, level2_limit)
VALUES ('REQ','Permintaan Barang','REQ','APX_DEMO_REQUESTS','REQUEST_ID','REQUEST_NO','STATUS',
  '(select nvl(sum(l.line_amount), 0) from apx_demo_request_lines l where l.request_id = t.request_id)',
  'apx_demo_request_pkg.check_submit','MANAGER','DIRECTOR',10000000);
INSERT INTO app.apx_demo_user_roles (username, role_code) VALUES
  ('ADMIN1','ADMIN'), ('REQ1','REQUESTER'), ('REQ2','REQUESTER'), ('MGR1','MANAGER'), ('MGR1','REQUESTER'),
  ('DIR1','DIRECTOR'), ('WH1','WAREHOUSE');
INSERT INTO app.apx_demo_departments (dept_code, dept_name) VALUES ('OPS','Operations'), ('IT','Information Technology');
INSERT INTO app.apx_demo_items (item_code, item_name, category, uom, std_price) VALUES
  ('ATK-001','Kertas A4 80gsm','ATK','RIM',55000), ('IT-001','Laptop 14 inch','IT','UNIT',12500000);
