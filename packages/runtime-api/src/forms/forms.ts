import { createHash } from 'node:crypto';
import { BusinessTx } from '../context';
import { FieldError, errors } from '../errors';

/**
 * APEX form regions (NATIVE_FORM). Item list, labels, required flags, data types and defaults come from the
 * export through the generated UI spec of the application (see bindUiSpec); behaviour that APEX evaluates as
 * PL/SQL (read-only conditions, button conditions) is implemented by the application's page services.
 */

/** The part of a generated UI spec (apex2next.ui-spec) the form runtime reads. */
export interface UiSpecLike {
  readonly application: { readonly dateFormat?: string | null };
  readonly pages: unknown;
}
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
  /** Number field attributes min_value / max_value (plug-in attributes in the export). */
  readonly minValue: string | null;
  readonly maxValue: string | null;
}

export interface FormDef {
  readonly page: number;
  readonly region: string;
  /** Source table or view of the form region (lower case, schema app). */
  readonly source: string;
  readonly pk: FormItem;
  readonly items: readonly FormItem[];
  /** Application date format (p_date_format), used in the date validation message. */
  readonly dateFormat: string;
}

type SpecItem = {
  prompt?: string; displayAs?: string; source?: string; sourceType?: string; sourceDataType?: string;
  isRequired?: boolean; isPrimaryKey?: boolean; isQueryOnly?: boolean; namedLov?: string; itemDefault?: string;
  attributes?: Record<string, string>;
};

/** Form definition of a NATIVE_FORM region from the UI spec. */
export function formDef(spec: UiSpecLike, page: number, region: string): FormDef {
  const p = (spec.pages as Record<string, unknown>)[String(page)] as { region: Record<string, { queryTable?: string }>; item?: Record<string, SpecItem> };
  const table = p.region[region]?.queryTable;
  if (!table) throw new Error(`form region ${page}:${region} not found`);
  const items: FormItem[] = Object.entries(p.item ?? {})
    .filter(([, i]) => i.source && i.sourceType !== 'FACET_COLUMN' && i.sourceType !== 'ALWAYS_NULL')
    .map(([item, i]) => ({
      item, column: i.source!.toLowerCase(), label: i.prompt ?? item, displayAs: i.displayAs ?? 'NATIVE_TEXT_FIELD',
      dataType: (i.sourceDataType ?? 'VARCHAR2') as FormItem['dataType'], required: i.isRequired === true,
      primaryKey: i.isPrimaryKey === true, queryOnly: i.isQueryOnly === true, lov: i.namedLov ?? null,
      defaultValue: i.itemDefault ?? null,
      minValue: i.attributes?.min_value ?? null, maxValue: i.attributes?.max_value ?? null,
    }));
  const pk = items.find((i) => i.primaryKey);
  if (!pk) throw new Error(`form ${page}:${region} has no primary key item`);
  return { page, region, source: `app.${table.toLowerCase()}`, pk, items, dateFormat: spec.application.dateFormat ?? 'DD-MON-YYYY' };
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

function inRange(value: string, item: FormItem): boolean {
  const n = Number(value);
  return (item.minValue === null || n >= Number(item.minValue)) && (item.maxValue === null || n <= Number(item.maxValue));
}

/** APEX number field messages (APEX.NUMBER_FIELD.*): the range message replaces "must be Numeric" when a bound exists. */
function numberMessage(item: FormItem): string {
  if (item.minValue !== null && item.maxValue !== null) return `${item.label} must be a number between ${item.minValue} and ${item.maxValue}.`;
  if (item.minValue !== null) return `${item.label} must be a number greater than or equal to ${item.minValue}.`;
  if (item.maxValue !== null) return `${item.label} must be a number less than or equal to ${item.maxValue}.`;
  return `${item.label} must be Numeric.`;
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
    } else if (item.dataType === 'NUMBER' && (!NUMBER.test(value) || !inRange(value, item))) {
      problems.push({ field: item.item, message: numberMessage(item) });
    } else if (item.dataType === 'DATE' && !validDate(value)) {
      problems.push({ field: item.item, message: `${item.label} does not match format ${form.dateFormat}.` });
    }
    values[item.column] = value;
  }
  return { values, problems };
}

/**
 * APEX runtime success messages of NATIVE_FORM_DML (language en; assumption A-02, confirmed on oracleapex.com
 * in WP9.6). "Row updated." appears only when the submit changed a value.
 */
export const DML_MESSAGES = { 'DML:CREATED': 'Row created.', 'DML:UPDATED': 'Row updated.', 'DML:DELETED': 'Row deleted.' } as const;

/** Page response for one submit: message keys (DML:* or page:PROCESS, in APEX order) and their joined text. */
export interface SubmitResult {
  readonly id: string;
  readonly message: string | null;
  readonly messageKeys: string[];
  readonly ignored?: string[];
}

/** Builds a SubmitResult; process keys resolve to the export's process success message. */
export function result(spec: UiSpecLike, id: string, keys: (string | null | false)[]): SubmitResult {
  const messageKeys = keys.filter((k): k is string => !!k);
  const texts = messageKeys.map((k) => {
    if (k in DML_MESSAGES) return DML_MESSAGES[k as keyof typeof DML_MESSAGES];
    const [page, proc] = k.split(':');
    const pages = spec.pages as Record<string, { process?: Record<string, { processSuccessMessage?: string }> }>;
    return pages[page]?.process?.[proc]?.processSuccessMessage ?? null;
  }).filter((t): t is string => !!t);
  return { id, message: texts.length ? texts.join(' ') : null, messageKeys };
}

/** True when a submitted value differs from the loaded row (numbers compared numerically). */
export function changed(form: FormDef, row: Record<string, string | null>, values: Record<string, string | null>): boolean {
  return form.items.some((i) => {
    if (!(i.column in values)) return false;
    const a = row[i.column] ?? null;
    const b = values[i.column] ?? null;
    if (a === null || b === null) return a !== b;
    return i.dataType === 'NUMBER' ? Number(a) !== Number(b) : a !== b;
  });
}

/** formDef and result bound to one application's UI spec. */
export function bindUiSpec(spec: UiSpecLike) {
  return {
    formDef: (page: number, region: string) => formDef(spec, page, region),
    result: (id: string, keys: (string | null | false)[]) => result(spec, id, keys),
  };
}
