import { UI_SPEC } from './ui-spec.generated';

/** Typed-loose access to the generated APEX UI specification. */
type Loose = Record<string, any>;

export function page(id: number): Loose {
  const p = (UI_SPEC.pages as unknown as Record<string, Loose>)[String(id)];
  if (!p) throw new Error(`APEX page ${id} not in UI spec`);
  return p;
}

export function item(pageId: number, name: string): Loose {
  const i = page(pageId).item?.[name];
  if (!i) throw new Error(`item ${name} not in page ${pageId}`);
  return i;
}

export function button(pageId: number, name: string): Loose {
  const b = page(pageId).button?.[name];
  if (!b) throw new Error(`button ${name} not in page ${pageId}`);
  return b;
}

export function staticLov(name: string): { display: string; value: string }[] {
  const lov = (UI_SPEC.lovs as unknown as Record<string, Loose>)[name];
  if (!lov || lov.location !== 'STATIC') throw new Error(`static LOV ${name} not in UI spec`);
  return lov.values.map((v: Loose) => ({ display: v.display, value: v.return }));
}

export function lovDisplay(name: string, value: string | null | undefined): string {
  if (value === null || value === undefined) return '';
  return staticLov(name).find((v) => v.value === value)?.display ?? value;
}

/** APEX runtime success messages of form DML (language en). */
export const DML_MESSAGES: Record<string, string> = { 'DML:CREATED': 'Row created.', 'DML:UPDATED': 'Row updated.', 'DML:DELETED': 'Row deleted.' };

/** Success message for flash keys "DML:*" / "page:PROCESS" (comma separated), joined like APEX does. */
export function processMessage(keys: string | undefined): string | null {
  if (!keys) return null;
  const texts = keys.split(',').map((key) => {
    if (DML_MESSAGES[key]) return DML_MESSAGES[key];
    const [p, name] = key.split(':');
    if (!/^\d+$/.test(p ?? '') || !name) return null;
    try {
      return page(Number(p)).process?.[name]?.processSuccessMessage ?? null;
    } catch {
      return null;
    }
  }).filter((t): t is string => !!t);
  return texts.length ? texts.join(' ') : null;
}

export const APP = UI_SPEC.application;
/** &APP_TITLE. / header logo text (p_logo_text). */
export const APP_TITLE = (UI_SPEC.application as { logoText?: string | null }).logoText ?? APP.name;
export const NAVIGATION = UI_SPEC.navigation as unknown as { label: string; page: number | null; sequence: number; icon: string | null; parent: string | null; scheme: string | null }[];
export const BREADCRUMBS = UI_SPEC.breadcrumbs as unknown as { label: string; page: number; parent: string | null }[];
export const DELETE_CONFIRM = 'Would you like to perform this delete action?';

/** Browser title of a page: its step title (APEX p_step_title). */
export function pageTitle(id: number): string {
  return String(page(id).title ?? '').replace('&APP_TITLE.', APP_TITLE ?? '');
}
