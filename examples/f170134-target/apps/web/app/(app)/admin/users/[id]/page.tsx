import { FormDialog } from '../../../../../components/FormDialog';
import { first, safeReturn, type SearchParams } from '../../../../../lib/routes';
import { pageTitle } from '../../../../../lib/spec';

export const metadata = { title: pageTitle(501) };

/** Page 501 (modal), edit mode. */
export default async function Page({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<SearchParams> }) {
  const { id } = await params;
  const sp = await searchParams;
  return <FormDialog pageId={501} form="userRole" id={id} load={`/forms/userRole/${encodeURIComponent(id)}`} returnTo={safeReturn(first(sp.return), '/admin/users')} />;
}
