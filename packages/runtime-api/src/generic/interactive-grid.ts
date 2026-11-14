import type { BusinessTx } from '../context';
import { errors } from '../errors';
import { type FormDef, checksum, fetchForm, validateItems, writableItems } from '../forms/forms';
import { assertValid, deleteRow, insertRow, updateRow, validateForInsert } from './table-dml';

/**
 * A bounded set of row changes submitted by an Interactive Grid.
 *
 * This is deliberately a runtime primitive, not an HTTP endpoint: the owning application must
 * authorize the operation and call it inside BusinessDatabase.run so every change shares one
 * PostgreSQL transaction. A failure rejects the call; the surrounding transaction must roll back.
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

function validId(id: unknown): id is string {
  return typeof id === 'string' && id.length > 0 && id.length <= MAX_ROW_ID_LENGTH;
}

/**
 * Applies at most 100 changes in the caller's transaction.
 *
 * - Only the FormDef's writable columns are accepted.
 * - Insert/update values pass the same item validation as native forms.
 * - Update/delete require the form runtime's lost-update checksum.
 * - Duplicate row IDs in one batch are rejected to avoid order-dependent writes.
 * - SQL identifiers remain sourced from FormDef; submitted values are bound parameters.
 *
 * Authorization and transaction ownership intentionally remain with the application service.
 */
export async function applyInteractiveGridChanges(
  tx: BusinessTx,
  form: FormDef,
  changes: readonly InteractiveGridChange[],
): Promise<InteractiveGridChangeResult[]> {
  if (!Array.isArray(changes) || changes.length === 0 || changes.length > MAX_GRID_CHANGES) {
    throw errors.invalidInput(`Grid changes must contain between 1 and ${MAX_GRID_CHANGES} operations.`);
  }

  const seen = new Set<string>();
  for (const change of changes) {
    if (!change || !['insert', 'update', 'delete'].includes(change.operation)) {
      throw errors.invalidInput('Unsupported Interactive Grid operation.');
    }
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
  }

  const results: InteractiveGridChangeResult[] = [];
  // A savepoint makes this batch atomic even if an application catches the error inside its outer transaction.
  await tx.query('SAVEPOINT apex2next_ig_batch');
  try {
    for (const change of changes) {
      if (change.operation === 'insert') {
        const checked = validateForInsert(form, change.values);
        assertValid(checked.problems);
        // Preserve database defaults for omitted optional columns; do not turn absence into NULL.
        const supplied = new Set(Object.keys(change.values));
        const values = Object.fromEntries(Object.entries(checked.values).filter(([column]) => supplied.has(column))) as Record<string, string | null>;
        const id = await insertRow(tx, form, values);
        results.push({ operation: 'insert', id });
      } else if (change.operation === 'update') {
        // IG payloads commonly contain changed columns only. Merge with the locked current row so
        // omitted columns are preserved, while checksum verification still prevents lost updates.
        const current = await fetchForm(tx, form, change.id, true);
        if (!current) throw errors.notFound(`${form.region} ${change.id}`, 'UI-FRM-01');
        if (typeof change.checksum !== 'string' || change.checksum !== checksum(form, current)) throw errors.lostUpdate();
        const currentWritable = Object.fromEntries(writableItems(form).map((item) => [item.column, current[item.column] ?? null]));
        const checked = validateItems(form, { ...currentWritable, ...change.values });
        assertValid(checked.problems);
        await updateRow(tx, form, change.id, change.checksum, checked.values);
        results.push({ operation: 'update', id: change.id });
      } else {
        await deleteRow(tx, form, change.id, change.checksum);
        results.push({ operation: 'delete', id: change.id });
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
