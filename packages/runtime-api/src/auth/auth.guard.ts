import { CanActivate, ExecutionContext, Inject, Injectable, Optional, SetMetadata, createParamDecorator } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import type { Request } from 'express';
import { Principal, principal } from '../context';
import { BusinessRuleError, errors } from '../errors';
import { AccountsService } from './accounts.service';
import { AUTH_CONFIG } from './auth.tokens';
import type { AuthConfig } from './auth.config';
import { verifySession } from './session-token';

const PUBLIC = 'apex2next:public';
const DURING_PASSWORD_CHANGE = 'apex2next:password-change';
/** Marks a route as reachable without a session (APEX public pages: login, health). */
export const Public = () => SetMetadata(PUBLIC, true);
/** Marks a route as reachable while the account must still change its temporary password. */
export const AllowDuringPasswordChange = () => SetMetadata(DURING_PASSWORD_CHANGE, true);

type AuthedRequest = Request & { principal?: Principal; mustChangePassword?: boolean };

/**
 * Global guard: every route requires a valid session token unless marked @Public() (fail closed). For local accounts
 * the account must also still be active, unlocked and on the token's session version (revocation), and an account
 * with a temporary password may only reach the routes that let it change it.
 */
@Injectable()
export class SessionGuard implements CanActivate {
  constructor(private readonly reflector: Reflector, @Inject(AUTH_CONFIG) private readonly config: AuthConfig,
    @Optional() private readonly accounts?: AccountsService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const targets = [context.getHandler(), context.getClass()];
    if (this.reflector.getAllAndOverride<boolean>(PUBLIC, targets)) return true;
    const req = context.switchToHttp().getRequest<AuthedRequest>();
    const header = req.headers.authorization ?? '';
    const token = header.startsWith('Bearer ') ? header.slice(7) : null;
    const session = verifySession(this.config.sessionSecret, token, undefined,
      { maxLifetimeSeconds: this.config.sessionTtlSeconds });
    if (!session) throw errors.unauthenticated();
    if (this.config.mode === 'local') {
      if (!this.accounts || !(await this.accounts.sessionValid(session.sub, session.ver))) throw errors.unauthenticated();
      if (session.pwc && !this.reflector.getAllAndOverride<boolean>(DURING_PASSWORD_CHANGE, targets)) {
        throw new BusinessRuleError('PASSWORD_CHANGE_REQUIRED', 'Password sementara harus diganti terlebih dahulu.', null, 'BR-SEC-07');
      }
    }
    req.principal = principal(session.sub);
    req.mustChangePassword = session.pwc === true;
    return true;
  }
}

/** The verified principal of the request (replaces :APP_USER). */
export const Actor = createParamDecorator((_: unknown, context: ExecutionContext): Principal => {
  const req = context.switchToHttp().getRequest<AuthedRequest>();
  if (!req.principal) throw errors.unauthenticated();
  return req.principal;
});
