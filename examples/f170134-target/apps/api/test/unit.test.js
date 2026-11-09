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
