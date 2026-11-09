import 'server-only';
import { cookies } from 'next/headers';

/** httpOnly cookie holding the API session token (never readable by browser scripts). */
export const SESSION_COOKIE = 'a2n_session';
export const USERNAME_COOKIE = 'a2n_login_username';

export async function sessionToken(): Promise<string | null> {
  return (await cookies()).get(SESSION_COOKIE)?.value ?? null;
}

export async function setSession(token: string, maxAge: number) {
  (await cookies()).set(SESSION_COOKIE, token, {
    httpOnly: true, sameSite: 'lax', secure: process.env.NODE_ENV === 'production', path: '/', maxAge,
  });
}

export async function clearSession() {
  (await cookies()).delete(SESSION_COOKIE);
}
