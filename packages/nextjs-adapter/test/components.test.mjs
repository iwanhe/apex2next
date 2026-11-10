import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { RuntimeForm, RuntimeReportTable } from '../dist/index.js';

test('RuntimeForm renders labels, normalized values, required markers and field errors', () => {
  const html = renderToStaticMarkup(React.createElement(RuntimeForm, {
    fields: [
      { id: 'p-name', name: 'P_NAME', label: 'Name', kind: 'TEXT', dataType: 'VARCHAR2', required: true, writable: true, trimSpaces: 'BOTH' },
      { id: 'p-status', name: 'P_STATUS', label: 'Status', kind: 'DISPLAY', dataType: 'VARCHAR2', required: false, writable: false, trimSpaces: 'NONE' },
    ],
    values: { P_NAME: 'Widget', P_STATUS: 'APPROVED' },
    errors: [{ field: 'P_NAME', message: 'Name must have some value.' }],
  }));
  assert.match(html, /for="p-name"/);
  assert.match(html, /value="Widget"/);
  assert.match(html, /APPROVED/);
  assert.match(html, /role="alert"/);
  assert.match(html, /Name must have some value/);
});

test('RuntimeReportTable hides hidden columns and renders empty state', () => {
  const html = renderToStaticMarkup(React.createElement(RuntimeReportTable, {
    columns: [
      { name: 'REQUEST_NO', label: 'Request No', dataType: 'STRING', sortable: true, searchable: true },
      { name: 'SECRET', label: 'Secret', dataType: 'STRING', sortable: false, searchable: false, hidden: true },
    ],
    rows: [],
  }));
  assert.match(html, /Request No/);
  assert.doesNotMatch(html, /Secret/);
  assert.match(html, /No data found/);
});

test('RuntimeReportTable renders visible row values and nulls safely', () => {
  const html = renderToStaticMarkup(React.createElement(RuntimeReportTable, {
    columns: [
      { name: 'REQUEST_NO', label: 'Request No', dataType: 'STRING', sortable: true, searchable: true },
      { name: 'STATUS', label: 'Status', dataType: 'STRING', sortable: false, searchable: true },
    ],
    rows: [{ REQUEST_NO: 'REQ-001', STATUS: null }],
    rowKey: 'REQUEST_NO',
  }));
  assert.match(html, /REQ-001/);
  assert.match(html, /<td><\/td>/);
});
