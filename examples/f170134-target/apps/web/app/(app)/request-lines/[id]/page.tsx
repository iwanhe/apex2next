import { FormDialog } from '../../../../components/FormDialog';
import { first, safeReturn, type SearchParams } from '../../../../lib/routes';
import { pageTitle } from '../../../../lib/spec';

export const metadata = { title: pageTitle(311) };

/** Page 311 (modal), edit mode. */
export default async function Page({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<SearchParams> }) {
  const { id } = await params;
  const sp = await searchParams;
  return <FormDialog pageId={311} form="requestLine" id={id} load={`/forms/requestLine/${encodeURIComponent(id)}`}
    returnTo={safeReturn(first(sp.return), '/request-lines')} />;
}
