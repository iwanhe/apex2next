import Link from 'next/link';
import { ErrorRegion, SuccessMessage } from '../../../../components/Alerts';
import { PageHeader } from '../../../../components/PageHeader';
import { ReportTable, visibleColumns } from '../../../../components/ReportTable';
import { apiGet, type ReportResult } from '../../../../lib/api';
import { formatValue } from '../../../../lib/format';
import { apiErrorOnly } from '../../../../lib/guard';
import { first, qs, type SearchParams } from '../../../../lib/routes';
import { page } from '../../../../lib/spec';

interface Detail {
  list: ReportResult;
  selected: Record<string, string | null> | null;
  headerColumns?: ReportResult['columns'];
  lines: ReportResult | null;
  buttons: { EDIT_HEADER: boolean; CREATE_REQUEST_LINES: boolean };
}

/**
 * Page 302 Detail Permintaan (only in the SQL export, see D-003): master list, header of the selected request
 * (P302_REQUEST_ID), its lines, EDIT_HEADER -> 301 and CREATE_REQUEST_LINES -> 311 while DRAFT/REJECTED.
 * Closing those dialogs returns here, which re-renders the regions (DA NATIVE_REFRESH).
 */
export default async function Page({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  const p = page(302);
  const id = first(sp.id);
  const listPage = first(sp.page);
  let d: Detail;
  try {
    d = await apiGet<Detail>(`/pages/302${qs({ requestId: id, page: listPage })}`);
  } catch (e) {
    return <><PageHeader page={302} title={p.title} /><ErrorRegion error={apiErrorOnly(e)} /></>;
  }
  const here = `/requests/detail${qs({ id, page: listPage })}`;
  const rr = p.reportRegion;
  return (
    <>
      <PageHeader page={302} title={p.title} />
      <SuccessMessage flash={first(sp.msg)} />
      <div className="master-detail">
        <section className="region" aria-label="Daftar Permintaan Barang">
          <h2>Daftar Permintaan Barang</h2>
          <ReportTable result={d.list} basePath="/requests/detail" params={{ id, page: listPage }}
            noData={rr['Daftar Permintaan Barang'].queryNoDataFound}
            columnLinks={{ request_no: (r) => `/requests/detail${qs({ id: r.request_id ?? undefined, page: listPage })}` }} testId="master-list" />
        </section>
        <div>
          {d.selected === null ? (
            <section className="region" aria-label="Belum dipilih" data-testid="not-selected">
              <p className="nodata" style={{ padding: 0 }}>Pilih Permintaan Barang di daftar kiri untuk melihat detailnya.</p>
            </section>
          ) : (
            <>
              <section className="region" aria-label="Permintaan Barang" data-testid="header">
                <div className="region-header">
                  <h2>Permintaan Barang</h2>
                  {d.buttons.EDIT_HEADER && <Link className="btn" href={`/requests/${id}?return=${encodeURIComponent(here)}`}>{p.button.EDIT_HEADER.buttonImageAlt}</Link>}
                </div>
                <dl style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: '6px 12px', margin: 0 }}>
                  {visibleColumns(d.headerColumns ?? []).map((c) => (
                    <div key={c.name} style={{ display: 'contents' }}>
                      <dt style={{ color: 'var(--muted)' }}>{c.label}</dt>
                      <dd style={{ margin: 0 }} data-testid={`header-${c.name}`}>{formatValue(d.selected![c.name], c.type, c.format)}</dd>
                    </div>
                  ))}
                </dl>
              </section>
              <section className="region" aria-label="Baris Permintaan">
                <div className="region-header">
                  <h2>Baris Permintaan</h2>
                  {d.buttons.CREATE_REQUEST_LINES && (
                    <Link className="btn btn-hot" href={`/request-lines/new${qs({ request_id: id, return: here })}`}>{p.button.CREATE_REQUEST_LINES.buttonImageAlt}</Link>
                  )}
                </div>
                {d.lines && <ReportTable result={d.lines} basePath="/requests/detail" params={{ id }} noData={rr['Baris Permintaan'].queryNoDataFound}
                  columnLinks={{ item_id_dsp: (r) => `/request-lines/${r.line_id}?return=${encodeURIComponent(here)}` }} testId="detail-lines" />}
              </section>
            </>
          )}
        </div>
      </div>
    </>
  );
}

