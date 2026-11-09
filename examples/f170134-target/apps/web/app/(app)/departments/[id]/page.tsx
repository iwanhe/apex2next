import { FormDialog } from '../../../../components/FormDialog';
import { first, safeReturn, type SearchParams } from '../../../../lib/routes';
import { pageTitle } from '../../../../lib/spec';

export const metadata = { title: pageTitle(201) };

/** Page 201 (modal), edit mode. */
export default async function Page({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<SearchParams> }) {
  const { id } = await params;
  const sp = await searchParams;
  return <FormDialog pageId={201} form="department" id={id} load={`/forms/department/${encodeURIComponent(id)}`} returnTo={safeReturn(first(sp.return), '/departments')} />;
}
