-- Roles of the local accounts (replaces the APEX access control list: Administration > Manage User Access).
-- Authorization schemes of type "is in role or group" are evaluated against this table.
-- Granted with: node apps/api/scripts/accounts.mjs grant <username> <ROLE>
CREATE TABLE IF NOT EXISTS iam.account_roles (
    username   varchar(255) NOT NULL REFERENCES iam.accounts (username) ON DELETE CASCADE,
    role       varchar(255) NOT NULL,
    granted_by varchar(255) NOT NULL,
    granted_at timestamptz  NOT NULL DEFAULT now(),
    PRIMARY KEY (username, role),
    CONSTRAINT account_roles_role_ck CHECK (role = upper(btrim(role)) AND role <> '')
);
ALTER TABLE iam.account_events DROP CONSTRAINT IF EXISTS account_events_event_ck;
ALTER TABLE iam.account_events ADD CONSTRAINT account_events_event_ck CHECK (event IN ('CREATED', 'LOGIN_OK',
    'LOGIN_FAILED', 'LOCKED', 'UNLOCKED', 'PASSWORD_CHANGED', 'PASSWORD_RESET', 'LOGOUT', 'SESSIONS_REVOKED',
    'DEACTIVATED', 'ACTIVATED', 'ROLE_GRANTED', 'ROLE_REVOKED'));
