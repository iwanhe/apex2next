import type { ReportResult } from './api';
import type { FacetView } from './components/Facets';
import { all } from './routes';
import type { AppSpec } from './spec';

/** Facet items of a page with counts from the API and selection from ?facet=ITEM:VALUE. */
export function facetViews(spec: AppSpec, pageId: number, result: ReportResult, facetParam: string | string[] | undefined): FacetView[] {
  const selected = all(facetParam);
  return result.facets.map((f) => {
    const def = spec.item(pageId, f.item);
    return {
      item: f.item, label: def.prompt,
      values: f.values.map((v) => ({ ...v, display: def.namedLov ? spec.lovDisplay(def.namedLov, v.value) : v.value })),
      selected: selected.filter((s) => s.startsWith(`${f.item}:`)).map((s) => s.slice(f.item.length + 1)),
    };
  });
}
