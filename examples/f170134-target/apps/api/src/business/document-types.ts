import { Injectable } from '@nestjs/common';
import { BusinessTx } from './context';
import { errors } from './errors';

/**
 * Replaces the configuration-driven dynamic SQL of APX_DEMO_APPROVAL_PKG (GET_DOC, SET_DOC_STATUS,
 * DOC_AMOUNT and the EXECUTE IMMEDIATE of VALIDATE_PROC, install.sql lines 505-561, 612-616).
 *
 * The source builds SQL from apx_demo_doc_types columns (table_name, pk_column, number_column,
 * status_column, amount_expr, validate_proc). AMOUNT_EXPR is an arbitrary SQL expression executed as
 * code and VALIDATE_PROC an arbitrary procedure name. The target never executes configuration text:
 * each document type has a reviewed adapter, and the configuration row must match it exactly or the
 * operation fails closed (BR-APR-02, DEV-05).
 */
export interface DocumentRow {
  docNo: string | null;
  status: string;
}

export interface DocumentAdapter {
  readonly docType: string;
  /** Expected apx_demo_doc_types values (upper-case identifiers, normalized expression text). */
  readonly expected: {
    tableName: string;
    pkColumn: string;
    numberColumn: string;
    statusColumn: string;
    amountExpr: string | null;
    validateProc: string | null;
  };
  /** BR-APR-05 GET_DOC: number and status, locking the document row for the rest of the transaction. */
  lock(tx: BusinessTx, docId: number): Promise<DocumentRow | null>;
  /** BR-APR-06 SET_DOC_STATUS: internal status change (source: g_bypass) with audit stamps. */
  setStatus(tx: BusinessTx, docId: number, status: string): Promise<void>;
  /** BR-APR-07 DOC_AMOUNT: reviewed implementation of AMOUNT_EXPR; NVL(..., 0). */
  amount(tx: BusinessTx, docId: number): Promise<string>;
  /** BR-APR-04 VALIDATE_PROC: reviewed implementation of the validation procedure. */
  validate(tx: BusinessTx, docId: number): Promise<void>;
}

/** Normalize SQL text for comparison: whitespace and case insensitive, quotes ignored. */
export function normalizeSql(text: string | null | undefined): string | null {
  if (text === null || text === undefined || text === '') return null;
  return text.replace(/"/g, '').replace(/\s+/g, '').toLowerCase();
}

/** Document type REQ: Permintaan Barang (apx_demo_requests). */
export const requestDocument: DocumentAdapter = {
  docType: 'REQ',
  expected: {
    tableName: 'APX_DEMO_REQUESTS',
    pkColumn: 'REQUEST_ID',
    numberColumn: 'REQUEST_NO',
    statusColumn: 'STATUS',
    amountExpr: normalizeSql(
      '(select nvl(sum(l.line_amount), 0) from apx_demo_request_lines l where l.request_id = t.request_id)'),
    validateProc: 'APX_DEMO_REQUEST_PKG.CHECK_SUBMIT',
  },
  async lock(tx, docId) {
    const r = await tx.query<{ request_no: string | null; status: string }>(
      'SELECT request_no, status FROM app.apx_demo_requests WHERE request_id = $1 FOR UPDATE', [docId]);
    return r.rowCount ? { docNo: r.rows[0].request_no, status: r.rows[0].status } : null;
  },
  async setStatus(tx, docId, status) {
    await tx.query(
      `UPDATE app.apx_demo_requests
          SET status = $2, updated_by = $3, updated_on = $4
        WHERE request_id = $1`,
      [docId, status, tx.principal.username, tx.now.timestamp]);
  },
  async amount(tx, docId) {
    const r = await tx.query<{ amount: string }>(
      `SELECT coalesce(sum(l.line_amount), 0)::text AS amount
         FROM app.apx_demo_request_lines l WHERE l.request_id = $1`, [docId]);
    return r.rows[0].amount;
  },
  /** Replaces APX_DEMO_REQUEST_PKG.CHECK_SUBMIT (install.sql lines 993-1006). */
  async validate(tx, docId) {
    const r = await tx.query<{ n: string }>(
      'SELECT count(*)::text AS n FROM app.apx_demo_request_lines WHERE request_id = $1', [docId]);
    if (r.rows[0].n === '0') throw errors.requestWithoutLines();
  },
};

export interface DocumentTypeConfig {
  doc_type: string;
  doc_name: string;
  prefix: string;
  table_name: string;
  pk_column: string;
  number_column: string;
  status_column: string;
  amount_expr: string | null;
  validate_proc: string | null;
  approver1_role: string | null;
  approver2_role: string | null;
  level2_limit: string;
}

@Injectable()
export class DocumentTypeRegistry {
  private readonly adapters = new Map<string, DocumentAdapter>([[requestDocument.docType, requestDocument]]);

  /** BR-APR-01 GET_TYPE + BR-APR-02 configuration check. */
  async resolve(tx: BusinessTx, docType: string): Promise<{ config: DocumentTypeConfig; adapter: DocumentAdapter }> {
    const r = await tx.query<DocumentTypeConfig>(
      'SELECT *, level2_limit::text AS level2_limit FROM app.apx_demo_doc_types WHERE doc_type = $1', [docType]);
    if (r.rowCount === 0) throw errors.unknownDocType(docType);
    const config = r.rows[0];
    const adapter = this.adapters.get(config.doc_type);
    if (!adapter) throw errors.configDrift(config.doc_type, 'no reviewed document adapter');
    const e = adapter.expected;
    const drift: string[] = [];
    if (config.table_name.toUpperCase() !== e.tableName) drift.push('table_name');
    if (config.pk_column.toUpperCase() !== e.pkColumn) drift.push('pk_column');
    if (config.number_column.toUpperCase() !== e.numberColumn) drift.push('number_column');
    if (config.status_column.toUpperCase() !== e.statusColumn) drift.push('status_column');
    if (normalizeSql(config.amount_expr) !== e.amountExpr) drift.push('amount_expr');
    if ((config.validate_proc?.toUpperCase() || null) !== e.validateProc) drift.push('validate_proc');
    if (drift.length) throw errors.configDrift(config.doc_type, drift.join(', '));
    return { config, adapter };
  }
}
