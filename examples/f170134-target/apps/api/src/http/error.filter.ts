import { ArgumentsHost, Catch, ExceptionFilter, HttpException, Logger } from '@nestjs/common';
import type { Response } from 'express';
import { BusinessRuleError, errors } from '../business/errors';

/**
 * Maps PostgreSQL constraint errors to the Oracle errors APEX users saw for the same constraint
 * (the constraint names are identical after WP9.3; the schema prefix is not reproduced).
 */
export function mapDatabaseError(error: unknown): BusinessRuleError | null {
  const e = error as { code?: string; constraint?: string; column?: string; table?: string };
  if (!e || typeof e.code !== 'string') return null;
  const name = (e.constraint ?? '').toUpperCase();
  switch (e.code) {
    case '23505':
      return errors.database('DB_UNIQUE_VIOLATION', `ORA-00001: unique constraint (${name}) violated`, -1);
    case '23503': {
      // PostgreSQL: "update or delete on table ... violates foreign key" = the parent still has children.
      const child = String((error as Error).message ?? '').startsWith('update or delete on table');
      return child
        ? errors.database('DB_FOREIGN_KEY_VIOLATION', `ORA-02292: integrity constraint (${name}) violated - child record found`, -2292)
        : errors.database('DB_FOREIGN_KEY_VIOLATION', `ORA-02291: integrity constraint (${name}) violated - parent key not found`, -2291);
    }
    case '23514':
      return errors.database('DB_CHECK_VIOLATION', `ORA-02290: check constraint (${name}) violated`, -2290);
    case '23502':
      return errors.database('DB_NOT_NULL_VIOLATION',
        `ORA-01400: cannot insert NULL into (${(e.table ?? '').toUpperCase()}.${(e.column ?? '').toUpperCase()})`, -1400);
    case '22001':
      return errors.database('DB_VALUE_TOO_LARGE', 'ORA-12899: value too large for column', -12899);
    case '22P02':
    case '22007':
    case '22008':
    case '22003':
      return errors.invalidInput('Nilai tidak valid.');
    default:
      return null;
  }
}

@Catch()
export class ApiErrorFilter implements ExceptionFilter {
  private readonly logger = new Logger('ApiErrorFilter');

  catch(exception: unknown, host: ArgumentsHost) {
    const res = host.switchToHttp().getResponse<Response>();
    const business = exception instanceof BusinessRuleError ? exception : mapDatabaseError(exception);
    if (business) {
      res.status(business.httpStatus).json(business.toJSON());
      return;
    }
    if (exception instanceof HttpException) {
      const status = exception.getStatus();
      res.status(status).json({ code: status === 404 ? 'NOT_FOUND' : 'HTTP_ERROR', message: exception.message });
      return;
    }
    this.logger.error(exception instanceof Error ? exception.stack ?? exception.message : String(exception));
    res.status(500).json({ code: 'INTERNAL_ERROR', message: 'Terjadi kesalahan pada server.' });
  }
}
