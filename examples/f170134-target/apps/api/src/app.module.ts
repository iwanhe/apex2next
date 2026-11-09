import { Module } from '@nestjs/common';
import { BusinessModule } from './business/business.module';
import { DatabaseModule } from './database/database.module';
import { HealthController } from './health.controller';

@Module({ imports: [DatabaseModule, BusinessModule], controllers: [HealthController] })
export class AppModule {}
