import { FormDialog } from '../../../../components/FormDialog';
import { first, safeReturn, type SearchParams } from '../../../../lib/routes';

/** Page 191 Approval (modal): display items, P191_NOTE, APPROVE/REJECT when can_act_yn = 'Y'. */
export default async function Page({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<SearchParams> }) {
  const { id } = await params;
  const sp = await searchParams;
  return <FormDialog pageId={191} form="approval" id={id} load={`/forms/approval/${encodeURIComponent(id)}`}
    returnTo={safeReturn(first(sp.return), '/approvals')} extraItems={{ P191_NOTE: { column: 'note' } }}
    flash={{ APPROVE: '191:CALL_APPROVE', REJECT: '191:CALL_REJECT' }} />;
}
