'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { skip, setup, rejectsWith } = require('./helpers');

test('WP9.4 document numbering: APX_DEMO_DOC_PKG.NEXT_NO replacement', { skip }, async (t) => {
  let now = new Date('2026-11-09T03:04:05Z');
  const env = await setup({ clock: { now: () => now } });
  t.after(() => env.pool.end());
  const { db, numbering, app, ids } = env;
  const next = () => db.run(env.as('requester'), (tx) => numbering.nextNo(tx, 'REQ'));

  await t.test('BR-DOC-01 PREFIX-YYYY-NNNN, sequential per period', async () => {
    assert.equal(await next(), 'REQ-2026-0001');
    assert.equal(await next(), 'REQ-2026-0002');
    now = new Date('2027-01-01T00:00:01Z');
    assert.equal(await next(), 'REQ-2027-0001', 'new period starts at 0001');
    now = new Date('2026-11-09T03:04:05Z');
    assert.equal(await next(), 'REQ-2026-0003');
  });

  await t.test('BR-DOC-02 gapless: a rolled back transaction releases its number', async () => {
    await assert.rejects(db.run(env.as('requester'), async (tx) => {
      assert.equal(await numbering.nextNo(tx, 'REQ'), 'REQ-2026-0004');
      throw new Error('abort');
    }), /abort/);
    assert.equal(await next(), 'REQ-2026-0004');
  });

  await t.test('BR-DOC-02 concurrent inserts get unique, gapless numbers (incl. first-of-period race)', async () => {
    now = new Date('2028-06-01T00:00:00Z');
    const rows = await Promise.all(Array.from({ length: 20 }, (_, i) =>
      app.createRequest(env.as('requester'), { department_id: ids.ops, purpose: `c${i}` })));
    const numbers = rows.map((r) => r.request_no).sort();
    assert.deepEqual(numbers, Array.from({ length: 20 }, (_, i) => `REQ-2028-${String(i + 1).padStart(4, '0')}`));
    now = new Date('2026-11-09T03:04:05Z');
  });

  await t.test('DEV-04 capacity: number 10000 raises instead of truncating like Oracle LPAD', async () => {
    await env.pool.query("UPDATE app.apx_demo_doc_seq SET last_no = 9999 WHERE doc_type = 'REQ' AND period = '2026'");
    await rejectsWith(assert, next(), 'NUMBERING_CAPACITY_EXCEEDED');
    const counter = await env.pool.query("SELECT last_no::int AS n FROM app.apx_demo_doc_seq WHERE period = '2026'");
    assert.equal(counter.rows[0].n, 9999, 'the failed call is rolled back');
  });

  await t.test('unknown document type behaves like ORA-01403', async () => {
    await rejectsWith(assert, db.run(env.as('requester'), (tx) => numbering.nextNo(tx, 'NOPE')), 'NOT_FOUND', -1403);
  });
});
