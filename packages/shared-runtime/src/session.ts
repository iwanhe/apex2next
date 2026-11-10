import type { RuntimeSessionClaims, RuntimeSessionPolicy } from './contracts.js';

export type RuntimeSessionInvalidReason =
  | 'MALFORMED_CLAIMS'
  | 'INVALID_POLICY'
  | 'ISSUED_IN_FUTURE'
  | 'EXPIRED'
  | 'INVALID_LIFETIME'
  | 'MAX_AGE_EXCEEDED';

export type RuntimeSessionValidation =
  | { readonly valid: true }
  | { readonly valid: false; readonly reason: RuntimeSessionInvalidReason };

/** Validates signed session claims after cryptographic verification by the authentication adapter. */
export function validateRuntimeSession(
  claims: RuntimeSessionClaims,
  policy: RuntimeSessionPolicy,
  nowEpochSeconds: number,
): RuntimeSessionValidation {
  if (!claims.sessionId || !claims.subject
    || !Number.isSafeInteger(claims.issuedAtEpochSeconds)
    || !Number.isSafeInteger(claims.expiresAtEpochSeconds)
    || !Number.isSafeInteger(claims.authVersion) || claims.authVersion < 0
    || !Number.isFinite(nowEpochSeconds)) {
    return { valid: false, reason: 'MALFORMED_CLAIMS' };
  }
  if (!Number.isSafeInteger(policy.maxAgeSeconds) || policy.maxAgeSeconds < 1
    || !Number.isSafeInteger(policy.clockSkewSeconds) || policy.clockSkewSeconds < 0) {
    return { valid: false, reason: 'INVALID_POLICY' };
  }
  if (claims.issuedAtEpochSeconds > nowEpochSeconds + policy.clockSkewSeconds) {
    return { valid: false, reason: 'ISSUED_IN_FUTURE' };
  }
  if (claims.expiresAtEpochSeconds <= nowEpochSeconds) {
    return { valid: false, reason: 'EXPIRED' };
  }
  const lifetime = claims.expiresAtEpochSeconds - claims.issuedAtEpochSeconds;
  if (lifetime <= 0) return { valid: false, reason: 'INVALID_LIFETIME' };
  if (lifetime > policy.maxAgeSeconds) return { valid: false, reason: 'MAX_AGE_EXCEEDED' };
  return { valid: true };
}
