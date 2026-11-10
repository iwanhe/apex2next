import Link from 'next/link';
import type { ReactNode } from 'react';

/** Modal page (p_page_mode MODAL) rendered as a routed dialog; Close/Cancel return to the parent page. */
export function Dialog({ page, title, closeHref, children }: { page: number; title: string; closeHref: string; children: ReactNode }) {
  return (
    <div className="dialog-backdrop">
      <section className="dialog" role="dialog" aria-modal="true" aria-labelledby={`dlg-${page}`} data-apex-page={page}>
        <div className="dialog-header">
          <h1 id={`dlg-${page}`}>{title}</h1>
          <Link href={closeHref} aria-label="Close">✕</Link>
        </div>
        {children}
      </section>
    </div>
  );
}
