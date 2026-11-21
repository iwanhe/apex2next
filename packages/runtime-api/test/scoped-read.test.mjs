import test from 'node:test';
import assert from 'node:assert/strict';
import { readScopedRows } from '../dist/generic/scoped-read.js';

const definition = {
  source: 'app.requests',
  columns: ['request_id', 'request_no', 'status'],
  orderBy: [{ column: 'request_no', direction: 'DESC' }],
};

function txWith(responses = []) {
  const calls = [];
  return {
    calls,
    async query(sql, values) {
      calls.push({ sql, values });
      const response = responses.shift();
      return response ?? { rows: [], rowCount: 0 };
    },
  };
}

const allow = {
  authorizationScheme: 'REQUESTS_READ',
  async authorize(_tx, scheme) { assert.equal(scheme, 'REQUESTS_READ'); return true; },
  async resolveBoundary() { return { column: 'department_id', value: 'D-10' }; },
};

test('scoped reads require server authorization before any SQL', async () => {
  const tx = txWith();
  const policy = { ...allow, async authorize() { return false; } };
  await assert.rejects(() => readScopedRows(tx, definition, policy), (e) => e.code === 'FORBIDDEN');
  assert.equal(tx.calls.length, 0);
});

test('scoped reads fail closed when row boundary cannot be resolved', async () => {
  const tx = txWith();
  const policy = { ...allow, async resolveBoundary() { return null; } };
  await assert.rejects(() => readScopedRows(tx, definition, policy), (e) => e.code === 'FORBIDDEN');
  assert.equal(tx.calls.length, 0);
});

test('count and page queries share the server-derived scope and use bind parameters', async () => {
  const tx = txWith([
    { rows: [{ total: '3' }], rowCount: 1 },
    { rows: [{ request_id: '1', request_no: 'REQ-1', status: 'DRAFT' }], rowCount: 1 },
  ]);
  const result = await readScopedRows(tx, definition, allow, { limit: 10, offset: 20 });
  assert.deepEqual(result, {
    rows: [{ request_id: '1', request_no: 'REQ-1', status: 'DRAFT' }],
    total: 3, limit: 10, offset: 20,
  });
  assert.equal(tx.calls[0].sql, 'SELECT COUNT(*)::text AS total FROM app.requests WHERE department_id = $1');
  assert.deepEqual(tx.calls[0].values, ['D-10']);
  assert.equal(tx.calls[1].sql, 'SELECT request_id, request_no, status FROM app.requests WHERE department_id = $1 ORDER BY request_no DESC LIMIT $2 OFFSET $3');
  assert.deepEqual(tx.calls[1].values, ['D-10', 10, 20]);
});

test('page limits are clamped and offsets normalized', async () => {
  const tx = txWith([{ rows: [{ total: '0' }] }, { rows: [] }]);
  const result = await readScopedRows(tx, definition, allow, { limit: 1000, offset: -5 });
  assert.equal(result.limit, 100);
  assert.equal(result.offset, 0);
  assert.deepEqual(tx.calls[1].values, ['D-10', 100, 0]);
});

test('rejects unsafe table, projection and order metadata', async () => {
  const tx = txWith();
  await assert.rejects(() => readScopedRows(tx, { ...definition, source: 'app.requests; DROP TABLE x' }, allow),
    (e) => e.code === 'INVALID_INPUT');
  await assert.rejects(() => readScopedRows(tx, { ...definition, columns: ['request_id', 'request_id'] }, allow),
    (e) => e.code === 'INVALID_INPUT');
  await assert.rejects(() => readScopedRows(tx, { ...definition, orderBy: [{ column: 'not_selected' }] }, allow),
    (e) => e.code === 'INVALID_INPUT');
  assert.equal(tx.calls.length, 0);
});
