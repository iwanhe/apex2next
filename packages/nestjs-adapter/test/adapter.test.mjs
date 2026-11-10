import 'reflect-metadata';
import test from 'node:test';
import assert from 'node:assert/strict';
import { BadRequestException } from '@nestjs/common';
import { RuntimePageItemsPipe } from '../dist/index.js';

const items = [
  { id: 'i1', name: 'P_NAME', label: 'Name', kind: 'TEXT', dataType: 'VARCHAR2', required: true, writable: true, trimSpaces: 'BOTH' },
  { id: 'i2', name: 'P_COUNT', label: 'Count', kind: 'NUMBER', dataType: 'NUMBER', required: true, writable: true, trimSpaces: 'BOTH', minValue: 1 },
];

test('NestJS page-item pipe returns normalized values', () => {
  const pipe = new RuntimePageItemsPipe(items);
  assert.deepEqual(pipe.transform({ P_NAME: '  Widget ', P_COUNT: '2' }, {}), {
    P_NAME: 'Widget', P_COUNT: '2',
  });
});

test('NestJS page-item pipe returns structured validation errors', () => {
  const pipe = new RuntimePageItemsPipe(items);
  assert.throws(
    () => pipe.transform({ P_NAME: '', P_COUNT: '0' }, {}),
    (error) => error instanceof BadRequestException
      && error.getResponse().code === 'VALIDATION_FAILED'
      && error.getResponse().fieldErrors.length === 2,
  );
});

test('NestJS page-item pipe rejects non-object payloads', () => {
  const pipe = new RuntimePageItemsPipe(items);
  assert.throws(() => pipe.transform(['unexpected'], {}), BadRequestException);
});
