import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { APP, APP_TITLE } from '../lib/spec';
import './globals.css';

export const metadata: Metadata = { title: APP_TITLE ?? undefined };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang={APP.language}>
      <body>{children}</body>
    </html>
  );
}
