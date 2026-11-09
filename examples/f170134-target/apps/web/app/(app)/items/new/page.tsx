import { FormDialog } from '../../../../components/FormDialog';
import { first, safeReturn, type SearchParams } from '../../../../lib/routes';
import { pageTitle } from '../../../../lib/spec';

export const metadata = { title: pageTitle(211) };

/** Page 211 (modal), create mode. */
export default async function Page({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  return <FormDialog pageId={211} form="item" id={null} load="/forms/item" returnTo={safeReturn(first(sp.return), '/items')} />;
}
