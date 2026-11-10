import test from 'node:test';
import assert from 'node:assert/strict';
import {
  assertRuntimeVersion,
  RuntimeVersionMismatchError,
  validateRuntimeSession,
} from '../dist/index.js';

const claims = {
  sessionId: 'session-1',
  subject: 'user-1',
  issuedAtEpochSeconds: 1_000,
  expiresAtEpochSeconds: 1_900,
  authVersion: 3,
};
const policy = { maxAgeSeconds: 900, clockSkewSeconds: 30 };

test('accepts valid signed session claims within the configured age', () => {
  assert.deepEqual(validateRuntimeSession(claims, policy, 1_500), { valid: true });
});

test('rejects expired, future-issued, over-age and malformed session claims', () => {
  assert.deepEqual(validateRuntimeSession(claims, policy, 1_900), { valid: false, reason: 'EXPIRED' });
  assert.deepEqual(validateRuntimeSession({ ...claims, issuedAtEpochSeconds: 2_000 }, policy, 1_500),
    { valid: false, reason: 'ISSUED_IN_FUTURE' });
  assert.deepEqual(validateRuntimeSession({ ...claims, expiresAtEpochSeconds: 2_000 }, policy, 1_500),
    { valid: false, reason: 'MAX_AGE_EXCEEDED' });
  assert.deepEqual(validateRuntimeSession({ ...claims, subject: '' }, policy, 1_500),
    { valid: false, reason: 'MALFORMED_CLAIMS' });
});

test('rejects invalid session policy configuration', () => {
  assert.deepEqual(validateRuntimeSession(claims, { maxAgeSeconds: 0, clockSkewSeconds: 0 }, 1_500),
    { valid: false, reason: 'INVALID_POLICY' });
});

test('lost-update guard accepts only matching non-empty opaque version tokens', () => {
  assert.doesNotThrow(() => assertRuntimeVersion('v1:abc', 'v1:abc'));
  assert.throws(() => assertRuntimeVersion('v1:abc', 'v1:def'), RuntimeVersionMismatchError);
  assert.throws(() => assertRuntimeVersion(undefined, 'v1:abc'), RuntimeVersionMismatchError);
  assert.throws(() => assertRuntimeVersion('v1:abc', null), RuntimeVersionMismatchError);
});
