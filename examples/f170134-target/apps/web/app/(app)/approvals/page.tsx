import { IrPage } from '../../../components/IrPage';
import type { SearchParams } from '../../../lib/routes';

/** Page 190 Approval Inbox (IR on apx_demo_approvals_v; detail link -> 191). */
export default async function Page({ searchParams }: { searchParams: Promise<SearchParams> }) {
  return <IrPage pageId={190} region="approvalInbox" regionName="Approval Inbox" basePath="/approvals" sp={await searchParams}
    detailLink={(r) => `/approvals/${r.approval_id}?return=${encodeURIComponent('/approvals')}`} />;
}
