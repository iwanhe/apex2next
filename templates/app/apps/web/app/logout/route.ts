import { NextResponse, type NextRequest } from 'next/server';
import { apiSend } from '../../lib/api';
import { SESSION_COOKIE } from '../../lib/session';

/**
 * Navigation bar "Sign Out": ends the session and returns to the login page. POST only (no CSRF via GET).
 * Local accounts: the API revokes the session server-side as well, so a copied token stops working.
 */
export async function POST(req: NextRequest) {
  const token = req.cookies.get(SESSION_COOKIE)?.value;
  if (token) {
    try {
      await apiSend('POST', '/auth/logout', {}, token);
    } catch {
      // expired or already revoked: nothing to end on the server
    }
  }
  const res = NextResponse.redirect(new URL('/login', req.url), 303);
  res.cookies.delete(SESSION_COOKIE);
  return res;
}
