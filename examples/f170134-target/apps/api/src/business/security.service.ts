import { Injectable } from '@nestjs/common';
import { BusinessTx } from './context';
import { errors } from './errors';

/**
 * Replaces APX_DEMO_SEC_PKG (install.sql lines 171-316). Role checks are delegated to the reviewed SQL
 * functions in 0002_wp94_business_functions.sql so that API checks and SQL views
 * (app.can_act_yn) share a single implementation.
 */
export type AuthorizationScheme = 'ADMIN_RIGHTS' | 'APP_USERS' | 'MASTER_DATA' | 'REQUESTER' | 'WAREHOUSE';

/** APEX authorization schemes (shared_components/security/authorizations/*.sql) with their messages. */
export const AUTHORIZATION_SCHEMES: Record<AuthorizationScheme, { roles: string[] | 'ANY'; message: string }> = {
  ADMIN_RIGHTS: { roles: ['ADMIN'], message: 'Akses ditolak: hanya untuk role ADMIN.' },
  APP_USERS: {
    roles: 'ANY',
    message: 'Akses ditolak: akun {APP_USER} belum punya role di aplikasi ini. Admin mendaftarkannya di '
      + 'Administration > Users & Roles (atau tabel ..._USER_ROLES).',
  },
  MASTER_DATA: { roles: ['WAREHOUSE'], message: 'Akses ditolak: hanya untuk role WAREHOUSE.' },
  REQUESTER: { roles: ['REQUESTER', 'MANAGER'], message: 'Akses ditolak: hanya untuk role REQUESTER/MANAGER.' },
  WAREHOUSE: { roles: ['WAREHOUSE'], message: 'Akses ditolak: hanya untuk role WAREHOUSE.' },
};

@Injectable()
export class SecurityService {
  /** BR-SEC-02: role or ADMIN; no bootstrap mode (DEV-01). */
  async hasRole(tx: BusinessTx, role: string, username?: string): Promise<boolean> {
    const result = await tx.query<{ ok: boolean }>('SELECT app.has_role($1, $2) AS ok', [role, username ?? null]);
    return result.rows[0].ok;
  }

  /** BR-SEC-04: registered with at least one role. */
  async hasAnyRole(tx: BusinessTx, username?: string): Promise<boolean> {
    const result = await tx.query<{ ok: boolean }>('SELECT app.has_any_role($1) AS ok', [username ?? null]);
    return result.rows[0].ok;
  }

  /** BR-SEC-05: evaluate an APEX authorization scheme for the transaction principal. */
  async isAuthorized(tx: BusinessTx, scheme: AuthorizationScheme): Promise<boolean> {
    const def = AUTHORIZATION_SCHEMES[scheme];
    if (def.roles === 'ANY') return this.hasAnyRole(tx);
    for (const role of def.roles) {
      if (await this.hasRole(tx, role)) return true;
    }
    return false;
  }

  async authorize(tx: BusinessTx, scheme: AuthorizationScheme): Promise<void> {
    if (!(await this.isAuthorized(tx, scheme))) {
      throw errors.forbidden(AUTHORIZATION_SCHEMES[scheme].message.replace('{APP_USER}', tx.principal.username));
    }
  }
}
