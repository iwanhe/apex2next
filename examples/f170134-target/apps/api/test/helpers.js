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

/** Seed through direct DML (the reviewed data-migration path): db/seed/dev-seed.sql. */
const SEED_SQL = require('node:fs').readFileSync(path.join(__dirname, '..', '..', '..', 'db', 'seed', 'dev-seed.sql'), 'utf8');
async function seed(pool) {
  await pool.query(SEED_SQL);
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

const DEV_PASSWORD = 'dev-password-for-tests';
const SESSION_SECRET = 'test-session-secret-0123456789abcdef';

/**
 * Starts the real Nest application (guards, filters, controllers) on an ephemeral port against a freshly
 * migrated and seeded database. Returns an HTTP client that logs users in through /auth/login.
 */
async function startApi() {
  const env = await setup();
  Object.assign(process.env, { AUTH_MODE: 'dev', DEV_LOGIN_PASSWORD: DEV_PASSWORD, SESSION_SECRET });
  const { NestFactory } = require('@nestjs/core');
  const { AppModule } = require('../dist/app.module.js');
  const nest = await NestFactory.create(AppModule, { logger: false });
  await nest.listen(0, '127.0.0.1');
  const base = await nest.getUrl();
  const call = async (token, method, url, body) => {
    const res = await fetch(base.replace('[::1]', '127.0.0.1') + url, {
      method, headers: { ...(token ? { authorization: `Bearer ${token}` } : {}), ...(body ? { 'content-type': 'application/json' } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
    const text = await res.text();
    return { status: res.status, body: text ? JSON.parse(text) : null };
  };
  const tokens = {};
  const login = async (key) => {
    const r = await call(null, 'POST', '/auth/login', { username: (USERS[key] ?? key).toLowerCase(), password: DEV_PASSWORD });
    if (r.status !== 200) throw new Error(`login ${key}: ${JSON.stringify(r.body)}`);
    return r.body.token;
  };
  const as = (key) => {
    const go = async (method, url, body) => {
      tokens[key] ??= await login(key);
      return call(tokens[key], method, url, body);
    };
    return { get: (u) => go('GET', u), post: (u, b) => go('POST', u, b ?? {}), put: (u, b) => go('PUT', u, b), del: (u, b) => go('DELETE', u, b ?? {}) };
  };
  const close = async () => { await nest.close(); await env.pool.end(); };
  return { ...env, base, call, as, close, SESSION_SECRET, DEV_PASSWORD };
}

module.exports = { DATABASE_URL, skip, FIXED_NOW, USERS, setup, rejectsWith, startApi };
