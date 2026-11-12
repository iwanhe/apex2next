import type { UiSpecLike } from '../forms/forms';
import type { ColumnType, FacetDef, ReportColumn, ReportDef } from './report';

/**
 * Region and LOV sources of a converted application (roadmap R3). The generator (`apex2next generate`) writes
 * them from the APEX export: the region SQL translated to PostgreSQL, allowlisted per region. Request
 * parameters only choose among known columns, so no client text reaches the SQL text.
 */
export interface RegionSource {
  readonly page: number;
  /** Region name in the inventory (REGION or REPORT_REGION). */
  readonly region: string;
  readonly kind: 'IR' | 'CLASSIC' | 'CARDS';
  /** Plain column list of one view or table (unqualified, as in the export). */
  readonly view?: string;
  /** Any other query: translated PostgreSQL text, run as a derived table. Exactly one of view / sql is set. */
  readonly sql?: string;
  readonly select: readonly string[];
  /** Source WHERE with :ITEM binds replaced by $n, e.g. request_id = to_number(:P302_REQUEST_ID). */
  readonly where?: { readonly sql: string; readonly source: string };
  /** Bind names in $n order (page items, APP_USER); the page service supplies the values. */
  readonly binds?: readonly string[];
  /** Column types for classic/cards regions (IR columns carry their type in the export). */
  readonly types?: Readonly<Record<string, ColumnType>>;
  readonly hidden?: readonly string[];
  readonly facets?: readonly FacetDef[];
  readonly searchable: boolean;
  readonly sortable: boolean;
  readonly rowsPerPage: number;
  /** Column types unknown (derived query without catalog entry); see ReportDef.untyped. */
  readonly untyped?: boolean;
}

/**
 * LOV query of the shared components. `sql` is the translated query without ORDER BY; it runs as a derived
 * table so that the order can use binary collation (Oracle NLS_SORT=BINARY). orderBy names the output column.
 */
export interface LovSource {
  /** The query as exported (kept for the drift test against the inventory). */
  readonly source: string;
  readonly sql: string;
  /** 'o': the query selects extra columns o1..on (ORDER BY columns that are not displayed), sorted per `order`. */
  readonly orderBy: 'd' | 'r' | 'o';
  readonly numeric?: boolean;
  readonly order?: readonly { readonly dir: 'ASC' | 'DESC'; readonly numeric?: boolean }[];
}

type AnyMap = Record<string, Record<string, unknown>>;
const pageOf = (spec: UiSpecLike, id: number) => (spec.pages as Record<string, AnyMap>)[String(id)];

/** Columns with type and visibility, taken from the export (IR columns, IR default report, report columns). */
export function regionColumns(spec: UiSpecLike, src: RegionSource): ReportColumn[] {
  const page = pageOf(spec, src.page);
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
export function regionDefaultSort(spec: UiSpecLike, src: RegionSource): { column: string; dir: 'ASC' | 'DESC' } {
  const page = pageOf(spec, src.page);
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

export function reportDef(spec: UiSpecLike, schema: string, src: RegionSource): ReportDef {
  if ((src.view === undefined) === (src.sql === undefined)) throw new Error(`region ${src.page}:${src.region} needs view or sql`);
  return {
    from: src.sql !== undefined ? `(${src.sql})` : `${schema}.${src.view}`, columns: regionColumns(spec, src),
    defaultSort: regionDefaultSort(spec, src), rowsPerPage: src.rowsPerPage,
    where: src.sql !== undefined ? undefined : src.where?.sql, facets: src.facets, searchable: src.searchable,
    untyped: src.untyped,
  };
}

export function lovSql(lov: LovSource): string {
  if (lov.orderBy === 'o') {
    const order = lov.order ?? [];
    if (!order.length) throw new Error('LOV orderBy o needs order columns');
    const names = order.map((_, i) => `o${i + 1}`);
    // text sorts byte-wise as NLS_SORT=BINARY; numbers by value; ISO date/time text sorts chronologically
    const keys = order.map((o, i) => (o.numeric ? `lov.${names[i]}` : `lov.${names[i]}::text COLLATE "C"`)
      + (o.dir === 'DESC' ? ' DESC' : ''));
    return `SELECT lov.d::text AS d, lov.r::text AS r FROM (${lov.sql}) lov(d, r, ${names.join(', ')}) ORDER BY ${keys.join(', ')}`;
  }
  return `SELECT lov.d::text AS d, lov.r::text AS r FROM (${lov.sql}) lov(d, r) ORDER BY lov.${lov.orderBy}${lov.numeric ? '' : ' COLLATE "C"'}`;
}

/** Region helpers bound to one application's UI spec and target schema. */
export function bindRegionSources(spec: UiSpecLike, options: { readonly schema: string }) {
  if (!/^[a-z_][a-z0-9_]*$/.test(options.schema)) throw new Error(`bad schema ${options.schema}`);
  return {
    regionColumns: (src: RegionSource) => regionColumns(spec, src),
    regionDefaultSort: (src: RegionSource) => regionDefaultSort(spec, src),
    reportDef: (src: RegionSource) => reportDef(spec, options.schema, src),
    lovSql,
  };
}

/**
 * Values of a region's binds in $n order. Page items come from the request as `item.<NAME>` (APEX sets them
 * from the URL the same way); APP_USER is always the signed-in user and never taken from the request.
 * Only the binds the generator allowlisted for the region are accepted; '' is NULL, as in APEX session state.
 */
export function regionBinds(src: RegionSource, query: Record<string, unknown>, username: string): (string | null)[] {
  const binds = src.binds ?? [];
  for (const key of Object.keys(query)) {
    if (!key.startsWith('item.')) continue;
    const name = key.slice(5);
    if (name === 'APP_USER' || !binds.includes(name)) throw new Error(`item ${name} is not a bind of region ${src.page}:${src.region}`);
  }
  return binds.map((name) => {
    if (name === 'APP_USER') return username;
    const value = query[`item.${name}`];
    if (Array.isArray(value)) throw new Error(`item ${name} given more than once`);
    return typeof value === 'string' && value !== '' ? value : null;
  });
}
