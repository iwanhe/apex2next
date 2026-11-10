// Binds a shared component of @apex2next/runtime-web to this application (roadmap R2).
import type { ReportResult } from '../lib/api';
import { facetViews as rt } from '@apex2next/runtime-web/facets-view';
import { SPEC } from '../lib/spec';

export const facetViews = (pageId: number, result: ReportResult, facetParam: string | string[] | undefined) =>
  rt(SPEC, pageId, result, facetParam);
