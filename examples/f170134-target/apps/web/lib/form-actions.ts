'use server';
import { redirect } from 'next/navigation';
import { ApiError, apiSend, displayError, type FieldError } from './api';
import { safeReturn } from './routes';

/** Serializable description of one APEX form dialog, bound to the server action by the page. */
export interface FormBinding {
  /** API form name: request, requestLine, department, item, userRole, docType, approval. */
  readonly form: string;
  readonly id: string | null;
  readonly returnTo: string;
  /** Columns posted for this render (read-only items are not submitted, like APEX). */
  readonly columns: string[];
}

export interface FormState {
  readonly error: string | null;
  readonly fieldErrors: FieldError[];
  readonly values: Record<string, string> | null;
  readonly version: number;
}

const PATHS: Record<string, (b: FormBinding) => { method: 'POST' | 'PUT' | 'DELETE'; path: string } | null> = {
  CREATE: (b) => ({ method: 'POST', path: `/forms/${b.form}` }),
  SAVE: (b) => (b.id ? { method: 'PUT', path: `/forms/${b.form}/${encodeURIComponent(b.id)}` } : null),
  DELETE: (b) => (b.id ? { method: 'DELETE', path: `/forms/${b.form}/${encodeURIComponent(b.id)}` } : null),
  SUBMIT: (b) => (b.id && b.form === 'request' ? { method: 'POST', path: `/forms/request/${encodeURIComponent(b.id)}/submit` } : null),
  APPROVE: (b) => (b.id && b.form === 'approval' ? { method: 'POST', path: `/forms/approval/${encodeURIComponent(b.id)}/approve` } : null),
  REJECT: (b) => (b.id && b.form === 'approval' ? { method: 'POST', path: `/forms/approval/${encodeURIComponent(b.id)}/reject` } : null),
};

/** Page submit: the pressed button is the APEX REQUEST; validations and DML run in the API. */
export async function submitApexForm(binding: FormBinding, prev: FormState, form: FormData): Promise<FormState> {
  const request = String(form.get('request') ?? '');
  const target = PATHS[request]?.(binding);
  const values: Record<string, string> = {};
  for (const c of binding.columns) values[c] = String(form.get(c) ?? '');
  if (!target) return { error: `Unknown request ${request}`, fieldErrors: [], values, version: prev.version + 1 };
  const body = binding.form === 'approval'
    ? { note: values.note ?? '' }
    : { checksum: String(form.get('checksum') ?? '') || undefined, values: request === 'DELETE' ? undefined : values };
  let keys: string[] = [];
  try {
    const r = await apiSend<{ messageKeys?: string[] }>(target.method, target.path, body);
    keys = r.messageKeys ?? [];
  } catch (e) {
    if (e instanceof ApiError) {
      if (e.status === 401) redirect('/login');
      return { error: e.body.fieldErrors?.length ? null : displayError(e.body), fieldErrors: e.body.fieldErrors ?? [], values, version: prev.version + 1 };
    }
    throw e;
  }
  const back = safeReturn(binding.returnTo, '/');
  // Success message keys (DML:* / page:PROCESS) travel in the URL; the text is resolved from the UI spec.
  redirect(keys.length ? `${back}${back.includes('?') ? '&' : '?'}msg=${encodeURIComponent(keys.join(','))}` : back);
}
