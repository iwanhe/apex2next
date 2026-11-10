'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { skip, setup, DATABASE_URL } = require('./helpers');

const DB_DIR = path.join(__dirname, '..', '..', '..', 'db');

async function snapshot(pool) {
  const q = async (sql) => (await pool.query(sql, ['app'])).rows;
  const tables = {};
  for (const r of await q(`select c.relname, a.attname, format_type(a.atttypid, a.atttypmod) as typ, not a.attnotnull as nullable,
      a.attidentity, a.attgenerated from pg_attribute a join pg_class c on c.oid = a.attrelid
      join pg_namespace n on n.oid = c.relnamespace where n.nspname = $1 and c.relkind = 'r' and c.relname <> 'schema_migrations'
      and a.attnum > 0 and not a.attisdropped order by c.relname, a.attnum`)) {
    (tables[r.relname] ??= { columns: [], constraints: [] }).columns.push(
      { name: r.attname, type: r.typ, nullable: r.nullable, identity: r.attidentity, generated: r.attgenerated });
  }
  for (const r of await q(`select c.relname, k.conname, k.contype::text as t from pg_constraint k join pg_class c on c.oid = k.conrelid
      join pg_namespace n on n.oid = c.relnamespace where n.nspname = $1 and c.relname <> 'schema_migrations'
      and k.contype in ('p','u','c','f') order by c.relname, k.conname`)) {
    tables[r.relname].constraints.push({ name: r.conname, type: r.t });
  }
  const views = {};
  for (const r of await q(`select c.relname, a.attname from pg_attribute a join pg_class c on c.oid = a.attrelid
      join pg_namespace n on n.oid = c.relnamespace where n.nspname = $1 and c.relkind = 'v' and a.attnum > 0
      order by c.relname, a.attnum`)) {
    (views[r.relname] ??= []).push(r.attname);
  }
  return { tables, views };
}

test('runner applies 0001 schema, 0002 reviewed functions, 0003 deferred views and 0004 local accounts', { skip }, async () => {
  const env = await setup({ seedData: false });
  try {
    const applied = (await env.pool.query('SELECT version FROM app.schema_migrations ORDER BY version')).rows.map((r) => r.version);
    assert.deepEqual(applied, ['0001_wp93_schema.sql', '0002_wp94_business_functions.sql', '0003_wp94_deferred_views.sql', '0004_wp9009_local_accounts.sql', '0005_wp9009_temp_password_expiry.sql']);
    const out = execFileSync(process.execPath, [path.join(__dirname, '..', 'scripts', 'migrate.mjs')],
      { env: { ...process.env, DATABASE_URL } }).toString();
    assert.equal(out, '', 're-running the runner must be a no-op');

    const plan = JSON.parse(fs.readFileSync(path.join(DB_DIR, 'schema-plan.json'), 'utf8'));
    const snap = await snapshot(env.pool);
    assert.deepEqual(snap.tables, plan.expectedCatalog.tables);
    assert.deepEqual(snap.views, { ...plan.expectedCatalog.views, ...plan.expectedCatalog.deferredViews });
    assert.equal(Object.keys(snap.views).length, 10, 'all 10 source views exist in PostgreSQL');

    const fns = (await env.pool.query(`select p.proname from pg_proc p join pg_namespace n on n.oid = p.pronamespace
      where n.nspname = 'app' order by 1`)).rows.map((r) => r.proname);
    assert.deepEqual(fns, ['can_act_yn', 'current_username', 'has_any_role', 'has_role', 'has_role_yn']);
  } finally {
    await env.pool.end();
  }
});

test('committed migrations are the generated plan output (no hand edits)', () => {
  const plan = JSON.parse(fs.readFileSync(path.join(DB_DIR, 'schema-plan.json'), 'utf8'));
  assert.equal(fs.readFileSync(path.join(DB_DIR, 'migrations', '0001_wp93_schema.sql'), 'utf8'), plan.sql);
  assert.equal(fs.readFileSync(path.join(DB_DIR, 'migrations', '0003_wp94_deferred_views.sql'), 'utf8'), plan.deferredSql);
  assert.equal(plan.transactionWrapper, false);
  assert.deepEqual(plan.functionMappings.map((m) => [m.source, m.target]), [['APX_DEMO_APPROVAL_PKG.CAN_ACT_YN', 'app.can_act_yn']]);
});
