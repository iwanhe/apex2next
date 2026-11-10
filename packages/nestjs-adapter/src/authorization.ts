import 'reflect-metadata';
import {
  CanActivate,
  ExecutionContext,
  ForbiddenException,
  Inject,
  Injectable,
  SetMetadata,
  UnauthorizedException,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import {
  isRuntimeAuthorized,
  type AuthorizationPolicy,
  type RuntimePrincipal,
} from '@apex2next/shared-runtime';

export const RUNTIME_POLICY_KEY = 'apex2next:runtime-policy';
export const RUNTIME_PUBLIC_KEY = 'apex2next:runtime-public';
export const RUNTIME_POLICY_RESOLVER = Symbol('RUNTIME_POLICY_RESOLVER');

export interface RuntimePolicyResolver {
  resolve(policyId: string): Promise<AuthorizationPolicy | null>;
}

/** Mark a controller or handler as requiring a named, centrally resolved runtime policy. */
export const RequireRuntimePolicy = (policyId: string) => SetMetadata(RUNTIME_POLICY_KEY, policyId);

/** Public routes must be explicit; routes with no policy metadata are denied by the guard. */
export const PublicRuntimeRoute = () => SetMetadata(RUNTIME_PUBLIC_KEY, true);

function asPrincipal(value: unknown): RuntimePrincipal | null {
  if (!value || typeof value !== 'object') return null;
  const candidate = value as Partial<RuntimePrincipal>;
  if (typeof candidate.subject !== 'string' || !Array.isArray(candidate.roles)
    || typeof candidate.authenticated !== 'boolean'
    || !candidate.roles.every((role) => typeof role === 'string')) return null;
  return {
    subject: candidate.subject,
    roles: candidate.roles,
    authenticated: candidate.authenticated,
    ...(candidate.attributes ? { attributes: candidate.attributes } : {}),
  };
}

@Injectable()
export class RuntimePolicyGuard implements CanActivate {
  constructor(
    private readonly reflector: Reflector,
    @Inject(RUNTIME_POLICY_RESOLVER) private readonly policies: RuntimePolicyResolver,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const targets = [context.getHandler(), context.getClass()];
    const isPublic = this.reflector.getAllAndOverride<boolean>(RUNTIME_PUBLIC_KEY, targets);
    if (isPublic === true) return true;

    const policyId = this.reflector.getAllAndOverride<string>(RUNTIME_POLICY_KEY, targets);
    if (!policyId || !policyId.trim()) {
      throw new ForbiddenException({ code: 'RUNTIME_POLICY_REQUIRED', message: 'Runtime authorization policy is required.' });
    }

    const request = context.switchToHttp().getRequest<{ user?: unknown }>();
    const principal = asPrincipal(request.user);
    if (!principal?.authenticated) {
      throw new UnauthorizedException({ code: 'UNAUTHENTICATED', message: 'Authentication is required.' });
    }

    const policy = await this.policies.resolve(policyId);
    if (!policy || !isRuntimeAuthorized(principal, policy)) {
      throw new ForbiddenException({ code: 'FORBIDDEN', message: policy?.message ?? 'Access denied.' });
    }
    return true;
  }
}
