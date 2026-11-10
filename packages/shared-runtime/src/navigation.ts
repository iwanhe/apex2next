import type { AuthorizationPolicy, RuntimeNavigationEntry, RuntimePrincipal } from './contracts.js';
import { isRuntimeAuthorized } from './authorization.js';

/** Returns visible navigation entries in stable source order; protected entries fail closed. */
export function resolveRuntimeNavigation(
  entries: readonly RuntimeNavigationEntry[],
  principal: RuntimePrincipal | null | undefined,
  policies: ReadonlyMap<string, AuthorizationPolicy>,
): readonly RuntimeNavigationEntry[] {
  const ids = new Set<string>();
  for (const entry of entries) {
    if (!entry.id || ids.has(entry.id)) throw new Error('Navigation entry IDs must be non-empty and unique.');
    ids.add(entry.id);
    if (!Number.isSafeInteger(entry.sequence) || entry.sequence < 1) {
      throw new Error(`Navigation entry ${entry.id} has an invalid sequence.`);
    }
    if (!entry.href.startsWith('/') || entry.href.startsWith('//')) {
      throw new Error(`Navigation entry ${entry.id} must use an application-relative path.`);
    }
  }
  return entries
    .filter((entry) => {
      if (entry.public) return true;
      if (!entry.authorizationPolicyId) return false;
      const policy = policies.get(entry.authorizationPolicyId);
      return policy ? isRuntimeAuthorized(principal, policy) : false;
    })
    .sort((left, right) => left.sequence - right.sequence);
}
