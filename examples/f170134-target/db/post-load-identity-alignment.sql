-- APEX2NEXT WP9.3 post-load identity/sequence alignment (run after data load, before writes)
BEGIN;
SELECT setval(pg_get_serial_sequence('app.apx_demo_user_roles', 'user_role_id'), GREATEST(COALESCE((SELECT max(user_role_id) FROM app.apx_demo_user_roles), 0) + 1, 1), false);
SELECT setval(pg_get_serial_sequence('app.apx_demo_approvals', 'approval_id'), GREATEST(COALESCE((SELECT max(approval_id) FROM app.apx_demo_approvals), 0) + 1, 1), false);
SELECT setval(pg_get_serial_sequence('app.apx_demo_departments', 'department_id'), GREATEST(COALESCE((SELECT max(department_id) FROM app.apx_demo_departments), 0) + 1, 1), false);
SELECT setval(pg_get_serial_sequence('app.apx_demo_items', 'item_id'), GREATEST(COALESCE((SELECT max(item_id) FROM app.apx_demo_items), 0) + 1, 1), false);
SELECT setval(pg_get_serial_sequence('app.apx_demo_requests', 'request_id'), GREATEST(COALESCE((SELECT max(request_id) FROM app.apx_demo_requests), 0) + 1, 1), false);
SELECT setval(pg_get_serial_sequence('app.apx_demo_request_lines', 'line_id'), GREATEST(COALESCE((SELECT max(line_id) FROM app.apx_demo_request_lines), 0) + 1, 1), false);
COMMIT;
