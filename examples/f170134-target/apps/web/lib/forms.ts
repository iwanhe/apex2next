import 'server-only';
import type { ButtonView, FieldView } from '../components/ApexForm';
import { apiGet, type LovEntry } from './api';
import { formatDate } from './format';
import { DELETE_CONFIRM, page } from './spec';
import { UI_SPEC } from './ui-spec.generated';

const KIND: Record<string, FieldView['kind'] | null> = {
  NATIVE_TEXT_FIELD: 'text', NATIVE_TEXTAREA: 'textarea', NATIVE_NUMBER_FIELD: 'number',
  NATIVE_DATE_PICKER_APEX: 'date', NATIVE_SELECT_LIST: 'select', NATIVE_DISPLAY_ONLY: 'display', NATIVE_HIDDEN: null,
};

async function lovOptions(name: string): Promise<{ display: string; value: string }[]> {
  const lov = (UI_SPEC.lovs as unknown as Record<string, { location: string; values: { display: string; return: string }[] }>)[name];
  if (lov?.location === 'STATIC') return lov.values.map((v) => ({ display: v.display, value: v.return }));
  return apiGet<LovEntry[]>(`/lovs/${encodeURIComponent(name)}`);
}

/**
 * Form items of an APEX page in item sequence, with labels, required flags, LOVs (null text, static or
 * dynamic values), inline help and the read-only state computed by the API.
 */
export async function formFields(pageId: number, values: Record<string, string | null>, readOnly: Record<string, boolean> = {},
                                 extra: Record<string, { column: string }> = {}): Promise<FieldView[]> {
  const items = Object.entries(page(pageId).item ?? {}) as [string, Record<string, any>][];
  const out: FieldView[] = [];
  for (const [name, i] of items.sort((a, b) => (a[1].itemSequence ?? 0) - (b[1].itemSequence ?? 0))) {
    const kind = KIND[i.displayAs];
    if (!kind) continue;
    const column = extra[name]?.column ?? (i.source ? String(i.source).toLowerCase() : null);
    if (!column) continue;
    const options = kind === 'select' && i.namedLov ? await lovOptions(i.namedLov) : undefined;
    const ro = readOnly[column] === true;
    const raw = values[column] ?? null;
    let displayValue: string | undefined;
    if (ro || kind === 'display') {
      displayValue = options ? options.find((o) => o.value === raw)?.display ?? raw ?? ''
        : i.sourceDataType === 'DATE' ? formatDate(raw) : raw ?? '';
    }
    out.push({
      item: name, column, label: i.prompt ?? name, kind, required: i.isRequired === true, readOnly: ro, options,
      nullText: kind === 'select' && i.lovDisplayNull === 'YES' ? i.lovNullText ?? '' : undefined,
      help: i.inlineHelpText ?? null, displayValue,
    });
  }
  return out;
}

/** Buttons whose server-evaluated condition is true, with label, hot flag, confirm text and position. */
export function formButtons(pageId: number, available: Record<string, boolean>): ButtonView[] {
  const buttons = Object.entries(page(pageId).button ?? {}) as [string, Record<string, any>][];
  return buttons
    .filter(([name, b]) => b.buttonAction === 'SUBMIT' && available[name] === true)
    .sort((a, b) => (a[1].buttonSequence ?? 0) - (b[1].buttonSequence ?? 0))
    .map(([name, b]) => ({
      name, label: b.buttonImageAlt ?? name, hot: b.buttonIsHot === 'Y', danger: b.databaseAction === 'DELETE',
      confirm: b.confirmMessage === '&APP_TEXT$DELETE_MSG!RAW.' ? DELETE_CONFIRM : b.confirmMessage ?? null,
      position: b.buttonPosition === 'NEXT' ? 'right' : 'left',
    }));
}

/** Label of the dialog's CANCEL button (DEFINED_BY_DA, NATIVE_DIALOG_CANCEL). */
export function cancelLabel(pageId: number): string {
  return page(pageId).button?.CANCEL?.buttonImageAlt ?? 'Cancel';
}

/** Columns posted by the form: editable, non-display items (read-only ones are not submitted). */
export function postedColumns(fields: FieldView[]): string[] {
  return fields.filter((f) => !f.readOnly && f.kind !== 'display').map((f) => f.column);
}
