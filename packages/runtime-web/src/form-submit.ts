import 'server-only';
import { redirect } from 'next/navigation';
import { ApiError, apiSend, displayError } from './api';
import type { FormBinding, FormState } from './form-types';
import { safeReturn } from './routes';

/**
 * Page submit of an APEX form (the pressed button is the APEX REQUEST; validations and DML run in the API).
 * Plain function: the application wraps it in its own 'use server' module and passes that action to the forms.
 */
/** Where one APEX request (button name) goes in the API, and an optional request body builder. */
export interface RequestTarget {
  readonly method: 'POST' | 'PUT' | 'DELETE';
  readonly path: string;
  readonly body?: (values: Record<string, string>) => unknown;
}
export type RequestRoutes = Record<string, (b: FormBinding) => RequestTarget | null>;

/** Native form DML requests (NATIVE_FORM_DML): CREATE, SAVE, DELETE on /forms/<form>[/<id>]. */
export const DML_REQUESTS: RequestRoutes = {
  CREATE: (b) => ({ method: 'POST', path: `/forms/${b.form}` }),
  SAVE: (b) => (b.id ? { method: 'PUT', path: `/forms/${b.form}/${encodeURIComponent(b.id)}` } : null),
  DELETE: (b) => (b.id ? { method: 'DELETE', path: `/forms/${b.form}/${encodeURIComponent(b.id)}` } : null),
};

/**
 * Page submit: the pressed button is the APEX REQUEST; validations and DML run in the API.
 * `requests` adds the application's own requests (process buttons such as SUBMIT or APPROVE) to DML_REQUESTS.
 */
export async function submitApexForm(requests: RequestRoutes, binding: FormBinding, prev: FormState, form: FormData): Promise<FormState> {
  const request = String(form.get('request') ?? '');
  const target = ({ ...DML_REQUESTS, ...requests })[request]?.(binding);
  const values: Record<string, string> = {};
  for (const c of binding.columns) values[c] = String(form.get(c) ?? '');
  if (!target) return { error: `Unknown request ${request}`, fieldErrors: [], values, version: prev.version + 1 };
  const body = target.body
    ? target.body(values)
    : { checksum: String(form.get('checksum') ?? '') || undefined, values: request === 'DELETE' ? undefined : values };
  let keys: string[] = [];
  try {
    const r = await apiSend<{ messageKeys?: string[] }>(target.method, target.path, body);
    keys = r.messageKeys ?? [];
  } catch (e) {
    if (e instanceof ApiError) {
      if (e.status === 401) redirect('/login');
      if (e.body.code === 'PASSWORD_CHANGE_REQUIRED') redirect('/account/password');
      return { error: e.body.fieldErrors?.length ? null : displayError(e.body), fieldErrors: e.body.fieldErrors ?? [], values, version: prev.version + 1 };
    }
    throw e;
  }
  const back = safeReturn(binding.returnTo, '/');
  // Success message keys (DML:* / page:PROCESS) travel in the URL; the text is resolved from the UI spec.
  redirect(keys.length ? `${back}${back.includes('?') ? '&' : '?'}msg=${encodeURIComponent(keys.join(','))}` : back);
}
