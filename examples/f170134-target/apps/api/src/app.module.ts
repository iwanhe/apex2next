import { Module } from '@nestjs/common';
import { APP_FILTER } from '@nestjs/core';
import { ApiErrorFilter, AuthModule, DatabaseModule } from '@apex2next/runtime-api';
import { BusinessModule } from './business/business.module';
import { HealthController } from './health.controller';
import { PagesModule } from './pages/pages.module';

@Module({
  imports: [DatabaseModule, AuthModule, BusinessModule, PagesModule],
  controllers: [HealthController],
  // Oracle-style constraint messages name the parsing schema of the source application (WP9.6: WKSP_KCSI).
  providers: [{ provide: APP_FILTER, useFactory: () => new ApiErrorFilter({ oracleSchema: process.env.DB_ERROR_SCHEMA ?? 'WKSP_KCSI' }) }],
})
export class AppModule {}
