import type { ReactNode } from 'react';
import { Shell } from '../../components/Shell';
import { apiGet, type Session } from '../../lib/api';
import { APP } from '../../lib/spec';

export const dynamic = 'force-dynamic';

/** Authenticated application shell; the application authorization scheme (APP_USERS) gates every page. */
export default async function AppLayout({ children }: { children: ReactNode }) {
  const session = await apiGet<Session>('/session');
  if (session.appAccessDenied) {
    return (
      <div className="login">
        <div className="panel denied">
          <h1>{APP.name}</h1>
          <div className="alert alert-error" role="alert" data-error-code="FORBIDDEN">{session.appAccessDenied}</div>
          <form action="/logout" method="post"><button className="btn" type="submit">Sign Out</button></form>
        </div>
      </div>
    );
  }
  return <Shell session={session}>{children}</Shell>;
}
