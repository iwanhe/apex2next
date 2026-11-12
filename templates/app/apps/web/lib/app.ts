import type { AppRuntime } from '@apex2next/runtime-web/app';
import { submitApexForm } from './form-actions';
import { PAGE_ROUTES } from './routes';
import { SPEC } from './spec';

/** This application as seen by the shared components: UI spec, page routes and form submit action. */
export const APP: AppRuntime = { spec: SPEC, routes: PAGE_ROUTES, submit: submitApexForm };
