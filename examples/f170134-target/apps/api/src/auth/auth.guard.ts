import { CanActivate, ExecutionContext, Inject, Injectable, SetMetadata, createParamDecorator } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import type { Request } from 'express';
import { Principal, principal } from '../business/context';
import { errors } from '../business/errors';
import { AUTH_CONFIG } from './auth.tokens';
import type { AuthConfig } from './auth.config';
import { verifySession } from './session-token';

const PUBLIC = 'apex2next:public';
/** Marks a route as reachable without a session (APEX public pages: login, health). */
export const Public = () => SetMetadata(PUBLIC, true);

type AuthedRequest = Request & { principal?: Principal };

/** Global guard: every route requires a valid session token unless marked @Public() (fail closed). */
@Injectable()
export class SessionGuard implements CanActivate {
  constructor(private readonly reflector: Reflector, @Inject(AUTH_CONFIG) private readonly config: AuthConfig) {}

  canActivate(context: ExecutionContext): boolean {
    if (this.reflector.getAllAndOverride<boolean>(PUBLIC, [context.getHandler(), context.getClass()])) return true;
    const req = context.switchToHttp().getRequest<AuthedRequest>();
    const header = req.headers.authorization ?? '';
    const token = header.startsWith('Bearer ') ? header.slice(7) : null;
    const session = verifySession(this.config.sessionSecret, token);
    if (!session) throw errors.unauthenticated();
    req.principal = principal(session.sub);
    return true;
  }
}

/** The verified principal of the request (replaces :APP_USER). */
export const Actor = createParamDecorator((_: unknown, context: ExecutionContext): Principal => {
  const req = context.switchToHttp().getRequest<AuthedRequest>();
  if (!req.principal) throw errors.unauthenticated();
  return req.principal;
});
