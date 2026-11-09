'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { skip, setup, rejectsWith } = require('./helpers');

async function draftWithLines(env, who, lines) {
  const req = await env.app.createRequest(env.as(who), { department_id: env.ids.ops, purpose: `lines ${lines.length}` });
  const id = Number(req.request_id);
  for (const [item, qty, price] of lines) {
    await env.app.addLine(env.as(who), { request_id: id, item_id: env.ids[item], qty, unit_price: price });
  }
  return { id, no: req.request_no };
}

const status = async (env, id) =>
  (await env.pool.query('SELECT status FROM app.apx_demo_requests WHERE request_id = $1', [id])).rows[0].status;

test('WP9.4 approval engine: APX_DEMO_APPROVAL_PKG replacement', { skip }, async (t) => {
  const env = await setup();
  t.after(() => env.pool.end());
  const { app, db, approvals } = env;

  await t.test('small request (<= level2_limit): submit -> MANAGER approves -> APPROVED', async () => {
    const doc = await draftWithLines(env, 'requester', [['atk', 20, 55000], ['atk', 5, 30000]]);
    const sub = await app.submitRequest(env.as('requester'), doc.id);
    assert.equal(sub.status, 'SUBMITTED');
    const step = (await env.pool.query('SELECT * FROM app.apx_demo_approvals WHERE approval_id = $1', [sub.approvalId])).rows[0];
    assert.deepEqual([step.approval_level, step.approver_role, step.amount, step.requested_by, step.status, step.doc_no],
      ['1', 'MANAGER', '1250000', 'REQ1', 'PENDING', doc.no]); // unconstrained NUMBER -> numeric (WP9.3 SCH002)
    assert.equal(await status(env, doc.id), 'SUBMITTED');
    const res = await app.approve(env.as('manager'), sub.approvalId, 'ok');
    assert.deepEqual(res, { approvalId: sub.approvalId, docStatus: 'APPROVED', nextApprovalId: null });
    assert.equal(await status(env, doc.id), 'APPROVED');
    const acted = (await env.pool.query('SELECT status, acted_by, acted_on::text, note FROM app.apx_demo_approvals WHERE approval_id = $1', [sub.approvalId])).rows[0];
    assert.deepEqual(acted, { status: 'APPROVED', acted_by: 'MGR1', acted_on: '2026-11-09 03:04:05', note: 'ok' });
    await rejectsWith(assert, app.approve(env.as('manager'), sub.approvalId), 'APPROVAL_ALREADY_PROCESSED', -20105);
  });

  await t.test('large request (> 10,000,000): level 1 MANAGER, then level 2 DIRECTOR for the original requester', async () => {
    const doc = await draftWithLines(env, 'requester', [['laptop', 2, 12500000]]);
    const sub = await app.submitRequest(env.as('requester'), doc.id);
    const lvl1 = await app.approve(env.as('manager'), sub.approvalId);
    assert.equal(lvl1.docStatus, null);
    assert.ok(lvl1.nextApprovalId);
    assert.equal(await status(env, doc.id), 'SUBMITTED', 'document stays SUBMITTED during level 2');
    const step2 = (await env.pool.query('SELECT approval_level, approver_role, requested_by, amount FROM app.apx_demo_approvals WHERE approval_id = $1', [lvl1.nextApprovalId])).rows[0];
    assert.deepEqual(step2, { approval_level: '2', approver_role: 'DIRECTOR', requested_by: 'REQ1', amount: '25000000' });
    await rejectsWith(assert, app.approve(env.as('manager'), lvl1.nextApprovalId), 'MISSING_APPROVER_ROLE', -20107);
    const lvl2 = await app.approve(env.as('director'), lvl1.nextApprovalId);
    assert.equal(lvl2.docStatus, 'APPROVED');
  });

  await t.test('amount exactly at the limit stays single-level (strict >)', async () => {
    const doc = await draftWithLines(env, 'requester', [['atk', 1, 10000000]]);
    const sub = await app.submitRequest(env.as('requester'), doc.id);
    assert.equal((await app.approve(env.as('manager'), sub.approvalId)).docStatus, 'APPROVED');
  });

  await t.test('reject requires a note, sets REJECTED, and the request can be edited and re-submitted', async () => {
    const doc = await draftWithLines(env, 'requester', [['atk', 1, 1]]);
    const sub = await app.submitRequest(env.as('requester'), doc.id);
    await rejectsWith(assert, app.reject(env.as('manager'), sub.approvalId, ''), 'REJECT_NOTE_REQUIRED', -20108);
    await rejectsWith(assert, app.reject(env.as('manager'), sub.approvalId, null), 'REJECT_NOTE_REQUIRED', -20108);
    const res = await app.reject(env.as('manager'), sub.approvalId, 'kurang detail');
    assert.equal(res.docStatus, 'REJECTED');
    await app.addLine(env.as('requester'), { request_id: doc.id, item_id: env.ids.atk, qty: 1, unit_price: 2 });
    const again = await app.submitRequest(env.as('requester'), doc.id);
    assert.notEqual(again.approvalId, sub.approvalId);
  });

  await t.test('submit guards: -20101 not DRAFT/REJECTED, -20201 without lines, -1403 unknown document', async () => {
    const doc = await draftWithLines(env, 'requester', [['atk', 1, 1]]);
    await app.submitRequest(env.as('requester'), doc.id);
    await rejectsWith(assert, app.submitRequest(env.as('requester'), doc.id), 'DOC_NOT_SUBMITTABLE', -20101);
    const empty = await draftWithLines(env, 'requester', []);
    await rejectsWith(assert, app.submitRequest(env.as('requester'), empty.id), 'REQUEST_WITHOUT_LINES', -20201);
    assert.equal(await status(env, empty.id), 'DRAFT', 'failed submit rolls back');
    await rejectsWith(assert, app.submitRequest(env.as('requester'), 424242), 'NOT_FOUND', -1403);
    await rejectsWith(assert, db.run(env.as('requester'), (tx) => approvals.submit(tx, 'XYZ', 1)), 'UNKNOWN_DOC_TYPE', -20100);
  });

  await t.test('segregation of duties: a manager cannot approve the own request (-20106)', async () => {
    const doc = await draftWithLines(env, 'manager', [['atk', 1, 1]]);
    const sub = await app.submitRequest(env.as('manager'), doc.id);
    await rejectsWith(assert, app.approve(env.as('manager'), sub.approvalId), 'SEGREGATION_OF_DUTIES', -20106);
    await rejectsWith(assert, app.approve(env.as('admin'), sub.approvalId + 999), 'NOT_FOUND', -1403);
    assert.equal((await app.approve(env.as('admin'), sub.approvalId)).docStatus, 'APPROVED', 'ADMIN may approve');
  });

  await t.test('no approver1 role: submit approves directly', async () => {
    await env.pool.query("UPDATE app.apx_demo_doc_types SET approver1_role = NULL WHERE doc_type = 'REQ'");
    try {
      const doc = await draftWithLines(env, 'requester', [['atk', 1, 1]]);
      assert.deepEqual(await app.submitRequest(env.as('requester'), doc.id),
        { docType: 'REQ', docId: doc.id, status: 'APPROVED', approvalId: null });
    } finally {
      await env.pool.query("UPDATE app.apx_demo_doc_types SET approver1_role = 'MANAGER' WHERE doc_type = 'REQ'");
    }
  });

  await t.test('DEV-05 configuration drift fails closed instead of executing configured SQL', async () => {
    const doc = await draftWithLines(env, 'requester', [['atk', 1, 1]]);
    await env.pool.query("UPDATE app.apx_demo_doc_types SET amount_expr = '(select 1 from dual)' WHERE doc_type = 'REQ'");
    try {
      await rejectsWith(assert, app.submitRequest(env.as('requester'), doc.id), 'DOC_TYPE_CONFIG_DRIFT');
    } finally {
      await env.pool.query(`UPDATE app.apx_demo_doc_types SET amount_expr =
        '(select nvl(sum(l.line_amount), 0) from apx_demo_request_lines l where l.request_id = t.request_id)' WHERE doc_type = 'REQ'`);
    }
  });

  await t.test('BR-APR-08 can_act_yn: SQL function, approvals view and service checks agree', async () => {
    const doc = await draftWithLines(env, 'requester', [['atk', 1, 1]]);
    const sub = await app.submitRequest(env.as('requester'), doc.id);
    const expected = { requester: 'N', manager: 'Y', director: 'N', admin: 'Y', warehouse: 'N', nobody: 'N' };
    for (const [who, yn] of Object.entries(expected)) {
      const viewYn = await db.run(env.as(who), async (tx) => (await tx.query(
        'SELECT can_act_yn FROM app.apx_demo_approvals_v WHERE approval_id = $1', [sub.approvalId])).rows[0].can_act_yn);
      const fnYn = await db.run(env.as(who), (tx) => approvals.canAct(tx, sub.approvalId));
      const assertOk = await db.run(env.as(who), async (tx) => {
        const step = (await tx.query(`SELECT approval_id::text, doc_type, doc_id::text, doc_no, approval_level::text,
          approver_role, amount::text, requested_by, status FROM app.apx_demo_approvals WHERE approval_id = $1`, [sub.approvalId])).rows[0];
        try { await approvals.assertCanAct(tx, step); return true; } catch { return false; }
      });
      assert.equal(viewYn, yn, `${who} view`);
      assert.equal(fnYn, yn === 'Y', `${who} function`);
      assert.equal(assertOk, yn === 'Y', `${who} assertCanAct`);
    }
    const unknown = await db.run(env.as('admin'), async (tx) => (await tx.query('SELECT app.can_act_yn(-1) AS yn')).rows[0].yn);
    assert.equal(unknown, 'N');
    const inbox = await app.approvalInbox(env.as('manager'));
    assert.ok(inbox.some((r) => r.approval_id === String(sub.approvalId) && r.can_act_yn === 'Y'));
    const kpis = await app.dashboardKpis(env.as('manager'));
    assert.deepEqual(kpis.map((k) => k.label), ['Approval Menunggu Anda', 'Permintaan Draft', 'Menunggu Approval']);
    // independent oracle for the KPI: pending steps MGR1 may act on (own roles MANAGER/REQUESTER, not own requests)
    const pendingForManager = (await env.pool.query(`SELECT count(*)::int AS n FROM app.apx_demo_approvals a
      WHERE a.status = 'PENDING' AND a.approver_role IN ('MANAGER', 'REQUESTER') AND upper(a.requested_by) <> 'MGR1'`)).rows[0].n;
    assert.ok(pendingForManager > 0);
    assert.equal(kpis[0].metric_value, pendingForManager);
    assert.equal((await app.dashboardKpis(env.as('warehouse')))[0].metric_value, 0, 'KPI is per principal');
  });

  await t.test('DEV-02 concurrency: parallel submits of one request create exactly one step', async () => {
    const doc = await draftWithLines(env, 'requester', [['atk', 1, 1]]);
    const results = await Promise.allSettled(Array.from({ length: 5 }, () => app.submitRequest(env.as('requester'), doc.id)));
    assert.equal(results.filter((r) => r.status === 'fulfilled').length, 1);
    for (const r of results.filter((x) => x.status === 'rejected')) assert.equal(r.reason.oracleCode, -20101);
    const steps = await env.pool.query('SELECT count(*)::int AS n FROM app.apx_demo_approvals WHERE doc_id = $1', [doc.id]);
    assert.equal(steps.rows[0].n, 1);
  });

  await t.test('concurrency: a line change racing a submit never lands on a SUBMITTED request', async () => {
    const doc = await draftWithLines(env, 'requester', [['atk', 1, 1]]);
    const [sub, line] = await Promise.allSettled([
      app.submitRequest(env.as('requester'), doc.id),
      app.addLine(env.as('requester'), { request_id: doc.id, item_id: env.ids.atk, qty: 2, unit_price: 3 }),
    ]);
    assert.equal(sub.status, 'fulfilled');
    const amount = (await env.pool.query('SELECT amount::text FROM app.apx_demo_approvals WHERE approval_id = $1', [sub.value.approvalId])).rows[0].amount;
    const lines = (await env.pool.query('SELECT coalesce(sum(line_amount),0)::text AS s FROM app.apx_demo_request_lines WHERE request_id = $1', [doc.id])).rows[0].s;
    if (line.status === 'fulfilled') assert.equal(amount, lines, 'line committed before submit is included in the amount');
    else assert.equal(line.reason.oracleCode, -20121);
    assert.equal(amount, lines, 'approved amount always equals the lines of the submitted request');
  });
});
