import { Injectable } from '@nestjs/common';
import {
  assertValid, BusinessDatabase, BusinessTx, changed, checksum, deleteRow, errors, fetchForm, FormDef, insertRow,
  lovSql as runtimeLovSql, Principal, regionBinds, ReportQuery, runReport, SubmitResult, updateRow, validateForInsert,
  validateItems,
} from '@apex2next/runtime-api';
import { SecurityService } from '../business/security.service';
import { formDef, result } from './forms';
import { FORM_SOURCES, FormName, LOV_SOURCES, REGION_SOURCES, RegionName, reportDef } from './report-definitions';
import { UI_SPEC } from './ui-spec.generated';

/**
 * Generic page layer of a converted application (apex2next template). One transaction per call, like an
 * APEX page request; every call checks the application authorization scheme and the page's scheme.
 * Business logic that APEX ran in PL/SQL processes belongs in dedicated services; the generation report
 * lists them (GEN006, GEN009).
 */
type SpecPage = { scheme: string | null };
const pageScheme = (page: number) => ((UI_SPEC.pages as unknown as Record<string, SpecPage>)[String(page)]?.scheme ?? null);
const appScheme = (UI_SPEC.application as { securityScheme?: string | null }).securityScheme ?? null;

type FormSource = { page: number; region: string; dml?: readonly string[] };
const FORMS = Object.fromEntries(
  Object.entries(FORM_SOURCES as Record<string, FormSource>).map(([name, f]) => [name, { def: formDef(f.page, f.region), dml: f.dml ?? [] }]),
) as Record<string, { def: FormDef; dml: readonly string[] }>;

type ItemSpec = { source?: string; itemDefault?: string };
type ProcessSpec = { processType?: string; processSuccessMessage?: string };

/** The page's NATIVE_FORM_DML success message when it has one; otherwise the APEX default row message. */
function dmlKey(form: FormDef, fallback: string): string {
  const procs = (UI_SPEC.pages as unknown as Record<string, { process?: Record<string, ProcessSpec> }>)[String(form.page)]?.process ?? {};
  const dml = Object.entries(procs).find(([, p]) => p.processType === 'NATIVE_FORM_DML' && p.processSuccessMessage);
  return dml ? `${form.page}:${dml[0]}` : fallback;
}

@Injectable()
export class PagesService {
  constructor(private readonly db: BusinessDatabase, private readonly security: SecurityService) {}

  private async authorizePage(tx: BusinessTx, page: number) {
    await this.security.authorize(tx, appScheme);
    await this.security.authorize(tx, pageScheme(page));
  }

  private run<T>(actor: Principal, page: number, work: (tx: BusinessTx) => Promise<T>) {
    return this.db.run(actor, async (tx) => {
      await this.authorizePage(tx, page);
      return work(tx);
    });
  }

  /** Session info for the shell: user, evaluated authorization schemes, application access. */
  me(actor: Principal) {
    return this.db.run(actor, async (tx) => {
      const schemes: Record<string, boolean> = {};
      for (const name of this.security.names()) schemes[name] = await this.security.isAuthorized(tx, name);
      const denied = appScheme && !schemes[appScheme] ? this.security.message(tx, appScheme) : null;
      return { username: actor.username, schemes, appAccessDenied: denied };
    });
  }

  report(actor: Principal, name: RegionName, query: ReportQuery, raw: Record<string, unknown>) {
    const src = REGION_SOURCES[name];
    if (!src) throw errors.invalidInput(`Region ${name} is not known.`);
    let binds: (string | null)[];
    try {
      binds = regionBinds(src, raw, actor.username);
    } catch (e) {
      throw errors.invalidInput((e as Error).message);
    }
    return this.run(actor, src.page, (tx) => runReport(tx, reportDef(src), query, binds));
  }

  lov(actor: Principal, name: string) {
    const src = (LOV_SOURCES as Record<string, (typeof LOV_SOURCES)[keyof typeof LOV_SOURCES]>)[name];
    if (!src) throw errors.invalidInput(`LOV ${name} is not known.`);
    return this.db.run(actor, async (tx) => {
      await this.security.authorize(tx, appScheme);
      const r = await tx.query<{ d: string; r: string }>(runtimeLovSql(src));
      return r.rows.map((x) => ({ display: x.d, value: x.r }));
    });
  }

  private form(name: string) {
    const f = FORMS[name as FormName];
    if (!f) throw errors.invalidInput(`Form ${name} is not known.`);
    return f;
  }

  /** Native DML buttons of the form page by name: available by their database action and the row state. */
  private buttons(f: { dml: readonly string[]; def: FormDef }, id: string | null) {
    const page = (UI_SPEC.pages as unknown as Record<string, { button?: Record<string, { databaseAction?: string }> }>)[String(f.def.page)];
    const out: Record<string, boolean> = {};
    for (const [name, b] of Object.entries(page?.button ?? {})) {
      if (b.databaseAction === 'INSERT') out[name] = id === null && f.dml.includes('i');
      else if (b.databaseAction === 'UPDATE') out[name] = id !== null && f.dml.includes('u');
      else if (b.databaseAction === 'DELETE') out[name] = id !== null && f.dml.includes('d');
    }
    return out;
  }

  /** Static item defaults of the export; values passed by the calling page (create mode) win. */
  private defaults(form: FormDef, passed: Record<string, unknown>) {
    const items = (UI_SPEC.pages as unknown as Record<string, { item?: Record<string, ItemSpec> }>)[String(form.page)]?.item ?? {};
    const values: Record<string, string | null> = {};
    for (const i of form.items) {
      const d = items[i.item]?.itemDefault ?? null;
      values[i.column] = d !== null && !/^\s*select\s/i.test(d) ? d : null;
    }
    for (const [k, v] of Object.entries(passed)) if (k in values && typeof v === 'string') values[k] = v;
    return values;
  }

  /** NATIVE_FORM_INIT: the row with its lost-update checksum, or the defaults of a new row. */
  formGet(actor: Principal, name: string, id: string | null, passed: Record<string, unknown> = {}) {
    const f = this.form(name);
    return this.run(actor, f.def.page, async (tx) => {
      if (id === null) return { values: this.defaults(f.def, passed), checksum: null, buttons: this.buttons(f, null) };
      const row = await fetchForm(tx, f.def, id);
      if (!row) throw errors.notFound(`${f.def.region} ${id}`, 'UI-FRM-01');
      return { values: row, checksum: checksum(f.def, row), buttons: this.buttons(f, id) };
    });
  }

  private needs(f: { dml: readonly string[]; def: FormDef }, op: 'i' | 'u' | 'd') {
    if (!f.dml.includes(op)) {
      throw errors.invalidInput(`${f.def.region}: this operation is not converted (see the generation report, GEN009).`);
    }
  }

  formCreate(actor: Principal, name: string, input: Record<string, unknown>): Promise<SubmitResult> {
    const f = this.form(name);
    this.needs(f, 'i');
    return this.run(actor, f.def.page, async (tx) => {
      const { values, problems } = validateForInsert(f.def, input);
      assertValid(problems);
      const id = await insertRow(tx, f.def, values);
      return result(id, [dmlKey(f.def, 'DML:CREATED')]);
    });
  }

  formUpdate(actor: Principal, name: string, id: string, check: unknown, input: Record<string, unknown>): Promise<SubmitResult> {
    const f = this.form(name);
    this.needs(f, 'u');
    return this.run(actor, f.def.page, async (tx) => {
      const { values, problems } = validateItems(f.def, input);
      assertValid(problems);
      const row = await updateRow(tx, f.def, id, check, values);
      return result(id, [changed(f.def, row, values) && dmlKey(f.def, 'DML:UPDATED')]);
    });
  }

  formDelete(actor: Principal, name: string, id: string, check: unknown): Promise<SubmitResult> {
    const f = this.form(name);
    this.needs(f, 'd');
    return this.run(actor, f.def.page, async (tx) => {
      await deleteRow(tx, f.def, id, check);
      return result(id, [dmlKey(f.def, 'DML:DELETED')]);
    });
  }
}
