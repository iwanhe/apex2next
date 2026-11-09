import { NextResponse, type NextRequest } from 'next/server';
import { SESSION_COOKIE } from '../../lib/session';

/** Navigation bar "Sign Out": ends the session and returns to the login page. POST only (no CSRF via GET). */
export async function POST(req: NextRequest) {
  const res = NextResponse.redirect(new URL('/login', req.url), 303);
  res.cookies.delete(SESSION_COOKIE);
  return res;
}
