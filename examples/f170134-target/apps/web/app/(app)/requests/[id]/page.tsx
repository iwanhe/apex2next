import { FormDialog } from '../../../../components/FormDialog';
import { first, safeReturn, type SearchParams } from '../../../../lib/routes';

/** Page 301 Permintaan Barang (modal): SAVE / SUBMIT / DELETE by status, read-only items by status. */
export default async function Page({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<SearchParams> }) {
  const { id } = await params;
  const sp = await searchParams;
  return <FormDialog pageId={301} form="request" id={id} load={`/forms/request/${encodeURIComponent(id)}`}
    returnTo={safeReturn(first(sp.return), '/requests')} flash={{ SUBMIT: '301:CALL_SUBMIT_REQUESTS' }} />;
}
