#!/usr/bin/env node
// DISPOSABLE databases only: drops schemas app and iam (local accounts), applies db/migrations and the dev seed.
// Refuses unless ALLOW_DB_RESET=1 and NODE_ENV is not production.
import { execFileSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import pg from 'pg';

if (process.env.ALLOW_DB_RESET !== '1' || process.env.NODE_ENV === 'production') {
  throw new Error('reset-dev-db refused: set ALLOW_DB_RESET=1 on a disposable database');
}
const here = dirname(fileURLToPath(import.meta.url));
const client = new pg.Client({ connectionString: process.env.DATABASE_URL });
await client.connect();
await client.query('DROP SCHEMA IF EXISTS app CASCADE');
await client.query('DROP SCHEMA IF EXISTS iam CASCADE');
await client.end();
execFileSync(process.execPath, [join(here, 'migrate.mjs')], { stdio: 'inherit' });
execFileSync(process.execPath, [join(here, 'seed-dev.mjs')], { stdio: 'inherit' });
