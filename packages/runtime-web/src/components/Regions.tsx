import Link from 'next/link';
import { createElement, type ReactNode } from 'react';
import { apiGet, type ReportResult } from '../api';
import type { AppRuntime } from '../app';
import { apiErrorOnly } from '../guard';
import { first, qs, type SearchParams } from '../routes';
import { ErrorRegion } from './Alerts';
import { ReportTable, SearchBar, type Row } from './ReportTable';

/**
 * Regions of a composed page (R4a): a page assembled region by region by `apex2next generate`.
 * Each data region fetches its own rows; its paging and search parameters are prefixed with the region key
 * so that several reports can share one page.
 */

/** Static content after the generator's allowlist: text, or an allowed tag with children and a safe href. */
export type StaticNode = string | { t: string; href?: string; c?: StaticNode[] };

const TAGS = new Set(['p', 'br', 'ul', 'ol', 'li', 'strong', 'b', 'em', 'i', 'a', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'code', 'pre', 'span', 'div', 'small', 'blockquote', 'hr', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'dl', 'dt',
  'dd', 'u', 'sup', 'sub']);
const VOID = new Set(['br', 'hr']);

function renderNodes(nodes: StaticNode[], path = ''): ReactNode[] {
  return nodes.map((n, i) => {
    if (typeof n === 'string') return n;
    const key = `${path}${i}`;
    if (!TAGS.has(n.t)) return renderNodes(n.c ?? [], `${key}.`);  // defence in depth: unknown tags keep only text
    if (n.t === 'a') {
      const href = n.href ?? '';
      const children = renderNodes(n.c ?? [], `${key}.`);
      if (href.startsWith('/')) return <Link key={key} href={href}>{children}</Link>;
      if (/^https:\/\//.test(href)) return <a key={key} href={href} rel="noopener noreferrer">{children}</a>;
      return children;
    }
    return createElement(n.t, { key }, VOID.has(n.t) ? undefined : renderNodes(n.c ?? [], `${key}.`));
  });
}

export function StaticRegion({ title, nodes }: { title: string; nodes: StaticNode[] }) {
  return (
    <section className="region" aria-label={title}>
      <h2 className="region-title">{title}</h2>
      <div className="region-body">{renderNodes(nodes)}</div>
    </section>
  );
}

export interface ListEntry { label: string; href?: string; icon?: string; description?: string }

export function ListRegion({ title, items }: { title: string; items: ListEntry[] }) {
  return (
    <section className="region" aria-label={title}>
      <h2 className="region-title">{title}</h2>
      <ul className="media-list">
        {items.map((it, i) => (
          <li key={i}>
            <div className="title">{it.href ? <Link href={it.href}>{it.label}</Link> : it.label}</div>
            {it.description && <div className="description">{it.description}</div>}
          </li>
        ))}
      </ul>
    </section>
  );
}

interface DataProps {
  app: AppRuntime;
  pageId: number; region: string; regionName: string; basePath: string; sp: SearchParams;
  /** Hidden page items the region query binds (item name -> value, from the page URL). */
  items?: Record<string, string | null>;
}

/** Query string of the region's API call: own parameters plus item binds as item.NAME. */
function apiQuery(params: Record<string, string | undefined>, items?: Record<string, string | null>) {
  const binds = Object.fromEntries(Object.entries(items ?? {}).map(([k, v]) => [`item.${k}`, v ?? undefined]));
  return qs({ ...params, ...binds });
}

/** basePath already carries the page items; add region parameters to it. */
function join(basePath: string, extra: Record<string, string | undefined>) {
  const rest = qs(extra);
  if (!rest) return basePath;
  return basePath.includes('?') ? `${basePath}&${rest.slice(1)}` : `${basePath}${rest}`;
}

async function fetchRegion(region: string, params: Record<string, string | undefined>, items?: Record<string, string | null>) {
  return apiGet<ReportResult>(`/regions/${region}${apiQuery(params, items)}`);
}

/** Classic report region; paging parameter `<region>.page`. */
export async function ReportRegion(props: DataProps & { columnLinks?: Record<string, (row: Row) => string> }) {
  const pageKey = `${props.region}.page`;
  const page = first(props.sp[pageKey]);
  let result: ReportResult;
  try {
    result = await fetchRegion(props.region, { page }, props.items);
  } catch (e) {
    return <ErrorRegion error={apiErrorOnly(e)} />;
  }
  const spec = props.app.spec.page(props.pageId);
  const noData = (spec.reportRegion?.[props.regionName] as { queryNoDataFound?: string } | undefined)?.queryNoDataFound ?? 'no data found';
  // ReportTable links pages as basePath + {page}; give it a base that renames page to the region's key
  const base = props.basePath;
  return (
    <section className="region" aria-label={props.regionName}>
      <h2 className="region-title">{props.regionName}</h2>
      <ReportTable result={result} basePath={base} params={{}} noData={noData} columnLinks={props.columnLinks}
        testId={`report-${props.region}`} pageParam={pageKey} />
    </section>
  );
}

/** Interactive Report region: search, sort, paging and download, with the page's single IR parameters. */
export async function IrRegion(props: DataProps & { detailLink?: (row: Row) => string; children?: ReactNode }) {
  const params = { q: first(props.sp.q), sort: first(props.sp.sort), dir: first(props.sp.dir), page: first(props.sp.page) };
  let result: ReportResult;
  try {
    result = await fetchRegion(props.region, params, props.items);
  } catch (e) {
    return <ErrorRegion error={apiErrorOnly(e)} />;
  }
  const p = props.app.spec.page(props.pageId);
  const ir = (p.ir ?? {})[props.regionName] as Record<string, string> | undefined ?? Object.values(p.ir ?? {})[0] as Record<string, string> | undefined;
  const itemParams = Object.fromEntries(Object.entries(props.items ?? {}).map(([k, v]) => [`item.${k}`, v ?? undefined]));
  return (
    <section className="region" aria-label={props.regionName}>
      <SearchBar basePath={props.basePath} q={params.q} keep={{ sort: params.sort, dir: params.dir }}
        download={ir?.downloadFormats ? `/download/${props.region}${qs({ q: params.q, sort: params.sort, dir: params.dir, ...itemParams }) || '?'}` : undefined}>
        {props.children}
      </SearchBar>
      <ReportTable kind="IR" result={result} basePath={props.basePath} params={params} sortable
        noData={ir?.noDataFoundMessage ?? 'No data found.'} detailLink={props.detailLink} testId={`report-${props.region}`} />
    </section>
  );
}

/** Cards region (no faceted search); "Load more" through `<region>.page`. */
export async function CardsRegion(props: DataProps & { cardLink?: (row: Row) => string; cardKey?: string }) {
  const pageKey = `${props.region}.page`;
  let result: ReportResult;
  try {
    result = await fetchRegion(props.region, { page: first(props.sp[pageKey]) }, props.items);
  } catch (e) {
    return <ErrorRegion error={apiErrorOnly(e)} />;
  }
  const p = props.app.spec.page(props.pageId);
  const cards = p.cards[props.regionName];
  const more = result.page * result.rowsPerPage < result.total;
  const col = (name?: string | null) => (name ? name.toLowerCase() : null);
  return (
    <section className="region" aria-label={props.regionName}>
      {result.rows.length === 0 ? <div className="nodata">{p.region[props.regionName]?.plugQueryNoDataFound ?? 'No data found'}</div> : (
        <div className="cards" data-testid={`cards-${props.region}`}>
          {result.rows.map((r, i) => {
            const title = r[col(cards?.titleColumnName) ?? ''] ?? '';
            return (
              <article className="card" key={props.cardKey ? r[props.cardKey] ?? i : i}>
                <div className="icon" aria-hidden="true">◆</div>
                <div>
                  <div className="title">{props.cardLink ? <Link href={props.cardLink(r)}>{title}</Link> : title}</div>
                  {cards?.subTitleColumnName && <div className="subtitle">{r[col(cards.subTitleColumnName)!]}</div>}
                  {cards?.bodyColumnName && <div>{r[col(cards.bodyColumnName)!]}</div>}
                </div>
              </article>
            );
          })}
        </div>
      )}
      {more && <div className="pagination"><Link href={join(props.basePath, { [pageKey]: String(result.page + 1) })}>Load more</Link></div>}
    </section>
  );
}
