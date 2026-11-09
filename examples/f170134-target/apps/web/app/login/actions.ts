'use server';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { ApiError, apiSend } from '../../lib/api';
import { USERNAME_COOKIE, setSession } from '../../lib/session';

export interface LoginState { error: string | null; username: string }

/** Page 9999 processes: Set Username Cookie, Login (apex_authentication.login), then the home page. */
export async function login(_: LoginState, form: FormData): Promise<LoginState> {
  const username = String(form.get('username') ?? '');
  const password = String(form.get('password') ?? '');
  try {
    const r = await apiSend<{ token: string; expiresIn: number }>('POST', '/auth/login', { username, password }, null);
    await setSession(r.token, r.expiresIn);
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return { error: e.body.message, username };
    throw e;
  }
  const jar = await cookies();
  if (form.get('remember') === 'Y') {
    jar.set(USERNAME_COOKIE, username, { httpOnly: true, sameSite: 'lax', secure: process.env.NODE_ENV === 'production', path: '/', maxAge: 30 * 86400 });
  } else {
    jar.delete(USERNAME_COOKIE);
  }
  redirect('/');
}
