import { ColumnType, FacetDef, ReportColumn, ReportDef } from './report';
import { UI_SPEC } from './ui-spec.generated';

/**
 * WP9.5 region sources. Every entry restates the region SQL of the APEX export as an allowlisted
 * (view, select list, filter) triple; test/ui-spec.test.js proves each one equals the region source in
 * ui/apex-page-inventory.json, so a changed export cannot silently change what runs here.
 */

export interface RegionSource {
  readonly page: number;
  /** Region name in the inventory (REGION or REPORT_REGION). */
  readonly region: string;
  readonly kind: 'IR' | 'CLASSIC' | 'CARDS';
  /** View or table of the source SQL (unqualified, as in the export). */
  readonly view: string;
  readonly select: readonly string[];
  /** Source WHERE with :ITEM binds replaced by $n, e.g. request_id = to_number(:P302_REQUEST_ID). */
  readonly where?: { readonly sql: string; readonly source: string };
  /** Column types for classic/cards regions (IR columns carry their type in the export). */
  readonly types?: Readonly<Record<string, ColumnType>>;
  readonly hidden?: readonly string[];
  readonly facets?: readonly FacetDef[];
  readonly searchable: boolean;
  readonly sortable: boolean;
  readonly rowsPerPage: number;
}

/**
 * APEX does not store a rows-per-page value for these IR default reports; the runtime default of an
 * Interactive Report is used (assumption A-01, to be confirmed against the running source in WP9.7).
 */
export const IR_DEFAULT_ROWS = 50;
/** Cards region with p_plug_query_num_rows_type=SCROLL: rows are fetched in batches while scrolling. */
export const CARDS_BATCH_ROWS = 50;

export const REGION_SOURCES = {
  approvalInbox: {
    page: 190, region: 'Approval Inbox', kind: 'IR', view: 'apx_demo_approvals_v',
    select: ['approval_id', 'doc_name', 'doc_no', 'approval_level', 'approver_role', 'amount', 'requested_by',
      'requested_on', 'status', 'can_act_yn', 'acted_by', 'acted_on', 'note'],
    searchable: true, sortable: true, rowsPerPage: IR_DEFAULT_ROWS,
  },
  departments: {
    page: 200, region: 'Departments', kind: 'IR', view: 'apx_demo_departments_v',
    select: ['department_id', 'dept_code', 'dept_name', 'active_yn', 'updated_by', 'updated_on'],
    searchable: true, sortable: true, rowsPerPage: IR_DEFAULT_ROWS,
  },
  items: {
    page: 210, region: 'Hasil Items', kind: 'CARDS', view: 'apx_demo_items_v',
    select: ['item_id', 'item_code', 'item_name', 'category', 'uom', 'std_price', 'active_yn', 'updated_by', 'updated_on'],
    types: { item_id: 'NUMBER', std_price: 'NUMBER', updated_on: 'DATE' }, hidden: ['item_id'],
    facets: [{ item: 'P210_CATEGORY', column: 'CATEGORY' }, { item: 'P210_ACTIVE_YN', column: 'ACTIVE_YN' }],
    searchable: true, sortable: false, rowsPerPage: CARDS_BATCH_ROWS,
  },
  requests: {
    page: 300, region: 'Hasil Permintaan Barang', kind: 'CLASSIC', view: 'apx_demo_requests_v',
    select: ['request_id', 'request_no', 'department_id_dsp', 'request_date', 'need_date', 'purpose', 'status',
      'updated_by', 'updated_on'],
    types: { request_id: 'NUMBER', request_date: 'DATE', need_date: 'DATE', updated_on: 'DATE' },
    facets: [{ item: 'P300_STATUS', column: 'STATUS' }, { item: 'P300_DEPARTMENT_ID_DSP', column: 'DEPARTMENT_ID_DSP' }],
    searchable: true, sortable: false, rowsPerPage: 15,
  },
  requestMasterList: {
    page: 302, region: 'Daftar Permintaan Barang', kind: 'CLASSIC', view: 'apx_demo_requests_v',
    select: ['request_id', 'request_no', 'department_id_dsp', 'status'], types: { request_id: 'NUMBER' },
    searchable: false, sortable: false, rowsPerPage: 15,
  },
  requestHeader: {
    page: 302, region: 'Permintaan Barang', kind: 'CLASSIC', view: 'apx_demo_requests_v',
    select: ['request_id', 'request_no', 'department_id_dsp', 'request_date', 'need_date', 'purpose', 'status'],
    where: { sql: 'request_id = $1', source: 'request_id = to_number(:P302_REQUEST_ID)' },
    types: { request_id: 'NUMBER', request_date: 'DATE', need_date: 'DATE' },
    searchable: false, sortable: false, rowsPerPage: 15,
  },
  requestDetailLines: {
    page: 302, region: 'Baris Permintaan', kind: 'CLASSIC', view: 'apx_demo_request_lines_v',
    select: ['line_id', 'item_id_dsp', 'qty', 'unit_price', 'line_amount'],
    where: { sql: 'request_id = $1', source: 'request_id = to_number(:P302_REQUEST_ID)' },
    types: { line_id: 'NUMBER', qty: 'NUMBER', unit_price: 'NUMBER', line_amount: 'NUMBER' },
    searchable: false, sortable: false, rowsPerPage: 15,
  },
  requestLines: {
    page: 310, region: 'Baris Permintaan', kind: 'IR', view: 'apx_demo_request_lines_v',
    select: ['line_id', 'request_id_dsp', 'item_id_dsp', 'qty', 'unit_price', 'line_amount', 'updated_by', 'updated_on'],
    searchable: true, sortable: true, rowsPerPage: IR_DEFAULT_ROWS,
  },
  requestSummary: {
    page: 400, region: 'Rekap Permintaan', kind: 'IR', view: 'apx_demo_request_summary_v',
    select: ['request_no', 'dept_name', 'request_date', 'purpose', 'line_count', 'total_amount', 'status'],
    searchable: true, sortable: true, rowsPerPage: IR_DEFAULT_ROWS,
  },
  userRoles: {
    page: 500, region: 'Users & Roles', kind: 'IR', view: 'apx_demo_user_roles_v',
    select: ['user_role_id', 'username', 'role_code', 'role_name', 'created_by', 'created_on'],
    searchable: true, sortable: true, rowsPerPage: IR_DEFAULT_ROWS,
  },
  docTypes: {
    page: 510, region: 'Document Types & Approval', kind: 'IR', view: 'apx_demo_doc_types',
    select: ['doc_type', 'doc_name', 'prefix', 'approver1_role', 'approver2_role', 'level2_limit'],
    searchable: true, sortable: true, rowsPerPage: IR_DEFAULT_ROWS,
  },
} as const satisfies Record<string, RegionSource>;

export type RegionName = keyof typeof REGION_SOURCES;

type AnyMap = Record<string, Record<string, unknown>>;

/** Columns with type and visibility, taken from the export (IR columns, IR default report, report columns). */
export function regionColumns(src: RegionSource): ReportColumn[] {
  const page = (UI_SPEC.pages as unknown as Record<string, AnyMap>)[String(src.page)];
  const irCols = (page.irColumn ?? {}) as Record<string, {
    columnType?: string; displayTextAs?: string; columnLabel?: string; formatMask?: string; columnAlignment?: string }>;
  const repCols = (page.reportColumn ?? {}) as Record<string, {
    hiddenColumn?: string; columnHeading?: string; columnFormat?: string; columnAlignment?: string;
    columnDisplaySequence?: number }>;
  const irReport = Object.entries((page.irReport ?? {}) as Record<string, { reportColumns?: string }>)
    .find(([name]) => name.startsWith(`${src.region}.`))?.[1];
  const displayed = irReport?.reportColumns?.split(':');
  return src.select.map((name) => {
    const upper = name.toUpperCase();
    if (src.kind === 'IR') {
      const c = irCols[`${src.region}.${upper}`];
      if (!c) throw new Error(`IR column ${src.region}.${upper} missing in UI spec`);
      return { name, type: (c.columnType ?? 'STRING') as ColumnType,
        hidden: c.displayTextAs === 'HIDDEN_ESCAPE_SC' || (displayed ? !displayed.includes(upper) : false),
        label: c.columnLabel ?? null, format: c.formatMask ?? null, align: c.columnAlignment ?? null,
        order: displayed && displayed.includes(upper) ? displayed.indexOf(upper) : 1000 };
    }
    const rc = repCols[`${src.region}.${upper}`];
    const hidden = src.kind === 'CLASSIC' ? rc?.hiddenColumn === 'Y' : (src.hidden ?? [] as readonly string[]).includes(name);
    return { name, type: (src.types as Record<string, ColumnType> | undefined)?.[name] ?? 'STRING', hidden,
      label: rc?.columnHeading ?? null, format: rc?.columnFormat ?? null, align: rc?.columnAlignment ?? null,
      order: rc?.columnDisplaySequence ?? src.select.indexOf(name) };
  });
}

/** Default order: IR default report sort, or the region's static ORDER BY. */
export function regionDefaultSort(src: RegionSource): { column: string; dir: 'ASC' | 'DESC' } {
  const page = (UI_SPEC.pages as unknown as Record<string, AnyMap>)[String(src.page)];
  if (src.kind === 'IR') {
    const rpt = Object.entries((page.irReport ?? {}) as Record<string, { sortColumn1?: string; sortDirection1?: string }>)
      .find(([name]) => name.startsWith(`${src.region}.`))?.[1];
    return { column: (rpt?.sortColumn1 ?? src.select[0]).toLowerCase(), dir: rpt?.sortDirection1 === 'DESC' ? 'DESC' : 'ASC' };
  }
  const region = ((page.reportRegion ?? {}) as Record<string, { queryOrderBy?: string }>)[src.region]
    ?? ((page.region ?? {}) as Record<string, { queryOrderBy?: string }>)[src.region];
  const [column, dir] = (region?.queryOrderBy ?? src.select[0]).split(/\s+/);
  return { column: column.toLowerCase(), dir: dir?.toUpperCase() === 'DESC' ? 'DESC' : 'ASC' };
}

export function reportDef(src: RegionSource): ReportDef {
  return {
    from: `app.${src.view}`, columns: regionColumns(src), defaultSort: regionDefaultSort(src), rowsPerPage: src.rowsPerPage,
    where: src.where?.sql, facets: src.facets, searchable: src.searchable,
  };
}

/**
 * LOV SQL (shared components), allowlisted like region sources. The query runs as a derived table so that
 * its ORDER BY can use binary collation (Oracle NLS_SORT=BINARY); orderBy names the output column.
 */
export interface LovSource {
  readonly source: string;
  readonly orderBy: 'd' | 'r';
  readonly numeric?: boolean;
}

export const LOV_SOURCES = {
  APX_DEMO_DEPARTMENTS: { source: "select dept_code || ' - ' || dept_name d, department_id r from apx_demo_departments where active_yn = 'Y' order by 1", orderBy: 'd' },
  APX_DEMO_ITEMS: { source: "select item_code || ' - ' || item_name || ' (' || uom || ')' d, item_id r from apx_demo_items where active_yn = 'Y' order by 1", orderBy: 'd' },
  APX_DEMO_REQUESTS: { source: "select request_no || ' - ' || purpose d, request_id r from apx_demo_requests where status in ('DRAFT', 'REJECTED') order by 1", orderBy: 'd' },
  APX_DEMO_REQUEST_LINES: { source: 'select line_id d, line_id r from apx_demo_request_lines order by 1', orderBy: 'd', numeric: true },
  DEMO_ROLES: { source: "select role_code || ' - ' || role_name d, role_code r from apx_demo_roles order by role_code", orderBy: 'r' },
} as const satisfies Record<string, LovSource>;

export type DynamicLov = keyof typeof LOV_SOURCES;

export function lovSql(lov: LovSource): string {
  const base = lov.source.replace(/\s+order by\s+[a-z0-9_]+$/i, '')
    .replace(/\bfrom (apx_demo_[a-z_]+)/g, 'from app.$1');
  return `SELECT lov.d::text AS d, lov.r::text AS r FROM (${base}) lov ORDER BY lov.${lov.orderBy}${lov.numeric ? '' : ' COLLATE "C"'}`;
}
