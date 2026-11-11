import { bindRegionSources } from '@apex2next/runtime-api';
import { UI_SPEC } from './ui-spec.generated';

/**
 * Region, LOV and form sources of this application. Since roadmap R3 they are generated from the APEX export
 * (app-sources.generated.ts, `apex2next generate`); the helpers come from @apex2next/runtime-api, bound to this
 * application's UI spec and target schema. test/ui-spec.test.js still proves each source against the inventory.
 */
export type { LovSource, RegionSource } from '@apex2next/runtime-api';
export { FORM_SOURCES, LOV_SOURCES, REGION_SOURCES } from './app-sources.generated';
export type { DynamicLov, FormName, RegionName } from './app-sources.generated';
export const { regionColumns, regionDefaultSort, reportDef, lovSql } = bindRegionSources(UI_SPEC, { schema: 'app' });
