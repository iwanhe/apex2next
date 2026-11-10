import 'server-only';
import { buttonAllowed as allowed } from '@apex2next/runtime-web/authz';
import { SPEC } from './spec';

export { getSession } from '@apex2next/runtime-web/authz';

/** Button authorization scheme of this application's spec (p_security_scheme). */
export const buttonAllowed = (pageId: number, button: string) => allowed(SPEC, pageId, button);
