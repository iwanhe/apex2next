"""Generated PostgreSQL runtime templates for target workspaces."""
from __future__ import annotations

import json
from typing import Any


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def build_runtime_files(files: dict[str, str]) -> dict[str, str]:
    """Return WP8.6 runtime files and update generated package metadata."""
    root_package = json.loads(files["package.json"])
    root_package["scripts"]["db:migrate"] = "pnpm --filter @generated/api db:migrate"

    api_package = json.loads(files["apps/api/package.json"])
    api_package["dependencies"]["pg"] = "^8.16.3"
    api_package["devDependencies"]["@types/pg"] = "^8.15.5"
    api_package["scripts"]["test"] = "pnpm build && node --test"
    api_package["scripts"]["db:migrate"] = "node scripts/migrate.mjs"

    files["README.md"] = files["README.md"].replace(
        "then run pnpm dev. Web is on port 3000; API health is on port 3001/health.",
        "then run pnpm db:migrate and pnpm dev. Web is on port 3000; API liveness is on "
        "port 3001/health and database readiness is on port 3001/health/ready.",
    ).replace(
        "Run pnpm build, pnpm test, and pnpm typecheck before deployment.",
        "Run pnpm build, pnpm test, and pnpm typecheck before deployment. The API uses "
        "parameterized PostgreSQL queries, explicit transactions, and a conservative "
        "repository base; configure DATABASE_URL and review migrations.",
    )

    app_module = files["apps/api/src/app.module.ts"].replace(
        "import { Module } from '@nestjs/common';",
        "import { Module } from '@nestjs/common';\nimport { DatabaseModule } from './database/database.module';",
    ).replace(
        "@Module({ controllers:",
        "@Module({ imports: [DatabaseModule], controllers:",
    )

    return {
        "apps/api/src/app.module.ts": app_module,
        "package.json": _json(root_package) + "\n",
        "apps/api/package.json": _json(api_package) + "\n",
        ".env.example": (
            "DATABASE_URL=postgresql://apex2next:apex2next@localhost:5432/apex2next\n"
            "API_PORT=3001\nDB_POOL_MAX=10\n"
        ),
        "docker-compose.yml": """services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: apex2next
      POSTGRES_USER: apex2next
      POSTGRES_PASSWORD: apex2next
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U apex2next -d apex2next"]
      interval: 5s
      timeout: 3s
      retries: 20
    volumes:
      - postgres_data:/var/lib/postgresql/data
volumes:
  postgres_data:
""",
        "apps/api/src/database/postgres-database.ts": """import { Injectable, OnApplicationShutdown } from '@nestjs/common';
import { Pool, PoolClient, QueryResult, QueryResultRow } from 'pg';

@Injectable()
export class PostgresDatabase implements OnApplicationShutdown {
  constructor(private readonly pool: Pool) {}

  query<Row extends QueryResultRow = QueryResultRow>(
    text: string,
    values: unknown[] = [],
  ): Promise<QueryResult<Row>> {
    return this.pool.query<Row>(text, values);
  }

  async transaction<T>(work: (client: PoolClient) => Promise<T>): Promise<T> {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');
      const result = await work(client);
      await client.query('COMMIT');
      return result;
    } catch (error) {
      try {
        await client.query('ROLLBACK');
      } catch {
        // Preserve the original error; the client is still released below.
      }
      throw error;
    } finally {
      client.release();
    }
  }

  async close(): Promise<void> {
    await this.pool.end();
  }

  async onApplicationShutdown(): Promise<void> {
    await this.close();
  }
}
""",
        "apps/api/src/database/postgres-repository.ts": """import { PostgresDatabase } from './postgres-database';

const TABLE_IDENTIFIER = /^[a-z_][a-z0-9_]*(?:\\.[a-z_][a-z0-9_]*)?$/;
const COLUMN_IDENTIFIER = /^[a-z_][a-z0-9_]*$/;

function quoteIdentifier(identifier: string, pattern: RegExp): string {
  if (!pattern.test(identifier)) {
    throw new Error('Unsafe PostgreSQL identifier; use reviewed lowercase identifiers.');
  }
  return identifier.split('.').map((part) => '"' + part + '"').join('.');
}

/** Generic repository: identifiers are allowlisted and values are always bound. */
export class PostgresRepository<Row extends Record<string, unknown>> {
  private readonly tableSql: string;
  private readonly idColumnSql: string;
  private readonly columnSql: Map<string, string>;

  constructor(
    private readonly database: PostgresDatabase,
    table: string,
    idColumn: string,
    writableColumns: string[],
  ) {
    this.tableSql = quoteIdentifier(table, TABLE_IDENTIFIER);
    this.idColumnSql = quoteIdentifier(idColumn, COLUMN_IDENTIFIER);
    if (writableColumns.length === 0 || new Set(writableColumns).size !== writableColumns.length) {
      throw new Error('writableColumns must be non-empty and unique.');
    }
    this.columnSql = new Map(
      writableColumns.map((column) => [column, quoteIdentifier(column, COLUMN_IDENTIFIER)]),
    );
  }

  async findById(id: string | number): Promise<Row | null> {
    const result = await this.database.query<Row>(
      'SELECT * FROM ' + this.tableSql + ' WHERE ' + this.idColumnSql + ' = $1 LIMIT 1',
      [id],
    );
    return result.rows[0] ?? null;
  }

  async insert(values: Partial<Row>): Promise<Row> {
    const entries = this.orderedEntries(values);
    if (entries.length === 0) throw new Error('insert requires at least one writable field.');
    const columns = entries.map(([key]) => this.columnSql.get(key) as string);
    const placeholders = entries.map((_, index) => '$' + (index + 1));
    const sql = 'INSERT INTO ' + this.tableSql + ' (' + columns.join(', ') + ') VALUES (' +
      placeholders.join(', ') + ') RETURNING *';
    const result = await this.database.query<Row>(sql, entries.map(([, value]) => value));
    return result.rows[0];
  }

  async updateById(id: string | number, values: Partial<Row>): Promise<Row | null> {
    const entries = this.orderedEntries(values);
    if (entries.length === 0) throw new Error('updateById requires at least one writable field.');
    const assignments = entries.map(
      ([key], index) => this.columnSql.get(key) + ' = $' + (index + 1),
    );
    const sql = 'UPDATE ' + this.tableSql + ' SET ' + assignments.join(', ') +
      ' WHERE ' + this.idColumnSql + ' = $' + (entries.length + 1) + ' RETURNING *';
    const result = await this.database.query<Row>(
      sql, [...entries.map(([, value]) => value), id],
    );
    return result.rows[0] ?? null;
  }

  async deleteById(id: string | number): Promise<boolean> {
    const result = await this.database.query(
      'DELETE FROM ' + this.tableSql + ' WHERE ' + this.idColumnSql + ' = $1',
      [id],
    );
    return (result.rowCount ?? 0) > 0;
  }

  private orderedEntries(values: Partial<Row>): Array<[string, unknown]> {
    const input = values as Record<string, unknown>;
    const unknown = Object.keys(input).filter((key) => !this.columnSql.has(key));
    if (unknown.length > 0) throw new Error('Unknown or non-writable columns: ' + unknown.join(', '));
    return [...this.columnSql.keys()]
      .filter((key) => Object.prototype.hasOwnProperty.call(input, key))
      .map((key) => [key, input[key]]);
  }
}
""",
        "apps/api/src/database/database.module.ts": """import { Global, Module } from '@nestjs/common';
import { Pool } from 'pg';
import { PostgresDatabase } from './postgres-database';

@Global()
@Module({
  providers: [{
    provide: PostgresDatabase,
    useFactory: () => {
      const connectionString = process.env.DATABASE_URL;
      if (!connectionString) {
        throw new Error('DATABASE_URL is required; refusing to start without a database target.');
      }
      const max = Number(process.env.DB_POOL_MAX ?? 10);
      if (!Number.isInteger(max) || max < 1 || max > 100) {
        throw new Error('DB_POOL_MAX must be an integer between 1 and 100.');
      }
      return new PostgresDatabase(new Pool({
        connectionString, max, connectionTimeoutMillis: 5000,
        idleTimeoutMillis: 30000, application_name: 'apex2next-generated-api',
      }));
    },
  }],
  exports: [PostgresDatabase],
})
export class DatabaseModule {}
""",
        "apps/api/src/health.controller.ts": """import {
  Controller, Get, ServiceUnavailableException,
} from '@nestjs/common';
import { PostgresDatabase } from './database/postgres-database';

@Controller()
export class HealthController {
  constructor(private readonly database: PostgresDatabase) {}

  @Get('health')
  health() {
    return { status: 'ok', service: 'apex2next-generated-api' };
  }

  @Get('health/ready')
  async readiness() {
    try {
      await this.database.query('SELECT 1');
      return { status: 'ready', database: 'ok' };
    } catch {
      throw new ServiceUnavailableException('Database is not ready.');
    }
  }
}
""",
        "db/migrations/0001_baseline.sql": """-- Business tables are not inferred from UI metadata.
CREATE SCHEMA IF NOT EXISTS app;
CREATE TABLE IF NOT EXISTS app.schema_migrations (
  version text PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now()
);
""",
        "apps/api/scripts/migrate.mjs": r"""import { readdir, readFile } from 'node:fs/promises';
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
""",
        "apps/api/test/postgres.integration.test.js": """const test = require('node:test');
const assert = require('node:assert/strict');
const { Pool } = require('pg');
const { PostgresDatabase } = require('../dist/database/postgres-database.js');
const { PostgresRepository } = require('../dist/database/postgres-repository.js');

test('PostgreSQL repository and transaction contract', { skip: !process.env.DATABASE_URL }, async () => {
  const pool = new Pool({ connectionString: process.env.DATABASE_URL, max: 3 });
  const database = new PostgresDatabase(pool);
  const repository = new PostgresRepository(
    database, 'apex2next_test.runtime_probe', 'id', ['id', 'payload'],
  );
  try {
    await database.query('CREATE SCHEMA IF NOT EXISTS apex2next_test');
    await database.query('DROP TABLE IF EXISTS apex2next_test.runtime_probe');
    await database.query(
      'CREATE TABLE apex2next_test.runtime_probe (id text PRIMARY KEY, payload text NOT NULL)',
    );
    const maliciousText = "value'); DROP TABLE app.schema_migrations; --";
    const inserted = await repository.insert({ id: 'probe-1', payload: maliciousText });
    assert.equal(inserted.payload, maliciousText);
    assert.equal((await repository.findById('probe-1')).payload, maliciousText);
    const updated = await repository.updateById('probe-1', { payload: 'updated' });
    assert.equal(updated.payload, 'updated');
    assert.equal(await repository.deleteById('probe-1'), true);
    assert.equal(await repository.findById('probe-1'), null);
    await assert.rejects(
      () => repository.insert({ id: 'probe-2', payload: 'x', ignored: 'not-allowed' }),
      /Unknown or non-writable columns/,
    );
    assert.throws(
      () => new PostgresRepository(
        database, 'runtime_probe; DROP TABLE app.schema_migrations', 'id', ['id'],
      ),
      /Unsafe PostgreSQL identifier/,
    );
    await assert.rejects(
      () => database.transaction(async (client) => {
        await client.query(
          'INSERT INTO apex2next_test.runtime_probe(id, payload) VALUES ($1, $2)',
          ['rollback-1', 'must rollback'],
        );
        throw new Error('force rollback');
      }),
      /force rollback/,
    );
    assert.equal(await repository.findById('rollback-1'), null);
  } finally {
    await database.query('DROP TABLE IF EXISTS apex2next_test.runtime_probe');
    await database.query('DROP SCHEMA IF EXISTS apex2next_test');
    await database.close();
  }
});
""",
    }
