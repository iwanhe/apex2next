import type { ReactNode } from 'react';
import type { Session } from '../lib/api';
import { APP_TITLE, NAVIGATION } from '../lib/spec';
import { PAGE_ROUTES } from '../lib/routes';
import { NavLink } from './NavLink';

/**
 * Universal Theme shell: navigation menu (shared component "Navigation Menu", entries filtered by their
 * authorization scheme) and navigation bar (&APP_USER., Sign Out).
 */
export function Shell({ session, children }: { session: Session; children: ReactNode }) {
  const allowed = (scheme: string | null) => !scheme || session.schemes[scheme] === true;
  const top = NAVIGATION.filter((n) => !n.parent && allowed(n.scheme));
  const children_ = (label: string) => NAVIGATION.filter((n) => n.parent === label && allowed(n.scheme));
  const hrefs = NAVIGATION.filter((n) => allowed(n.scheme)).map((n) => PAGE_ROUTES[n.page ?? 100] ?? '/');
  return (
    <div className="shell">
      <header className="topbar">
        <a className="app-name" href="/">{APP_TITLE}</a>
        <nav className="navbar" aria-label="Navigation bar">
          <span data-testid="app-user">{session.username}</span>
          {session.authMode === 'local' && <a className="linklike" href="/account/password">Ganti Password</a>}
          <form action="/logout" method="post">
            <button className="linklike" type="submit">Sign Out</button>
          </form>
        </nav>
      </header>
      <nav className="sidenav" aria-label="Navigation menu">
        <ul>
          {top.map((n) => {
            const kids = children_(n.label);
            return (
              <li key={n.label}>
                {kids.length ? <span>{n.label}</span> : <NavLink all={hrefs} href={PAGE_ROUTES[n.page ?? 100] ?? '/'}>{n.label}</NavLink>}
                {kids.length > 0 && (
                  <ul>
                    {kids.map((k) => (
                      <li key={k.label}><NavLink all={hrefs} href={PAGE_ROUTES[k.page ?? 100] ?? '/'}>{k.label}</NavLink></li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      </nav>
      <main>{children}</main>
    </div>
  );
}
