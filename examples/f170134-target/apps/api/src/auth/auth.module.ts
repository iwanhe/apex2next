import { Module } from '@nestjs/common';
import { APP_GUARD } from '@nestjs/core';
import { authConfigFromEnv } from './auth.config';
import { AuthController } from './auth.controller';
import { SessionGuard } from './auth.guard';
import { AUTH_CONFIG } from './auth.tokens';

@Module({
  controllers: [AuthController],
  providers: [
    { provide: AUTH_CONFIG, useFactory: () => authConfigFromEnv() },
    { provide: APP_GUARD, useClass: SessionGuard },
  ],
  exports: [AUTH_CONFIG],
})
export class AuthModule {}
