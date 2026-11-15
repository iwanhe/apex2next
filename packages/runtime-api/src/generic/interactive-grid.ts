import type { BusinessTx } from '../context';
import { errors } from '../errors';
import { type FormDef, checksum, validateItems, writableItems } from '../forms/forms';
import { assertValid, validateForInsert } from './table-dml';

/** A server-derived row boundary. Never construct this object from request-body or query parameters. */
export interface InteractiveGridRowScope {
  /** Physical ownership/tenant column in the source table, not a browser-visible form item. */
  readonly column: string;
  /** Value derived from the verified Principal / server-side tenant resolver. */
  readonly value: string;
}

/** Explicit operation grants plus a mandatory row boundary. Missing policy means deny. */
export interface InteractiveGridAccess {
  readonly operations: readonly InteractiveGridChange['operation'][];
  readonly rowScope: InteractiveGridRowScope;
}

/**
 * A bounded set of row changes submitted by an Interactive Grid.
 * The caller must create access from authenticated server context and run inside BusinessDatabase.run.
 */
export type InteractiveGridChange =
  | { readonly operation: 'insert'; readonly values: Record<string, unknown> }
  | { readonly operation: 'update'; readonly id: string; readonly checksum: string; readonly values: Record<string, unknown> }
  | { readonly operation: 'delete'; readonly id: string; readonly checksum: string };

export interface InteractiveGridChangeResult {
  readonly operation: InteractiveGridChange['operation'];
  readonly id: string;
}

const MAX_GRID_CHANGES = 100;
const MAX_ROW_ID_LENGTH = 256;
const IDENT = /^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)?$/;

function ident(name: string): string {
  if (!IDENT.test(name)) throw errors.invalidInput('Invalid Interactive Grid identifier in server metadata.');
  return name;
}

function validId(id: unknown): id is string {
  return typeof id === 'string' && id.length > 0 && id.length <= MAX_ROW_ID_LENGTH;
}

/** Validate the server-owned policy before any database access. */
export function assertInteractiveGridAccess(access: InteractiveGridAccess | undefined,
  operation: InteractiveGridChange['operation']): InteractiveGridRowScope {
  if (!access || !Array.isArray(access.operations) || !access.operations.includes(operation)
    || !access.rowScope || typeof access.rowScope.column !== 'string'
    || typeof access.rowScope.value !== 'string' || !access.rowScope.value.trim()) {
    throw errors.forbidden('Interactive Grid operation is not authorized or has no server-derived row scope.');
  }
  ident(access.rowScope.column);
  return access.rowScope;
}

function projection(form: FormDef): string {
  return form.items.map((item) => {
    if (!/^[a-z_][a-z0-9_]*$/.test(item.column)) throw errors.invalidInput('Invalid form column in server metadata.');
    return item.dataType === 'DATE'
      ? `to_char(${item.column}, 'YYYY-MM-DD') AS ${item.column}`
      : `${item.column}::text AS ${item.column}`;
  }).join(', ');
}

async function fetchScoped(tx: BusinessTx, form: FormDef, id: string, scope: InteractiveGridRowScope) {
  const result = await tx.query<Record<string, string | null>>(
    `SELECT ${projection(form)} FROM ${ident(form.source)} WHERE ${ident(form.pk.column)} = $1 AND ${ident(scope.column)} = $2 FOR UPDATE`,
    [id, scope.value]);
  return result.rows[0] ?? null;
}

/**
 * Applies at most 100 changes atomically inside the caller's transaction.
 * SELECT-for-update, UPDATE and DELETE all carry the trusted row-scope predicate.
 * INSERT overwrites no ownership field: a client attempt to submit it is rejected and the server value is inserted.
 * This is not an HTTP endpoint; callers must authorize using verified identity before invoking it.
 */
export async function applyInteractiveGridChanges(
  tx: BusinessTx,
  form: FormDef,
  changes: readonly InteractiveGridChange[],
  access: InteractiveGridAccess,
): Promise<InteractiveGridChangeResult[]> {
  if (!Array.isArray(changes) || changes.length === 0 || changes.length > MAX_GRID_CHANGES) {
    throw errors.invalidInput(`Grid changes must contain between 1 and ${MAX_GRID_CHANGES} operations.`);
  }
  const scope = access?.rowScope;
  if (!scope || typeof scope.column !== 'string' || !/^[a-z_][a-z0-9_]*$/.test(scope.column)
    || typeof scope.value !== 'string' || !scope.value.trim()
    || form.items.some((item) => item.column === scope.column)) {
    throw errors.forbidden('Interactive Grid requires a valid server-derived row scope outside the editable form items.');
  }

  const seen = new Set<string>();
  for (const change of changes) {
    if (!change || !['insert', 'update', 'delete'].includes(change.operation)) {
      throw errors.invalidInput('Unsupported Interactive Grid operation.');
    }
    assertInteractiveGridAccess(access, change.operation);
    if (change.operation !== 'insert') {
      if (!validId(change.id) || typeof change.checksum !== 'string' || !change.checksum) {
        throw errors.invalidInput('Interactive Grid update/delete requires a valid row id and checksum.');
      }
      if (seen.has(change.id)) throw errors.invalidInput(`Duplicate row id in Interactive Grid batch: ${change.id}.`);
      seen.add(change.id);
    }
    if (change.operation !== 'delete' && (!change.values || typeof change.values !== 'object' || Array.isArray(change.values))) {
      throw errors.invalidInput('Interactive Grid row values must be an object.');
    }
    if (change.operation === 'insert' && Object.prototype.hasOwnProperty.call(change.values, scope.column)) {
      throw errors.forbidden('Ownership and tenant columns are server-managed.');
    }
  }

  const results: InteractiveGridChangeResult[] = [];
  await tx.query('SAVEPOINT apex2next_ig_batch');
  try {
    for (const change of changes) {
      if (change.operation === 'insert') {
        const checked = validateForInsert(form, change.values);
        assertValid(checked.problems);
        const supplied = new Set(Object.keys(change.values));
        const values = Object.fromEntries(Object.entries(checked.values).filter(([column]) => supplied.has(column))) as Record<string, string | null>;
        const cols = [...Object.keys(values), scope.column];
        const sql = `INSERT INTO ${ident(form.source)} (${cols.map(ident).join(', ')}) VALUES (${cols.map((_, n) => `$${n + 1}`).join(', ')}) RETURNING ${ident(form.pk.column)}::text AS id`;
        const inserted = await tx.query<{ id: string }>(sql, [...Object.values(values), scope.value]);
        results.push({ operation: 'insert', id: inserted.rows[0].id });
      } else {
        const current = await fetchScoped(tx, form, change.id, scope);
        if (!current) throw errors.notFound(`${form.region} ${change.id}`, 'UI-IG-SEC-01');
        if (change.checksum !== checksum(form, current)) throw errors.lostUpdate();
        if (change.operation === 'update') {
          const currentWritable = Object.fromEntries(writableItems(form).map((item) => [item.column, current[item.column] ?? null]));
          const checked = validateItems(form, { ...currentWritable, ...change.values });
          assertValid(checked.problems);
          const cols = Object.keys(checked.values);
          if (cols.length) {
            const sql = `UPDATE ${ident(form.source)} SET ${cols.map((column, n) => `${ident(column)} = $${n + 3}`).join(', ')} WHERE ${ident(form.pk.column)} = $1 AND ${ident(scope.column)} = $2`;
            const updated = await tx.query(sql, [change.id, scope.value, ...cols.map((column) => checked.values[column])]);
            if (updated.rowCount !== 1) throw errors.notFound(`${form.region} ${change.id}`, 'UI-IG-SEC-01');
          }
          results.push({ operation: 'update', id: change.id });
        } else {
          const deleted = await tx.query(
            `DELETE FROM ${ident(form.source)} WHERE ${ident(form.pk.column)} = $1 AND ${ident(scope.column)} = $2`,
            [change.id, scope.value]);
          if (deleted.rowCount !== 1) throw errors.notFound(`${form.region} ${change.id}`, 'UI-IG-SEC-01');
          results.push({ operation: 'delete', id: change.id });
        }
      }
    }
    await tx.query('RELEASE SAVEPOINT apex2next_ig_batch');
    return results;
  } catch (error) {
    await tx.query('ROLLBACK TO SAVEPOINT apex2next_ig_batch');
    await tx.query('RELEASE SAVEPOINT apex2next_ig_batch');
    throw error;
  }
}
