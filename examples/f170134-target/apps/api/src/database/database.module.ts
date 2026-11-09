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
      }));
    },
  }, DatabaseHealthService],
  exports: [PostgresDatabase, DatabaseHealthService],
})
export class DatabaseModule {}
