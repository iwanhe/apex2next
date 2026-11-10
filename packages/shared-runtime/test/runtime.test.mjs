import test from 'node:test';
import assert from 'node:assert/strict';
import {
  createRuntimeReportPlan,
  isRuntimeAuthorized,
  validateRuntimeItems,
} from '../dist/index.js';

const items = [
  { id: 'i1', name: 'P_NAME', label: 'Name', kind: 'TEXT', dataType: 'VARCHAR2', required: true, writable: true, trimSpaces: 'BOTH', maxLength: 20 },
  { id: 'i2', name: 'P_AMOUNT', label: 'Amount', kind: 'NUMBER', dataType: 'NUMBER', required: true, writable: true, trimSpaces: 'BOTH', minValue: 0, maxValue: 100 },
  { id: 'i3', name: 'P_DATE', label: 'Date', kind: 'DATE', dataType: 'DATE', required: false, writable: true, trimSpaces: 'BOTH' },
  { id: 'i4', name: 'P_STATUS', label: 'Status', kind: 'DISPLAY', dataType: 'VARCHAR2', required: false, writable: false, trimSpaces: 'NONE' },
];

test('normalizes empty strings to null and trims text', () => {
  const result = validateRuntimeItems(items, { P_NAME: '  Widget  ', P_AMOUNT: '12', P_DATE: '' });
  assert.deepEqual(result.values, { P_NAME: 'Widget', P_AMOUNT: '12', P_DATE: null });
  assert.deepEqual(result.errors, []);
});

test('reports all required, numeric, range and date errors together', () => {
  const result = validateRuntimeItems(items, { P_NAME: ' ', P_AMOUNT: '101', P_DATE: '2026-02-30' });
  assert.equal(result.errors.length, 3);
  assert.deepEqual(result.errors.map((error) => error.field), ['P_NAME', 'P_AMOUNT', 'P_DATE']);
});

test('rejects unknown and read-only item submissions', () => {
  const result = validateRuntimeItems(items, { P_NAME: 'Widget', P_AMOUNT: '1', P_STATUS: 'APPROVED' });
  assert.equal(result.values && Object.keys(result.values).length, 0);
  assert.equal(result.errors[0].field, 'P_STATUS');
});

test('authorization is fail-closed and role matching is case-insensitive', () => {
  const policy = { id: 'p1', mode: 'ANY_ROLE', roles: ['ADMIN', 'MANAGER'], message: 'Denied' };
  assert.equal(isRuntimeAuthorized(null, policy), false);
  assert.equal(isRuntimeAuthorized({ subject: 'u1', roles: ['manager'], authenticated: true }, policy), true);
  assert.equal(isRuntimeAuthorized({ subject: 'u2', roles: [], authenticated: true }, policy), false);
  assert.equal(isRuntimeAuthorized({ subject: 'u3', roles: ['ADMIN'], authenticated: false }, policy), false);
});

test('registered policy requires an authenticated principal with at least one role', () => {
  const policy = { id: 'registered', mode: 'REGISTERED', roles: [], message: 'Denied' };
  assert.equal(isRuntimeAuthorized({ subject: 'u1', roles: ['USER'], authenticated: true }, policy), true);
  assert.equal(isRuntimeAuthorized({ subject: 'u1', roles: [], authenticated: true }, policy), false);
});

test('report plan validates sort and clamps page size', () => {
  const definition = {
    id: 'requests',
    columns: [
      { name: 'REQUEST_NO', label: 'Request No', dataType: 'STRING', sortable: true, searchable: true },
      { name: 'AMOUNT', label: 'Amount', dataType: 'NUMBER', sortable: true, searchable: true },
      { name: 'SECRET', label: 'Secret', dataType: 'STRING', sortable: false, searchable: false, hidden: true },
    ],
    defaultSort: { column: 'REQUEST_NO', direction: 'ASC' },
    defaultPageSize: 25,
    maxPageSize: 100,
    searchable: true,
  };
  assert.deepEqual(createRuntimeReportPlan(definition, { search: 'abc', sort: 'amount', direction: 'desc', page: 2, pageSize: 500 }), {
    search: 'abc', sort: 'AMOUNT', direction: 'DESC', page: 2, pageSize: 100, offset: 100,
  });
  assert.throws(() => createRuntimeReportPlan(definition, { sort: 'secret' }), /Unsupported report sort/);
  assert.throws(() => createRuntimeReportPlan(definition, { direction: 'SIDEWAYS' }), /direction/);
});
