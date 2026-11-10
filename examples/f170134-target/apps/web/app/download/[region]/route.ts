import { type NextRequest } from 'next/server';
import { ApiError, apiGet, type ReportResult } from '../../../lib/api';
import { formatValue } from '../../../lib/format';
import { visibleColumns } from '../../../components/ReportTable';

/** IR download (p_download_formats CSV:HTML:XLSX:PDF): every row of the filtered and sorted report, visible columns, formatted. */
/** Allowed regions and their IR region titles; APEX names the file after the region title (J-04). */
const TITLES: Record<string, string> = {
  approvalInbox: 'Approval Inbox', departments: 'Departments', requestLines: 'Baris Permintaan',
  requestSummary: 'Rekap Permintaan', userRoles: 'Users & Roles', docTypes: 'Document Types & Approval',
};

/** Content-Disposition as APEX sends it: plain filename plus RFC 5987 filename*. */
const disposition = (file: string) =>
  `attachment; filename="${file.replace(/["\\]/g, '_')}"; filename*=UTF-8''${encodeURIComponent(file)}`;

const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!));

export async function GET(req: NextRequest, ctx: { params: Promise<{ region: string }> }) {
  const { region } = await ctx.params;
  if (!Object.hasOwn(TITLES, region)) return new Response('Not found', { status: 404 });
  const sp = new URLSearchParams(req.nextUrl.searchParams);
  const format = sp.get('format') === 'html' ? 'html' : 'csv';
  sp.delete('format'); sp.delete('page'); sp.set('all', '1');
  let result: ReportResult;
  try {
    result = await apiGet<ReportResult>(`/regions/${region}?${sp.toString()}`);
  } catch (e) {
    if (e instanceof ApiError) return new Response(e.body.message, { status: e.status });
    throw e;
  }
  const cols = visibleColumns(result.columns);
  const rows = result.rows.map((r) => cols.map((c) => formatValue(r[c.name], c.type, c.format)));
  if (format === 'html') {
    const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${esc(TITLES[region])}</title></head><body><table border="1"><tr>${
      cols.map((c) => `<th>${esc(c.label ?? c.name)}</th>`).join('')}</tr>${
      rows.map((r) => `<tr>${r.map((v) => `<td>${esc(v)}</td>`).join('')}</tr>`).join('')}</table></body></html>`;
    return new Response(html, { headers: { 'content-type': 'text/html; charset=utf-8', 'content-disposition': disposition(`${TITLES[region]}.html`) } });
  }
  const cell = (v: string) => (/[",\n\r]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
  // As observed on APEX 26.2 (J-04): UTF-8 without BOM, LF line ends, header = column labels, formatted values.
  const csv = [cols.map((c) => cell(c.label ?? c.name)), ...rows.map((r) => r.map(cell))].map((r) => `${r.join(',')}\n`).join('');
  return new Response(csv, { headers: { 'content-type': 'text/csv; charset=UTF-8', 'content-disposition': disposition(`${TITLES[region]}.csv`) } });
}
