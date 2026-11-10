import 'server-only';
import { cache } from 'react';
import { apiGet, type Session } from './api';
import type { AppSpec } from './spec';

/** The session (user and evaluated authorization schemes), fetched once per request. */
export const getSession = cache(() => apiGet<Session>('/session'));

/**
 * Button authorization scheme (the button's p_security_scheme in the export, e.g. CREATE on page 200 only for
 * MASTER_DATA). A button without a scheme is always shown; the target page still enforces its own scheme.
 */
export async function buttonAllowed(spec: AppSpec, pageId: number, button: string): Promise<boolean> {
  const scheme = spec.page(pageId).button?.[button]?.securityScheme as string | undefined;
  if (!scheme) return true;
  return (await getSession()).schemes[scheme] === true;
}
