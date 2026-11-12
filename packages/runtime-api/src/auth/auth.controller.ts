import { Body, Controller, HttpCode, Inject, Post, Req } from '@nestjs/common';
import type { Request } from 'express';
import { createHash, timingSafeEqual } from 'node:crypto';
import { Principal, principal } from '../context';
import { BusinessRuleError } from '../errors';
import { AccountsService, INVALID_LOGIN } from './accounts.service';
import type { AuthConfig } from './auth.config';
import { Actor, AllowDuringPasswordChange, Public } from './auth.guard';
import { AUTH_CONFIG } from './auth.tokens';
import { RateLimiter } from './rate-limit';
import { signSession } from './session-token';

export { INVALID_LOGIN };

const digest = (s: string) => createHash('sha256').update(s, 'utf8').digest();
const str = (v: unknown, max = 256) => (typeof v === 'string' ? v.slice(0, max) : '');

/**
 * Page 9999 Login (process "Login": apex_authentication.login), Sign Out and change password.
 * AUTH_MODE=local: accounts in schema iam (WP9-009). AUTH_MODE=dev: shared DEV_LOGIN_PASSWORD, tests only.
 * APP_USER is the upper-cased username in both modes.
 */
@Controller('auth')
export class AuthController {
  private readonly limiter: RateLimiter;

  constructor(@Inject(AUTH_CONFIG) private readonly config: AuthConfig, private readonly accounts: AccountsService) {
    this.limiter = new RateLimiter(config.loginRatePerMinute);
  }

  @Public()
  @Post('login')
  @HttpCode(200)
  async login(@Body() body: { username?: unknown; password?: unknown }, @Req() req: Request) {
    if (this.config.mode === 'local' && !this.limiter.take(this.client(req))) {
      throw new BusinessRuleError('TOO_MANY_ATTEMPTS', 'Terlalu banyak percobaan login. Coba lagi dalam 1 menit.', null, 'BR-SEC-08');
    }
    const username = str(body?.username).trim().toUpperCase();
    const password = str(body?.password, 1024);
    if (this.config.mode === 'local') {
      const r = await this.accounts.login(username, password);
      return this.issue(r.username, r.sessionVersion, r.mustChangePassword);
    }
    const ok = timingSafeEqual(digest(password), digest(this.config.devPassword));
    if (!ok || !username) throw new BusinessRuleError('UNAUTHENTICATED', INVALID_LOGIN, null, 'BR-SEC-01');
    return this.issue(principal(username).username);
  }

  /** Change password (forced after a temporary password). Returns a new token; every older token is revoked. */
  @AllowDuringPasswordChange()
  @Post('password')
  @HttpCode(200)
  async password(@Actor() actor: Principal, @Body() body: { current?: unknown; next?: unknown; confirm?: unknown }) {
    if (this.config.mode !== 'local') {
      throw new BusinessRuleError('ACTION_NOT_AVAILABLE', 'Ganti password hanya untuk akun lokal (AUTH_MODE=local).', null, 'BR-SEC-07');
    }
    const r = await this.accounts.changePassword(actor.username, str(body?.current, 1024), str(body?.next, 1024), str(body?.confirm, 1024));
    return this.issue(r.username, r.sessionVersion, false);
  }

  /** Sign Out: local accounts revoke every token of the account. */
  @AllowDuringPasswordChange()
  @Post('logout')
  @HttpCode(204)
  async logout(@Actor() actor: Principal) {
    if (this.config.mode === 'local') await this.accounts.logout(actor.username);
  }

  private issue(username: string, ver?: number, pwc = false) {
    const token = signSession(this.config.sessionSecret, username, this.config.sessionTtlSeconds, undefined,
      ver === undefined ? {} : { ver, ...(pwc ? { pwc } : {}) });
    return { token, username, expiresIn: this.config.sessionTtlSeconds, mustChangePassword: pwc };
  }

  private client(req: Request): string {
    if (this.config.trustProxy) {
      const fwd = req.header('x-forwarded-for')?.split(',')[0]?.trim();
      if (fwd) return fwd;
    }
    return req.socket.remoteAddress ?? 'unknown';
  }
}
