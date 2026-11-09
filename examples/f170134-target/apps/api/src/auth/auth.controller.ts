import { Body, Controller, HttpCode, Inject, Post } from '@nestjs/common';
import { createHash, timingSafeEqual } from 'node:crypto';
import { principal } from '../business/context';
import { BusinessRuleError } from '../business/errors';
import type { AuthConfig } from './auth.config';
import { Public } from './auth.guard';
import { AUTH_CONFIG } from './auth.tokens';
import { signSession } from './session-token';

/** APEX login message for wrong credentials (Oracle APEX Accounts, language en). */
export const INVALID_LOGIN = 'Invalid Login Credentials';

const digest = (s: string) => createHash('sha256').update(s, 'utf8').digest();

/**
 * Page 9999 Login (process "Login": apex_authentication.login). AUTH_MODE=dev only: the username is
 * free, the password is the shared DEV_LOGIN_PASSWORD; APP_USER is the upper-cased username.
 */
@Controller('auth')
export class AuthController {
  constructor(@Inject(AUTH_CONFIG) private readonly config: AuthConfig) {}

  @Public()
  @Post('login')
  @HttpCode(200)
  login(@Body() body: { username?: unknown; password?: unknown }) {
    const username = typeof body?.username === 'string' ? body.username : '';
    const password = typeof body?.password === 'string' ? body.password : '';
    const ok = timingSafeEqual(digest(password), digest(this.config.devPassword));
    if (!ok || !username.trim()) {
      throw new BusinessRuleError('UNAUTHENTICATED', INVALID_LOGIN, null, 'BR-SEC-01');
    }
    const actor = principal(username);
    const token = signSession(this.config.sessionSecret, actor.username, this.config.sessionTtlSeconds);
    return { token, username: actor.username, expiresIn: this.config.sessionTtlSeconds };
  }
}
