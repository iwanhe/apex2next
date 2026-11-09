'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { skip, setup, rejectsWith } = require('./helpers');

test('WP9.4 security: SEC_PKG replacement, authorization schemes, fail-closed principal', { skip }, async (t) => {
  const env = await setup();
  t.after(() => env.pool.end());
  const { db, security } = env;

  await t.test('BR-SEC-02 has_role: own role, ADMIN override, case-insensitive username', async () => {
    await db.run(env.as('requester'), async (tx) => {
      assert.equal(await security.hasRole(tx, 'requester'), true);
      assert.equal(await security.hasRole(tx, 'MANAGER'), false);
      assert.equal(await security.hasRole(tx, 'MANAGER', 'mgr1'), true);
      assert.equal(await security.hasRole(tx, 'DIRECTOR', 'admin1'), true, 'ADMIN passes every role check');
    });
  });

  await t.test('BR-SEC-04 has_any_role and BR-SEC-05 page schemes', async () => {
    const check = (who, scheme) => db.run(env.as(who), (tx) => security.isAuthorized(tx, scheme));
    assert.equal(await check('nobody', 'APP_USERS'), false);
    assert.equal(await check('warehouse', 'APP_USERS'), true);
    assert.equal(await check('manager', 'REQUESTER'), true);
    assert.equal(await check('warehouse', 'REQUESTER'), false);
    assert.equal(await check('warehouse', 'MASTER_DATA'), true);
    assert.equal(await check('admin', 'MASTER_DATA'), true);
    assert.equal(await check('requester', 'ADMIN_RIGHTS'), false);
    await rejectsWith(assert, db.run(env.as('nobody'), (tx) => security.authorize(tx, 'APP_USERS')), 'FORBIDDEN');
    await assert.rejects(db.run(env.as('nobody'), (tx) => security.authorize(tx, 'APP_USERS')),
      /akun NOBODY belum punya role/);
  });

  await t.test('principal is transaction-local and absent outside a business transaction', async () => {
    const r = await env.pool.query('SELECT app.current_username() AS u, app.has_role($1) AS ok', ['ADMIN']);
    assert.deepEqual(r.rows[0], { u: null, ok: false }, 'no principal -> fail closed');
    await db.run(env.as('admin'), async () => {});
    const after = await env.pool.query('SELECT app.current_username() AS u');
    assert.equal(after.rows[0].u, null, 'set_config(..., true) does not leak to pooled connections');
  });

  await t.test('DEV-01 no bootstrap mode: without any ADMIN nobody passes role checks', async () => {
    await env.pool.query("DELETE FROM app.apx_demo_user_roles WHERE role_code = 'ADMIN'");
    assert.equal(await db.run(env.as('nobody'), (tx) => security.hasRole(tx, 'ADMIN')), false);
    assert.equal(await db.run(env.as('nobody'), (tx) => security.hasAnyRole(tx)), false);
    await env.pool.query("INSERT INTO app.apx_demo_user_roles (username, role_code) VALUES ('ADMIN1', 'ADMIN')");
  });
});
