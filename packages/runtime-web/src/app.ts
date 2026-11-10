import type { FormBinding, FormState } from './form-types';
import type { AppSpec } from './spec';

/**
 * What the shared components need from one application: its UI spec, the route of each APEX page and the
 * application's form submit server action (server actions live in the application, see form-actions.ts).
 */
export interface AppRuntime {
  readonly spec: AppSpec;
  readonly routes: Record<number, string>;
  readonly submit: (binding: FormBinding, prev: FormState, form: FormData) => Promise<FormState>;
}
