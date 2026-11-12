import { ArgumentsHost, Catch, ExceptionFilter, HttpException, Logger } from '@nestjs/common';
import type { Response } from 'express';
import { BusinessRuleError, errors } from '../errors';

/** Options of the Oracle-compatible error mapping. */
export interface ErrorMappingOptions {
  /**
   * Schema name shown in Oracle-style constraint messages: APEX shows the parsing schema of the source application
   * (e.g. WKSP_KCSI for app 170134, observed in WP9.6).
   */
  readonly oracleSchema: string;
}

/** Column list of a PostgreSQL key detail, e.g. "Key (dept_code)=(OPS) already exists." -> DEPT_CODE. */
function keyColumns(detail: string | undefined): string {
  const m = /^Key \(([^)]*)\)=/.exec(detail ?? '');
  return m ? m[1].split(',').map((c) => c.trim().toUpperCase()).join(', ') : '';
}

/**
 * Maps PostgreSQL constraint errors to the Oracle errors APEX users see for the same constraint (constraint and
 * table names are identical after WP9.3). ORA-00001 uses the Oracle 23ai text observed on oracleapex.com.
 */
export function mapDatabaseError(error: unknown, options: ErrorMappingOptions): BusinessRuleError | null {
  const OWNER = options.oracleSchema.toUpperCase();
  const e = error as { code?: string; constraint?: string; column?: string; table?: string; detail?: string };
  if (!e || typeof e.code !== 'string') return null;
  const name = `${OWNER}.${(e.constraint ?? '').toUpperCase()}`;
  switch (e.code) {
    case '23505':
      return errors.database('DB_UNIQUE_VIOLATION',
        `ORA-00001: unique constraint (${name}) violated on table ${OWNER}.${(e.table ?? '').toUpperCase()} columns (${keyColumns(e.detail)})`, -1);
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
        `ORA-01400: cannot insert NULL into ("${OWNER}"."${(e.table ?? '').toUpperCase()}"."${(e.column ?? '').toUpperCase()}")`, -1400);
    case 'P0001': {
      // RAISE_APPLICATION_ERROR converted by schema-plan --convert-triggers: DETAIL carries the Oracle error number.
      const m = /^ORA-(20\d{3})$/.exec(e.detail ?? '');
      if (!m) return null;
      const message = String((error as Error).message ?? '');
      return errors.database('DB_APPLICATION_ERROR', `ORA-${m[1]}: ${message}`, -Number(m[1]));
    }
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

  constructor(private readonly options: ErrorMappingOptions) {}

  catch(exception: unknown, host: ArgumentsHost) {
    const res = host.switchToHttp().getResponse<Response>();
    const business = exception instanceof BusinessRuleError ? exception : mapDatabaseError(exception, this.options);
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
