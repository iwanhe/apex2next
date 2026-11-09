import { Module } from '@nestjs/common';
import { PostgresDatabase } from '../database/postgres-database';
import { PagesService } from '../pages/pages.service';
import { ApprovalService } from './approval.service';
import { BusinessDatabase, Clock, businessConfigFromEnv, systemClock } from './context';
import { DocumentTypeRegistry } from './document-types';
import { MasterDataService } from './master-data.service';
import { NumberingService } from './numbering.service';
import { PermintaanBarangService } from './permintaan-barang.service';
import { RequestService } from './request.service';
import { SecurityService } from './security.service';

@Module({
  providers: [
    {
      provide: BusinessDatabase,
      inject: [PostgresDatabase],
      useFactory: (database: PostgresDatabase) => new BusinessDatabase(database, systemClock, businessConfigFromEnv()),
    },
    SecurityService,
    NumberingService,
    DocumentTypeRegistry,
    ApprovalService,
    RequestService,
    MasterDataService,
    PermintaanBarangService,
  ],
  exports: [PermintaanBarangService, BusinessDatabase, SecurityService, RequestService, ApprovalService, MasterDataService],
})
export class BusinessModule {}

/** Composition root for tests and scripts (Nest DI uses BusinessModule). */
export function createBusinessServices(database: PostgresDatabase, options: { timeZone?: string; clock?: Clock } = {}) {
  const security = new SecurityService();
  const numbering = new NumberingService();
  const registry = new DocumentTypeRegistry();
  const approvals = new ApprovalService(registry, security);
  const requests = new RequestService(numbering);
  const masterData = new MasterDataService();
  const db = new BusinessDatabase(database, options.clock ?? systemClock, { timeZone: options.timeZone ?? 'UTC' });
  return {
    db, security, numbering, registry, approvals, requests, masterData,
    app: new PermintaanBarangService(db, security, requests, approvals, masterData),
    pages: new PagesService(db, security, requests, approvals, masterData),
  };
}
