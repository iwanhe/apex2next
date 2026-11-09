import { FormDialog } from '../../../../components/FormDialog';
import { first, safeReturn, type SearchParams } from '../../../../lib/routes';

/** Page 301 Permintaan Barang (modal), create mode. */
export default async function Page({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  return <FormDialog pageId={301} form="request" id={null} load="/forms/request" returnTo={safeReturn(first(sp.return), '/requests')} />;
}
