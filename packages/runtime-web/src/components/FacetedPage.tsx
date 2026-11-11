import Link from 'next/link';
import { apiGet, type ReportResult } from '../api';
import type { AppRuntime } from '../app';
import { buttonAllowed } from '../authz';
import { facetViews } from '../facets-view';
import { apiErrorOnly } from '../guard';
import { all, first, qs, type SearchParams } from '../routes';
import { ErrorRegion, SuccessMessage } from './Alerts';
import { Facets } from './Facets';
import { PageHeader } from './PageHeader';
import { ReportTable, type Row } from './ReportTable';

/**
 * A normal page with a Faceted Search region and one result region: a classic report (page 300 of the pilot)
 * or a Cards region (page 210). `back` is this page with its current search and facets, for return links.
 */
export async function FacetedPage(props: {
  app: AppRuntime;
  pageId: number; region: string; regionName: string; basePath: string; sp: SearchParams;
  kind: 'CLASSIC' | 'CARDS';
  /** The NATIVE_SEARCH facet item of the page. */
  searchItem: string;
  createHref?: (back: string) => string;
  /** Classic report: link per column name. */
  columnLinks?: Record<string, (row: Row, back: string) => string>;
  /** Cards: title link and the column that identifies a card. */
  cardLink?: (row: Row, back: string) => string;
  cardKey?: string;
}) {
  const { spec } = props.app;
  const p = spec.page(props.pageId);
  const { sp, basePath } = props;
  const params = { q: first(sp.q), facet: all(sp.facet), page: first(sp.page) };
  let result: ReportResult;
  try {
    result = await apiGet<ReportResult>(`/regions/${props.region}${qs(params)}`);
  } catch (e) {
    return <><PageHeader app={props.app} page={props.pageId} title={p.title} /><ErrorRegion error={apiErrorOnly(e)} /></>;
  }
  const back = `${basePath}${qs(params)}`;
  const filterName = Object.entries((p.region ?? {}) as Record<string, { plugSourceType?: string }>)
    .find(([, r]) => r.plugSourceType === 'NATIVE_FACETED_SEARCH')?.[0] ?? 'Filter';
  const create = props.createHref && p.button?.CREATE && (await buttonAllowed(spec, props.pageId, 'CREATE'))
    ? <Link className="btn btn-hot" href={props.createHref(back)}>{p.button.CREATE.buttonImageAlt}</Link> : false;
  const columnLinks = Object.fromEntries(Object.entries(props.columnLinks ?? {})
    .map(([name, link]) => [name, (r: Row) => link(r, back)]));
  const cards = props.kind === 'CARDS' ? p.cards[props.regionName] : null;
  const more = result.page * result.rowsPerPage < result.total;
  return (
    <>
      <PageHeader app={props.app} page={props.pageId} title={p.title} actions={create} />
      <SuccessMessage app={props.app} flash={first(sp.msg)} />
      <div className="layout-facets">
        <aside className="region" aria-label={filterName}>
          <Facets basePath={basePath} searchItem={props.searchItem} searchLabel={spec.item(props.pageId, props.searchItem).prompt}
            q={params.q} facets={facetViews(spec, props.pageId, result, sp.facet)} />
        </aside>
        <section className="region" aria-label={props.regionName}>
          {cards === null ? (
            <ReportTable result={result} basePath={basePath} params={params} noData={p.reportRegion[props.regionName].queryNoDataFound}
              columnLinks={columnLinks} testId={`report-${props.region}`} />
          ) : (
            <>
              {result.rows.length === 0 ? <div className="nodata">{p.region[props.regionName].plugQueryNoDataFound}</div> : (
                <div className="cards" data-testid="cards">
                  {result.rows.map((r, i) => (
                    <article className="card" key={props.cardKey ? r[props.cardKey] : i}>
                      <div className="icon" aria-hidden="true">◆</div>
                      <div>
                        <div className="title">
                          {props.cardLink ? <Link href={props.cardLink(r, back)}>{r[cards.titleColumnName.toLowerCase()]}</Link>
                            : r[cards.titleColumnName.toLowerCase()]}
                        </div>
                        {cards.subTitleColumnName && <div className="subtitle">{r[cards.subTitleColumnName.toLowerCase()]}</div>}
                        {cards.bodyColumnName && <div>{r[cards.bodyColumnName.toLowerCase()]}</div>}
                      </div>
                    </article>
                  ))}
                </div>
              )}
              {more && <div className="pagination"><Link href={`${basePath}${qs({ ...params, page: String(result.page + 1) })}`}>Load more</Link></div>}
            </>
          )}
        </section>
      </div>
    </>
  );
}
