import { IrPage } from '../../../components/IrPage';
import type { SearchParams } from '../../../lib/routes';
import { pageTitle } from '../../../lib/spec';

export const metadata = { title: pageTitle(200) };

/** Page 200 Departments (IR; detail link and CREATE -> 201). */
export default async function Page({ searchParams }: { searchParams: Promise<SearchParams> }) {
  return <IrPage pageId={200} region="departments" regionName="Departments" basePath="/departments" sp={await searchParams}
    detailLink={(r) => `/departments/${r.department_id}`} createHref="/departments/new" />;
}
