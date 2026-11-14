import test from 'node:test';
import assert from 'node:assert/strict';
import { applyInteractiveGridChanges } from '../dist/generic/interactive-grid.js';
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
    if (sql.startsWith('SAVEPOINT') || sql.startsWith('RELEASE')) return { rows: [], rowCount: 0 };
    if (sql.startsWith('SELECT')) return { rows: [current], rowCount: 1 };
    if (sql.startsWith('UPDATE')) return { rows: [], rowCount: 1 };
    throw new Error(`unexpected SQL: ${sql}`);
  });
  const result = await applyInteractiveGridChanges(tx, form, [
    { operation: 'update', id: '10', checksum: checksum(form, current), values: { ename: 'New' } },
  ]);
  assert.deepEqual(result, [{ operation: 'update', id: '10' }]);
  const update = seen.find((q) => q.sql.startsWith('UPDATE'));
  assert.deepEqual(update.values, ['10', 'New', '20']);
});

test('insert preserves database defaults for omitted optional columns', async () => {
  const seen = [];
  const tx = txWith(async (sql, values = []) => {
    seen.push({ sql, values });
    if (sql.startsWith('SAVEPOINT') || sql.startsWith('RELEASE')) return { rows: [], rowCount: 0 };
    if (sql.startsWith('INSERT')) return { rows: [{ id: '11' }], rowCount: 1 };
    throw new Error(`unexpected SQL: ${sql}`);
  });
  const result = await applyInteractiveGridChanges(tx, form, [
    { operation: 'insert', values: { ename: 'New' } },
  ]);
  assert.deepEqual(result, [{ operation: 'insert', id: '11' }]);
  const insert = seen[0];
  assert.match(insert.sql, /INSERT INTO app\.employee \(ename\) VALUES \(\$1\)/);
  assert.deepEqual(insert.values, ['New']);
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
