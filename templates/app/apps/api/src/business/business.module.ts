import { Module } from '@nestjs/common';
import { businessConfigFromEnv, BusinessDatabase, clockFromEnv, PostgresDatabase } from '@apex2next/runtime-api';
import { SecurityService } from './security.service';

/** Business services of the application. Add the services that replace its PL/SQL packages here. */
@Module({
  providers: [
    {
      provide: BusinessDatabase,
      inject: [PostgresDatabase],
      useFactory: (database: PostgresDatabase) => new BusinessDatabase(database, clockFromEnv(), businessConfigFromEnv()),
    },
    SecurityService,
  ],
  exports: [BusinessDatabase, SecurityService],
})
export class BusinessModule {}
