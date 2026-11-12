'use strict';
// WP9.5 page layer over HTTP: session auth, APEX authorization schemes, forms (validations, read-only
// items, button conditions, lost update), reports (search/sort/facets/download), LOVs and DB error mapping.
const test = require('node:test');
const assert = require('node:assert/strict');
const { skip, startApi } = require('./helpers');
const { signSession } = require('@apex2next/runtime-api');

const year = String(new Date().getUTCFullYear());
const today = new Date().toISOString().slice(0, 10);

function expectError(r, status, code, message) {
  assert.equal(r.status, status, JSON.stringify(r.body));
  assert.equal(r.body.code, code, JSON.stringify(r.body));
  if (message !== undefined) assert.equal(r.body.message, message);
}

test('WP9.5 page layer over HTTP', { skip }, async (t) => {
  const api = await startApi();
  t.after(() => api.close());
  const req1 = api.as('requester');
  const mgr1 = api.as('manager');
  const wh1 = api.as('warehouse');
  const admin = api.as('admin');
  const nobody = api.as('nobody');
  const dept = api.ids.ops;

  await t.test('authentication: fail closed, APEX login message, normalized APP_USER', async () => {
    expectError(await api.call(null, 'GET', '/session'), 401, 'UNAUTHENTICATED');
    expectError(await api.call('garbage', 'GET', '/session'), 401, 'UNAUTHENTICATED');
    expectError(await api.call(null, 'POST', '/auth/login', { username: 'req1', password: 'wrong-password' }),
      401, 'UNAUTHENTICATED', 'Invalid Login Credentials');
    expectError(await api.call(null, 'POST', '/auth/login', { username: '  ', password: api.DEV_PASSWORD }),
      401, 'UNAUTHENTICATED', 'Invalid Login Credentials');
    const expired = signSession(api.SESSION_SECRET, 'REQ1', 60, Math.floor(Date.now() / 1000) - 3600);
    expectError(await api.call(expired, 'GET', '/session'), 401, 'UNAUTHENTICATED');
    const forged = signSession('another-secret-another-secret-0000', 'ADMIN1', 3600);
    expectError(await api.call(forged, 'GET', '/session'), 401, 'UNAUTHENTICATED');
    const me = await req1.get('/session');
    assert.equal(me.status, 200);
    assert.equal(me.body.username, 'REQ1');
    assert.deepEqual(me.body.schemes, { ADMIN_RIGHTS: false, APP_USERS: true, MASTER_DATA: false, REQUESTER: true, WAREHOUSE: false });
    assert.equal((await api.call(null, 'GET', '/health')).status, 200, 'health stays public');
  });

  await t.test('APP_USERS application scheme: a signed-in user without roles is refused everywhere', async () => {
    const me = await nobody.get('/session');
    assert.equal(me.status, 200);
    assert.match(me.body.appAccessDenied, /^Akses ditolak: akun NOBODY belum punya role/);
    expectError(await nobody.get('/pages/100'), 403, 'FORBIDDEN', me.body.appAccessDenied);
    expectError(await nobody.get('/regions/approvalInbox'), 403, 'FORBIDDEN');
    expectError(await nobody.get('/lovs/DEMO_ROLES'), 403, 'FORBIDDEN');
  });

  await t.test('page authorization schemes from the export', async () => {
    expectError(await wh1.get('/forms/request'), 403, 'FORBIDDEN', 'Akses ditolak: hanya untuk role REQUESTER/MANAGER.');
    expectError(await req1.get('/forms/department'), 403, 'FORBIDDEN', 'Akses ditolak: hanya untuk role WAREHOUSE.');
    expectError(await req1.get('/regions/userRoles'), 403, 'FORBIDDEN', 'Akses ditolak: hanya untuk role ADMIN.');
    expectError(await wh1.get('/forms/docType/REQ'), 403, 'FORBIDDEN');
    assert.equal((await req1.get('/regions/departments')).status, 200, 'page 200 is APP_USERS');
    assert.equal((await admin.get('/forms/department')).status, 200, 'ADMIN satisfies every role check');
    assert.equal((await admin.get('/forms/request')).status, 200);
  });

  let requestId;
  let lineId;
  await t.test('page 301 create: item defaults, required + page validation messages, trim', async () => {
    const init = await req1.get('/forms/request');
    assert.equal(init.status, 200);
    assert.equal(init.body.values.request_date, today, 'P301_REQUEST_DATE default trunc(sysdate)');
    assert.equal(init.body.values.status, 'DRAFT');
    assert.deepEqual(init.body.buttons, { CREATE: true, DELETE: false, SAVE: false, SUBMIT: false });
    assert.equal(init.body.readOnly.status, true);

    const bad = await req1.post('/forms/request', { values: { department_id: '', request_date: today, need_date: '2000-01-01', purpose: ' ' } });
    expectError(bad, 422, 'VALIDATION_FAILED');
    assert.deepEqual(bad.body.fieldErrors, [
      { field: 'P301_DEPARTMENT_ID', message: 'Department must have some value.' },
      { field: 'P301_PURPOSE', message: 'Keperluan must have some value.' },
      { field: 'P301_NEED_DATE', message: 'Tanggal dibutuhkan tidak boleh sebelum tanggal permintaan.' },
    ]);
    const badDate = await req1.post('/forms/request', { values: { department_id: String(dept), request_date: '2026-02-30', purpose: 'x' } });
    assert.deepEqual(badDate.body.fieldErrors, [{ field: 'P301_REQUEST_DATE', message: 'Tanggal does not match format DD-MON-YYYY.' }]);

    const ok = await req1.post('/forms/request', { values: {
      department_id: String(dept), request_date: today, need_date: '', purpose: '  ATK kantor  ', notes: '', status: 'APPROVED' } });
    assert.equal(ok.status, 201, JSON.stringify(ok.body));
    assert.equal(ok.body.message, 'Row created.');
    requestId = ok.body.id;
    const row = await req1.get(`/forms/request/${requestId}`);
    assert.equal(row.body.values.purpose, 'ATK kantor', 'trim_spaces BOTH');
    assert.equal(row.body.values.notes, null);
    assert.equal(row.body.values.status, 'DRAFT', 'status is read-only on create and forced to DRAFT');
    assert.equal(row.body.values.request_no, `REQ-${year}-0001`);
    assert.deepEqual(row.body.buttons, { CREATE: false, DELETE: true, SAVE: true, SUBMIT: true });
    assert.equal(typeof row.body.checksum, 'string');
  });

  await t.test('page 311 line form + page 302 master-detail', async () => {
    const init = await req1.get(`/forms/requestLine?request_id=${requestId}`);
    assert.equal(init.body.values.request_id, requestId, 'P311_REQUEST_ID from the 302 link');
    assert.equal(init.body.values.unit_price, '0', 'P311_UNIT_PRICE default 0');
    const bad = await req1.post('/forms/requestLine', { values: { request_id: requestId, item_id: String(api.ids.atk), qty: '1,5', unit_price: '' } });
    assert.deepEqual(bad.body.fieldErrors, [
      { field: 'P311_QTY', message: 'Qty must be a number greater than or equal to 0.' },
      { field: 'P311_UNIT_PRICE', message: 'Harga Satuan must have some value.' },
    ]);
    const ok = await req1.post('/forms/requestLine', { values: { request_id: requestId, item_id: String(api.ids.atk), qty: '3', unit_price: '55000' } });
    assert.equal(ok.status, 201, JSON.stringify(ok.body));
    lineId = ok.body.id;
    const line = await req1.get(`/forms/requestLine/${lineId}`);
    assert.equal(line.body.values.line_amount, '165000');

    const none = await req1.get('/pages/302');
    assert.equal(none.body.selected, null, '"Belum dipilih" region when P302_REQUEST_ID is null');
    assert.equal(none.body.list.rows[0].request_no, `REQ-${year}-0001`);
    const detail = await req1.get(`/pages/302?requestId=${requestId}`);
    assert.equal(detail.body.selected.purpose, 'ATK kantor');
    assert.equal(detail.body.lines.rows.length, 1);
    assert.equal(detail.body.lines.rows[0].item_id_dsp, 'ATK-001 - Kertas A4 80gsm (RIM)');
    assert.deepEqual(detail.body.buttons, { EDIT_HEADER: true, CREATE_REQUEST_LINES: true });
    const asWarehouse = await wh1.get(`/pages/302?requestId=${requestId}`);
    assert.deepEqual(asWarehouse.body.buttons, { EDIT_HEADER: false, CREATE_REQUEST_LINES: false }, 'button schemes: REQUESTER only (J-05)');
  });

  let approvalId;
  await t.test('page 301 SUBMIT: save + submit in one transaction, then the form is locked', async () => {
    const row = await req1.get(`/forms/request/${requestId}`);
    const values = { ...row.body.values };
    delete values.request_id; delete values.request_no; delete values.status;
    const r = await req1.post(`/forms/request/${requestId}/submit`, { checksum: row.body.checksum, values: { ...values, notes: 'mohon segera' } });
    assert.equal(r.status, 200, JSON.stringify(r.body));
    assert.equal(r.body.message, 'Row updated. Dokumen diajukan untuk approval.', 'notes changed, so the DML message comes first');
    assert.deepEqual(r.body.messageKeys, ['DML:UPDATED', '301:CALL_SUBMIT_REQUESTS']);
    const after = await req1.get(`/forms/request/${requestId}`);
    assert.equal(after.body.values.status, 'SUBMITTED');
    assert.equal(after.body.values.notes, 'mohon segera', 'SAVE_REQUESTS ran before CALL_SUBMIT_REQUESTS');
    assert.deepEqual(after.body.buttons, { CREATE: false, DELETE: false, SAVE: false, SUBMIT: false });
    assert.deepEqual(after.body.readOnly, { department_id: true, need_date: true, purpose: true, status: true });
    expectError(await req1.put(`/forms/request/${requestId}`, { checksum: after.body.checksum, values: { request_date: today } }),
      409, 'ACTION_NOT_AVAILABLE', 'Aksi SAVE tidak tersedia: status SUBMITTED');
    expectError(await req1.del(`/forms/request/${requestId}`, { checksum: after.body.checksum }),
      409, 'ACTION_NOT_AVAILABLE', 'Aksi DELETE tidak tersedia: status SUBMITTED');
    const lineForm = await req1.get(`/forms/requestLine/${lineId}`);
    expectError(await req1.del(`/forms/requestLine/${lineId}`, { checksum: lineForm.body.checksum }), 409, 'REQUEST_LINES_LOCKED');
    const detail = await req1.get(`/pages/302?requestId=${requestId}`);
    assert.equal(detail.body.buttons.CREATE_REQUEST_LINES, false);
    const lov = await req1.get('/lovs/APX_DEMO_REQUESTS');
    assert.deepEqual(lov.body, [], 'submitted requests leave the DRAFT/REJECTED LOV');
  });

  await t.test('pages 190/191 approval inbox and dialog', async () => {
    const inbox = await mgr1.get('/regions/approvalInbox');
    assert.equal(inbox.status, 200);
    assert.equal(inbox.body.rows.length, 1);
    assert.equal(inbox.body.rows[0].can_act_yn, 'Y');
    approvalId = inbox.body.rows[0].approval_id;
    const asRequester = await req1.get(`/forms/approval/${approvalId}`);
    assert.deepEqual(asRequester.body.buttons, { APPROVE: false, REJECT: false });
    const form = await mgr1.get(`/forms/approval/${approvalId}`);
    assert.deepEqual(form.body.buttons, { APPROVE: true, REJECT: true });
    assert.equal(form.body.values.amount, '165000');
    expectError(await mgr1.post(`/forms/approval/${approvalId}/reject`, { note: '   ' }), 422, 'REJECT_NOTE_REQUIRED', 'Alasan penolakan wajib diisi.');
    expectError(await req1.post(`/forms/approval/${approvalId}/approve`, {}), 403, 'SEGREGATION_OF_DUTIES', 'Segregation of duties: pengaju tidak boleh menyetujui dokumennya sendiri.');
    expectError(await wh1.post(`/forms/approval/${approvalId}/approve`, {}), 403, 'MISSING_APPROVER_ROLE', 'Anda tidak memiliki role MANAGER untuk approval ini.');
    const home = await mgr1.get('/pages/100');
    assert.equal(home.body.kpis[0].metric_value, '1', 'Approval Menunggu Anda');
    const ok = await mgr1.post(`/forms/approval/${approvalId}/approve`, { note: ' ok ' });
    assert.equal(ok.status, 200);
    assert.equal(ok.body.message, 'Dokumen disetujui.');
    expectError(await mgr1.post(`/forms/approval/${approvalId}/approve`, {}), 409, 'APPROVAL_ALREADY_PROCESSED');
    const done = await mgr1.get(`/forms/approval/${approvalId}`);
    assert.equal(done.body.values.status, 'APPROVED');
  });

  await t.test('page 301 after approval: status editable, locked items ignored, lost update detected', async () => {
    const row = await req1.get(`/forms/request/${requestId}`);
    assert.equal(row.body.values.status, 'APPROVED');
    assert.deepEqual(row.body.readOnly, { department_id: true, need_date: true, purpose: true, status: false });
    assert.equal(row.body.buttons.SAVE, true);
    const stale = row.body.checksum;
    const r = await req1.put(`/forms/request/${requestId}`, { checksum: stale, values: {
      request_date: row.body.values.request_date, purpose: 'tampered', status: 'FULFILLED', notes: 'diterima' } });
    assert.equal(r.status, 200, JSON.stringify(r.body));
    const after = await req1.get(`/forms/request/${requestId}`);
    assert.equal(after.body.values.status, 'FULFILLED');
    assert.equal(after.body.values.purpose, 'ATK kantor', 'read-only item is not submitted');
    expectError(await req1.put(`/forms/request/${requestId}`, { checksum: stale, values: { request_date: today, status: 'CLOSED' } }),
      409, 'LOST_UPDATE', 'Current version of data in database has changed since user initiated update process.');
    expectError(await req1.put(`/forms/request/${requestId}`, { values: { request_date: today } }), 409, 'LOST_UPDATE');
    expectError(await req1.put(`/forms/request/${requestId}`, { checksum: after.body.checksum, values: { request_date: today, status: 'DRAFT' } }),
      409, 'REQUEST_STATUS_TRANSITION');
  });

  await t.test('pages 201/211: master data DML, normalization, DB errors with Oracle messages', async () => {
    const init = await wh1.get('/forms/department');
    assert.equal(init.body.values.active_yn, 'Y', 'P201_ACTIVE_YN default Y');
    const created = await wh1.post('/forms/department', { values: { dept_code: ' qa ', dept_name: 'Quality', active_yn: 'Y' } });
    assert.equal(created.status, 201, JSON.stringify(created.body));
    const row = await wh1.get(`/forms/department/${created.body.id}`);
    assert.equal(row.body.values.dept_code, 'QA');
    expectError(await wh1.post('/forms/department', { values: { dept_code: 'qa', dept_name: 'Dup', active_yn: 'Y' } }),
      409, 'DB_UNIQUE_VIOLATION', 'ORA-00001: unique constraint (WKSP_KCSI.APX_DEMO_DEPARTMENTS_U1) violated on table WKSP_KCSI.APX_DEMO_DEPARTMENTS columns (DEPT_CODE)');
    const ops = await wh1.get(`/forms/department/${dept}`);
    expectError(await wh1.del(`/forms/department/${dept}`, { checksum: ops.body.checksum }),
      409, 'DB_FOREIGN_KEY_VIOLATION', 'ORA-02292: integrity constraint (WKSP_KCSI.APX_DEMO_REQUESTS_FK1) violated - child record found');
    const upd = await wh1.put(`/forms/department/${created.body.id}`, { checksum: row.body.checksum, values: { dept_code: 'qa', dept_name: 'Quality Assurance', active_yn: 'N' } });
    assert.equal(upd.status, 200, JSON.stringify(upd.body));
    assert.equal(upd.body.message, 'Row updated.');
    expectError(await wh1.del(`/forms/department/${created.body.id}`, { checksum: row.body.checksum }), 409, 'LOST_UPDATE');
    const fresh = await wh1.get(`/forms/department/${created.body.id}`);
    const same = await wh1.put(`/forms/department/${created.body.id}`, { checksum: fresh.body.checksum, values: { dept_code: 'QA', dept_name: 'Quality Assurance', active_yn: 'N' } });
    assert.deepEqual([same.status, same.body.message, same.body.messageKeys], [200, null, []], 'no change, no "Row updated."');
    const del = await wh1.del(`/forms/department/${created.body.id}`, { checksum: fresh.body.checksum });
    assert.deepEqual([del.status, del.body.message], [200, 'Row deleted.']);
    expectError(await wh1.get(`/forms/department/${created.body.id}`), 404, 'NOT_FOUND');

    const item = await wh1.get('/forms/item');
    assert.deepEqual([item.body.values.std_price, item.body.values.active_yn], ['0', 'Y']);
    const badItem = await wh1.post('/forms/item', { values: { item_code: 'x', item_name: 'X', category: '', uom: 'pcs', std_price: 'abc', active_yn: 'Y' } });
    assert.deepEqual(badItem.body.fieldErrors, [
      { field: 'P211_CATEGORY', message: 'Kategori must have some value.' },
      { field: 'P211_STD_PRICE', message: 'Harga Standar must be a number greater than or equal to 0.' },
    ]);
    expectError(await wh1.post('/forms/item', { values: { item_code: 'x', item_name: 'X', category: 'FOOD', uom: 'pcs', std_price: '1', active_yn: 'Y' } }),
      422, 'DB_CHECK_VIOLATION', 'ORA-02290: check constraint (WKSP_KCSI.APX_DEMO_ITEMS_CK1) violated');
    expectError(await wh1.post('/forms/item', { values: { item_code: 'x', item_name: 'X', category: 'ATK', uom: 'pcs', std_price: '1', active_yn: 'Y', created_by: 'X' } }),
      422, 'INVALID_INPUT');
  });

  await t.test('pages 501/511: administration forms', async () => {
    const init = await admin.get('/forms/userRole');
    assert.equal(init.body.values.username, 'ADMIN1', 'P501_USERNAME default :APP_USER');
    const r = await admin.post('/forms/userRole', { values: { username: 'new.user', role_code: 'requester' } });
    assert.equal(r.status, 201, JSON.stringify(r.body));
    const row = await admin.get(`/forms/userRole/${r.body.id}`);
    assert.deepEqual([row.body.values.username, row.body.values.role_code], ['NEW.USER', 'REQUESTER']);
    expectError(await admin.post('/forms/userRole', { values: { username: 'x', role_code: 'NOPE' } }), 409, 'DB_FOREIGN_KEY_VIOLATION');
    assert.equal((await admin.del(`/forms/userRole/${r.body.id}`, { checksum: row.body.checksum })).status, 200);

    const doc = await admin.get('/forms/docType/REQ');
    assert.deepEqual(doc.body.buttons, { CREATE: false, SAVE: true, DELETE: false });
    const v = { ...doc.body.values };
    delete v.doc_type;
    const saved = await admin.put('/forms/docType/REQ', { checksum: doc.body.checksum, values: { ...v, level2_limit: '20000000', approver2_role: '' } });
    assert.equal(saved.status, 200, JSON.stringify(saved.body));
    const reread = await admin.get('/forms/docType/REQ');
    assert.deepEqual([reread.body.values.level2_limit, reread.body.values.approver2_role], ['20000000', null]);
  });

  await t.test('reports: IR search/sort/paging, faceted search counts, download', async () => {
    for (let i = 0; i < 3; i++) {
      await req1.post('/forms/request', { values: { department_id: String(api.ids.ops + 1), request_date: today, purpose: `Laptop ${i}` } });
    }
    const all = await req1.get('/regions/requests');
    assert.equal(all.body.total, 4);
    assert.equal(all.body.rowsPerPage, 15);
    assert.deepEqual(all.body.rows.map((r) => r.request_no), [4, 3, 2, 1].map((n) => `REQ-${year}-000${n}`), 'ORDER BY REQUEST_NO DESC');
    const status = all.body.facets.find((f) => f.item === 'P300_STATUS');
    assert.deepEqual(status.values, [{ value: 'DRAFT', count: 3 }, { value: 'FULFILLED', count: 1 }]);
    const filtered = await req1.get('/regions/requests?facet=P300_STATUS:FULFILLED');
    assert.equal(filtered.body.total, 1);
    assert.deepEqual(filtered.body.facets.find((f) => f.item === 'P300_STATUS').values.length, 2, 'a facet ignores its own selection');
    assert.deepEqual(filtered.body.facets.find((f) => f.item === 'P300_DEPARTMENT_ID_DSP').values, [{ value: 'OPS - Operations', count: 1 }]);
    const search = await req1.get('/regions/requests?q=LAPTOP%201');
    assert.equal(search.body.total, 1, 'row search is case-insensitive contains');
    const byDate = await req1.get(`/regions/requests?q=${encodeURIComponent(new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' }).replace(/ /g, '-').toLowerCase())}`);
    assert.equal(byDate.body.total, 4, 'dates are searched in DD-MON-YYYY');
    expectError(await req1.get('/regions/requests?facet=P999:X'), 422, 'INVALID_INPUT');

    const ir = await mgr1.get('/regions/requestSummary?sort=total_amount&dir=desc');
    assert.equal(ir.body.rows[0].total_amount, '165000');
    assert.equal(ir.body.rowsPerPage, 50);
    expectError(await mgr1.get('/regions/requestSummary?sort=password'), 422, 'INVALID_INPUT');
    const lines = await req1.get('/regions/requestLines?all=1');
    assert.equal(lines.body.rows.length, 1);
    // J-04: numbers sort by value, not by their text (9 < 10 < 165000; as text "10" < "165000" < "9")
    const draftId = String(all.body.rows[0].request_id);
    for (const price of ['10', '9']) {
      const added = await req1.post('/forms/requestLine', { values: { request_id: draftId, item_id: String(api.ids.atk), qty: '1', unit_price: price } });
      assert.equal(added.status, 201, JSON.stringify(added.body));
    }
    const byAmount = await req1.get('/regions/requestLines?sort=line_amount&dir=asc');
    assert.deepEqual(byAmount.body.rows.map((r) => r.line_amount), ['9', '10', '165000']);
    const byId = await req1.get('/regions/requestLines');
    assert.deepEqual(byId.body.rows.map((r) => Number(r.line_id)), byId.body.rows.map((r) => Number(r.line_id)).sort((x, y) => x - y), 'default LINE_ID ASC by value');
    // R4a: a region bound to a hidden page item is served generically; the value comes as item.<NAME>
    const noHeader = await req1.get('/regions/requestHeader');
    assert.equal(noHeader.status, 200, JSON.stringify(noHeader.body));
    assert.equal(noHeader.body.rows.length, 0, 'P302_REQUEST_ID null: no header');
    const header = await req1.get(`/regions/requestHeader?item.P302_REQUEST_ID=${draftId}`);
    assert.equal(header.body.rows.length, 1);
    expectError(await req1.get(`/regions/requestHeader?item.P999_X=1`), 422, 'INVALID_INPUT', 'item P999_X is not a bind of region 302:Permintaan Barang');
    expectError(await req1.get(`/regions/requestHeader?item.APP_USER=DEMO_DIR`), 422, 'INVALID_INPUT');
    expectError(await req1.get(`/regions/requestHeader?item.P302_REQUEST_ID=abc`), 422, 'INVALID_INPUT');
    expectError(await req1.get('/regions/nope'), 422, 'INVALID_INPUT');

    const items = await req1.get('/regions/items?facet=P210_CATEGORY:IT');
    assert.deepEqual(items.body.rows.map((r) => r.item_code), ['IT-001']);
    assert.deepEqual(items.body.facets.find((f) => f.item === 'P210_CATEGORY').values, [{ value: 'ATK', count: 1 }, { value: 'IT', count: 1 }]);
  });

  await t.test('LOVs', async () => {
    const roles = await req1.get('/lovs/DEMO_ROLES');
    assert.deepEqual(roles.body.map((r) => r.value), ['ADMIN', 'DIRECTOR', 'MANAGER', 'REQUESTER', 'WAREHOUSE']);
    assert.equal(roles.body[0].display, 'ADMIN - Administrator');
    const items = await req1.get('/lovs/APX_DEMO_ITEMS');
    assert.deepEqual(items.body.map((r) => r.display), ['ATK-001 - Kertas A4 80gsm (RIM)', 'IT-001 - Laptop 14 inch (UNIT)']);
    expectError(await req1.get('/lovs/YES_NO'), 422, 'INVALID_INPUT', 'LOV YES_NO tidak dikenal.');
  });
});
