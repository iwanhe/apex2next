'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { principal, wallClock, businessConfigFromEnv } = require('../dist/business/context.js');
const { errors } = require('../dist/business/errors.js');
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
  const { accessLog } = require('../dist/http/access-log.js');
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
  const { clockFromEnv, systemClock } = require('../dist/business/context.js');
  assert.equal(clockFromEnv({}), systemClock);
  let real = Date.parse('2026-12-01T00:00:00Z');
  const clock = clockFromEnv({ APP_CLOCK_START: '2026-11-09T07:45:00Z' }, () => real);
  assert.equal(clock.now().toISOString(), '2026-11-09T07:45:00.000Z');
  real += 90_000;
  assert.equal(clock.now().toISOString(), '2026-11-09T07:46:30.000Z');
  assert.throws(() => clockFromEnv({ APP_CLOCK_START: '2026-11-09T07:45:00Z', NODE_ENV: 'production' }), /refused/);
  assert.throws(() => clockFromEnv({ APP_CLOCK_START: '2026-11-09 07:45' }), /ISO instant/);
});
