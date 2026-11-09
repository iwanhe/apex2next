'use client';
import { useRef } from 'react';

export interface FacetView {
  item: string;
  label: string;
  values: { value: string; display: string; count: number }[];
  selected: string[];
}

/**
 * Faceted search region: search facet + checkbox facets with counts (p_fc_show_counts), zero counts hidden,
 * ordered by count; first 7 entries then "Show more" (p_fc_show_more_count=7). Changes submit the GET form.
 */
export function Facets({ basePath, searchItem, searchLabel, q, facets }: {
  basePath: string; searchItem: string; searchLabel: string; q?: string; facets: FacetView[];
}) {
  const form = useRef<HTMLFormElement>(null);
  const submit = () => form.current?.requestSubmit();
  return (
    <form ref={form} action={basePath} method="get" aria-label="Filter">
      <div className="facet">
        <h3><label htmlFor={searchItem}>{searchLabel}</label></h3>
        <input id={searchItem} type="search" name="q" defaultValue={q ?? ''} style={{ width: '100%' }} />
      </div>
      {facets.map((f) => {
        const selected = new Set(f.selected);
        const visible = f.values.filter((v) => v.count > 0 || selected.has(v.value));
        return (
          <fieldset className="facet" key={f.item} style={{ border: 0, padding: 0 }}>
            <h3><legend>{f.label}</legend></h3>
            {visible.map((v, i) => {
              const row = (
                <label key={v.value}>
                  <input type="checkbox" name="facet" value={`${f.item}:${v.value}`} defaultChecked={selected.has(v.value)} onChange={submit} />
                  {v.display}<span className="count">{v.count}</span>
                </label>
              );
              return i < 7 ? row : null;
            })}
            {visible.length > 7 && (
              <details>
                <summary>Show more</summary>
                {visible.slice(7).map((v) => (
                  <label key={v.value}>
                    <input type="checkbox" name="facet" value={`${f.item}:${v.value}`} defaultChecked={selected.has(v.value)} onChange={submit} />
                    {v.display}<span className="count">{v.count}</span>
                  </label>
                ))}
              </details>
            )}
          </fieldset>
        );
      })}
      <noscript><button className="btn" type="submit">Apply</button></noscript>
    </form>
  );
}
