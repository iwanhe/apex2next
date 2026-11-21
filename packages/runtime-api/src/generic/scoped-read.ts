import type { BusinessTx } from '../context';
import { errors } from '../errors';

const IDENT = /^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)?$/;
const MAX_PAGE_SIZE = 100;

function ident(value: string): string {
  if (!IDENT.test(value)) throw errors.invalidInput('Invalid identifier in scoped-read server metadata.');
  return value;
}

export interface ScopedReadBoundary {
  readonly column: string;
  /** Resolved by server policy after authorization; never copied from client filters. */
  readonly value: string;
}

export interface ScopedReadDefinition {
  /** Static, server-owned table/view name. */
  readonly source: string;
  /** Static allowlist of projected columns. */
  readonly columns: readonly string[];
  /** Static order-by columns/directions. */
  readonly orderBy?: readonly { readonly column: string; readonly direction?: 'ASC' | 'DESC' }[];
}

export interface ScopedReadPolicy {
  readonly authorizationScheme: string;
  authorize(tx: BusinessTx, scheme: string): Promise<boolean>;
  resolveBoundary(tx: BusinessTx, definition: ScopedReadDefinition): Promise<ScopedReadBoundary | null>;
}

export interface ScopedReadResult<Row extends Record<string, unknown>> {
  readonly rows: readonly Row[];
  readonly total: number;
  readonly limit: number;
  readonly offset: number;
}

/**
 * Read-only query helper that makes a server-derived row boundary mandatory.
 * This is intentionally limited to static table/view metadata: it does not accept SQL,
 * client-selected columns, predicates, or sort expressions.
 */
export async function readScopedRows<Row extends Record<string, unknown> = Record<string, unknown>>(
  tx: BusinessTx,
  definition: ScopedReadDefinition,
  policy: ScopedReadPolicy,
  requestedPage: { readonly limit?: number; readonly offset?: number } = {},
): Promise<ScopedReadResult<Row>> {
  if (!policy || typeof policy.authorize !== 'function' || typeof policy.resolveBoundary !== 'function'
    || typeof policy.authorizationScheme !== 'string' || !policy.authorizationScheme.trim()) {
    throw errors.forbidden('Scoped-read policy is not configured.');
  }
  if (!(await policy.authorize(tx, policy.authorizationScheme))) {
    throw errors.forbidden('Scoped-read authorization denied.');
  }
  const boundary = await policy.resolveBoundary(tx, definition);
  if (!boundary || typeof boundary.column !== 'string' || typeof boundary.value !== 'string'
    || !boundary.value.trim()) {
    throw errors.forbidden('Scoped-read boundary could not be resolved.');
  }
  const source = ident(definition.source);
  if (!Array.isArray(definition.columns) || definition.columns.length === 0) {
    throw errors.invalidInput('Scoped-read requires an explicit projection.');
  }
  const columns = definition.columns.map(ident);
  if (new Set(columns).size !== columns.length) throw errors.invalidInput('Scoped-read projection contains duplicate columns.');
  const scopeColumn = ident(boundary.column);
  const orderBy = (definition.orderBy ?? []).map(({ column, direction = 'ASC' }) => {
    if (!columns.includes(column) && column !== scopeColumn) throw errors.invalidInput('Scoped-read ordering must use projected or boundary columns.');
    if (direction !== 'ASC' && direction !== 'DESC') throw errors.invalidInput('Invalid scoped-read order direction.');
    return `${ident(column)} ${direction}`;
  }).join(', ');
  const limit = Number.isInteger(requestedPage.limit) ? Math.max(1, Math.min(MAX_PAGE_SIZE, requestedPage.limit!)) : 25;
  const offset = Number.isInteger(requestedPage.offset) ? Math.max(0, requestedPage.offset!) : 0;
  const predicate = `${scopeColumn} = $1`;
  const totalResult = await tx.query<{ total: string | number }>(
    `SELECT COUNT(*)::text AS total FROM ${source} WHERE ${predicate}`, [boundary.value]);
  const select = `SELECT ${columns.join(', ')} FROM ${source} WHERE ${predicate}${orderBy ? ` ORDER BY ${orderBy}` : ''} LIMIT $2 OFFSET $3`;
  const rowsResult = await tx.query<Row>(select, [boundary.value, limit, offset]);
  return { rows: rowsResult.rows, total: Number(totalResult.rows[0]?.total ?? 0), limit, offset };
}
