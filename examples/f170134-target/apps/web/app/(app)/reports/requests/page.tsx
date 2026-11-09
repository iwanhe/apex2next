import { IrPage } from '../../../../components/IrPage';
import type { SearchParams } from '../../../../lib/routes';
import { pageTitle } from '../../../../lib/spec';

export const metadata = { title: pageTitle(400) };

/** Page 400 Rekap Permintaan (IR on apx_demo_request_summary_v, no detail link). */
export default async function Page({ searchParams }: { searchParams: Promise<SearchParams> }) {
  return <IrPage pageId={400} region="requestSummary" regionName="Rekap Permintaan" basePath="/reports/requests" sp={await searchParams} />;
}
