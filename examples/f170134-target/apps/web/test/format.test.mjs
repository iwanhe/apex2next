// Display formats of the source application (DD-MON-YYYY, TO_CHAR number masks). Node >= 22.6 strips TS types.
import test from 'node:test';
import assert from 'node:assert/strict';
import { formatDate, formatNumber, formatValue, rowRange } from '../lib/format.ts';

test('DD-MON-YYYY from ISO date or timestamp', () => {
  assert.equal(formatDate('2026-11-09'), '09-NOV-2026');
  assert.equal(formatDate('2026-01-31 23:59:59'), '31-JAN-2026');
  assert.equal(formatDate(null), '');
});

test('TO_CHAR masks used by the application', () => {
  assert.equal(formatNumber('165000', '999G999G999G999G990'), '165,000');
  assert.equal(formatNumber('0', '999G999G999G999G990'), '0');
  assert.equal(formatNumber('3', '999G999G999G990D99'), '3.00');
  assert.equal(formatNumber('1234.5', '999G999G999G990D99'), '1,234.50');
  assert.equal(formatNumber('-1234567', '999G999G999G999G990'), '-1,234,567');
  assert.equal(formatNumber('12500000.4', '999G999G999G999G990'), '12,500,000', 'rounded to the mask');
  assert.equal(formatNumber('42', null), '42', 'no mask: value as stored');
  assert.equal(formatValue('2026-11-09 00:00:00', 'DATE'), '09-NOV-2026');
  assert.equal(formatValue('x', 'STRING'), 'x');
});

test('IR pagination label', () => {
  assert.equal(rowRange(1, 15, 15, 40), '1 - 15 of 40');
  assert.equal(rowRange(3, 15, 10, 40), '31 - 40 of 40');
  assert.equal(rowRange(1, 15, 0, 0), '');
});
