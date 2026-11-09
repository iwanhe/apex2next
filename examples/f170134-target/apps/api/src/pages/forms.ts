import { createHash } from 'node:crypto';
import { BusinessTx } from '../business/context';
import { FieldError, errors } from '../business/errors';
import { UI_SPEC } from './ui-spec.generated';

/**
 * WP9.5 form regions (NATIVE_FORM). Item list, labels, required flags, data types and defaults come from the
 * export through the generated UI spec; behaviour that APEX evaluates as PL/SQL (read-only conditions,
 * button conditions) is implemented by the page services.
 */
export interface FormItem {
  readonly item: string;
  readonly column: string;
  readonly label: string;
  readonly displayAs: string;
  readonly dataType: 'NUMBER' | 'DATE' | 'VARCHAR2';
  readonly required: boolean;
  readonly primaryKey: boolean;
  readonly queryOnly: boolean;
  readonly lov: string | null;
  readonly defaultValue: string | null;
}

export interface FormDef {
  readonly page: number;
  readonly region: string;
  /** Source table or view of the form region (lower case, schema app). */
  readonly source: string;
  readonly pk: FormItem;
  readonly items: readonly FormItem[];
}

type SpecItem = {
  prompt?: string; displayAs?: string; source?: string; sourceType?: string; sourceDataType?: string;
  isRequired?: boolean; isPrimaryKey?: boolean; isQueryOnly?: boolean; namedLov?: string; itemDefault?: string;
};

export function formDef(page: number, region: string): FormDef {
  const p = (UI_SPEC.pages as unknown as Record<string, unknown>)[String(page)] as { region: Record<string, { queryTable?: string }>; item?: Record<string, SpecItem> };
  const table = p.region[region]?.queryTable;
  if (!table) throw new Error(`form region ${page}:${region} not found`);
  const items: FormItem[] = Object.entries(p.item ?? {})
    .filter(([, i]) => i.source && i.sourceType !== 'FACET_COLUMN' && i.sourceType !== 'ALWAYS_NULL')
    .map(([item, i]) => ({
      item, column: i.source!.toLowerCase(), label: i.prompt ?? item, displayAs: i.displayAs ?? 'NATIVE_TEXT_FIELD',
      dataType: (i.sourceDataType ?? 'VARCHAR2') as FormItem['dataType'], required: i.isRequired === true,
      primaryKey: i.isPrimaryKey === true, queryOnly: i.isQueryOnly === true, lov: i.namedLov ?? null,
      defaultValue: i.itemDefault ?? null,
    }));
  const pk = items.find((i) => i.primaryKey);
  if (!pk) throw new Error(`form ${page}:${region} has no primary key item`);
  return { page, region, source: `app.${table.toLowerCase()}`, pk, items };
}

/** Writable items: not the key, not query-only, not display-only. */
export function writableItems(form: FormDef): FormItem[] {
  return form.items.filter((i) => !i.primaryKey && !i.queryOnly && i.displayAs !== 'NATIVE_DISPLAY_ONLY');
}

function columnExpr(i: FormItem): string {
  if (!/^[a-z_][a-z0-9_]*$/.test(i.column)) throw new Error(`bad column ${i.column}`);
  return i.dataType === 'DATE' ? `to_char(${i.column}, 'YYYY-MM-DD') AS ${i.column}` : `${i.column}::text AS ${i.column}`;
}

/** Lost-update checksum over the values the form loaded (APEX p_lost_update_check_type VALUES). */
export function checksum(form: FormDef, row: Record<string, string | null>): string {
  const values = form.items.map((i) => row[i.column] ?? null);
  return createHash('sha256').update(JSON.stringify([form.page, form.region, values])).digest('base64url');
}

export async function fetchForm(tx: BusinessTx, form: FormDef, id: string | number, lock = false) {
  const r = await tx.query<Record<string, string | null>>(
    `SELECT ${form.items.map(columnExpr).join(', ')} FROM ${form.source} WHERE ${form.pk.column} = $1${lock ? ' FOR UPDATE' : ''}`,
    [id]);
  return r.rows[0] ?? null;
}

/** Loads the row for UPDATE/DELETE, locks it and verifies the checksum the client received. */
export async function lockForChange(tx: BusinessTx, form: FormDef, id: string | number, clientChecksum: unknown) {
  const row = await fetchForm(tx, form, id, true);
  if (!row) throw errors.notFound(`${form.region} ${id}`, 'UI-FRM-01');
  if (typeof clientChecksum !== 'string' || clientChecksum !== checksum(form, row)) throw errors.lostUpdate();
  return row;
}

const NUMBER = /^[-+]?(\d+(\.\d*)?|\.\d+)$/;
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

function validDate(v: string): boolean {
  const m = ISO_DATE.exec(v);
  if (!m) return false;
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
  return d.getUTCFullYear() === Number(m[1]) && d.getUTCMonth() === Number(m[2]) - 1 && d.getUTCDate() === Number(m[3]);
}

/**
 * Normalizes submitted values ('' -> null, trimmed numbers) and runs the APEX built-in item validations:
 * value required and number/date format, with the APEX runtime messages (application language en).
 * Items in `skip` (read-only by condition) are neither validated nor returned.
 */
export function validateItems(form: FormDef, input: Record<string, unknown>, skip: ReadonlySet<string> = new Set()) {
  const known = new Set(writableItems(form).map((i) => i.column));
  const unknown = Object.keys(input).filter((k) => !known.has(k));
  if (unknown.length) throw errors.invalidInput(`Kolom tidak dikenal atau tidak dapat diubah: ${unknown.join(', ')}`);
  const values: Record<string, string | null> = {};
  const problems: FieldError[] = [];
  for (const item of writableItems(form)) {
    if (skip.has(item.column)) continue;
    const raw = input[item.column];
    if (raw !== undefined && raw !== null && typeof raw !== 'string' && typeof raw !== 'number') {
      problems.push({ field: item.item, message: `${item.label} tidak valid.` });
      continue;
    }
    const text = raw === undefined || raw === null ? null : String(raw);
    // Text items have trim_spaces=BOTH in the export; Oracle stores '' as NULL.
    const value = text === null || text.trim() === '' ? null : text.trim();
    if (value === null) {
      if (item.required) problems.push({ field: item.item, message: `${item.label} must have some value.` });
    } else if (item.dataType === 'NUMBER' && !NUMBER.test(value)) {
      problems.push({ field: item.item, message: `${item.label} must be Numeric.` });
    } else if (item.dataType === 'DATE' && !validDate(value)) {
      problems.push({ field: item.item, message: `${item.label} does not match format ${UI_SPEC.application.dateFormat}.` });
    }
    values[item.column] = value;
  }
  return { values, problems };
}

/** Dialog/page response for one form submit: the row as reloaded and the APEX success message, if any. */
export interface SubmitResult {
  readonly id: string;
  readonly message: string | null;
  readonly ignored?: string[];
}
