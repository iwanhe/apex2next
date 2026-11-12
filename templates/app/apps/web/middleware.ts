import { NextResponse, type NextRequest } from 'next/server';

/** Every page except the login page requires a session cookie (the API validates the token itself). */
export function middleware(req: NextRequest) {
  if (!req.cookies.get('a2n_session')) {
    const url = req.nextUrl.clone();
    url.pathname = '/login';
    url.search = '';
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = { matcher: ['/((?!login|_next/|favicon.ico|icon.svg).*)'] };
