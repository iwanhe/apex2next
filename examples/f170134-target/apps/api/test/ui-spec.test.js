'use strict';
// WP9.5 drift guards (no database): the target must stay in step with the APEX page inventory derived from
// the authoritative SQL export (ui/apex-page-inventory.json).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const ROOT = path.join(__dirname, '..', '..', '..');
const inventory = JSON.parse(fs.readFileSync(path.join(ROOT, 'ui', 'apex-page-inventory.json'), 'utf8'));
const coverage = JSON.parse(fs.readFileSync(path.join(ROOT, 'ui', 'coverage.json'), 'utf8'));
const { REGION_SOURCES, LOV_SOURCES, regionColumns } = require('../dist/pages/report-definitions.js');
const { AUTHORIZATION_SCHEMES } = require('../dist/business/security.service.js');
const { PAGE_SCHEMES } = require('../dist/business/permintaan-barang.service.js');

const norm = (sql) => sql.toLowerCase().replace(/\s+/g, ' ').replace(/\s*,\s*/g, ', ').trim();
const pageOf = (id) => inventory.pages.find((p) => p.id === id);
const component = (page, key) => pageOf(page).components.find((c) => c.key === key);

test('generated UI spec is current', () => {
  execFileSync(process.execPath, [path.join(ROOT, 'scripts', 'generate-ui-spec.mjs'), '--check'], { stdio: 'pipe' });
});

test('region sources restate the region SQL of the export', () => {
  for (const [name, src] of Object.entries(REGION_SOURCES)) {
    const region = component(src.page, `P${src.page}:REPORT_REGION:${src.region}`) ?? component(src.page, `P${src.page}:REGION:${src.region}`);
    assert.ok(region, `${name}: region ${src.region} on page ${src.page}`);
    const sql = region.props.plug_source ?? region.props.source;
    const expected = `select ${src.select.join(', ')} from ${src.view}${src.where ? ` where ${src.where.source}` : ''}`;
    assert.equal(norm(sql), norm(expected), name);
    assert.equal(regionColumns(src).length, src.select.length);
  }
});

test('LOV sources restate the shared-component LOV queries', () => {
  const dynamic = inventory.lovs.filter((l) => l.location !== 'STATIC');
  assert.deepEqual(Object.keys(LOV_SOURCES).sort(), dynamic.map((l) => l.name).sort());
  for (const lov of dynamic) assert.equal(norm(LOV_SOURCES[lov.name].source), norm(lov.query), lov.name);
});

test('authorization schemes and messages match the export', () => {
  for (const a of inventory.authorizations) {
    assert.ok(AUTHORIZATION_SCHEMES[a.name], a.name);
    assert.equal(AUTHORIZATION_SCHEMES[a.name].message, a.errorMessage.replace('&APP_USER.', '{APP_USER}'), a.name);
  }
  const scheme = (id) => pageOf(id).scheme;
  assert.equal(PAGE_SCHEMES.approvalInbox, scheme(191));
  assert.equal(PAGE_SCHEMES.requestForm, scheme(301));
  assert.equal(PAGE_SCHEMES.requestLineForm, scheme(311));
  assert.equal(PAGE_SCHEMES.masterDataForm, scheme(201));
  assert.equal(PAGE_SCHEMES.masterDataForm, scheme(211));
  assert.equal(PAGE_SCHEMES.userRoleForm, scheme(501));
  assert.equal(inventory.application.securityScheme, 'APP_USERS');
});

test('coverage matrix maps every inventory component exactly once', () => {
  assert.equal(coverage.inventorySha256, inventory.sha256, 'coverage.json was reviewed against this inventory');
  const keys = inventory.pages.flatMap((p) => p.components.map((c) => c.key)).sort();
  assert.deepEqual(Object.keys(coverage.components).sort(), keys);
  assert.deepEqual(Object.keys(coverage.pages).sort(), inventory.pages.map((p) => String(p.id)).sort());
  for (const [key, entry] of [...Object.entries(coverage.components), ...Object.entries(coverage.pages), ...Object.entries(coverage.shared)]) {
    assert.ok(coverage.statuses.includes(entry.status), `${key}: ${entry.status}`);
    if (entry.status !== 'IMPLEMENTED') assert.ok(entry.note, `${key}: ${entry.status} needs a note`);
    for (const ref of `${entry.where ?? ''} ${entry.web ?? ''}`.match(/apps\/[A-Za-z0-9_./()[\]-]+/g) ?? []) {
      assert.ok(fs.existsSync(path.join(ROOT, ref)), `${key}: ${ref} exists`);
    }
  }
  for (const gap of coverage.gaps) assert.match(gap.id, /^G-\d{2}$/);
});
