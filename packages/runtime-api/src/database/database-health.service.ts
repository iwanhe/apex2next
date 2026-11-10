import {
  Injectable, ServiceUnavailableException,
} from '@nestjs/common';
import { PostgresDatabase } from './postgres-database';

@Injectable()
export class DatabaseHealthService {
  constructor(private readonly database: PostgresDatabase) {}

  async readiness() {
    try {
      await this.database.query('SELECT 1');
      return { status: 'ready', database: 'ok' };
    } catch {
      throw new ServiceUnavailableException('Database is not ready.');
    }
  }
}
