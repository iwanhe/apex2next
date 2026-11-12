import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import pg from 'pg';

const { Pool } = pg;
const connectionString = process.env.DATABASE_URL;
if (!connectionString) {
  throw new Error('DATABASE_URL is required to run reviewed target migrations.');
}
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const migrationsDir = path.join(root, 'db', 'migrations');
const pool = new Pool({ connectionString, max: 1, connectionTimeoutMillis: 5000 });
const client = await pool.connect();

try {
  await client.query("SELECT pg_advisory_lock(hashtext('apex2next:migrations'))");
  await client.query('CREATE SCHEMA IF NOT EXISTS app');
  await client.query(
    'CREATE TABLE IF NOT EXISTS app.schema_migrations ' +
    '(version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())',
  );
  const files = (await readdir(migrationsDir))
    .filter((name) => /^\d+_[a-z0-9_-]+\.sql$/.test(name))
    .sort();

  for (const file of files) {
    const existing = await client.query(
      'SELECT 1 FROM app.schema_migrations WHERE version = $1', [file],
    );
    if (existing.rowCount) continue;
    const sql = await readFile(path.join(migrationsDir, file), 'utf8');
    await client.query('BEGIN');
    try {
      await client.query(sql);
      await client.query('INSERT INTO app.schema_migrations(version) VALUES ($1)', [file]);
      await client.query('COMMIT');
      process.stdout.write('applied ' + file + '\n');
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    }
  }
} finally {
  try {
    await client.query("SELECT pg_advisory_unlock(hashtext('apex2next:migrations'))");
  } finally {
    client.release();
    await pool.end();
  }
}
