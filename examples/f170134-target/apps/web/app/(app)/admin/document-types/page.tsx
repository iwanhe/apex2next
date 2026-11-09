import { IrPage } from '../../../../components/IrPage';
import type { SearchParams } from '../../../../lib/routes';

/** Page 510 Document Types & Approval (ADMIN_RIGHTS; detail link -> 511, update only). */
export default async function Page({ searchParams }: { searchParams: Promise<SearchParams> }) {
  return <IrPage pageId={510} region="docTypes" regionName="Document Types & Approval" basePath="/admin/document-types" sp={await searchParams}
    detailLink={(r) => `/admin/document-types/${encodeURIComponent(r.doc_type ?? '')}`} />;
}
