'use server';
import { submitApexForm as submit, type RequestRoutes } from '@apex2next/runtime-web/form-submit';
import type { FormBinding, FormState } from '@apex2next/runtime-web/form-types';

/**
 * Process buttons of this application besides the native form DML (CREATE/SAVE/DELETE).
 * Add one entry per converted process button, e.g.
 *   APPROVE: (b) => (b.id && b.form === 'approval' ? { method: 'POST', path: `/forms/approval/${b.id}/approve` } : null),
 */
const REQUESTS: RequestRoutes = {};

/** Form submit server action of this application (AppRuntime.submit). */
export async function submitApexForm(binding: FormBinding, prev: FormState, form: FormData): Promise<FormState> {
  return submit(REQUESTS, binding, prev, form);
}
