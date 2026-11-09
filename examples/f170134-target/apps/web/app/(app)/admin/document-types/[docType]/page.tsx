import { FormDialog } from '../../../../../components/FormDialog';
import { first, safeReturn, type SearchParams } from '../../../../../lib/routes';
import { pageTitle } from '../../../../../lib/spec';

export const metadata = { title: pageTitle(511) };

/** Page 511 Document Type (modal, update only). */
export default async function Page({ params, searchParams }: { params: Promise<{ docType: string }>; searchParams: Promise<SearchParams> }) {
  const { docType } = await params;
  const sp = await searchParams;
  return <FormDialog pageId={511} form="docType" id={docType} load={`/forms/docType/${encodeURIComponent(docType)}`}
    returnTo={safeReturn(first(sp.return), '/admin/document-types')} />;
}
