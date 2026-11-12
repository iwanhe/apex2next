#!/usr/bin/env node
// Applies db/seed/dev-seed.sql to DATABASE_URL. Refuses to run when NODE_ENV=production.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import pg from 'pg';

if (process.env.NODE_ENV === 'production') throw new Error('seed-dev refused: NODE_ENV=production');
const url = process.env.DATABASE_URL;
if (!url) throw new Error('DATABASE_URL is required');
const sql = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', 'db', 'seed', 'dev-seed.sql'), 'utf8');
const client = new pg.Client({ connectionString: url });
await client.connect();
try {
  await client.query('BEGIN');
  await client.query(sql);
  await client.query('COMMIT');
} catch (e) {
  await client.query('ROLLBACK');
  throw e;
} finally {
  await client.end();
}
