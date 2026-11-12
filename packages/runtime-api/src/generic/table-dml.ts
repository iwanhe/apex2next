import { errors, type FieldError } from '../errors';
import type { BusinessTx } from '../context';
import { type FormDef, type FormItem, lockForChange, normalizeValue, validateItems, writableItems } from '../forms/forms';

/**
 * Native form DML on the form's source table (APEX NATIVE_FORM_DML), for forms that have no PL/SQL processes
 * of their own (R4a). Column names come from the form definition of the UI spec and are checked against an
 * identifier pattern; values are always parameters. Triggers and defaults of the target table still apply.
 */
const IDENT = /^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)?$/;

function ident(name: string): string {
  if (!IDENT.test(name)) throw new Error(`bad identifier ${name}`);
  return name;
}

/** A primary key the user types (not hidden, not query-only) is part of the INSERT. */
export function enteredKey(form: FormDef): FormItem | null {
  const pk = form.pk;
  return pk.displayAs !== 'NATIVE_HIDDEN' && !pk.queryOnly ? pk : null;
}

export function validateForInsert(form: FormDef, input: Record<string, unknown>) {
  const key = enteredKey(form);
  const rest = { ...input };
  let keyValue: string | null = null;
  const problems: FieldError[] = [];
  if (key) {
    const raw = rest[key.column];
    delete rest[key.column];
    keyValue = typeof raw === 'string' || typeof raw === 'number' ? normalizeValue(raw, key) : null;
    if (keyValue === null) problems.push({ field: key.item, message: `${key.label} must have some value.` });
  }
  const checked = validateItems(form, rest);
  return { values: key && keyValue !== null ? { ...checked.values, [key.column]: keyValue } : checked.values,
    problems: [...problems, ...checked.problems] };
}

export async function insertRow(tx: BusinessTx, form: FormDef, values: Record<string, string | null>): Promise<string> {
  const allowed = new Set([...writableItems(form).map((i) => i.column), ...(enteredKey(form) ? [form.pk.column] : [])]);
  const cols = Object.keys(values).filter((c) => allowed.has(c));
  const sql = cols.length
    ? `INSERT INTO ${ident(form.source)} (${cols.map(ident).join(', ')}) VALUES (${cols.map((_, n) => `$${n + 1}`).join(', ')})`
    : `INSERT INTO ${ident(form.source)} DEFAULT VALUES`;
  const r = await tx.query<{ id: string }>(`${sql} RETURNING ${ident(form.pk.column)}::text AS id`, cols.map((c) => values[c]));
  return r.rows[0].id;
}

export async function updateRow(tx: BusinessTx, form: FormDef, id: string, checksum: unknown,
  values: Record<string, string | null>): Promise<Record<string, string | null>> {
  const row = await lockForChange(tx, form, id, checksum);
  const allowed = new Set(writableItems(form).map((i) => i.column));
  const cols = Object.keys(values).filter((c) => allowed.has(c));
  if (cols.length) {
    await tx.query(`UPDATE ${ident(form.source)} SET ${cols.map((c, n) => `${ident(c)} = $${n + 2}`).join(', ')} `
      + `WHERE ${ident(form.pk.column)} = $1`, [id, ...cols.map((c) => values[c])]);
  }
  return row;
}

export async function deleteRow(tx: BusinessTx, form: FormDef, id: string, checksum: unknown): Promise<void> {
  await lockForChange(tx, form, id, checksum);
  await tx.query(`DELETE FROM ${ident(form.source)} WHERE ${ident(form.pk.column)} = $1`, [id]);
}

export function assertValid(problems: FieldError[]) {
  if (problems.length) throw errors.validation(problems);
}
