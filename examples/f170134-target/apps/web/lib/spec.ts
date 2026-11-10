import { createAppSpec } from '@apex2next/runtime-web/spec';
import { UI_SPEC } from './ui-spec.generated';

/** This application's UI spec, bound to the accessors of @apex2next/runtime-web (roadmap R2). */
export const SPEC = createAppSpec(UI_SPEC);
export const { APP, APP_TITLE, NAVIGATION, BREADCRUMBS, page, item, button, staticLov, lovDisplay, processMessage, pageTitle } = SPEC;
export { DELETE_CONFIRM, DML_MESSAGES } from '@apex2next/runtime-web/spec';
