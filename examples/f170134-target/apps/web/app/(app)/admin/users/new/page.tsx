import { FormDialog } from '../../../../../components/FormDialog';
import { first, safeReturn, type SearchParams } from '../../../../../lib/routes';

/** Page 501 (modal), create mode. */
export default async function Page({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  return <FormDialog pageId={501} form="userRole" id={null} load="/forms/userRole" returnTo={safeReturn(first(sp.return), '/admin/users')} />;
}
