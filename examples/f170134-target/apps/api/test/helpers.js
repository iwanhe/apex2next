'use strict';
// Shared harness for WP9.4 integration tests. Requires a DISPOSABLE PostgreSQL database in DATABASE_URL:
// every test file drops and recreates schema "app" and applies db/migrations with the real runner.
const { execFileSync } = require('node:child_process');
const path = require('node:path');
const { Pool } = require('pg');
const { PostgresDatabase } = require('../dist/database/postgres-database.js');
const { createBusinessServices } = require('../dist/business/business.module.js');
const { principal } = require('../dist/business/context.js');

const DATABASE_URL = process.env.DATABASE_URL;
const skip = !DATABASE_URL && 'DATABASE_URL (disposable PostgreSQL) not set';
const FIXED_NOW = new Date('2026-11-09T03:04:05Z');

const USERS = {
  admin: 'ADMIN1', requester: 'REQ1', requester2: 'REQ2', manager: 'MGR1', director: 'DIR1',
  warehouse: 'WH1', nobody: 'NOBODY',
};

async function resetDatabase() {
  const pool = new Pool({ connectionString: DATABASE_URL, max: 1 });
  try {
    await pool.query('DROP SCHEMA IF EXISTS app CASCADE');
  } finally {
    await pool.end();
  }
  execFileSync(process.execPath, [path.join(__dirname, '..', 'scripts', 'migrate.mjs')],
    { env: { ...process.env, DATABASE_URL }, stdio: 'pipe' });
}

/** Seed through direct DML (the reviewed data-migration path), mirroring 06_config_seed.sql. */
async function seed(pool) {
  await pool.query(`
    INSERT INTO app.apx_demo_roles (role_code, role_name) VALUES
      ('REQUESTER','Requester'), ('MANAGER','Department Manager'), ('DIRECTOR','Director'),
      ('WAREHOUSE','Warehouse'), ('ADMIN','Administrator');
    INSERT INTO app.apx_demo_doc_types (doc_type, doc_name, prefix, table_name, pk_column, number_column,
      status_column, amount_expr, validate_proc, approver1_role, approver2_role, level2_limit)
    VALUES ('REQ','Permintaan Barang','REQ','APX_DEMO_REQUESTS','REQUEST_ID','REQUEST_NO','STATUS',
      '(select nvl(sum(l.line_amount), 0) from apx_demo_request_lines l where l.request_id = t.request_id)',
      'apx_demo_request_pkg.check_submit','MANAGER','DIRECTOR',10000000);
    INSERT INTO app.apx_demo_user_roles (username, role_code) VALUES
      ('ADMIN1','ADMIN'), ('REQ1','REQUESTER'), ('REQ2','REQUESTER'), ('MGR1','MANAGER'), ('MGR1','REQUESTER'),
      ('DIR1','DIRECTOR'), ('WH1','WAREHOUSE');
    INSERT INTO app.apx_demo_departments (dept_code, dept_name) VALUES ('OPS','Operations'), ('IT','Information Technology');
    INSERT INTO app.apx_demo_items (item_code, item_name, category, uom, std_price) VALUES
      ('ATK-001','Kertas A4 80gsm','ATK','RIM',55000), ('IT-001','Laptop 14 inch','IT','UNIT',12500000);
  `);
}

async function setup({ seedData = true, clock } = {}) {
  await resetDatabase();
  const pool = new Pool({ connectionString: DATABASE_URL, max: 12 });
  if (seedData) await seed(pool);
  const database = new PostgresDatabase(pool);
  const services = createBusinessServices(database, { timeZone: 'UTC', clock: clock ?? { now: () => FIXED_NOW } });
  const ids = seedData ? {
    ops: Number((await pool.query("SELECT department_id FROM app.apx_demo_departments WHERE dept_code='OPS'")).rows[0].department_id),
    atk: Number((await pool.query("SELECT item_id FROM app.apx_demo_items WHERE item_code='ATK-001'")).rows[0].item_id),
    laptop: Number((await pool.query("SELECT item_id FROM app.apx_demo_items WHERE item_code='IT-001'")).rows[0].item_id),
  } : {};
  return { pool, database, ...services, ids, as: (key) => principal(USERS[key] ?? key) };
}

/** Assert a BusinessRuleError with the given code (and Oracle code when given). */
async function rejectsWith(assert, promise, code, oracleCode) {
  await assert.rejects(promise, (err) => {
    assert.equal(err.name, 'BusinessRuleError', String(err));
    assert.equal(err.code, code);
    if (oracleCode !== undefined) assert.equal(err.oracleCode, oracleCode);
    return true;
  });
}

module.exports = { DATABASE_URL, skip, FIXED_NOW, USERS, setup, rejectsWith };
