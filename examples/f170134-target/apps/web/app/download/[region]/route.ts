import { type NextRequest } from 'next/server';
import { ApiError, apiGet, type ReportResult } from '../../../lib/api';
import { formatValue } from '../../../lib/format';
import { visibleColumns } from '../../../components/ReportTable';

/** IR download (p_download_formats CSV:HTML:XLSX:PDF): every row of the filtered report, visible columns, formatted. */
const ALLOWED = new Set(['approvalInbox', 'departments', 'requestLines', 'requestSummary', 'userRoles', 'docTypes']);

const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!));

export async function GET(req: NextRequest, ctx: { params: Promise<{ region: string }> }) {
  const { region } = await ctx.params;
  if (!ALLOWED.has(region)) return new Response('Not found', { status: 404 });
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
    const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${esc(region)}</title></head><body><table border="1"><tr>${
      cols.map((c) => `<th>${esc(c.label ?? c.name)}</th>`).join('')}</tr>${
      rows.map((r) => `<tr>${r.map((v) => `<td>${esc(v)}</td>`).join('')}</tr>`).join('')}</table></body></html>`;
    return new Response(html, { headers: { 'content-type': 'text/html; charset=utf-8', 'content-disposition': `attachment; filename="${region}.html"` } });
  }
  const cell = (v: string) => (/[",\n\r]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
  const csv = [cols.map((c) => cell(c.label ?? c.name)), ...rows.map((r) => r.map(cell))].map((r) => r.join(',')).join('\r\n');
  return new Response(`﻿${csv}\r\n`, { headers: { 'content-type': 'text/csv; charset=utf-8', 'content-disposition': `attachment; filename="${region}.csv"` } });
}
