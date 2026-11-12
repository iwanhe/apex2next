'use strict';
// WP9-009 local accounts (AUTH_MODE=local): login, forced password change, lockout, revocation, rate limit, CLI.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { skip, startApi, DATABASE_URL } = require('./helpers');
const { hashPassword, verifyPassword, checkPolicy, temporaryPassword } = require('@apex2next/runtime-api');
const { RateLimiter } = require('@apex2next/runtime-api');
const { authConfigFromEnv } = require('@apex2next/runtime-api');

const CLI = path.join(__dirname, '..', 'scripts', 'accounts.mjs');
const cli = (...args) => execFileSync(process.execPath, [CLI, ...args, '--by', 'TEST_OPERATOR'],
  { env: { ...process.env, DATABASE_URL } }).toString();
const tempFrom = (out) => /temporary password: (\S+)/.exec(out)[1];

test('password hashing, policy and temporary passwords', async () => {
  const h = await hashPassword('Rahasia123x');
  assert.match(h, /^scrypt\$131072\$8\$1\$/);
  assert.equal(await verifyPassword('Rahasia123x', h), true);
  assert.equal(await verifyPassword('rahasia123x', h), false);
  assert.equal(await verifyPassword('x', 'garbage'), false);
  assert.notEqual(await hashPassword('Rahasia123x'), h, 'salted');
  assert.deepEqual(checkPolicy({ minLength: 10 }, 'REQ1', 'Rahasia123x', 'old'), []);
  assert.deepEqual(checkPolicy({ minLength: 10 }, 'REQ1', 'short1', undefined), ['Password minimal 10 karakter.']);
  assert.ok(checkPolicy({ minLength: 10 }, 'REQ1', 'abcdefghijkl').includes('Password harus berisi huruf dan angka.'));
  assert.ok(checkPolicy({ minLength: 10 }, 'REQ1', 'xxreq1xx99yy').includes('Password tidak boleh memuat username.'));
  const t = temporaryPassword();
  assert.equal(t.length, 16);
  assert.deepEqual(checkPolicy({ minLength: 10 }, 'NOBODY', t), []);
});

test('rate limiter: fixed window per client', () => {
  let now = 0;
  const rl = new RateLimiter(2, 60_000, () => now);
  assert.deepEqual([rl.take('a'), rl.take('a'), rl.take('a'), rl.take('b')], [true, true, false, true]);
  now = 60_000;
  assert.equal(rl.take('a'), true);
});

test('auth config: local mode needs no dev password, refuses nothing else in production', () => {
  const c = authConfigFromEnv({ AUTH_MODE: 'local', NODE_ENV: 'production', SESSION_SECRET: 'x'.repeat(32) });
  assert.equal(c.mode, 'local');
  assert.equal(c.maxFailedLogins, 5);
  assert.throws(() => authConfigFromEnv({ AUTH_MODE: 'dev', NODE_ENV: 'production', SESSION_SECRET: 'x'.repeat(32), DEV_LOGIN_PASSWORD: 'y'.repeat(12) }));
  assert.throws(() => authConfigFromEnv({ AUTH_MODE: 'sso', SESSION_SECRET: 'x'.repeat(32) }));
});

test('AUTH_MODE=local end to end', { skip }, async () => {
  const api = await startApi({ authEnv: { AUTH_MODE: 'local', LOGIN_MAX_FAILURES: '3', LOGIN_LOCK_MINUTES: '15', LOGIN_RATE_PER_MINUTE: '1000' } });
  try {
    const login = (username, password) => api.call(null, 'POST', '/auth/login', { username, password });
    const invalid = { code: 'UNAUTHENTICATED', oracleCode: null, rule: 'BR-SEC-01', message: 'Invalid Login Credentials' };

    // accounts from the role table (APEX users), temporary passwords printed once
    const imported = cli('import-roles');
    const temp = tempFrom(imported.split('\n').find((l) => l.startsWith('REQ1')));
    assert.match(cli('create', 'req1'), /REQ1\texists/);

    // unknown user, wrong password: same answer
    assert.deepEqual((await login('ghost', temp)).body, invalid);
    assert.deepEqual((await login('req1', 'wrong-password-1')).body, invalid);

    // temporary password: signed in, but only the password change is allowed
    const first = await login(' Req1 ', temp);
    assert.equal(first.status, 200);
    assert.equal(first.body.username, 'REQ1');
    assert.equal(first.body.mustChangePassword, true);
    const blocked = await api.call(first.body.token, 'GET', '/session');
    assert.equal(blocked.status, 403);
    assert.equal(blocked.body.code, 'PASSWORD_CHANGE_REQUIRED');

    // change: validation messages, then success with a new token; the old token is revoked
    const bad = await api.call(first.body.token, 'POST', '/auth/password', { current: 'nope', next: 'short', confirm: 'other' });
    assert.equal(bad.status, 422);
    assert.deepEqual(bad.body.fieldErrors.map((f) => f.field), ['current_password', 'new_password', 'new_password', 'confirm_password']);
    const changed = await api.call(first.body.token, 'POST', '/auth/password', { current: temp, next: 'Permintaan2026', confirm: 'Permintaan2026' });
    assert.equal(changed.status, 200, JSON.stringify(changed.body));
    assert.equal(changed.body.mustChangePassword, false);
    assert.equal((await api.call(first.body.token, 'GET', '/session')).status, 401, 'token before the change is revoked');
    const session = await api.call(changed.body.token, 'GET', '/session');
    assert.equal(session.status, 200);
    assert.equal(session.body.username, 'REQ1');

    // sign out revokes the session
    assert.equal((await api.call(changed.body.token, 'POST', '/auth/logout')).status, 204);
    assert.equal((await api.call(changed.body.token, 'GET', '/session')).status, 401);

    // lockout after 3 consecutive failures (a successful login resets the count); a locked account refuses the right password too
    for (const pw of ['wrong-password-2', 'wrong-password-3', 'wrong-password-4']) await login('req1', pw);
    assert.deepEqual((await login('req1', 'Permintaan2026')).body, invalid);
    const ev = (await api.pool.query(
      "SELECT event, detail FROM iam.account_events WHERE username = 'REQ1' ORDER BY event_id")).rows.map((r) => `${r.event}:${r.detail ?? ''}`);
    assert.deepEqual(ev, ['CREATED:', 'LOGIN_FAILED:attempt 1', 'LOGIN_OK:', 'PASSWORD_CHANGED:', 'LOGOUT:',
      'LOGIN_FAILED:attempt 1', 'LOGIN_FAILED:attempt 2', 'LOGIN_FAILED:attempt 3', 'LOCKED:15 min', 'LOGIN_FAILED:locked']);
    assert.ok(!ev.join().includes('Permintaan2026'));

    // operator: unlock -> login works; deactivate -> live token stops working; reset -> new temporary password
    cli('unlock', 'REQ1');
    const again = await login('req1', 'Permintaan2026');
    assert.equal(again.status, 200);
    assert.equal(again.body.mustChangePassword, false);
    cli('deactivate', 'REQ1');
    assert.equal((await api.call(again.body.token, 'GET', '/session')).status, 401);
    assert.deepEqual((await login('req1', 'Permintaan2026')).body, invalid);
    cli('activate', 'REQ1');
    const reset = tempFrom(cli('reset', 'REQ1'));
    assert.deepEqual((await login('req1', 'Permintaan2026')).body, invalid);
    assert.equal((await login('req1', reset)).body.mustChangePassword, true);
    // temporary passwords travel by e-mail, so they expire
    await api.pool.query("UPDATE iam.accounts SET temp_password_expires_at = now() - interval '1 minute' WHERE username = 'REQ1'");
    assert.deepEqual((await login('req1', reset)).body, invalid);
    const last = (await api.pool.query("SELECT detail FROM iam.account_events WHERE username = 'REQ1' ORDER BY event_id DESC LIMIT 1")).rows[0];
    assert.equal(last.detail, 'temporary password expired');
    assert.match(cli('list'), /REQ1/);

    // roles still come from the APEX role table: an account without roles is refused by APP_USERS
    const noRoles = tempFrom(cli('create', 'norole'));
    const exp = (await api.pool.query(
      "SELECT temp_password_expires_at BETWEEN now() + interval '71 hours' AND now() + interval '73 hours' AS ok FROM iam.accounts WHERE username = 'NOROLE'")).rows[0];
    assert.equal(exp.ok, true, 'default expiry 72 h');
    const t2 = await login('norole', noRoles);
    const c2 = await api.call(t2.body.token, 'POST', '/auth/password', { current: noRoles, next: 'Lainnya12345', confirm: 'Lainnya12345' });
    const cleared = (await api.pool.query("SELECT temp_password_expires_at FROM iam.accounts WHERE username = 'NOROLE'")).rows[0];
    assert.equal(cleared.temp_password_expires_at, null);
    const home = await api.call(c2.body.token, 'GET', '/pages/100');
    assert.equal(home.status, 403);
  } finally {
    await api.close();
    for (const k of ['AUTH_MODE', 'LOGIN_MAX_FAILURES', 'LOGIN_LOCK_MINUTES', 'LOGIN_RATE_PER_MINUTE']) delete process.env[k];
  }
});

test('AUTH_MODE=local login rate limit per client', { skip }, async () => {
  const api = await startApi({ authEnv: { AUTH_MODE: 'local', LOGIN_RATE_PER_MINUTE: '3' } });
  try {
    const statuses = [];
    for (let i = 0; i < 4; i++) statuses.push((await api.call(null, 'POST', '/auth/login', { username: 'x', password: 'y' })).status);
    assert.deepEqual(statuses, [401, 401, 401, 429]);
  } finally {
    await api.close();
    for (const k of ['AUTH_MODE', 'LOGIN_RATE_PER_MINUTE']) delete process.env[k];
  }
});
