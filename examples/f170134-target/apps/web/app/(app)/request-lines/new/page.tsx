import { FormDialog } from '../../../../components/FormDialog';
import { first, qs, safeReturn, type SearchParams } from '../../../../lib/routes';

/** Page 311 (modal), create mode; P311_REQUEST_ID may come from page 302 (CREATE_REQUEST_LINES). */
export default async function Page({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  return <FormDialog pageId={311} form="requestLine" id={null} load={`/forms/requestLine${qs({ request_id: first(sp.request_id) })}`}
    returnTo={safeReturn(first(sp.return), '/request-lines')} />;
}
