import { BusinessTx } from '../business/context';
import { errors } from '../business/errors';

/**
 * WP9.5 report engine for APEX Interactive Reports, Classic Reports and Cards regions.
 *
 * Region SQL is an allowlisted constant per region (report-definitions.ts); request parameters only choose
 * among known columns, so no client text reaches the SQL text. Semantics kept from APEX:
 *  - row search: case-insensitive "contains" over the displayed columns (dates as DD-MON-YYYY);
 *  - sort: one column, ASC NULLS LAST / DESC NULLS FIRST (Oracle default) with binary collation ("C"),
 *    matching NLS_SORT=BINARY of the source session;
 *  - faceted search: OR inside a facet, AND across facets; facet counts are computed with every other
 *    facet and the search applied; zero counts hidden; ordered by count (p_fc_sort_by_top_counts).
 */
export type ColumnType = 'STRING' | 'NUMBER' | 'DATE';

export interface ReportColumn {
  readonly name: string;
  readonly type: ColumnType;
  readonly hidden: boolean;
  /** Display metadata copied from the export (IR column label / report column heading, format mask, alignment). */
  readonly label?: string | null;
  readonly format?: string | null;
  readonly align?: string | null;
  /** Display position (IR default report column list, or classic report column sequence). */
  readonly order?: number;
}

export interface FacetDef {
  /** Page item of the facet, e.g. P300_STATUS. */
  readonly item: string;
  readonly column: string;
}

export interface ReportDef {
  readonly from: string;
  readonly columns: readonly ReportColumn[];
  readonly defaultSort: { readonly column: string; readonly dir: 'ASC' | 'DESC' };
  readonly rowsPerPage: number;
  /** Fixed filter with $n parameters (e.g. master-detail binds), appended with AND. */
  readonly where?: string;
  readonly facets?: readonly FacetDef[];
  readonly searchable: boolean;
}

export interface ReportQuery {
  readonly search?: string;
  readonly sort?: string;
  readonly dir?: string;
  readonly page?: number;
  readonly facets?: Record<string, readonly string[]>;
  /** Download: every row (APEX downloads the whole filtered report). */
  readonly all?: boolean;
}

export interface FacetResult {
  readonly item: string;
  readonly values: { value: string; count: number }[];
}

export interface ReportResult {
  readonly rows: Record<string, string | null>[];
  readonly total: number;
  readonly page: number;
  readonly rowsPerPage: number;
  readonly sort: { column: string; dir: 'ASC' | 'DESC' };
  readonly facets: FacetResult[];
  readonly columns: readonly ReportColumn[];
}

const ident = (name: string) => {
  if (!/^[a-z_][a-z0-9_]*$/.test(name)) throw new Error(`bad identifier ${name}`);
  return name;
};

function selectExpr(c: ReportColumn): string {
  const col = ident(c.name.toLowerCase());
  return c.type === 'DATE' ? `to_char(${col}, 'YYYY-MM-DD HH24:MI:SS') AS ${col}` : `${col}::text AS ${col}`;
}

function searchExpr(c: ReportColumn): string {
  const col = ident(c.name.toLowerCase());
  return c.type === 'DATE' ? `upper(to_char(${col}, 'DD-MON-YYYY'))` : `upper(${col}::text)`;
}

function likePattern(text: string): string {
  return `%${text.toUpperCase().replace(/[\\%_]/g, (m) => `\\${m}`)}%`;
}

export async function runReport(tx: BusinessTx, def: ReportDef, query: ReportQuery, params: unknown[] = []): Promise<ReportResult> {
  const byName = new Map(def.columns.map((c) => [c.name.toLowerCase(), c]));
  const sortName = (query.sort ?? def.defaultSort.column).toLowerCase();
  const sortCol = byName.get(sortName);
  if (!sortCol) throw errors.invalidInput(`Kolom urut tidak dikenal: ${query.sort}`);
  const dir = (query.dir ?? def.defaultSort.dir).toUpperCase() === 'DESC' ? 'DESC' : 'ASC';
  const search = (query.search ?? '').trim();
  if (search && !def.searchable) throw errors.invalidInput('Region ini tidak mendukung pencarian.');
  const unknownFacets = Object.keys(query.facets ?? {}).filter((k) => !(def.facets ?? []).some((f) => f.item === k));
  if (unknownFacets.length) throw errors.invalidInput(`Facet tidak dikenal: ${unknownFacets.join(', ')}`);
  /** WHERE clause and binds for one statement; exceptFacet leaves that facet's own filter out (counts). */
  const filter = (exceptFacet?: string) => {
    const values: unknown[] = [...params];
    const bind = (v: unknown) => { values.push(v); return `$${values.length}`; };
    const where: string[] = def.where ? [`(${def.where})`] : [];
    if (search) {
      const p = bind(likePattern(search));
      where.push(`(${def.columns.filter((c) => !c.hidden).map((c) => `${searchExpr(c)} LIKE ${p}`).join(' OR ')})`);
    }
    for (const f of def.facets ?? []) {
      const selected = query.facets?.[f.item] ?? [];
      if (f.item === exceptFacet || !selected.length) continue;
      where.push(`${ident(f.column.toLowerCase())}::text = ANY(${bind([...selected])}::text[])`);
    }
    return { where, values };
  };
  const main = filter();
  const whereSql = main.where.length ? `WHERE ${main.where.join(' AND ')}` : '';
  // Sort on the source column (src.col), not on the text-cast output alias of the same name: numbers and dates
  // must sort by value as in APEX (J-04), strings byte-wise as NLS_SORT=BINARY.
  const sortRef = `src.${ident(sortName)}`;
  const sortExpr = sortCol.type === 'STRING' ? `${sortRef} COLLATE "C"` : sortRef;
  const page = Math.max(1, Math.floor(Number(query.page ?? 1)) || 1);
  const limit = query.all ? '' : `LIMIT ${def.rowsPerPage} OFFSET ${(page - 1) * def.rowsPerPage}`;
  const rows = await tx.query(
    `SELECT ${def.columns.map(selectExpr).join(', ')} FROM ${def.from} AS src ${whereSql}
      ORDER BY ${sortExpr} ${dir} NULLS ${dir === 'ASC' ? 'LAST' : 'FIRST'} ${limit}`, main.values);
  const total = await tx.query<{ n: string }>(`SELECT count(*)::text AS n FROM ${def.from} ${whereSql}`, main.values);
  const facets: FacetResult[] = [];
  for (const f of def.facets ?? []) {
    const fq = filter(f.item);
    const col = ident(f.column.toLowerCase());
    const r = await tx.query<{ value: string; count: string }>(
      `SELECT ${col}::text AS value, count(*)::text AS count FROM ${def.from}
        WHERE ${[...fq.where, `${col} IS NOT NULL`].join(' AND ')}
        GROUP BY ${col} ORDER BY count(*) DESC, ${col}::text COLLATE "C"`, fq.values);
    facets.push({ item: f.item, values: r.rows.map((x) => ({ value: x.value, count: Number(x.count) })) });
  }
  return { rows: rows.rows, total: Number(total.rows[0].n), page, rowsPerPage: def.rowsPerPage,
    sort: { column: sortCol.name, dir }, facets, columns: def.columns };
}
