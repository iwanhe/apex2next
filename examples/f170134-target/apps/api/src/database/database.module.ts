import { Global, Module } from '@nestjs/common';
import { Pool } from 'pg';
import { PostgresDatabase } from './postgres-database';
import { DatabaseHealthService } from './database-health.service';

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
        idleTimeoutMillis: 30000, application_name: 'apex2next-f170134-api',
        // OLTP pages: JIT compilation cost more than it saved on the report views (WP9.7 performance test,
        // 2x slower IR search at 60k lines). PG_JIT=on restores the server default.
        options: process.env.PG_JIT === 'on' ? undefined : '-c jit=off',
      }));
    },
  }, DatabaseHealthService],
  exports: [PostgresDatabase, DatabaseHealthService],
})
export class DatabaseModule {}
