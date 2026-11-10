import { Inject, Injectable } from '@nestjs/common';
import { PostgresDatabase } from '../database/postgres-database';
import { BusinessRuleError, errors } from '../business/errors';
import type { AuthConfig } from './auth.config';
import { AUTH_CONFIG } from './auth.tokens';
import { checkPolicy, dummyHash, hashPassword, verifyPassword } from './password';

/** APEX login message for wrong credentials (Oracle APEX Accounts, language en); also used for locked/inactive accounts. */
export const INVALID_LOGIN = 'Invalid Login Credentials';

interface AccountRow {
  username: string;
  password_hash: string;
  must_change_password: boolean;
  active: boolean;
  failed_attempts: number;
  locked: boolean;
  temp_expired: boolean;
  session_version: number;
}

export interface LoginResult { readonly username: string; readonly sessionVersion: number; readonly mustChangePassword: boolean }

/**
 * Local accounts in schema iam (WP9-009). Every outcome is written to iam.account_events; passwords never are.
 * Unknown, inactive and locked accounts get the same answer and take the same time as a wrong password.
 */
@Injectable()
export class AccountsService {
  constructor(private readonly db: PostgresDatabase, @Inject(AUTH_CONFIG) private readonly config: AuthConfig) {}

  private async find(username: string): Promise<AccountRow | null> {
    const r = await this.db.query<AccountRow>(
      `SELECT username, password_hash, must_change_password, active, failed_attempts,
              coalesce(locked_until > now(), false) AS locked,
              (must_change_password AND coalesce(temp_password_expires_at <= now(), false)) AS temp_expired, session_version
         FROM iam.accounts WHERE username = $1`, [username]);
    return r.rows[0] ?? null;
  }

  private event(username: string, event: string, actor: string, detail: string | null = null) {
    return this.db.query('INSERT INTO iam.account_events (username, event, actor, detail) VALUES ($1, $2, $3, $4)',
      [username, event, actor, detail]);
  }

  async login(username: string, password: string): Promise<LoginResult> {
    const account = username ? await this.find(username) : null;
    const ok = await verifyPassword(password, account?.password_hash ?? await dummyHash());
    if (!account) throw invalid();
    if (!account.active || account.locked) {
      await this.event(account.username, 'LOGIN_FAILED', account.username, account.active ? 'locked' : 'inactive');
      throw invalid();
    }
    if (ok && account.temp_expired) {
      // temporary passwords travel by e-mail, so they expire (TEMP_PASSWORD_HOURS); the operator issues a new one
      await this.event(account.username, 'LOGIN_FAILED', account.username, 'temporary password expired');
      throw invalid();
    }
    if (!ok) {
      // After max failures the account locks for lockMinutes and the counter restarts, so an expired lock gives a
      // fresh set of attempts. (APEX workspace accounts lock until an administrator unlocks them; see WP9-009 doc.)
      const r = await this.db.query<{ failed_attempts: number; locked: boolean }>(
        `UPDATE iam.accounts
            SET failed_attempts = CASE WHEN failed_attempts + 1 >= $2 THEN 0 ELSE failed_attempts + 1 END,
                locked_until = CASE WHEN failed_attempts + 1 >= $2 THEN now() + make_interval(mins => $3) END
          WHERE username = $1
        RETURNING failed_attempts, locked_until IS NOT NULL AS locked`,
        [account.username, this.config.maxFailedLogins, this.config.lockMinutes]);
      const { failed_attempts: n, locked } = r.rows[0];
      await this.event(account.username, 'LOGIN_FAILED', account.username, `attempt ${locked ? this.config.maxFailedLogins : n}`);
      if (locked) await this.event(account.username, 'LOCKED', 'SYSTEM', `${this.config.lockMinutes} min`);
      throw invalid();
    }
    await this.db.query(
      `UPDATE iam.accounts SET failed_attempts = 0,
              locked_until = NULL, last_login_at = now() WHERE username = $1`, [account.username]);
    await this.event(account.username, 'LOGIN_OK', account.username);
    return { username: account.username, sessionVersion: account.session_version, mustChangePassword: account.must_change_password };
  }

  /** The session is still valid: the account exists, is active and not locked, and the token's version is current. */
  async sessionValid(username: string, version: number | undefined): Promise<boolean> {
    const a = await this.find(username);
    return !!a && a.active && !a.locked && a.session_version === version;
  }

  async changePassword(username: string, current: string, next: string, confirm: string): Promise<LoginResult> {
    const account = await this.find(username);
    if (!account || !account.active) throw errors.unauthenticated();
    const fieldErrors: { field: string; message: string }[] = [];
    if (!(await verifyPassword(current, account.password_hash))) {
      fieldErrors.push({ field: 'current_password', message: 'Password lama salah.' });
    }
    for (const m of checkPolicy({ minLength: this.config.passwordMinLength }, username, next, current)) {
      fieldErrors.push({ field: 'new_password', message: m });
    }
    if (next !== confirm) fieldErrors.push({ field: 'confirm_password', message: 'Konfirmasi password tidak sama.' });
    if (fieldErrors.length) {
      throw new BusinessRuleError('VALIDATION_FAILED', fieldErrors.map((f) => f.message).join('\n'), null, 'BR-SEC-07', fieldErrors);
    }
    const r = await this.db.query<{ session_version: number }>(
      `UPDATE iam.accounts SET password_hash = $2, must_change_password = false, temp_password_expires_at = NULL, password_changed_at = now(),
              session_version = session_version + 1, updated_by = $1, updated_at = now()
        WHERE username = $1 RETURNING session_version`, [username, await hashPassword(next)]);
    await this.event(username, 'PASSWORD_CHANGED', username);
    return { username, sessionVersion: r.rows[0].session_version, mustChangePassword: false };
  }

  /** Sign Out: every token of the account stops working (tokens are stateless, so this ends all its sessions). */
  async logout(username: string): Promise<void> {
    await this.db.query('UPDATE iam.accounts SET session_version = session_version + 1 WHERE username = $1', [username]);
    await this.event(username, 'LOGOUT', username);
  }
}

function invalid() {
  return new BusinessRuleError('UNAUTHENTICATED', INVALID_LOGIN, null, 'BR-SEC-01');
}
