import Link from 'next/link';
import { ErrorRegion, SuccessMessage } from '../../../components/Alerts';
import { Facets } from '../../../components/Facets';
import { facetViews } from '../../../components/facets-view';
import { PageHeader } from '../../../components/PageHeader';
import { ReportTable } from '../../../components/ReportTable';
import { apiGet, type ReportResult } from '../../../lib/api';
import { buttonAllowed } from '../../../lib/authz';
import { apiErrorOnly } from '../../../lib/guard';
import { all, first, qs, type SearchParams } from '../../../lib/routes';
import { item, page } from '../../../lib/spec';
import { pageTitle } from '../../../lib/spec';

export const metadata = { title: pageTitle(300) };

/** Page 300 Permintaan Barang: faceted search + classic report (15 rows, REQUEST_NO DESC, link -> 301). */
export default async function Page({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  const p = page(300);
  const params = { q: first(sp.q), facet: all(sp.facet), page: first(sp.page) };
  let result: ReportResult;
  try {
    result = await apiGet<ReportResult>(`/regions/requests${qs(params)}`);
  } catch (e) {
    return <><PageHeader page={300} title={p.title} /><ErrorRegion error={apiErrorOnly(e)} /></>;
  }
  const back = `/requests${qs(params)}`;
  return (
    <>
      <PageHeader page={300} title={p.title}
        actions={await buttonAllowed(300, 'CREATE') && <Link className="btn btn-hot" href={`/requests/new?return=${encodeURIComponent(back)}`}>{p.button.CREATE.buttonImageAlt}</Link>} />
      <SuccessMessage flash={first(sp.msg)} />
      <div className="layout-facets">
        <aside className="region" aria-label="Filter">
          <Facets basePath="/requests" searchItem="P300_SEARCH" searchLabel={item(300, 'P300_SEARCH').prompt} q={params.q}
            facets={facetViews(300, result, sp.facet)} />
        </aside>
        <section className="region" aria-label="Hasil Permintaan Barang">
          <ReportTable result={result} basePath="/requests" params={params} noData={p.reportRegion['Hasil Permintaan Barang'].queryNoDataFound}
            columnLinks={{ request_no: (r) => `/requests/${r.request_id}?return=${encodeURIComponent(back)}` }} testId="report-requests" />
        </section>
      </div>
    </>
  );
}
