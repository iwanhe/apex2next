/**
 * Authentication configuration. Replaces the APEX "Oracle APEX Accounts" scheme.
 *
 * AUTH_MODE=local (WP9-009, owner decision 2026-11-10): accounts in schema iam with scrypt password hashes,
 * forced change of the temporary password, lockout after repeated failures, a per-client login rate limit and
 * server-side session revocation (session_version). The APEX authorization schemes still decide what a signed-in
 * user may see (APP_USERS rejects users without roles, exactly like the source).
 * AUTH_MODE=dev: any username with one shared DEV_LOGIN_PASSWORD; tests and parity runs only.
 * The configuration fails closed:
 *   - AUTH_MODE unset or unknown -> the API refuses to start;
 *   - AUTH_MODE=dev with NODE_ENV=production -> refused;
 *   - SESSION_SECRET shorter than 32 characters, DEV_LOGIN_PASSWORD (dev) shorter than 12 -> refused.
 */
export interface AuthConfig {
  readonly mode: 'dev' | 'local';
  readonly sessionSecret: string;
  /** dev mode only. */
  readonly devPassword: string;
  /** Session lifetime in seconds (APEX default maximum session length: 8 hours). */
  readonly sessionTtlSeconds: number;
  /** local mode: failed logins before the account locks, lock duration, password minimum length. */
  readonly maxFailedLogins: number;
  readonly lockMinutes: number;
  readonly passwordMinLength: number;
  /** Login attempts per client per minute (local mode); the client is the socket address or, with TRUST_PROXY=1, x-forwarded-for. */
  readonly loginRatePerMinute: number;
  readonly trustProxy: boolean;
}

function int(env: NodeJS.ProcessEnv, key: string, fallback: number, min: number, max: number): number {
  const v = Number(env[key] ?? fallback);
  if (!Number.isInteger(v) || v < min || v > max) throw new Error(`${key} must be an integer between ${min} and ${max}.`);
  return v;
}

export function authConfigFromEnv(env: NodeJS.ProcessEnv = process.env): AuthConfig {
  const mode = env.AUTH_MODE;
  if (mode !== 'dev' && mode !== 'local') {
    throw new Error('AUTH_MODE must be "local" (accounts in schema iam) or "dev" (tests only).');
  }
  if (mode === 'dev' && env.NODE_ENV === 'production') {
    throw new Error('AUTH_MODE=dev is refused when NODE_ENV=production.');
  }
  const sessionSecret = env.SESSION_SECRET ?? '';
  if (sessionSecret.length < 32) throw new Error('SESSION_SECRET must be at least 32 characters.');
  const devPassword = mode === 'dev' ? env.DEV_LOGIN_PASSWORD ?? '' : '';
  if (mode === 'dev' && devPassword.length < 12) throw new Error('DEV_LOGIN_PASSWORD must be at least 12 characters.');
  return {
    mode, sessionSecret, devPassword,
    sessionTtlSeconds: int(env, 'SESSION_TTL_SECONDS', 8 * 3600, 60, 24 * 3600),
    maxFailedLogins: int(env, 'LOGIN_MAX_FAILURES', 5, 3, 20),
    lockMinutes: int(env, 'LOGIN_LOCK_MINUTES', 15, 1, 1440),
    passwordMinLength: int(env, 'PASSWORD_MIN_LENGTH', 10, 8, 64),
    loginRatePerMinute: int(env, 'LOGIN_RATE_PER_MINUTE', 20, 1, 1000),
    trustProxy: env.TRUST_PROXY === '1',
  };
}
