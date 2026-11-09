/**
 * Oracle/APEX display formats of the source application (language en, NLS AMERICAN):
 * application date format DD-MON-YYYY and number format masks such as 999G999G999G999G990.
 */
const MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];

/** "2026-11-09" or "2026-11-09 03:04:05" -> "09-NOV-2026". */
export function formatDate(value: string | null | undefined): string {
  if (!value) return '';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!m) return value;
  return `${m[3]}-${MONTHS[Number(m[2]) - 1]}-${m[1]}`;
}

/** TO_CHAR(n, mask) for the masks used by the application (G = ',', D = '.'). */
export function formatNumber(value: string | null | undefined, mask?: string | null): string {
  if (value === null || value === undefined || value === '') return '';
  if (!mask) return value;
  const decimals = mask.includes('D') ? mask.split('D')[1].length : 0;
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  const fixed = Math.abs(n).toFixed(decimals);
  const [int, frac] = fixed.split('.');
  const grouped = mask.includes('G') ? int.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : int;
  const width = mask.length + 1;
  const out = `${n < 0 ? '-' : ''}${grouped}${frac !== undefined ? `.${frac}` : ''}`;
  if (out.length > width) return '#'.repeat(width); // Oracle overflow
  return out;
}

export function formatValue(value: string | null | undefined, type: string, mask?: string | null): string {
  if (type === 'DATE') return formatDate(value);
  if (type === 'NUMBER') return formatNumber(value, mask);
  return value ?? '';
}

/** APEX IR "Rows x - y of z" pagination label. */
export function rowRange(page: number, size: number, shown: number, total: number): string {
  if (total === 0) return '';
  const from = (page - 1) * size + 1;
  return `${from} - ${from + shown - 1} of ${total}`;
}
