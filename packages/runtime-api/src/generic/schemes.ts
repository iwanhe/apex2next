import type { BusinessTx } from '../context';

/**
 * Authorization schemes of a converted application (R4a). `apex2next generate` proposes a rule per scheme
 * when the export makes it unambiguous; the application may override any rule. A scheme without a rule
 * denies access: an unconverted check must never open a page.
 */
export type SchemeRule =
  | { readonly allow: true }
  /** APEX "is in role or group" (APEX ACL): roles of the signed-in account in iam.account_roles. */
  | { readonly roles: readonly string[] }
  /** "Rows returned" / "No rows returned": translated SQL; its only possible bind is APP_USER ($1). */
  | { readonly exists: string; readonly negate?: boolean; readonly appUser?: boolean };

export interface SchemeDef {
  readonly name: string;
  readonly errorMessage: string | null;
  readonly rule: SchemeRule | null;
}

export async function evaluateScheme(tx: BusinessTx, def: SchemeDef | undefined): Promise<boolean> {
  const rule = def?.rule;
  if (!rule) return false;
  if ('allow' in rule) return true;
  if ('roles' in rule) {
    const r = await tx.query<{ ok: boolean }>(
      'SELECT EXISTS (SELECT 1 FROM iam.account_roles WHERE username = $1 AND role = ANY($2::text[])) AS ok',
      [tx.principal.username, rule.roles]);
    return r.rows[0].ok;
  }
  const r = await tx.query(rule.exists, rule.appUser ? [tx.principal.username] : []);
  return (r.rowCount ?? 0) > 0 !== (rule.negate === true);
}

/** Message APEX shows when a scheme fails (its error message, or the APEX default). */
export function schemeMessage(def: SchemeDef | undefined, name: string): string {
  return def?.errorMessage ?? `Access denied by authorization scheme ${name}.`;
}
