import { Injectable } from '@nestjs/common';
import { BusinessTx, errors } from '@apex2next/runtime-api';
import { NumberingService } from './numbering.service';

/**
 * Write paths for Permintaan Barang. Replaces the row triggers APX_DEMO_REQUESTS_TRG
 * (install.sql lines 779-815) and APX_DEMO_REQUEST_LINES_TRG (lines 818-847). All writes to these
 * tables go through this service. PostgreSQL has no equivalent triggers, so direct DML bypasses
 * these rules by design (the same as the source's package bypass), and that path is reserved for
 * reviewed data migration.
 */
export interface RequestInput {
  request_no?: string | null;
  department_id: number;
  request_date?: string | null;
  need_date?: string | null;
  purpose: string;
  notes?: string | null;
  status?: string | null;
}

export type RequestPatch = Partial<RequestInput>;

export interface RequestRow {
  request_id: string;
  request_no: string | null;
  department_id: string;
  request_date: string;
  need_date: string | null;
  purpose: string;
  notes: string | null;
  status: string;
  created_by: string | null;
  created_on: string | null;
  updated_by: string | null;
  updated_on: string | null;
}

export interface LineInput {
  request_id: number;
  item_id: number;
  qty: string | number;
  unit_price?: string | number | null;
}

const REQUEST_COLUMNS = `request_id::text, request_no, department_id::text, request_date::text, need_date::text,
  purpose, notes, status, created_by, created_on::text, updated_by, updated_on::text`;
const EDITABLE: Array<keyof RequestInput> = ['request_no', 'department_id', 'request_date', 'need_date', 'purpose', 'notes', 'status'];
/** BR-REQ-07: columns frozen once the request left DRAFT/REJECTED (silently kept, as in the source). */
const LOCKED_AFTER_SUBMIT: Array<keyof RequestInput> = ['department_id', 'purpose', 'need_date'];
const OPEN_STATES = new Set(['DRAFT', 'REJECTED']);
/** BR-REQ-06: the only user-driven status changes. */
const ALLOWED_FROM = new Set(['APPROVED', 'FULFILLED', 'CLOSED']);
const ALLOWED_TO = new Set(['FULFILLED', 'CLOSED']);

function nullIfEmpty<T>(v: T): T | null {
  return (v as unknown) === '' ? null : v; // Oracle stores '' as NULL (WP9.3 SCH004)
}

@Injectable()
export class RequestService {
  constructor(private readonly numbering: NumberingService) {}

  /**
   * BR-REQ-01 status is always DRAFT on insert; BR-REQ-02 request_no from NEXT_NO('REQ') when not given
   * (period = transaction clock, not request_date, as in the source); BR-REQ-03 request_date defaults to
   * today (TRUNC(SYSDATE)); BR-AUD-01 audit stamps.
   */
  async create(tx: BusinessTx, input: RequestInput): Promise<RequestRow> {
    const requestNo = nullIfEmpty(input.request_no ?? null) ?? (await this.numbering.nextNo(tx, 'REQ'));
    const r = await tx.query<RequestRow>(
      `INSERT INTO app.apx_demo_requests
         (request_no, department_id, request_date, need_date, purpose, notes, status,
          created_by, created_on, updated_by, updated_on)
       VALUES ($1, $2, $3, $4, $5, $6, 'DRAFT', $7, $8, $7, $8)
       RETURNING ${REQUEST_COLUMNS}`,
      [requestNo, input.department_id, nullIfEmpty(input.request_date ?? null) ?? tx.now.date,
       nullIfEmpty(input.need_date ?? null), nullIfEmpty(input.purpose), nullIfEmpty(input.notes ?? null),
       tx.principal.username, tx.now.timestamp]);
    return r.rows[0];
  }

  /**
   * BR-REQ-04 SUBMITTED requests cannot be changed (-20110); BR-REQ-05 CANCELLED/CLOSED are final (-20111);
   * BR-REQ-06 status changes only APPROVED/FULFILLED/CLOSED -> FULFILLED/CLOSED (-20112);
   * BR-REQ-07 department_id/purpose/need_date are kept when the request is not DRAFT/REJECTED.
   * Returns the row and the fields that were ignored (the source ignores them silently).
   */
  async update(tx: BusinessTx, requestId: number, patch: RequestPatch): Promise<{ row: RequestRow; ignored: string[] }> {
    const unknown = Object.keys(patch).filter((k) => !EDITABLE.includes(k as keyof RequestInput));
    if (unknown.length) throw errors.invalidInput(`Kolom tidak dapat diubah: ${unknown.join(', ')}`);
    const current = await this.lock(tx, requestId);
    if (current.status === 'SUBMITTED') throw errors.requestSubmitted(current.request_no);
    if (current.status === 'CANCELLED' || current.status === 'CLOSED') throw errors.requestFinal(current.request_no, current.status);
    const next: Record<string, unknown> = {};
    for (const key of EDITABLE) {
      if (Object.prototype.hasOwnProperty.call(patch, key)) next[key] = nullIfEmpty(patch[key] ?? null);
    }
    const newStatus = (next.status as string | null | undefined) ?? current.status;
    if (newStatus !== current.status && !(ALLOWED_FROM.has(current.status) && ALLOWED_TO.has(newStatus))) {
      throw errors.statusTransition(current.status, newStatus);
    }
    const ignored: string[] = [];
    if (!OPEN_STATES.has(current.status)) {
      for (const key of LOCKED_AFTER_SUBMIT) {
        if (key in next) {
          const before = (current as unknown as Record<string, unknown>)[key];
          if (String(next[key] ?? '') !== String(before ?? '')) ignored.push(key);
          delete next[key];
        }
      }
    }
    const keys = Object.keys(next);
    const sets = keys.map((k, i) => `${k} = $${i + 2}`);
    sets.push(`updated_by = $${keys.length + 2}`, `updated_on = $${keys.length + 3}`);
    const r = await tx.query<RequestRow>(
      `UPDATE app.apx_demo_requests SET ${sets.join(', ')} WHERE request_id = $1 RETURNING ${REQUEST_COLUMNS}`,
      [requestId, ...keys.map((k) => next[k]), tx.principal.username, tx.now.timestamp]);
    return { row: r.rows[0], ignored };
  }

  /**
   * BR-REQ-08 the source has no delete trigger on requests: a request can be deleted in any status and its
   * lines cascade (the line trigger returns on ORA-04091 during the cascade). Kept for parity; see finding
   * F-03 for the owner decision.
   */
  async delete(tx: BusinessTx, requestId: number): Promise<void> {
    await this.lock(tx, requestId);
    await tx.query('DELETE FROM app.apx_demo_requests WHERE request_id = $1', [requestId]);
  }

  /** BR-LIN-01 lines change only while the parent request is DRAFT/REJECTED (-20121); BR-AUD-01 audit. */
  async addLine(tx: BusinessTx, input: LineInput) {
    await this.assertParentOpen(tx, input.request_id);
    const r = await tx.query(
      `INSERT INTO app.apx_demo_request_lines
         (request_id, item_id, qty, unit_price, created_by, created_on, updated_by, updated_on)
       VALUES ($1, $2, $3, coalesce($4::numeric, 0), $5, $6, $5, $6)
       RETURNING line_id::text, request_id::text, item_id::text, qty::text, unit_price::text, line_amount::text`,
      [input.request_id, input.item_id, input.qty, nullIfEmpty(input.unit_price ?? null), tx.principal.username, tx.now.timestamp]);
    return r.rows[0];
  }

  /**
   * BR-LIN-01 for updates. DEV-03: when a line is moved to another request, both the old and the new parent
   * must be open (the source checks only the new parent, so lines could leave a submitted request).
   */
  async updateLine(tx: BusinessTx, lineId: number, patch: Partial<LineInput>) {
    const allowed = ['request_id', 'item_id', 'qty', 'unit_price'];
    const unknown = Object.keys(patch).filter((k) => !allowed.includes(k));
    if (unknown.length) throw errors.invalidInput(`Kolom tidak dapat diubah: ${unknown.join(', ')}`);
    const line = await this.lockLine(tx, lineId);
    const target = patch.request_id ?? Number(line.request_id);
    await this.assertParentOpen(tx, Number(line.request_id));
    if (target !== Number(line.request_id)) await this.assertParentOpen(tx, target);
    const keys = allowed.filter((k) => Object.prototype.hasOwnProperty.call(patch, k));
    const sets = keys.map((k, i) => `${k} = $${i + 2}`);
    sets.push(`updated_by = $${keys.length + 2}`, `updated_on = $${keys.length + 3}`);
    const r = await tx.query(
      `UPDATE app.apx_demo_request_lines SET ${sets.join(', ')} WHERE line_id = $1
       RETURNING line_id::text, request_id::text, item_id::text, qty::text, unit_price::text, line_amount::text`,
      [lineId, ...keys.map((k) => nullIfEmpty((patch as Record<string, unknown>)[k] ?? null)),
       tx.principal.username, tx.now.timestamp]);
    return r.rows[0];
  }

  async deleteLine(tx: BusinessTx, lineId: number): Promise<void> {
    const line = await this.lockLine(tx, lineId);
    await this.assertParentOpen(tx, Number(line.request_id));
    await tx.query('DELETE FROM app.apx_demo_request_lines WHERE line_id = $1', [lineId]);
  }

  private async lock(tx: BusinessTx, requestId: number): Promise<RequestRow> {
    const r = await tx.query<RequestRow>(
      `SELECT ${REQUEST_COLUMNS} FROM app.apx_demo_requests WHERE request_id = $1 FOR UPDATE`, [requestId]);
    if (r.rowCount === 0) throw errors.notFound(`Permintaan Barang ${requestId}`, 'BR-REQ-04');
    return r.rows[0];
  }

  private async lockLine(tx: BusinessTx, lineId: number): Promise<{ request_id: string }> {
    const r = await tx.query<{ request_id: string }>(
      'SELECT request_id::text FROM app.apx_demo_request_lines WHERE line_id = $1 FOR UPDATE', [lineId]);
    if (r.rowCount === 0) throw errors.notFound(`Baris Permintaan ${lineId}`, 'BR-LIN-01');
    return r.rows[0];
  }

  /** Locks the parent so a concurrent submit and line change serialize (WP9.2 race finding, DEV-02). */
  private async assertParentOpen(tx: BusinessTx, requestId: number): Promise<void> {
    const r = await tx.query<{ status: string }>(
      'SELECT status FROM app.apx_demo_requests WHERE request_id = $1 FOR UPDATE', [requestId]);
    if (r.rowCount === 0) throw errors.notFound(`Permintaan Barang ${requestId}`, 'BR-LIN-01');
    if (!OPEN_STATES.has(r.rows[0].status)) throw errors.linesLocked(r.rows[0].status);
  }
}
