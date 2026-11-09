import { Module } from '@nestjs/common';
import { APP_FILTER } from '@nestjs/core';
import { AuthModule } from './auth/auth.module';
import { BusinessModule } from './business/business.module';
import { DatabaseModule } from './database/database.module';
import { HealthController } from './health.controller';
import { ApiErrorFilter } from './http/error.filter';
import { PagesModule } from './pages/pages.module';

@Module({
  imports: [DatabaseModule, AuthModule, BusinessModule, PagesModule],
  controllers: [HealthController],
  providers: [{ provide: APP_FILTER, useClass: ApiErrorFilter }],
})
export class AppModule {}
