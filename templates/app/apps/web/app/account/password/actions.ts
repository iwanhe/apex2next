'use server';
import { redirect } from 'next/navigation';
import { ApiError, apiSend, type FieldError } from '../../../lib/api';
import { setSession } from '../../../lib/session';

export interface PasswordState { errors: FieldError[] }

/** Change password (WP9-009 local accounts). The API returns a new session; every older one is revoked. */
export async function changePassword(_: PasswordState, form: FormData): Promise<PasswordState> {
  const body = { current: String(form.get('current') ?? ''), next: String(form.get('next') ?? ''), confirm: String(form.get('confirm') ?? '') };
  try {
    const r = await apiSend<{ token: string; expiresIn: number }>('POST', '/auth/password', body);
    await setSession(r.token, r.expiresIn);
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) redirect('/login');
    if (e instanceof ApiError && e.body.fieldErrors?.length) return { errors: e.body.fieldErrors };
    if (e instanceof ApiError) return { errors: [{ field: null, message: e.body.message }] };
    throw e;
  }
  redirect('/');
}
