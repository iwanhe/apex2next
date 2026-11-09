import { FormDialog } from '../../../../components/FormDialog';
import { first, safeReturn, type SearchParams } from '../../../../lib/routes';

/** Page 211 (modal), edit mode. */
export default async function Page({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<SearchParams> }) {
  const { id } = await params;
  const sp = await searchParams;
  return <FormDialog pageId={211} form="item" id={id} load={`/forms/item/${encodeURIComponent(id)}`} returnTo={safeReturn(first(sp.return), '/items')} />;
}
