-- APEX2NEXT WP9.4 reviewed business functions for Demo Permintaan Barang (170134).
-- HAND-WRITTEN and reviewed (not generated). Runner format: the migration runner wraps this file in
-- one transaction. Behavior references: docs/migration/wp9.4-business-logic-f170134.md.
--
-- Principal model (replaces APEX APP_USER / SYS_CONTEXT, BR-SEC-01):
--   the API sets the authenticated username per transaction with
--     SELECT set_config('app.username', <username>, true)   -- true = transaction-local
--   and never accepts it from the client. Without it every check below fails closed.
--
-- Deviation DEV-01: APX_DEMO_SEC_PKG.BOOTSTRAP_MODE (every role check passes while no ADMIN exists,
-- WP9.2 finding SEC-001) is intentionally NOT reproduced. The first ADMIN is provisioned explicitly.

SET LOCAL search_path TO app;

-- BR-SEC-01 APP_USER: upper-cased authenticated username, NULL when no principal is set.
CREATE FUNCTION app.current_username() RETURNS text
LANGUAGE sql STABLE PARALLEL SAFE
AS $$ SELECT nullif(upper(btrim(current_setting('app.username', true))), '') $$;

-- BR-SEC-02 HAS_ROLE: the user holds the role or ADMIN.
CREATE FUNCTION app.has_role(p_role text, p_username text DEFAULT NULL) RETURNS boolean
LANGUAGE sql STABLE PARALLEL SAFE
AS $$
  SELECT EXISTS (
    SELECT 1
      FROM app.apx_demo_user_roles ur
     WHERE ur.username = upper(coalesce(p_username, app.current_username()))
       AND ur.role_code IN (upper(p_role), 'ADMIN'))
$$;

-- BR-SEC-03 HAS_ROLE_YN: 'Y'/'N' form for SQL consumers.
CREATE FUNCTION app.has_role_yn(p_role text, p_username text DEFAULT NULL) RETURNS text
LANGUAGE sql STABLE PARALLEL SAFE
AS $$ SELECT CASE WHEN app.has_role(p_role, p_username) THEN 'Y' ELSE 'N' END $$;

-- BR-SEC-04 HAS_ANY_ROLE: the user is registered with at least one role.
CREATE FUNCTION app.has_any_role(p_username text DEFAULT NULL) RETURNS boolean
LANGUAGE sql STABLE PARALLEL SAFE
AS $$
  SELECT EXISTS (
    SELECT 1
      FROM app.apx_demo_user_roles ur
     WHERE ur.username = upper(coalesce(p_username, app.current_username())))
$$;

-- BR-APR-08 CAN_ACT_YN (mirrors APX_DEMO_APPROVAL_PKG.CAN_ACT_YN, install.sql lines 626-645):
--   unknown approval -> 'N'; not PENDING or requested by the current user -> 'N';
--   otherwise HAS_ROLE_YN(approver_role). NULL comparisons follow the Oracle evaluation order.
CREATE FUNCTION app.can_act_yn(p_approval_id bigint) RETURNS text
LANGUAGE sql STABLE PARALLEL SAFE
AS $$
  SELECT coalesce((
    SELECT CASE
             WHEN a.status <> 'PENDING' OR upper(a.requested_by) = app.current_username() THEN 'N'
             WHEN app.has_role(a.approver_role) THEN 'Y'
             ELSE 'N'
           END
      FROM app.apx_demo_approvals a
     WHERE a.approval_id = p_approval_id), 'N')
$$;

COMMENT ON FUNCTION app.current_username() IS 'WP9.4 BR-SEC-01: transaction-local principal set by the API (app.username).';
COMMENT ON FUNCTION app.has_role(text, text) IS 'WP9.4 BR-SEC-02: replaces APX_DEMO_SEC_PKG.HAS_ROLE without bootstrap mode (DEV-01).';
COMMENT ON FUNCTION app.can_act_yn(bigint) IS 'WP9.4 BR-APR-08: replaces APX_DEMO_APPROVAL_PKG.CAN_ACT_YN.';
