import Link from 'next/link';
import type { ReportColumn, ReportResult } from '../api';
import { formatValue, rowRange } from '../format';
import { qs } from '../routes';

export type Row = Record<string, string | null>;

/** Visible columns in display order (IR default report list / classic column sequence). */
export function visibleColumns(columns: ReportColumn[]): ReportColumn[] {
  return columns.filter((c) => !c.hidden).sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
}

/**
 * Interactive / classic report body. IR features kept: row search, column-heading sort, pagination
 * ("x - y of z"), detail link column and download (CSV/HTML). Other IR actions are recorded as gaps.
 */
export function ReportTable(props: {
  result: ReportResult;
  basePath: string;
  params: Record<string, string | string[] | undefined>;
  sortable?: boolean;
  noData: string;
  detailLink?: (row: Row) => string;
  columnLinks?: Record<string, (row: Row) => string>;
  testId?: string;
  kind?: 'IR' | 'CLASSIC';
  /** Name of the paging parameter (default `page`); a composed page prefixes it with the region key. */
  pageParam?: string;
}) {
  const { result, params } = props;
  const cols = visibleColumns(result.columns);
  const pageParam = props.pageParam ?? 'page';
  const link = (extra: Record<string, string | undefined>) => {
    const query = qs({ ...params, ...extra });
    if (!query) return props.basePath;
    return props.basePath.includes('?') ? `${props.basePath}&${query.slice(1)}` : `${props.basePath}${query}`;
  };
  if (!result.rows.length) return <div className="nodata" data-testid={props.testId ? `${props.testId}-nodata` : undefined}>{props.noData}</div>;
  const pages = Math.ceil(result.total / result.rowsPerPage);
  return (
    <div data-testid={props.testId}>
      <table className="report">
        <thead>
          <tr>
            {props.detailLink && <th aria-label="Edit"></th>}
            {cols.map((c) => {
              const num = c.type === 'NUMBER' || c.align === 'RIGHT';
              const active = result.sort.column.toLowerCase() === c.name;
              const nextDir = active && result.sort.dir === 'ASC' ? 'desc' : 'asc';
              return (
                <th key={c.name} className={num ? 'num' : undefined} scope="col">
                  {props.sortable
                    ? <Link href={link({ sort: c.name, dir: nextDir, page: undefined })}>{c.label ?? c.name}{active ? (result.sort.dir === 'ASC' ? ' ▲' : ' ▼') : ''}</Link>
                    : c.label ?? c.name}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {result.rows.map((row, i) => (
            <tr key={i}>
              {props.detailLink && <td><Link href={props.detailLink(row)} aria-label="Edit" title="Edit">✎</Link></td>}
              {cols.map((c) => {
                const text = formatValue(row[c.name], c.type, c.format);
                const href = props.columnLinks?.[c.name]?.(row);
                return (
                  <td key={c.name} className={c.type === 'NUMBER' || c.align === 'RIGHT' ? 'num' : undefined}>
                    {href ? <Link href={href}>{text}</Link> : text}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="pagination">
        <span data-testid="row-range">{rowRange(result.page, result.rowsPerPage, result.rows.length, result.total, props.kind ?? 'CLASSIC')}</span>
        {result.page > 1 && <Link href={link({ [pageParam]: String(result.page - 1) })}>‹ Previous</Link>}
        {result.page < pages && <Link href={link({ [pageParam]: String(result.page + 1) })}>Next ›</Link>}
      </div>
    </div>
  );
}

/** IR search bar (GET form, works without JavaScript) with the region's extra buttons. */
export function SearchBar(props: { basePath: string; q?: string; keep?: Record<string, string | undefined>; children?: React.ReactNode; download?: string }) {
  return (
    <div className="toolbar">
      <form action={props.basePath} method="get" role="search" style={{ display: 'flex', gap: 8 }}>
        {Object.entries(props.keep ?? {}).map(([k, v]) => v ? <input key={k} type="hidden" name={k} value={v} /> : null)}
        <input type="search" name="q" defaultValue={props.q ?? ''} placeholder="Search" aria-label="Search" />
        <button className="btn" type="submit">Go</button>
      </form>
      {props.download && (
        <>
          <a className="btn" href={`${props.download}&format=csv`}>Download CSV</a>
          <a className="btn" href={`${props.download}&format=html`}>Download HTML</a>
        </>
      )}
      {props.children}
    </div>
  );
}
