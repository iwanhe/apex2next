'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { principal, wallClock, businessConfigFromEnv } = require('@apex2next/runtime-api');
const { errors } = require('@apex2next/runtime-api');
const { normalizeSql, requestDocument } = require('../dist/business/document-types.js');
const { AUTHORIZATION_SCHEMES } = require('../dist/business/security.service.js');

test('BR-SEC-01 principal is trimmed, upper-cased and required', () => {
  assert.deepEqual(principal('  req1 '), { username: 'REQ1' });
  assert.throws(() => principal(''), (e) => e.code === 'UNAUTHENTICATED');
  assert.throws(() => principal(null), (e) => e.code === 'UNAUTHENTICATED');
});

test('clock policy: one wall-clock value per configured time zone (replaces SYSDATE)', () => {
  const d = new Date('2026-12-31T20:30:00Z');
  assert.deepEqual(wallClock(d, 'UTC'), { timestamp: '2026-12-31 20:30:00', date: '2026-12-31 00:00:00', year: '2026' });
  assert.deepEqual(wallClock(d, 'Asia/Jakarta'), { timestamp: '2027-01-01 03:30:00', date: '2027-01-01 00:00:00', year: '2027' });
  assert.throws(() => businessConfigFromEnv({ APP_TIME_ZONE: 'Mars/Base' }), /not a valid IANA/);
  assert.equal(businessConfigFromEnv({}).timeZone, 'UTC');
});

test('error messages keep the Oracle text and NULL-as-empty concatenation', () => {
  const e = errors.notSubmittable(null, 'SUBMITTED');
  assert.equal(e.message, 'Dokumen  berstatus SUBMITTED dan tidak dapat diajukan.');
  assert.equal(e.oracleCode, -20101);
  assert.equal(e.httpStatus, 409);
  assert.equal(errors.statusTransition('DRAFT', 'CLOSED').message,
    'Perubahan status DRAFT -> CLOSED tidak diizinkan. Gunakan Submit for Approval.');
  assert.deepEqual(Object.keys(errors.linesLocked('APPROVED').toJSON()), ['code', 'oracleCode', 'rule', 'message']);
});

test('BR-APR-02 document type configuration is compared, not executed', () => {
  assert.equal(
    normalizeSql('(select NVL(sum(l.line_amount), 0)\n from apx_demo_request_lines l where l.request_id = t.request_id)'),
    requestDocument.expected.amountExpr);
  assert.notEqual(normalizeSql('(select 1 from dual)'), requestDocument.expected.amountExpr);
  assert.equal(normalizeSql(''), null);
});

test('BR-SEC-05 authorization schemes match the APEX export', () => {
  assert.deepEqual(Object.keys(AUTHORIZATION_SCHEMES).sort(), ['ADMIN_RIGHTS', 'APP_USERS', 'MASTER_DATA', 'REQUESTER', 'WAREHOUSE']);
  assert.deepEqual(AUTHORIZATION_SCHEMES.REQUESTER.roles, ['REQUESTER', 'MANAGER']);
  assert.equal(AUTHORIZATION_SCHEMES.APP_USERS.roles, 'ANY');
});

test('WP9.7 access log: one JSON line, no query string, request id echoed, user after auth', () => {
  const { EventEmitter } = require('node:events');
  const { accessLog } = require('@apex2next/runtime-api');
  const lines = [];
  const mw = accessLog((l) => lines.push(JSON.parse(l)));
  const run = (header) => {
    const req = { method: 'GET', path: '/regions/requestLines', originalUrl: '/regions/requestLines?q=secret', header: () => header };
    const res = Object.assign(new EventEmitter(), { statusCode: 200, headers: {}, setHeader(k, v) { this.headers[k] = v; } });
    let nextCalled = false;
    mw(req, res, () => { nextCalled = true; });
    req.principal = { username: 'REQ1' };
    res.emit('finish');
    assert.ok(nextCalled);
    return res;
  };
  const res = run('abc-123');
  assert.equal(res.headers['x-request-id'], 'abc-123');
  assert.deepEqual({ ...lines[0], t: 'x', ms: 0 }, { t: 'x', id: 'abc-123', method: 'GET', path: '/regions/requestLines', status: 200, ms: 0, user: 'REQ1' });
  assert.ok(!JSON.stringify(lines[0]).includes('secret'));
  run('bad id with spaces');
  assert.match(lines[1].id, /^[0-9a-f-]{36}$/);
});

test('APP_CLOCK_START: replay clock starts at the instant and runs forward; refused in production', () => {
  const { clockFromEnv, systemClock } = require('@apex2next/runtime-api');
  assert.equal(clockFromEnv({}), systemClock);
  let real = Date.parse('2026-12-01T00:00:00Z');
  const clock = clockFromEnv({ APP_CLOCK_START: '2026-11-09T07:45:00Z' }, () => real);
  assert.equal(clock.now().toISOString(), '2026-11-09T07:45:00.000Z');
  real += 90_000;
  assert.equal(clock.now().toISOString(), '2026-11-09T07:46:30.000Z');
  assert.throws(() => clockFromEnv({ APP_CLOCK_START: '2026-11-09T07:45:00Z', NODE_ENV: 'production' }), /refused/);
  assert.throws(() => clockFromEnv({ APP_CLOCK_START: '2026-11-09 07:45' }), /ISO instant/);
});

// Ported from PR #2 (R2 shared-runtime draft) into @apex2next/runtime-api, 2026-11-12.
test('item normalization follows trim_spaces; numbers and dates are always trimmed; empty is NULL', () => {
  const { normalizeValue } = require('@apex2next/runtime-api');
  const text = (trimSpaces) => ({ dataType: 'VARCHAR2', trimSpaces });
  assert.equal(normalizeValue('  a b  ', text('BOTH')), 'a b');
  assert.equal(normalizeValue('  a  ', text('LEADING')), 'a  ');
  assert.equal(normalizeValue('  a  ', text('TRAILING')), '  a');
  assert.equal(normalizeValue('  a  ', text('NONE')), '  a  ');
  assert.equal(normalizeValue('   ', text('NONE')), '   ');
  assert.equal(normalizeValue('', text('NONE')), null);
  assert.equal(normalizeValue('   ', text('BOTH')), null);
  assert.equal(normalizeValue(' 12 ', { dataType: 'NUMBER', trimSpaces: 'NONE' }), '12');
  assert.equal(normalizeValue(undefined, text('BOTH')), null);
});

test('session tokens issued in the future or longer than the TTL are refused', () => {
  const { signSession, verifySession } = require('@apex2next/runtime-api');
  const secret = 'unit-secret-unit-secret-unit-secret-00';
  const now = 1_800_000_000;
  const ok = signSession(secret, 'REQ1', 3600, now);
  assert.equal(verifySession(secret, ok, now + 10, { maxLifetimeSeconds: 3600 }).sub, 'REQ1');
  assert.equal(verifySession(secret, ok, now + 10, { maxLifetimeSeconds: 1800 }), null, 'TTL shrank after signing');
  const future = signSession(secret, 'REQ1', 3600, now + 600);
  assert.equal(verifySession(secret, future, now), null);
  assert.equal(verifySession(secret, signSession(secret, 'REQ1', 3600, now + 30), now).sub, 'REQ1', 'within clock skew');
});

test('report paging refuses page numbers that overflow the OFFSET; hidden columns are no user sort choice', async () => {
  const { runReport } = require('@apex2next/runtime-api');
  const sql = [];
  const tx = { query: async (text) => { sql.push(text); return { rows: [{ n: '0' }], rowCount: 0 }; } };
  const def = { from: 'app.t', rowsPerPage: 15, searchable: false, defaultSort: { column: 'ID', dir: 'ASC' },
    columns: [{ name: 'ID', type: 'NUMBER', hidden: true }, { name: 'NAME', type: 'STRING' }] };
  for (const page of ['Infinity', '1e300', String(Number.MAX_SAFE_INTEGER)]) {
    await assert.rejects(runReport(tx, def, { page }), (e) => e.code === 'INVALID_INPUT', page);
  }
  assert.equal(sql.length, 0);
  await runReport(tx, def, { page: 'abc' });
  assert.match(sql[0], /OFFSET 0/);
  await runReport(tx, def, { sort: 'id' }); // the default sort column stays allowed even when hidden
  await assert.rejects(runReport(tx, { ...def, defaultSort: { column: 'NAME', dir: 'ASC' } }, { sort: 'id' }),
    (e) => e.code === 'INVALID_INPUT');
});

test('LOV ordered by columns it does not show (R4a): extra derived columns, binary text order', () => {
  const { lovSql } = require('@apex2next/runtime-api');
  const sql = lovSql({ source: 'x', sql: 'select description d, cd r, display_order, updated from app.s', orderBy: 'o',
    order: [{ dir: 'ASC', numeric: true }, { dir: 'DESC' }] });
  assert.equal(sql, 'SELECT lov.d::text AS d, lov.r::text AS r FROM (select description d, cd r, display_order, updated from app.s) '
    + 'lov(d, r, o1, o2) ORDER BY lov.o1, lov.o2::text COLLATE "C" DESC');
  assert.throws(() => lovSql({ source: 'x', sql: 'select 1, 2', orderBy: 'o' }), /order columns/);
});

test('converted RAISE_APPLICATION_ERROR (P0001 + DETAIL ORA-20nnn) keeps its Oracle number', () => {
  const { mapDatabaseError } = require('@apex2next/runtime-api');
  const e = Object.assign(new Error('Start date must be before end date'), { code: 'P0001', detail: 'ORA-20001' });
  const mapped = mapDatabaseError(e, { oracleSchema: 'WKSP_X' });
  assert.equal(mapped.code, 'DB_APPLICATION_ERROR');
  assert.equal(mapped.message, 'ORA-20001: Start date must be before end date');
  assert.equal(mapped.oracleCode, -20001);
  assert.equal(mapDatabaseError(Object.assign(new Error('x'), { code: 'P0001' }), { oracleSchema: 'WKSP_X' }), null);
});
