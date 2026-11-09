/**
 * WP9.5 authentication configuration. Replaces the APEX "Oracle APEX Accounts" scheme for the pilot.
 *
 * The production identity provider is decided in WP9-009. Until then only AUTH_MODE=dev exists: any
 * username signs in with one shared DEV_LOGIN_PASSWORD (as a workspace account would), and the APEX
 * authorization schemes then decide what the user may see (APP_USERS rejects users without roles,
 * exactly like the source). The configuration fails closed:
 *   - AUTH_MODE unset or unknown -> the API refuses to start;
 *   - AUTH_MODE=dev with NODE_ENV=production -> refused;
 *   - SESSION_SECRET shorter than 32 characters or DEV_LOGIN_PASSWORD shorter than 12 -> refused.
 */
export interface AuthConfig {
  readonly mode: 'dev';
  readonly sessionSecret: string;
  readonly devPassword: string;
  /** Session lifetime in seconds (APEX default maximum session length: 8 hours). */
  readonly sessionTtlSeconds: number;
}

export function authConfigFromEnv(env: NodeJS.ProcessEnv = process.env): AuthConfig {
  const mode = env.AUTH_MODE;
  if (mode !== 'dev') {
    throw new Error('AUTH_MODE must be set. Only AUTH_MODE=dev exists until the identity provider is decided (WP9-009).');
  }
  if (env.NODE_ENV === 'production') {
    throw new Error('AUTH_MODE=dev is refused when NODE_ENV=production.');
  }
  const sessionSecret = env.SESSION_SECRET ?? '';
  if (sessionSecret.length < 32) throw new Error('SESSION_SECRET must be at least 32 characters.');
  const devPassword = env.DEV_LOGIN_PASSWORD ?? '';
  if (devPassword.length < 12) throw new Error('DEV_LOGIN_PASSWORD must be at least 12 characters.');
  const ttl = Number(env.SESSION_TTL_SECONDS ?? 8 * 3600);
  if (!Number.isInteger(ttl) || ttl < 60 || ttl > 24 * 3600) {
    throw new Error('SESSION_TTL_SECONDS must be an integer between 60 and 86400.');
  }
  return { mode, sessionSecret, devPassword, sessionTtlSeconds: ttl };
}
