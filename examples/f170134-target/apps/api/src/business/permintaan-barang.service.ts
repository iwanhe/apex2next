import { Injectable } from '@nestjs/common';
import { ApprovalService } from './approval.service';
import { BusinessDatabase, Principal } from './context';
import { MasterDataService } from './master-data.service';
import { LineInput, RequestInput, RequestPatch, RequestService } from './request.service';
import { AuthorizationScheme, SecurityService } from './security.service';

/**
 * Application service: one transaction per use case, the principal published to PostgreSQL, the APEX
 * page authorization scheme checked first (BR-SEC-05), then the domain rule. The page -> scheme mapping
 * comes from the APEX export (create_page p_required_role); HTTP controllers are part of WP9.5.
 */
export const PAGE_SCHEMES = {
  approvalInbox: 'APP_USERS',      // pages 190/191
  requestForm: 'REQUESTER',        // page 301 (SAVE_REQUESTS, CALL_SUBMIT_REQUESTS)
  requestLineForm: 'REQUESTER',    // page 311
  masterDataForm: 'MASTER_DATA',   // pages 201/211
  userRoleForm: 'ADMIN_RIGHTS',    // page 501
  reports: 'APP_USERS',            // pages 100/300/302/310/400
} as const satisfies Record<string, AuthorizationScheme>;

@Injectable()
export class PermintaanBarangService {
  constructor(
    private readonly db: BusinessDatabase,
    private readonly security: SecurityService,
    private readonly requests: RequestService,
    private readonly approvals: ApprovalService,
    private readonly masterData: MasterDataService,
  ) {}

  createRequest(actor: Principal, input: RequestInput) {
    return this.db.run(actor, async (tx) => {
      await this.security.authorize(tx, PAGE_SCHEMES.requestForm);
      return this.requests.create(tx, input);
    });
  }

  updateRequest(actor: Principal, requestId: number, patch: RequestPatch) {
    return this.db.run(actor, async (tx) => {
      await this.security.authorize(tx, PAGE_SCHEMES.requestForm);
      return this.requests.update(tx, requestId, patch);
    });
  }

  deleteRequest(actor: Principal, requestId: number) {
    return this.db.run(actor, async (tx) => {
      await this.security.authorize(tx, PAGE_SCHEMES.requestForm);
      return this.requests.delete(tx, requestId);
    });
  }

  addLine(actor: Principal, input: LineInput) {
    return this.db.run(actor, async (tx) => {
      await this.security.authorize(tx, PAGE_SCHEMES.requestLineForm);
      return this.requests.addLine(tx, input);
    });
  }

  updateLine(actor: Principal, lineId: number, patch: Partial<LineInput>) {
    return this.db.run(actor, async (tx) => {
      await this.security.authorize(tx, PAGE_SCHEMES.requestLineForm);
      return this.requests.updateLine(tx, lineId, patch);
    });
  }

  deleteLine(actor: Principal, lineId: number) {
    return this.db.run(actor, async (tx) => {
      await this.security.authorize(tx, PAGE_SCHEMES.requestLineForm);
      return this.requests.deleteLine(tx, lineId);
    });
  }

  /** Page 301 CALL_SUBMIT_REQUESTS: apx_demo_approval_pkg.submit('REQ', :P301_REQUEST_ID). */
  submitRequest(actor: Principal, requestId: number) {
    return this.db.run(actor, async (tx) => {
      await this.security.authorize(tx, PAGE_SCHEMES.requestForm);
      return this.approvals.submit(tx, 'REQ', requestId);
    });
  }

  /** Page 191 CALL_APPROVE. */
  approve(actor: Principal, approvalId: number, note?: string | null) {
    return this.db.run(actor, async (tx) => {
      await this.security.authorize(tx, PAGE_SCHEMES.approvalInbox);
      return this.approvals.approve(tx, approvalId, note);
    });
  }

  /** Page 191 CALL_REJECT. */
  reject(actor: Principal, approvalId: number, note: string | null | undefined) {
    return this.db.run(actor, async (tx) => {
      await this.security.authorize(tx, PAGE_SCHEMES.approvalInbox);
      return this.approvals.reject(tx, approvalId, note);
    });
  }

  /** Page 190 inbox / page 100 KPI read through the converted views (can_act_yn uses app.username). */
  approvalInbox(actor: Principal) {
    return this.db.run(actor, async (tx) => {
      await this.security.authorize(tx, PAGE_SCHEMES.approvalInbox);
      const r = await tx.query(
        `SELECT approval_id::text, doc_type, doc_no, approval_level::text, approver_role, amount::text,
                requested_by, status, can_act_yn
           FROM app.apx_demo_approvals_v WHERE status = 'PENDING' ORDER BY approval_id`);
      return r.rows;
    });
  }

  dashboardKpis(actor: Principal) {
    return this.db.run(actor, async (tx) => {
      await this.security.authorize(tx, PAGE_SCHEMES.reports);
      const r = await tx.query('SELECT seq, icon, label, metric_value::int FROM app.apx_demo_dash_kpi_v ORDER BY seq');
      return r.rows;
    });
  }

  saveMasterData(actor: Principal, entity: 'departments' | 'items', values: Record<string, unknown>, id?: number) {
    return this.db.run(actor, async (tx) => {
      await this.security.authorize(tx, PAGE_SCHEMES.masterDataForm);
      return id === undefined ? this.masterData.create(tx, entity, values) : this.masterData.update(tx, entity, id, values);
    });
  }

  saveUserRole(actor: Principal, values: Record<string, unknown>, id?: number) {
    return this.db.run(actor, async (tx) => {
      await this.security.authorize(tx, PAGE_SCHEMES.userRoleForm);
      return id === undefined ? this.masterData.create(tx, 'userRoles', values) : this.masterData.update(tx, 'userRoles', id, values);
    });
  }
}
