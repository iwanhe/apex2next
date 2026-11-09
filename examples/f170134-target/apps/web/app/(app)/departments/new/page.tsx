import { FormDialog } from '../../../../components/FormDialog';
import { first, safeReturn, type SearchParams } from '../../../../lib/routes';

/** Page 201 (modal), create mode. */
export default async function Page({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  return <FormDialog pageId={201} form="department" id={null} load="/forms/department" returnTo={safeReturn(first(sp.return), '/departments')} />;
}
