import type { ReportResult } from '../lib/api';
import { all } from '../lib/routes';
import { item, lovDisplay } from '../lib/spec';
import type { FacetView } from './Facets';

/** Facet items of a page with counts from the API and selection from ?facet=ITEM:VALUE. */
export function facetViews(pageId: number, result: ReportResult, facetParam: string | string[] | undefined): FacetView[] {
  const selected = all(facetParam);
  return result.facets.map((f) => {
    const spec = item(pageId, f.item);
    return {
      item: f.item, label: spec.prompt,
      values: f.values.map((v) => ({ ...v, display: spec.namedLov ? lovDisplay(spec.namedLov, v.value) : v.value })),
      selected: selected.filter((s) => s.startsWith(`${f.item}:`)).map((s) => s.slice(f.item.length + 1)),
    };
  });
}
