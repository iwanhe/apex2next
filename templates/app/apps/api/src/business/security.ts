import type { SchemeRule } from '@apex2next/runtime-api';

/**
 * Reviewed rules of the authorization schemes. A rule here replaces the rule `apex2next generate` proposed in
 * security-schemes.generated.ts; a scheme with no rule in either file denies access.
 *
 * Examples:
 *   'Administration Rights': { roles: ['ADMINISTRATOR'] },           // iam.account_roles (accounts.mjs grant)
 *   'Reader Rights': { allow: true },
 *   'Team Members': { exists: 'SELECT 1 FROM app.team WHERE upper(username) = $1', appUser: true },
 */
export const RULES: Record<string, SchemeRule> = {};
