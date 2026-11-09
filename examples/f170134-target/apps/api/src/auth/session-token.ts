import { createHmac, randomBytes, timingSafeEqual } from 'node:crypto';

/**
 * Stateless session token: base64url(JSON payload) + "." + base64url(HMAC-SHA256). The payload holds the
 * normalized username (the APEX APP_USER), issue/expiry times and a random id. The web tier keeps it in
 * an httpOnly cookie and forwards it as a Bearer token; it is never exposed to browser scripts.
 */
export interface SessionPayload {
  readonly sub: string;
  readonly iat: number;
  readonly exp: number;
  readonly jti: string;
}

const b64 = (buf: Buffer) => buf.toString('base64url');

function mac(secret: string, data: string): Buffer {
  return createHmac('sha256', secret).update(data).digest();
}

export function signSession(secret: string, username: string, ttlSeconds: number, nowSeconds = Math.floor(Date.now() / 1000)): string {
  const payload: SessionPayload = { sub: username, iat: nowSeconds, exp: nowSeconds + ttlSeconds, jti: b64(randomBytes(12)) };
  const body = b64(Buffer.from(JSON.stringify(payload), 'utf8'));
  return `${body}.${b64(mac(secret, body))}`;
}

/** Returns the payload of a valid, unexpired token, otherwise null. */
export function verifySession(secret: string, token: string | undefined | null, nowSeconds = Math.floor(Date.now() / 1000)): SessionPayload | null {
  if (!token || token.length > 2048) return null;
  const parts = token.split('.');
  if (parts.length !== 2) return null;
  const [body, signature] = parts;
  const expected = mac(secret, body);
  let given: Buffer;
  try {
    given = Buffer.from(signature, 'base64url');
  } catch {
    return null;
  }
  if (given.length !== expected.length || !timingSafeEqual(given, expected)) return null;
  let payload: SessionPayload;
  try {
    payload = JSON.parse(Buffer.from(body, 'base64url').toString('utf8'));
  } catch {
    return null;
  }
  if (typeof payload.sub !== 'string' || !payload.sub || typeof payload.exp !== 'number' || payload.exp <= nowSeconds) return null;
  return payload;
}
