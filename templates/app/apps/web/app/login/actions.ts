'use server';
import { cookies, headers } from 'next/headers';
import { redirect } from 'next/navigation';
import { ApiError, apiSend } from '../../lib/api';
import { USERNAME_COOKIE, setSession } from '../../lib/session';

export interface LoginState { error: string | null; username: string }

/** Login page processes: Set Username Cookie, Login (apex_authentication.login), then the home page. */
export async function login(_: LoginState, form: FormData): Promise<LoginState> {
  const username = String(form.get('username') ?? '');
  const password = String(form.get('password') ?? '');
  // The API rate-limits logins per client; pass the browser's address on (honoured only with TRUST_PROXY=1, i.e. when
  // a trusted proxy such as Cloudflare Tunnel sets these headers; otherwise the API counts the web tier as one client).
  const h = await headers();
  const client = h.get('cf-connecting-ip') ?? h.get('x-forwarded-for')?.split(',')[0]?.trim() ?? h.get('x-real-ip');
  let mustChange = false;
  try {
    const r = await apiSend<{ token: string; expiresIn: number; mustChangePassword?: boolean }>(
      'POST', '/auth/login', { username, password }, null, client ? { 'x-forwarded-for': client } : undefined);
    await setSession(r.token, r.expiresIn);
    mustChange = r.mustChangePassword === true;
  } catch (e) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 429)) return { error: e.body.message, username };
    throw e;
  }
  const jar = await cookies();
  if (form.get('remember') === 'Y') {
    jar.set(USERNAME_COOKIE, username, { httpOnly: true, sameSite: 'lax', secure: process.env.NODE_ENV === 'production', path: '/', maxAge: 30 * 86400 });
  } else {
    jar.delete(USERNAME_COOKIE);
  }
  redirect(mustChange ? '/account/password' : '/');
}
