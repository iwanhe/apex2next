-- WP9-009: temporary passwords are handed over by e-mail (owner decision 2026-11-10), so they expire.
-- Set by the operator CLI on create/reset (TEMP_PASSWORD_HOURS, default 72); cleared when the user changes the password.
ALTER TABLE iam.accounts ADD COLUMN IF NOT EXISTS temp_password_expires_at timestamptz;
