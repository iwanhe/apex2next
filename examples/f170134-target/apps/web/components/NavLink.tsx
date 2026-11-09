'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';

/** Navigation entry; the current entry is the longest menu path that matches the location. */
export function NavLink({ href, all, children }: { href: string; all: string[]; children: ReactNode }) {
  const path = usePathname();
  const matches = (h: string) => (h === '/' ? path === '/' : path === h || path.startsWith(`${h}/`));
  const best = all.filter(matches).sort((a, b) => b.length - a.length)[0];
  return <Link href={href} aria-current={best === href ? 'page' : undefined}>{children}</Link>;
}
