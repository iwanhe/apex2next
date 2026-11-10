import { Injectable } from '@nestjs/common';
import { BusinessTx, errors } from '@apex2next/runtime-api';
import { DocumentAdapter, DocumentTypeConfig, DocumentTypeRegistry } from './document-types';
import { SecurityService } from './security.service';

/**
 * Replaces APX_DEMO_APPROVAL_PKG (install.sql lines 383-724). The package global G_BYPASS is replaced
 * by the internal DocumentAdapter.setStatus path: user-facing request updates enforce the trigger
 * guards (RequestService), approval-driven status changes do not.
 */
export const STATUS = {
  DRAFT: 'DRAFT', SUBMITTED: 'SUBMITTED', APPROVED: 'APPROVED', REJECTED: 'REJECTED', PENDING: 'PENDING',
} as const;

export interface ApprovalRow {
  approval_id: string;
  doc_type: string;
  doc_id: string;
  doc_no: string | null;
  approval_level: string;
  approver_role: string;
  amount: string | null;
  requested_by: string;
  status: string;
}

export type SubmitResult = { docType: string; docId: number; status: string; approvalId: number | null };
export type ActResult = { approvalId: number; docStatus: string | null; nextApprovalId: number | null };

@Injectable()
export class ApprovalService {
  constructor(
    private readonly registry: DocumentTypeRegistry,
    private readonly security: SecurityService,
  ) {}

  /**
   * BR-APR-03 SUBMIT: only DRAFT or REJECTED documents (-20101); BR-APR-04 validation (-20201);
   * no approver1 -> APPROVED directly, else SUBMITTED + level-1 step requested by the principal.
   * The document row is locked (FOR UPDATE) so concurrent submits cannot both create steps (DEV-02).
   */
  async submit(tx: BusinessTx, docType: string, docId: number): Promise<SubmitResult> {
    const { config, adapter } = await this.registry.resolve(tx, docType);
    const doc = await adapter.lock(tx, docId);
    if (!doc) throw errors.notFound(`Dokumen ${docType} ${docId}`, 'BR-APR-05');
    if (doc.status !== STATUS.DRAFT && doc.status !== STATUS.REJECTED) throw errors.notSubmittable(doc.docNo, doc.status);
    if (config.validate_proc) await adapter.validate(tx, docId);
    if (!config.approver1_role) {
      await adapter.setStatus(tx, docId, STATUS.APPROVED);
      return { docType, docId, status: STATUS.APPROVED, approvalId: null };
    }
    await adapter.setStatus(tx, docId, STATUS.SUBMITTED);
    const approvalId = await this.createStep(tx, config, adapter, docId, 1, config.approver1_role, tx.principal.username);
    return { docType, docId, status: STATUS.SUBMITTED, approvalId };
  }

  /** BR-APR-08 CAN_ACT_YN, evaluated by the reviewed SQL function shared with apx_demo_approvals_v. */
  async canAct(tx: BusinessTx, approvalId: number): Promise<boolean> {
    const r = await tx.query<{ yn: string }>('SELECT app.can_act_yn($1) AS yn', [approvalId]);
    return r.rows[0].yn === 'Y';
  }

  /**
   * BR-APR-10 APPROVE: lock the step, assert it can be processed, approve it; a level-1 step whose amount
   * exceeds LEVEL2_LIMIT with an APPROVER2_ROLE creates a level-2 step for the original requester,
   * otherwise the document becomes APPROVED.
   */
  async approve(tx: BusinessTx, approvalId: number, note?: string | null): Promise<ActResult> {
    const step = await this.lockStep(tx, approvalId);
    await this.assertCanAct(tx, step);
    await this.closeStep(tx, approvalId, STATUS.APPROVED, note ?? null);
    const { config, adapter } = await this.registry.resolve(tx, step.doc_type);
    const exceeds = await tx.query<{ x: boolean }>(
      'SELECT coalesce($1::numeric, 0) > $2::numeric AS x', [step.amount, config.level2_limit]); // exact decimals
    if (step.approval_level === '1' && config.approver2_role && exceeds.rows[0].x) {
      const next = await this.createStep(tx, config, adapter, Number(step.doc_id), 2, config.approver2_role, step.requested_by);
      return { approvalId, docStatus: null, nextApprovalId: next };
    }
    await adapter.setStatus(tx, Number(step.doc_id), STATUS.APPROVED);
    return { approvalId, docStatus: STATUS.APPROVED, nextApprovalId: null };
  }

  /** BR-APR-11 REJECT: as approve, but the note is mandatory (-20108) and the document becomes REJECTED. */
  async reject(tx: BusinessTx, approvalId: number, note: string | null | undefined): Promise<ActResult> {
    const step = await this.lockStep(tx, approvalId);
    await this.assertCanAct(tx, step);
    if (note === null || note === undefined || note === '') throw errors.rejectNoteRequired(); // Oracle '' IS NULL
    await this.closeStep(tx, approvalId, STATUS.REJECTED, note);
    const { adapter } = await this.registry.resolve(tx, step.doc_type);
    await adapter.setStatus(tx, Number(step.doc_id), STATUS.REJECTED);
    return { approvalId, docStatus: STATUS.REJECTED, nextApprovalId: null };
  }

  /** BR-APR-09 ASSERT_CAN_ACT with the source order of checks: -20105, -20106, -20107. */
  async assertCanAct(tx: BusinessTx, step: ApprovalRow): Promise<void> {
    if (step.status !== STATUS.PENDING) throw errors.alreadyProcessed(step.status);
    if (step.requested_by.toUpperCase() === tx.principal.username) throw errors.segregationOfDuties();
    if (!(await this.security.hasRole(tx, step.approver_role))) throw errors.missingRole(step.approver_role);
  }

  private async lockStep(tx: BusinessTx, approvalId: number): Promise<ApprovalRow> {
    const r = await tx.query<ApprovalRow>(
      `SELECT approval_id::text, doc_type, doc_id::text, doc_no, approval_level::text, approver_role,
              amount::text, requested_by, status
         FROM app.apx_demo_approvals WHERE approval_id = $1 FOR UPDATE`, [approvalId]);
    if (r.rowCount === 0) throw errors.notFound(`Approval ${approvalId}`, 'BR-APR-10');
    return r.rows[0];
  }

  private async closeStep(tx: BusinessTx, approvalId: number, status: string, note: string | null) {
    await tx.query(
      `UPDATE app.apx_demo_approvals
          SET status = $2, acted_by = $3, acted_on = $4, note = $5
        WHERE approval_id = $1`,
      [approvalId, status, tx.principal.username, tx.now.timestamp, note]);
  }

  /** BR-APR-07 CREATE_STEP: one PENDING step with the current document number and amount. */
  private async createStep(tx: BusinessTx, config: DocumentTypeConfig, adapter: DocumentAdapter, docId: number,
                           level: number, role: string, requestedBy: string): Promise<number> {
    const doc = await adapter.lock(tx, docId);
    if (!doc) throw errors.notFound(`Dokumen ${config.doc_type} ${docId}`, 'BR-APR-05');
    const amount = config.amount_expr === null ? '0' : await adapter.amount(tx, docId);
    const r = await tx.query<{ approval_id: string }>(
      `INSERT INTO app.apx_demo_approvals
         (doc_type, doc_id, doc_no, approval_level, approver_role, amount, requested_by, requested_on, status)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING approval_id::text`,
      [config.doc_type, docId, doc.docNo, level, role, amount, requestedBy, tx.now.timestamp, STATUS.PENDING]);
    return Number(r.rows[0].approval_id);
  }
}
