import Link from 'next/link';
import { apiGet, type ReportResult } from '../api';
import type { AppRuntime } from '../app';
import { buttonAllowed } from '../authz';
import { apiErrorOnly } from '../guard';
import { first, qs, type SearchParams } from '../routes';
import { ErrorRegion, SuccessMessage } from './Alerts';
import { PageHeader } from './PageHeader';
import { ReportTable, SearchBar, type Row } from './ReportTable';

/** A normal page with breadcrumb and one Interactive Report region (pages 190, 200, 310, 400, 500, 510). */
export async function IrPage(props: {
  app: AppRuntime;
  pageId: number; region: string; regionName: string; basePath: string; sp: SearchParams;
  detailLink?: (row: Row) => string; createHref?: string;
}) {
  const p = props.app.spec.page(props.pageId);
  const params = { q: first(props.sp.q), sort: first(props.sp.sort), dir: first(props.sp.dir), page: first(props.sp.page) };
  let result: ReportResult;
  try {
    result = await apiGet<ReportResult>(`/regions/${props.region}${qs(params)}`);
  } catch (e) {
    return <><PageHeader app={props.app} page={props.pageId} title={p.title} /><ErrorRegion error={apiErrorOnly(e)} /></>;
  }
  const ir = Object.values(p.ir ?? {})[0] as Record<string, string> | undefined;
  const create = p.button?.CREATE && (await buttonAllowed(props.app.spec, props.pageId, 'CREATE')) ? p.button.CREATE : undefined;
  return (
    <>
      <PageHeader app={props.app} page={props.pageId} title={p.title} />
      <SuccessMessage app={props.app} flash={first(props.sp.msg)} />
      <section className="region" aria-label={props.regionName}>
        <SearchBar basePath={props.basePath} q={params.q} keep={{ sort: params.sort, dir: params.dir }}
          download={ir?.downloadFormats ? `/download/${props.region}${qs({ q: params.q, sort: params.sort, dir: params.dir }) || '?'}` : undefined}>
          {props.createHref && create && <Link className="btn btn-hot" href={props.createHref}>{create.buttonImageAlt}</Link>}
        </SearchBar>
        <ReportTable kind="IR" result={result} basePath={props.basePath} params={params} sortable
          noData={ir?.noDataFoundMessage ?? 'No data found.'} detailLink={props.detailLink} testId={`report-${props.region}`} />
      </section>
    </>
  );
}
