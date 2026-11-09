'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { skip, setup, rejectsWith } = require('./helpers');

test('WP9.4 requests and lines: trigger behavior as explicit service rules', { skip }, async (t) => {
  const env = await setup();
  t.after(() => env.pool.end());
  const { app, db, requests, ids } = env;
  const req1 = env.as('requester');
  const setStatus = (id, status) => env.pool.query('UPDATE app.apx_demo_requests SET status = $2 WHERE request_id = $1', [id, status]);

  await t.test('BR-REQ-01..03 + BR-AUD-01 create: DRAFT forced, number assigned, defaults and audit', async () => {
    const row = await app.createRequest(req1, { department_id: ids.ops, purpose: 'ATK', status: 'APPROVED', notes: '' });
    assert.equal(row.status, 'DRAFT', 'status is forced to DRAFT on insert');
    assert.equal(row.request_no, 'REQ-2026-0001');
    assert.equal(row.request_date, '2026-11-09 00:00:00', 'TRUNC(SYSDATE) on the configured clock');
    assert.equal(row.notes, null, "'' is stored as NULL like Oracle");
    assert.deepEqual([row.created_by, row.created_on, row.updated_by, row.updated_on],
      ['REQ1', '2026-11-09 03:04:05', 'REQ1', '2026-11-09 03:04:05']);
    const explicit = await app.createRequest(req1, { department_id: ids.ops, purpose: 'x', request_no: 'MANUAL-1' });
    assert.equal(explicit.request_no, 'MANUAL-1', 'a provided request_no is kept');
  });

  await t.test('BR-SEC-05 page 301 requires REQUESTER/MANAGER', async () => {
    await rejectsWith(assert, app.createRequest(env.as('warehouse'), { department_id: ids.ops, purpose: 'x' }), 'FORBIDDEN');
  });

  await t.test('BR-REQ-04..07 update guards', async () => {
    const r = await app.createRequest(req1, { department_id: ids.ops, purpose: 'guarded' });
    const id = Number(r.request_id);
    const updated = await app.updateRequest(env.as('manager'), id, { purpose: 'changed', need_date: '2026-12-01' });
    assert.equal(updated.row.purpose, 'changed');
    assert.equal(updated.row.updated_by, 'MGR1');
    await rejectsWith(assert, app.updateRequest(req1, id, { status: 'CLOSED' }), 'REQUEST_STATUS_TRANSITION', -20112);
    await rejectsWith(assert, app.updateRequest(req1, id, { status: 'CANCELLED' }), 'REQUEST_STATUS_TRANSITION', -20112);

    await setStatus(id, 'SUBMITTED');
    await rejectsWith(assert, app.updateRequest(req1, id, { notes: 'x' }), 'REQUEST_LOCKED_SUBMITTED', -20110);

    await setStatus(id, 'APPROVED');
    const frozen = await app.updateRequest(req1, id, { purpose: 'too late', department_id: ids.ops + 1, notes: 'ok' });
    assert.equal(frozen.row.purpose, 'changed', 'locked columns keep their value (BR-REQ-07)');
    assert.equal(frozen.row.notes, 'ok');
    assert.deepEqual(frozen.ignored.sort(), ['department_id', 'purpose']);
    const fulfilled = await app.updateRequest(req1, id, { status: 'FULFILLED' });
    assert.equal(fulfilled.row.status, 'FULFILLED');
    const closed = await app.updateRequest(req1, id, { status: 'CLOSED' });
    assert.equal(closed.row.status, 'CLOSED');
    await rejectsWith(assert, app.updateRequest(req1, id, { notes: 'x' }), 'REQUEST_FINAL', -20111);
    await rejectsWith(assert, app.updateRequest(req1, 999999, { notes: 'x' }), 'NOT_FOUND', -1403);
    await rejectsWith(assert, app.updateRequest(req1, id, { created_by: 'X' }), 'INVALID_INPUT');
  });

  await t.test('BR-LIN-01 lines only while the parent is DRAFT/REJECTED; DEV-03 both parents checked', async () => {
    const a = Number((await app.createRequest(req1, { department_id: ids.ops, purpose: 'A' })).request_id);
    const b = Number((await app.createRequest(req1, { department_id: ids.ops, purpose: 'B' })).request_id);
    const line = await app.addLine(req1, { request_id: a, item_id: ids.atk, qty: 3, unit_price: '55000' });
    assert.equal(line.line_amount, '165000', 'generated qty * unit_price');
    const noPrice = await app.addLine(req1, { request_id: a, item_id: ids.atk, qty: 1 });
    assert.equal(noPrice.unit_price, '0', 'unit_price default 0');
    const audited = (await env.pool.query('SELECT created_by, updated_on::text FROM app.apx_demo_request_lines WHERE line_id = $1', [line.line_id])).rows[0];
    assert.deepEqual(audited, { created_by: 'REQ1', updated_on: '2026-11-09 03:04:05' });

    await setStatus(a, 'SUBMITTED');
    await rejectsWith(assert, app.addLine(req1, { request_id: a, item_id: ids.atk, qty: 1 }), 'REQUEST_LINES_LOCKED', -20121);
    await rejectsWith(assert, app.updateLine(req1, Number(line.line_id), { qty: 9 }), 'REQUEST_LINES_LOCKED', -20121);
    await rejectsWith(assert, app.deleteLine(req1, Number(line.line_id)), 'REQUEST_LINES_LOCKED', -20121);
    await rejectsWith(assert, app.updateLine(req1, Number(line.line_id), { request_id: b }), 'REQUEST_LINES_LOCKED', -20121);

    await setStatus(a, 'REJECTED');
    const moved = await app.updateLine(req1, Number(line.line_id), { request_id: b, qty: 4 });
    assert.equal(moved.request_id, String(b));
    assert.equal(moved.line_amount, '220000');
    await app.deleteLine(req1, Number(noPrice.line_id));
  });

  await t.test('BR-REQ-08 delete cascades lines in any status (source parity, finding F-03)', async () => {
    const id = Number((await app.createRequest(req1, { department_id: ids.ops, purpose: 'del' })).request_id);
    await app.addLine(req1, { request_id: id, item_id: ids.atk, qty: 1, unit_price: 1 });
    await setStatus(id, 'APPROVED');
    await app.deleteRequest(req1, id);
    const left = await env.pool.query('SELECT count(*)::int AS n FROM app.apx_demo_request_lines WHERE request_id = $1', [id]);
    assert.equal(left.rows[0].n, 0);
  });

  await t.test('BR-MD-01 master data normalization and audit; ADMIN-only user roles', async () => {
    const dept = await app.saveMasterData(env.as('warehouse'), 'departments', { dept_code: 'fin', dept_name: 'Finance' });
    assert.equal(dept.dept_code, 'FIN');
    assert.equal(dept.active_yn, 'Y');
    assert.equal(dept.created_by, 'WH1');
    const item = await app.saveMasterData(env.as('warehouse'), 'items',
      { item_code: 'con-9', item_name: 'Toner', category: 'CONSUMABLE', uom: 'pcs', std_price: 1 });
    assert.deepEqual([item.item_code, item.uom], ['CON-9', 'PCS']);
    const upd = await app.saveMasterData(env.as('admin'), 'items', { uom: 'box' }, Number(item.item_id));
    assert.deepEqual([upd.uom, upd.updated_by, upd.created_by], ['BOX', 'ADMIN1', 'WH1']);
    await rejectsWith(assert, app.saveMasterData(env.as('requester'), 'items', { item_code: 'x' }), 'FORBIDDEN');
    const ur = await app.saveUserRole(env.as('admin'), { username: 'new.user', role_code: 'requester' });
    assert.deepEqual([ur.username, ur.role_code], ['NEW.USER', 'REQUESTER']);
    await rejectsWith(assert, app.saveUserRole(env.as('manager'), { username: 'x', role_code: 'ADMIN' }), 'FORBIDDEN');
  });

  await t.test('transaction handling: a failing rule rolls back every change of the use case', async () => {
    const before = (await env.pool.query('SELECT count(*)::int AS n FROM app.apx_demo_requests')).rows[0].n;
    await assert.rejects(db.run(req1, async (tx) => {
      await requests.create(tx, { department_id: ids.ops, purpose: 'rolled back' });
      await requests.addLine(tx, { request_id: 987654, item_id: ids.atk, qty: 1 });
    }));
    assert.equal((await env.pool.query('SELECT count(*)::int AS n FROM app.apx_demo_requests')).rows[0].n, before);
  });
});
