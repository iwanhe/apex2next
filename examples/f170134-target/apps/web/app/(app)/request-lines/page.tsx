import { IrPage } from '../../../components/IrPage';
import type { SearchParams } from '../../../lib/routes';

/** Page 310 Baris Permintaan (IR; detail link and CREATE -> 311). */
export default async function Page({ searchParams }: { searchParams: Promise<SearchParams> }) {
  return <IrPage pageId={310} region="requestLines" regionName="Baris Permintaan" basePath="/request-lines" sp={await searchParams}
    detailLink={(r) => `/request-lines/${r.line_id}?return=${encodeURIComponent('/request-lines')}`}
    createHref={`/request-lines/new?return=${encodeURIComponent('/request-lines')}`} />;
}
