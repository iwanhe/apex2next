import { IrPage } from '../../../../components/IrPage';
import type { SearchParams } from '../../../../lib/routes';

/** Page 500 Users & Roles (ADMIN_RIGHTS; detail link and CREATE -> 501). */
export default async function Page({ searchParams }: { searchParams: Promise<SearchParams> }) {
  return <IrPage pageId={500} region="userRoles" regionName="Users & Roles" basePath="/admin/users" sp={await searchParams}
    detailLink={(r) => `/admin/users/${r.user_role_id}`} createHref="/admin/users/new" />;
}
