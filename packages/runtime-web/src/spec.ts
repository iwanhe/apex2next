/**
 * Typed-loose access to a generated APEX UI specification (apex2next.ui-spec; scripts/generate-ui-spec.mjs of
 * the target application). createAppSpec binds the accessors to one application's spec.
 */
type Loose = Record<string, any>;

/** APEX runtime success messages of form DML (language en). */
export const DML_MESSAGES: Record<string, string> = { 'DML:CREATED': 'Row created.', 'DML:UPDATED': 'Row updated.', 'DML:DELETED': 'Row deleted.' };
/** &APP_TEXT$DELETE_MSG!RAW. of the Universal Theme (language en). */
export const DELETE_CONFIRM = 'Would you like to perform this delete action?';

export interface NavigationEntry { label: string; page: number | null; sequence: number; icon: string | null; parent: string | null; scheme: string | null }
export interface BreadcrumbEntry { label: string; page: number; parent: string | null }

/** The part of a generated UI spec the web runtime reads. */
export interface UiSpecLike {
  readonly application: unknown;
  readonly pages: unknown;
  readonly lovs: unknown;
  readonly navigation: unknown;
  readonly breadcrumbs: unknown;
}

export function createAppSpec(spec: UiSpecLike) {
  const pages = spec.pages as Record<string, Loose>;
  const lovs = spec.lovs as Record<string, Loose>;
  const app = spec.application as Loose;

  function page(id: number): Loose {
    const p = pages[String(id)];
    if (!p) throw new Error(`APEX page ${id} not in UI spec`);
    return p;
  }
  function item(pageId: number, name: string): Loose {
    const i = page(pageId).item?.[name];
    if (!i) throw new Error(`item ${name} not in page ${pageId}`);
    return i;
  }
  function button(pageId: number, name: string): Loose {
    const b = page(pageId).button?.[name];
    if (!b) throw new Error(`button ${name} not in page ${pageId}`);
    return b;
  }
  function lov(name: string): Loose | undefined {
    return lovs[name];
  }
  function staticLov(name: string): { display: string; value: string }[] {
    const l = lovs[name];
    if (!l || l.location !== 'STATIC') throw new Error(`static LOV ${name} not in UI spec`);
    return l.values.map((v: Loose) => ({ display: v.display, value: v.return }));
  }
  function lovDisplay(name: string, value: string | null | undefined): string {
    if (value === null || value === undefined) return '';
    return staticLov(name).find((v) => v.value === value)?.display ?? value;
  }
  /** Success message for flash keys "DML:*" / "page:PROCESS" (comma separated), joined like APEX does. */
  function processMessage(keys: string | undefined): string | null {
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
  /** &APP_TITLE. / header logo text (p_logo_text). */
  const APP_TITLE: string = app.logoText ?? app.name;
  /** Browser title of a page: its step title (APEX p_step_title). */
  function pageTitle(id: number): string {
    return String(page(id).title ?? '').replace('&APP_TITLE.', APP_TITLE ?? '');
  }
  return {
    APP: app, APP_TITLE,
    NAVIGATION: spec.navigation as NavigationEntry[],
    BREADCRUMBS: spec.breadcrumbs as BreadcrumbEntry[],
    page, item, button, lov, staticLov, lovDisplay, processMessage, pageTitle,
  };
}

export type AppSpec = ReturnType<typeof createAppSpec>;
