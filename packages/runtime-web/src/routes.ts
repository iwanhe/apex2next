/** URL helpers of the target pages (search parameters, query strings, safe return targets). */
export type SearchParams = Record<string, string | string[] | undefined>;

export function first(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

export function all(v: string | string[] | undefined): string[] {
  return v === undefined ? [] : Array.isArray(v) ? v : [v];
}

/** Query string from params (undefined/empty dropped), used for sort/pagination/facet links. */
export function qs(params: Record<string, string | string[] | undefined | null>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue;
    for (const x of Array.isArray(v) ? v : [v]) sp.append(k, x);
  }
  const s = sp.toString();
  return s ? `?${s}` : '';
}

/** Only same-site relative paths are accepted as dialog return targets. */
export function safeReturn(v: string | undefined, fallback: string): string {
  return v && v.startsWith('/') && !v.startsWith('//') ? v : fallback;
}
