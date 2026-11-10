import type { AuthorizationPolicy, RuntimePrincipal } from './contracts.js';

/** Fail-closed authorization evaluator. Missing policies and unauthenticated principals are denied. */
export function isRuntimeAuthorized(
  principal: RuntimePrincipal | null | undefined,
  policy: AuthorizationPolicy | null | undefined,
): boolean {
  if (!principal?.authenticated || !policy) return false;
  if (policy.mode === 'REGISTERED') return principal.roles.length > 0;
  if (policy.roles.length === 0) return false;
  const roles = new Set(principal.roles.map((role) => role.toUpperCase()));
  return policy.mode === 'ALL_ROLES'
    ? policy.roles.every((role) => roles.has(role.toUpperCase()))
    : policy.roles.some((role) => roles.has(role.toUpperCase()));
}
