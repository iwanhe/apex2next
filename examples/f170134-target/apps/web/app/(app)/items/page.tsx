import Link from 'next/link';
import { ErrorRegion, SuccessMessage } from '../../../components/Alerts';
import { Facets } from '../../../components/Facets';
import { facetViews } from '../../../components/facets-view';
import { PageHeader } from '../../../components/PageHeader';
import { apiGet, type ReportResult } from '../../../lib/api';
import { apiErrorOnly } from '../../../lib/guard';
import { all, first, qs, type SearchParams } from '../../../lib/routes';
import { item, page } from '../../../lib/spec';
import { pageTitle } from '../../../lib/spec';

export const metadata = { title: pageTitle(210) };

/** Page 210 Items: faceted search (P210_SEARCH, P210_CATEGORY, P210_ACTIVE_YN) + Cards "Hasil Items". */
export default async function Page({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  const p = page(210);
  const params = { q: first(sp.q), facet: all(sp.facet), page: first(sp.page) };
  let result: ReportResult;
  try {
    result = await apiGet<ReportResult>(`/regions/items${qs(params)}`);
  } catch (e) {
    return <><PageHeader page={210} title={p.title} /><ErrorRegion error={apiErrorOnly(e)} /></>;
  }
  const cards = p.cards['Hasil Items'];
  const more = result.page * result.rowsPerPage < result.total;
  return (
    <>
      <PageHeader page={210} title={p.title} actions={<Link className="btn btn-hot" href="/items/new">{p.button.CREATE.buttonImageAlt}</Link>} />
      <SuccessMessage flash={first(sp.msg)} />
      <div className="layout-facets">
        <aside className="region" aria-label="Filter">
          <Facets basePath="/items" searchItem="P210_SEARCH" searchLabel={item(210, 'P210_SEARCH').prompt} q={params.q}
            facets={facetViews(210, result, sp.facet)} />
        </aside>
        <section className="region" aria-label="Hasil Items">
          {result.rows.length === 0 ? <div className="nodata">{p.region['Hasil Items'].plugQueryNoDataFound}</div> : (
            <div className="cards" data-testid="cards">
              {result.rows.map((r) => (
                <article className="card" key={r.item_id}>
                  <div className="icon" aria-hidden="true">◆</div>
                  <div>
                    <div className="title"><Link href={`/items/${r.item_id}`}>{r[cards.titleColumnName.toLowerCase()]}</Link></div>
                    <div className="subtitle">{r[cards.subTitleColumnName.toLowerCase()]}</div>
                    <div>{r[cards.bodyColumnName.toLowerCase()]}</div>
                  </div>
                </article>
              ))}
            </div>
          )}
          {more && <div className="pagination"><Link href={`/items${qs({ ...params, page: String(result.page + 1) })}`}>Load more</Link></div>}
        </section>
      </div>
    </>
  );
}
