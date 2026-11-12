'use server';
import { submitApexForm as submit, type RequestRoutes } from '@apex2next/runtime-web/form-submit';
import type { FormBinding, FormState } from '@apex2next/runtime-web/form-types';

/** Process buttons of this application besides the native form DML (CREATE/SAVE/DELETE). */
const REQUESTS: RequestRoutes = {
  SUBMIT: (b) => (b.id && b.form === 'request' ? { method: 'POST', path: `/forms/request/${encodeURIComponent(b.id)}/submit` } : null),
  APPROVE: (b) => (b.id && b.form === 'approval'
    ? { method: 'POST', path: `/forms/approval/${encodeURIComponent(b.id)}/approve`, body: (v) => ({ note: v.note ?? '' }) } : null),
  REJECT: (b) => (b.id && b.form === 'approval'
    ? { method: 'POST', path: `/forms/approval/${encodeURIComponent(b.id)}/reject`, body: (v) => ({ note: v.note ?? '' }) } : null),
};

/** Form submit server action of this application (AppRuntime.submit). */
export async function submitApexForm(binding: FormBinding, prev: FormState, form: FormData): Promise<FormState> {
  return submit(REQUESTS, binding, prev, form);
}
