import { Injectable } from '@nestjs/common';
import { ApprovalService } from '../business/approval.service';
import { BusinessDatabase, BusinessTx, errors, FieldError, Principal, ReportQuery, regionBinds, runReport } from '@apex2next/runtime-api';
import { MasterDataEntity, MasterDataService } from '../business/master-data.service';
import { RequestService } from '../business/request.service';
import { AUTHORIZATION_SCHEMES, AuthorizationScheme, SecurityService } from '../business/security.service';
import {
  FormDef, SubmitResult, changed, checksum, fetchForm, formDef, lockForChange, result, validateItems, writableItems,
} from './forms';
import {
  DynamicLov, FORM_SOURCES, FormName, LOV_SOURCES, REGION_SOURCES, RegionName, RegionSource, lovSql, reportDef,
} from './report-definitions';
import { UI_SPEC } from './ui-spec.generated';

/**
 * WP9.5 page layer: one method per APEX page action. Each call is one transaction (APEX commits once
 * per page submit), authorizes the application scheme (APP_USERS) and the page scheme from the export,
 * then runs the WP9.4 business services. Button conditions are enforced here as well (DEV-06).
 */
type PageId = number;
const pageScheme = (page: PageId) =>
  ((UI_SPEC.pages as unknown as Record<string, { scheme: string | null }>)[String(page)]?.scheme ?? null) as AuthorizationScheme | null;

/** Form definitions by form name; pages and regions come from the generated form sources (R3). */
const FORMS = Object.fromEntries(
  Object.entries(FORM_SOURCES).map(([name, f]) => [name, formDef(f.page, f.region)]),
) as Record<FormName, FormDef>;

/** Master-data forms whose DML goes through MasterDataService (normalization + audit triggers). */
const MASTER_FORMS: Record<'department' | 'item' | 'userRole', { form: FormDef; entity: MasterDataEntity }> = {
  department: { form: FORMS.department, entity: 'departments' },
  item: { form: FORMS.item, entity: 'items' },
  userRole: { form: FORMS.userRole, entity: 'userRoles' },
};
export type MasterFormName = keyof typeof MASTER_FORMS;

const OPEN = new Set(['DRAFT', 'REJECTED']);
const nvlDraft = (status: string | null | undefined) => status ?? 'DRAFT';

/** P301 read-only conditions (create_page_item p_read_only_when, PL/SQL expressions). */
function requestReadOnly(status: string | null) {
  const s = nvlDraft(status);
  const locked = !OPEN.has(s); // not (nvl(:P301_STATUS,'DRAFT') in ('DRAFT','REJECTED'))
  return {
    department_id: locked, need_date: locked, purpose: locked,
    status: !['APPROVED', 'FULFILLED', 'CLOSED'].includes(s), // nvl(...) not in ('APPROVED','FULFILLED','CLOSED')
  };
}

/** P301 button conditions. */
function requestButtons(id: string | null, status: string | null) {
  const s = nvlDraft(status);
  return {
    CREATE: id === null,
    DELETE: id !== null && s === 'DRAFT',
    SAVE: id !== null && !['SUBMITTED', 'CANCELLED', 'CLOSED'].includes(s),
    SUBMIT: id !== null && OPEN.has(s),
  };
}

/** P301 validation NEED_DATE_AFTER_REQUEST_DATE (SAVE, CREATE, SUBMIT); ISO dates compare as text. */
function needDateValidation(values: Record<string, string | null>): FieldError[] {
  const v = UI_SPEC.pages[301].validation.NEED_DATE_AFTER_REQUEST_DATE;
  const need = values.need_date ?? null;
  const req = values.request_date ?? null;
  // :P301_NEED_DATE is null or :P301_NEED_DATE >= :P301_REQUEST_DATE (NULL request date -> NULL -> fails)
  if (need === null || (req !== null && need >= req)) return [];
  return [{ field: 'P301_NEED_DATE', message: v.errorMessage }];
}

function assertNoProblems(problems: FieldError[]) {
  if (problems.length) throw errors.validation(problems);
}

function idOf(value: unknown): string {
  const text = String(value ?? '').trim();
  if (!/^\d{1,18}$/.test(text)) throw errors.invalidInput('ID tidak valid.');
  return text;
}

@Injectable()
export class PagesService {
  constructor(
    private readonly db: BusinessDatabase,
    private readonly security: SecurityService,
    private readonly requests: RequestService,
    private readonly approvals: ApprovalService,
    private readonly masterData: MasterDataService,
  ) {}

  /** Application authorization (APP_USERS) followed by the page authorization of the export. */
  private async authorizePage(tx: BusinessTx, page: PageId) {
    const app = UI_SPEC.application.securityScheme as AuthorizationScheme;
    await this.security.authorize(tx, app);
    const scheme = pageScheme(page);
    if (scheme && scheme !== app) await this.security.authorize(tx, scheme);
  }

  /** Button authorization scheme (p_security_scheme of the button; J-05): a button without one is always allowed. */
  private async buttonAuthorized(tx: BusinessTx, page: PageId, button: string): Promise<boolean> {
    const pageSpec = (UI_SPEC.pages as unknown as Record<string, { button?: Record<string, { securityScheme?: string }> }>)[String(page)];
    const scheme = pageSpec.button?.[button]?.securityScheme as AuthorizationScheme | undefined;
    return !scheme || this.security.isAuthorized(tx, scheme);
  }

  private run<T>(actor: Principal, page: PageId, work: (tx: BusinessTx) => Promise<T>) {
    return this.db.run(actor, async (tx) => {
      await this.authorizePage(tx, page);
      return work(tx);
    });
  }

  /** Session info for the shell: user, evaluated authorization schemes (navigation, page access). */
  me(actor: Principal) {
    return this.db.run(actor, async (tx) => {
      const schemes: Record<string, boolean> = {};
      for (const name of Object.keys(AUTHORIZATION_SCHEMES) as AuthorizationScheme[]) {
        schemes[name] = await this.security.isAuthorized(tx, name);
      }
      const denied = schemes.APP_USERS ? null
        : AUTHORIZATION_SCHEMES.APP_USERS.message.replace('{APP_USER}', actor.username);
      return { username: actor.username, schemes, appAccessDenied: denied };
    });
  }

  // ---------------------------------------------------------------- reads
  /** Page 100 Home: metric cards (Ringkasan) and the two charts. */
  home(actor: Principal) {
    return this.run(actor, 100, async (tx) => {
      const kpis = await tx.query('SELECT seq::text, icon, label, metric_value::text FROM app.apx_demo_dash_kpi_v ORDER BY seq');
      const byStatus = await tx.query('SELECT label, value::text FROM app.apx_demo_dash_c1_s1_v');
      const byDepartment = await tx.query('SELECT label, value::text FROM app.apx_demo_dash_c2_s1_v');
      return { kpis: kpis.rows, byStatus: byStatus.rows, byDepartment: byDepartment.rows };
    });
  }

  /** Any generated region; its binds are hidden page items from the request (item.NAME) or APP_USER (R4a). */
  report(actor: Principal, name: RegionName, query: ReportQuery, raw: Record<string, unknown> = {}) {
    const src: RegionSource = REGION_SOURCES[name];
    if (!src) throw errors.invalidInput(`Region ${name} tidak dikenal.`);
    let binds: (string | null)[];
    try {
      binds = regionBinds(src, raw, actor.username);
    } catch (e) {
      throw errors.invalidInput((e as Error).message);
    }
    return this.run(actor, src.page, (tx) => runReport(tx, reportDef(src), query, binds));
  }

  lov(actor: Principal, name: string) {
    const src = (LOV_SOURCES as Record<string, (typeof LOV_SOURCES)[DynamicLov]>)[name];
    if (!src) throw errors.invalidInput(`LOV ${name} tidak dikenal.`);
    return this.db.run(actor, async (tx) => {
      await this.security.authorize(tx, UI_SPEC.application.securityScheme as AuthorizationScheme);
      const r = await tx.query<{ d: string; r: string }>(lovSql(src));
      return r.rows.map((x) => ({ display: x.d, value: x.r }));
    });
  }

  /** Page 302 master-detail: list, selected header, its lines and the button conditions. */
  requestDetail(actor: Principal, requestId: string | null, page = 1) {
    return this.run(actor, 302, async (tx) => {
      const list = await runReport(tx, reportDef(REGION_SOURCES.requestMasterList), { page });
      if (requestId === null) return { list, selected: null, lines: null, buttons: { EDIT_HEADER: false, CREATE_REQUEST_LINES: false } };
      const id = idOf(requestId);
      const header = await runReport(tx, reportDef(REGION_SOURCES.requestHeader), {}, [id]);
      const lines = await runReport(tx, reportDef(REGION_SOURCES.requestDetailLines), { page: 1, all: true }, [id]);
      const open = await tx.query(
        "SELECT 1 FROM app.apx_demo_requests WHERE request_id = $1 AND status IN ('DRAFT', 'REJECTED')", [id]);
      return {
        list, selected: header.rows[0] ?? null, headerColumns: header.columns, lines,
        buttons: {
          EDIT_HEADER: await this.buttonAuthorized(tx, 302, 'EDIT_HEADER'),
          CREATE_REQUEST_LINES: (open.rowCount ?? 0) > 0 && await this.buttonAuthorized(tx, 302, 'CREATE_REQUEST_LINES'),
        },
      };
    });
  }

  // ---------------------------------------------------------------- page 191 approval dialog
  approvalForm(actor: Principal, approvalId: string) {
    return this.run(actor, 191, async (tx) => {
      const row = await fetchForm(tx, FORMS.approval, idOf(approvalId));
      if (!row) throw errors.notFound(`Approval ${approvalId}`, 'UI-FRM-01');
      const canAct = row.can_act_yn === 'Y'; // apx_demo_approval_pkg.can_act_yn(:P191_APPROVAL_ID) = 'Y'
      return { values: row, buttons: { APPROVE: canAct, REJECT: canAct } };
    });
  }

  /** CALL_APPROVE / CALL_REJECT with :P191_NOTE (trim_spaces BOTH; '' is NULL). */
  act(actor: Principal, approvalId: string, action: 'APPROVE' | 'REJECT', note: unknown): Promise<SubmitResult> {
    const text = typeof note === 'string' && note.trim() !== '' ? note.trim() : null;
    if (text !== null && text.length > 1000) throw errors.validation([{ field: 'P191_NOTE', message: 'ORA-12899: value too large for column' }]);
    return this.run(actor, 191, async (tx) => {
      const id = Number(idOf(approvalId));
      if (action === 'APPROVE') {
        await this.approvals.approve(tx, id, text);
        return result(String(id), ['191:CALL_APPROVE']);
      }
      await this.approvals.reject(tx, id, text);
      return result(String(id), ['191:CALL_REJECT']);
    });
  }

  // ---------------------------------------------------------------- generic form reads
  private formPage(form: FormDef): PageId {
    return form.page as PageId;
  }

  /** NATIVE_FORM_INIT: existing row (with checksum) or the item defaults of the export. */
  async formGet(actor: Principal, name: MasterFormName | 'docType' | 'requestLine', id: string | null,
                defaults: Record<string, string | null> = {}) {
    const form = name === 'docType' ? FORMS.docType : name === 'requestLine' ? FORMS.requestLine : MASTER_FORMS[name].form;
    return this.run(actor, this.formPage(form), async (tx) => {
      if (id === null) {
        if (name === 'docType') throw errors.invalidInput('Document Type hanya dapat diubah.');
        return { values: this.defaults(form, actor, tx, defaults), checksum: null, buttons: { CREATE: true, SAVE: false, DELETE: false } };
      }
      const key = name === 'docType' ? id : idOf(id);
      const row = await fetchForm(tx, form, key);
      if (!row) throw errors.notFound(`${form.region} ${id}`, 'UI-FRM-01');
      return { values: row, checksum: checksum(form, row), buttons: { CREATE: false, SAVE: true, DELETE: name !== 'docType' } };
    });
  }

  private defaults(form: FormDef, actor: Principal, tx: BusinessTx, extra: Record<string, string | null>) {
    const values: Record<string, string | null> = {};
    for (const i of form.items) {
      let v: string | null = i.defaultValue;
      if (v === 'select trunc(sysdate) from dual') v = tx.now.date.slice(0, 10);
      else if (v === 'select :APP_USER from dual') v = actor.username;
      else if (v !== null && /^select /i.test(v)) throw new Error(`unmapped SQL default for ${i.item}`);
      values[i.column] = v;
    }
    for (const [k, v] of Object.entries(extra)) if (k in values) values[k] = v;
    return values;
  }

  // ---------------------------------------------------------------- master data forms 201 / 211 / 501
  masterCreate(actor: Principal, name: MasterFormName, input: Record<string, unknown>): Promise<SubmitResult> {
    const { form, entity } = MASTER_FORMS[name];
    return this.run(actor, this.formPage(form), async (tx) => {
      const { values, problems } = validateItems(form, input);
      assertNoProblems(problems);
      const row = await this.masterData.create(tx, entity, values);
      return result(String(row[form.pk.column]), ['DML:CREATED']);
    });
  }

  masterUpdate(actor: Principal, name: MasterFormName, id: string, check: unknown, input: Record<string, unknown>): Promise<SubmitResult> {
    const { form, entity } = MASTER_FORMS[name];
    return this.run(actor, this.formPage(form), async (tx) => {
      const { values, problems } = validateItems(form, input);
      assertNoProblems(problems);
      const row = await lockForChange(tx, form, idOf(id), check);
      await this.masterData.update(tx, entity, Number(idOf(id)), values);
      return result(idOf(id), [changed(form, row, values) && 'DML:UPDATED']);
    });
  }

  masterDelete(actor: Principal, name: MasterFormName, id: string, check: unknown): Promise<SubmitResult> {
    const { form, entity } = MASTER_FORMS[name];
    return this.run(actor, this.formPage(form), async (tx) => {
      await lockForChange(tx, form, idOf(id), check); // DELETE: p_button_execute_validations N
      await this.masterData.delete(tx, entity, Number(idOf(id)));
      return result(idOf(id), ['DML:DELETED']);
    });
  }

  // ---------------------------------------------------------------- page 511 document type (update only)
  docTypeUpdate(actor: Principal, docType: string, check: unknown, input: Record<string, unknown>): Promise<SubmitResult> {
    const form = FORMS.docType;
    return this.run(actor, 511, async (tx) => {
      const { values, problems } = validateItems(form, input);
      assertNoProblems(problems);
      const row = await lockForChange(tx, form, docType, check);
      const cols = writableItems(form).map((i) => i.column);
      await tx.query(
        `UPDATE app.apx_demo_doc_types SET ${cols.map((c, n) => `${c} = $${n + 2}`).join(', ')} WHERE doc_type = $1`,
        [docType, ...cols.map((c) => values[c])]);
      return result(docType, [changed(form, row, values) && 'DML:UPDATED']);
    });
  }

  // ---------------------------------------------------------------- page 311 request line
  lineCreate(actor: Principal, input: Record<string, unknown>): Promise<SubmitResult> {
    return this.run(actor, 311, async (tx) => {
      const { values, problems } = validateItems(FORMS.requestLine, input);
      assertNoProblems(problems);
      const row = await this.requests.addLine(tx, {
        request_id: Number(values.request_id), item_id: Number(values.item_id), qty: values.qty as string,
        unit_price: values.unit_price,
      });
      return result(String(row.line_id), ['DML:CREATED']);
    });
  }

  lineUpdate(actor: Principal, id: string, check: unknown, input: Record<string, unknown>): Promise<SubmitResult> {
    return this.run(actor, 311, async (tx) => {
      const { values, problems } = validateItems(FORMS.requestLine, input);
      assertNoProblems(problems);
      const before = await lockForChange(tx, FORMS.requestLine, idOf(id), check);
      await this.requests.updateLine(tx, Number(idOf(id)), {
        request_id: Number(values.request_id), item_id: Number(values.item_id), qty: values.qty as string,
        unit_price: values.unit_price,
      });
      return result(idOf(id), [changed(FORMS.requestLine, before, values) && 'DML:UPDATED']);
    });
  }

  lineDelete(actor: Principal, id: string, check: unknown): Promise<SubmitResult> {
    return this.run(actor, 311, async (tx) => {
      await lockForChange(tx, FORMS.requestLine, idOf(id), check);
      await this.requests.deleteLine(tx, Number(idOf(id)));
      return result(idOf(id), ['DML:DELETED']);
    });
  }

  // ---------------------------------------------------------------- page 301 request
  requestGet(actor: Principal, id: string | null) {
    return this.run(actor, 301, async (tx) => {
      if (id === null) {
        const values = this.defaults(FORMS.request, actor, tx, {});
        return { values, checksum: null, buttons: requestButtons(null, values.status), readOnly: requestReadOnly(values.status) };
      }
      const row = await fetchForm(tx, FORMS.request, idOf(id));
      if (!row) throw errors.notFound(`Permintaan Barang ${id}`, 'UI-FRM-01');
      return { values: row, checksum: checksum(FORMS.request, row), buttons: requestButtons(row.request_id, row.status),
        readOnly: requestReadOnly(row.status) };
    });
  }

  /** CREATE: required items + NEED_DATE validation, then the insert path (status DRAFT, number from NEXT_NO). */
  requestCreate(actor: Principal, input: Record<string, unknown>): Promise<SubmitResult> {
    return this.run(actor, 301, async (tx) => {
      const readOnly = requestReadOnly(null);
      const skip = new Set(Object.entries(readOnly).filter(([, ro]) => ro).map(([c]) => c));
      const { values, problems } = validateItems(FORMS.request, input, skip);
      assertNoProblems([...problems, ...needDateValidation(values)]);
      const row = await this.requests.create(tx, {
        department_id: Number(values.department_id), request_date: values.request_date, need_date: values.need_date,
        purpose: values.purpose as string, notes: values.notes,
      });
      return result(String(row.request_id), ['DML:CREATED']);
    });
  }

  /**
   * SAVE and SUBMIT: SAVE_REQUESTS (form DML, UPDATE) for both buttons, then CALL_SUBMIT_REQUESTS for SUBMIT,
   * in one transaction. Read-only items keep their database value (they are not submitted in APEX).
   */
  requestSave(actor: Principal, id: string, check: unknown, input: Record<string, unknown>, submit: boolean): Promise<SubmitResult> {
    return this.run(actor, 301, async (tx) => {
      const row = await lockForChange(tx, FORMS.request, idOf(id), check);
      const buttons = requestButtons(row.request_id, row.status);
      if (submit && !buttons.SUBMIT) throw errors.actionNotAvailable('SUBMIT', `status ${row.status}`);
      if (!submit && !buttons.SAVE) throw errors.actionNotAvailable('SAVE', `status ${row.status}`);
      const readOnly = requestReadOnly(row.status);
      const skip = new Set(Object.entries(readOnly).filter(([, ro]) => ro).map(([c]) => c));
      const { values, problems } = validateItems(FORMS.request, input, skip);
      const merged = { ...row, ...values };
      assertNoProblems([...problems, ...needDateValidation(merged)]);
      await this.requests.update(tx, Number(row.request_id), values);
      const updated = changed(FORMS.request, row, values) && 'DML:UPDATED';
      if (!submit) return result(row.request_id as string, [updated]);
      await this.approvals.submit(tx, 'REQ', Number(row.request_id));
      return result(row.request_id as string, [updated, '301:CALL_SUBMIT_REQUESTS']);
    });
  }

  requestDelete(actor: Principal, id: string, check: unknown): Promise<SubmitResult> {
    return this.run(actor, 301, async (tx) => {
      const row = await lockForChange(tx, FORMS.request, idOf(id), check);
      if (!requestButtons(row.request_id, row.status).DELETE) throw errors.actionNotAvailable('DELETE', `status ${row.status}`);
      await this.requests.delete(tx, Number(row.request_id));
      return result(row.request_id as string, ['DML:DELETED']);
    });
  }
}
