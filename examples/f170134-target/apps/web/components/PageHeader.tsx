import Link from 'next/link';
import { BREADCRUMBS } from '../lib/spec';
import { PAGE_ROUTES } from '../lib/routes';

/** Breadcrumb region (shared component "Breadcrumb") and the page title. */
export function PageHeader({ page, title, actions }: { page: number; title: string; actions?: React.ReactNode }) {
  const entry = BREADCRUMBS.find((b) => b.page === page);
  const trail: { label: string; page: number }[] = [];
  let cur = entry;
  while (cur) {
    trail.unshift({ label: cur.label, page: cur.page });
    cur = cur.parent ? BREADCRUMBS.find((b) => b.label === cur!.parent) : undefined;
  }
  return (
    <div className="region-header" style={{ alignItems: 'flex-end' }}>
      <div>
        {trail.length > 1 && (
          <nav className="breadcrumb" aria-label="Breadcrumb">
            <ol>
              {trail.map((t, i) => (
                <li key={t.page}>{i < trail.length - 1 ? <Link href={PAGE_ROUTES[t.page]}>{t.label}</Link> : <span aria-current="page">{t.label}</span>}</li>
              ))}
            </ol>
          </nav>
        )}
        <h1 data-apex-page={page}>{title}</h1>
      </div>
      {actions && <div className="toolbar" style={{ marginBottom: 16 }}>{actions}</div>}
    </div>
  );
}
