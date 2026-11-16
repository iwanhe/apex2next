import test from 'node:test';
import assert from 'node:assert/strict';
import { applyInteractiveGridChanges as applyChanges, applyInteractiveGridChangesWithPolicy } from '../dist/generic/interactive-grid.js';
import { checksum } from '../dist/forms/forms.js';

const item = (column, options = {}) => ({
  item: `P1_${column.toUpperCase()}`, column, label: column, displayAs: 'NATIVE_TEXT_FIELD',
  dataType: 'VARCHAR2', required: false, primaryKey: false, queryOnly: false, lov: null,
  defaultValue: null, minValue: null, maxValue: null, trimSpaces: 'BOTH', ...options,
});
const form = {
  page: 1, region: 'Editable Grid', source: 'app.employee',
  pk: item('empno', { displayAs: 'NATIVE_HIDDEN', primaryKey: true, queryOnly: true }),
  items: [
    item('empno', { displayAs: 'NATIVE_HIDDEN', primaryKey: true, queryOnly: true }),
    item('ename', { required: true }),
    item('deptno'),
  ],
  dateFormat: 'YYYY-MM-DD',
};

function txWith(query) {
  return { query };
}
const noQuery = txWith(async () => { throw new Error('unexpected database call'); });
const access = { operations: ['insert', 'update', 'delete'], rowScope: { column: 'tenant_id', value: 'tenant-A' } };
const applyInteractiveGridChanges = (tx, definition, changes) => applyChanges(tx, definition, changes, access);

test('policy resolver receives the verified transaction principal and requested operations', async () => {
  const tx = { principal: { username: 'ALICE' }, query: noQuery.query };
  let seen;
  const resolver = {
    async resolve(context, definition, operations) {
      seen = { username: context.principal.username, definition, operations };
      return access;
    },
  };
  await assert.rejects(() => applyInteractiveGridChangesWithPolicy(tx, form, [
    { operation: 'update', id: '10', checksum: 'checksum', values: { ename: 'A' } },
  ], resolver), (e) => e.code === 'NOT_FOUND');
  assert.equal(seen.username, 'ALICE');
  assert.equal(seen.definition, form);
  assert.deepEqual(seen.operations, ['update']);
});

test('policy resolver fails closed when no policy is returned', async () => {
  const tx = { principal: { username: 'ALICE' }, query: noQuery.query };
  await assert.rejects(() => applyInteractiveGridChangesWithPolicy(tx, form, [
    { operation: 'insert', values: { ename: 'A' } },
  ], { async resolve() { return null; } }), (e) => e.code === 'FORBIDDEN');
});

test('policy resolver must grant every operation in a mixed batch', async () => {
  const tx = { principal: { username: 'ALICE' }, query: noQuery.query };
  await assert.rejects(() => applyInteractiveGridChangesWithPolicy(tx, form, [
    { operation: 'insert', values: { ename: 'A' } },
    { operation: 'delete', id: '10', checksum: 'checksum' },
  ], { async resolve() { return { ...access, operations: ['insert'] }; } }),
  (e) => e.code === 'FORBIDDEN');
});

test('rejects empty and oversized change batches before database access', async () => {
  await assert.rejects(() => applyInteractiveGridChanges(noQuery, form, []), (e) => e.code === 'INVALID_INPUT');
  await assert.rejects(() => applyInteractiveGridChanges(noQuery, form,
    Array.from({ length: 101 }, () => ({ operation: 'insert', values: {} }))),
  (e) => e.code === 'INVALID_INPUT');
});

test('rejects duplicate row IDs and missing lost-update checksums', async () => {
  await assert.rejects(() => applyInteractiveGridChanges(noQuery, form, [
    { operation: 'delete', id: '10', checksum: 'old' },
    { operation: 'update', id: '10', checksum: 'old', values: { ename: 'A' } },
  ]), (e) => e.code === 'INVALID_INPUT');
  await assert.rejects(() => applyInteractiveGridChanges(noQuery, form, [
    { operation: 'delete', id: '10', checksum: '' },
  ]), (e) => e.code === 'INVALID_INPUT');
});

test('partial update preserves omitted columns and verifies the loaded checksum', async () => {
  const current = { empno: '10', ename: 'Old', deptno: '20' };
  const seen = [];
  const tx = txWith(async (sql, values = []) => {
    seen.push({ sql, values });
    if (sql.startsWith('SAVEPOINT') || sql.startsWith('RELEASE') || sql.startsWith('ROLLBACK TO')) return { rows: [], rowCount: 0 };
    if (sql.startsWith('SELECT')) return { rows: [current], rowCount: 1 };
    if (sql.startsWith('UPDATE')) return { rows: [], rowCount: 1 };
    throw new Error(`unexpected SQL: ${sql}`);
  });
  const result = await applyInteractiveGridChanges(tx, form, [
    { operation: 'update', id: '10', checksum: checksum(form, current), values: { ename: 'New' } },
  ]);
  assert.deepEqual(result, [{ operation: 'update', id: '10' }]);
  const update = seen.find((q) => q.sql.startsWith('UPDATE'));
  assert.deepEqual(update.values, ['10', 'tenant-A', 'New', '20']);
});

test('insert preserves database defaults for omitted optional columns', async () => {
  const seen = [];
  const tx = txWith(async (sql, values = []) => {
    seen.push({ sql, values });
    if (sql.startsWith('SAVEPOINT') || sql.startsWith('RELEASE') || sql.startsWith('ROLLBACK TO')) return { rows: [], rowCount: 0 };
    if (sql.startsWith('INSERT')) return { rows: [{ id: '11' }], rowCount: 1 };
    throw new Error(`unexpected SQL: ${sql}`);
  });
  const result = await applyInteractiveGridChanges(tx, form, [
    { operation: 'insert', values: { ename: 'New' } },
  ]);
  assert.deepEqual(result, [{ operation: 'insert', id: '11' }]);
  const insert = seen.find((q) => q.sql.startsWith('INSERT'));
  assert.match(insert.sql, /INSERT INTO app\.employee \(ename, tenant_id\) VALUES \(\$1, \$2\)/);
  assert.deepEqual(insert.values, ['New', 'tenant-A']);
});

test('rolls the whole batch back to its savepoint when a later row fails', async () => {
  const current = { empno: '10', ename: 'Old', deptno: '20' };
  const seen = [];
  const tx = txWith(async (sql, values = []) => {
    seen.push({ sql, values });
    if (sql.startsWith('SAVEPOINT') || sql.startsWith('RELEASE') || sql.startsWith('ROLLBACK TO')) return { rows: [], rowCount: 0 };
    if (sql.startsWith('INSERT')) return { rows: [{ id: '11' }], rowCount: 1 };
    if (sql.startsWith('SELECT')) return { rows: [current], rowCount: 1 };
    throw new Error(`unexpected SQL: ${sql}`);
  });
  await assert.rejects(() => applyInteractiveGridChanges(tx, form, [
    { operation: 'insert', values: { ename: 'First' } },
    { operation: 'update', id: '10', checksum: 'stale-checksum', values: { ename: 'Second' } },
  ]), (e) => e.code === 'LOST_UPDATE');
  assert.ok(seen.some((q) => q.sql === 'ROLLBACK TO SAVEPOINT apex2next_ig_batch'));
});


test('scopes locked row lookup and update to the server tenant', async () => {
  const current = { empno: '10', ename: 'Old', deptno: '20' };
  const seen = [];
  const tx = txWith(async (sql, values = []) => {
    seen.push({ sql, values });
    if (sql.startsWith('SAVEPOINT') || sql.startsWith('RELEASE') || sql.startsWith('ROLLBACK TO')) return { rows: [], rowCount: 0 };
    if (sql.startsWith('SELECT')) return { rows: [current], rowCount: 1 };
    if (sql.startsWith('UPDATE')) return { rows: [], rowCount: 1 };
    throw new Error(`unexpected SQL: ${sql}`);
  });
  await applyInteractiveGridChanges(tx, form, [
    { operation: 'update', id: '10', checksum: checksum(form, current), values: { ename: 'Scoped' } },
  ]);
  const select = seen.find((q) => q.sql.startsWith('SELECT'));
  const update = seen.find((q) => q.sql.startsWith('UPDATE'));
  assert.match(select.sql, /tenant_id = \$2 FOR UPDATE/);
  assert.deepEqual(select.values, ['10', 'tenant-A']);
  assert.match(update.sql, /WHERE empno = \$1 AND tenant_id = \$2/);
  assert.deepEqual(update.values.slice(0, 2), ['10', 'tenant-A']);
});

test('cross-tenant row is indistinguishable from a missing row', async () => {
  const seen = [];
  const tx = txWith(async (sql, values = []) => {
    seen.push({ sql, values });
    if (sql.startsWith('SAVEPOINT') || sql.startsWith('RELEASE') || sql.startsWith('ROLLBACK TO')) return { rows: [], rowCount: 0 };
    if (sql.startsWith('SELECT')) return { rows: [], rowCount: 0 };
    throw new Error(`unexpected SQL: ${sql}`);
  });
  await assert.rejects(() => applyInteractiveGridChanges(tx, form, [
    { operation: 'delete', id: 'foreign-row', checksum: 'valid-looking-checksum' },
  ]), (e) => e.code === 'NOT_FOUND');
  const select = seen.find((q) => q.sql.startsWith('SELECT'));
  assert.deepEqual(select.values, ['foreign-row', 'tenant-A']);
  assert.match(select.sql, /tenant_id = \$2/);
});

test('insert rejects client-supplied ownership and policy without row scope fails closed', async () => {
  await assert.rejects(() => applyChanges(noQuery, form, [
    { operation: 'insert', values: { ename: 'Mallory', tenant_id: 'tenant-B' } },
  ], access), (e) => e.code === 'FORBIDDEN');
  await assert.rejects(() => applyChanges(noQuery, form, [
    { operation: 'insert', values: { ename: 'No scope' } },
  ], { operations: ['insert'] }), (e) => e.code === 'FORBIDDEN');
});
