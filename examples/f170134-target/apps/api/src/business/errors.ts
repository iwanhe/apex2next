/**
 * WP9.4 business error contract.
 *
 * Every RAISE_APPLICATION_ERROR of the source keeps its Oracle code and message text (Bahasa Indonesia)
 * so that APEX users see the same messages. Oracle conditions that surfaced as unhandled ORA errors
 * (e.g. ORA-01403 no data found) get an explicit code. HTTP status is a target decision.
 */
export type BusinessErrorCode =
  | 'UNKNOWN_DOC_TYPE'
  | 'DOC_NOT_SUBMITTABLE'
  | 'APPROVAL_ALREADY_PROCESSED'
  | 'SEGREGATION_OF_DUTIES'
  | 'MISSING_APPROVER_ROLE'
  | 'REJECT_NOTE_REQUIRED'
  | 'REQUEST_LOCKED_SUBMITTED'
  | 'REQUEST_FINAL'
  | 'REQUEST_STATUS_TRANSITION'
  | 'REQUEST_LINES_LOCKED'
  | 'REQUEST_WITHOUT_LINES'
  | 'NOT_FOUND'
  | 'NUMBERING_CAPACITY_EXCEEDED'
  | 'DOC_TYPE_CONFIG_DRIFT'
  | 'UNAUTHENTICATED'
  | 'FORBIDDEN'
  | 'INVALID_INPUT';

const HTTP_STATUS: Record<BusinessErrorCode, number> = {
  UNKNOWN_DOC_TYPE: 422,
  DOC_NOT_SUBMITTABLE: 409,
  APPROVAL_ALREADY_PROCESSED: 409,
  SEGREGATION_OF_DUTIES: 403,
  MISSING_APPROVER_ROLE: 403,
  REJECT_NOTE_REQUIRED: 422,
  REQUEST_LOCKED_SUBMITTED: 409,
  REQUEST_FINAL: 409,
  REQUEST_STATUS_TRANSITION: 409,
  REQUEST_LINES_LOCKED: 409,
  REQUEST_WITHOUT_LINES: 422,
  NOT_FOUND: 404,
  NUMBERING_CAPACITY_EXCEEDED: 409,
  DOC_TYPE_CONFIG_DRIFT: 500,
  UNAUTHENTICATED: 401,
  FORBIDDEN: 403,
  INVALID_INPUT: 422,
};

export class BusinessRuleError extends Error {
  readonly httpStatus: number;

  constructor(
    readonly code: BusinessErrorCode,
    message: string,
    /** Oracle error code of the source behavior, e.g. -20101 or -1403. */
    readonly oracleCode: number | null,
    /** Business rule identifier in docs/migration/wp9.4-business-logic-f170134.md. */
    readonly rule: string,
  ) {
    super(message);
    this.name = 'BusinessRuleError';
    this.httpStatus = HTTP_STATUS[code];
  }

  toJSON() {
    return { code: this.code, oracleCode: this.oracleCode, rule: this.rule, message: this.message };
  }
}

/** Oracle concatenation treats NULL as an empty string; keep that for message parity. */
export function s(value: unknown): string {
  return value === null || value === undefined ? '' : String(value);
}

export const errors = {
  unknownDocType: (docType: string) =>
    new BusinessRuleError('UNKNOWN_DOC_TYPE', `Jenis dokumen ${s(docType)} tidak dikenal.`, -20100, 'BR-APR-01'),
  notSubmittable: (docNo: unknown, status: unknown) =>
    new BusinessRuleError('DOC_NOT_SUBMITTABLE',
      `Dokumen ${s(docNo)} berstatus ${s(status)} dan tidak dapat diajukan.`, -20101, 'BR-APR-03'),
  alreadyProcessed: (status: unknown) =>
    new BusinessRuleError('APPROVAL_ALREADY_PROCESSED', `Approval ini sudah diproses (${s(status)}).`, -20105, 'BR-APR-09'),
  segregationOfDuties: () =>
    new BusinessRuleError('SEGREGATION_OF_DUTIES',
      'Segregation of duties: pengaju tidak boleh menyetujui dokumennya sendiri.', -20106, 'BR-APR-09'),
  missingRole: (role: unknown) =>
    new BusinessRuleError('MISSING_APPROVER_ROLE',
      `Anda tidak memiliki role ${s(role)} untuk approval ini.`, -20107, 'BR-APR-09'),
  rejectNoteRequired: () =>
    new BusinessRuleError('REJECT_NOTE_REQUIRED', 'Alasan penolakan wajib diisi.', -20108, 'BR-APR-11'),
  requestSubmitted: (requestNo: unknown) =>
    new BusinessRuleError('REQUEST_LOCKED_SUBMITTED',
      `Permintaan Barang ${s(requestNo)} sedang menunggu approval dan tidak dapat diubah.`, -20110, 'BR-REQ-04'),
  requestFinal: (requestNo: unknown, status: unknown) =>
    new BusinessRuleError('REQUEST_FINAL', `Permintaan Barang ${s(requestNo)} sudah ${s(status)}.`, -20111, 'BR-REQ-05'),
  statusTransition: (from: unknown, to: unknown) =>
    new BusinessRuleError('REQUEST_STATUS_TRANSITION',
      `Perubahan status ${s(from)} -> ${s(to)} tidak diizinkan. Gunakan Submit for Approval.`, -20112, 'BR-REQ-06'),
  linesLocked: (parentStatus: unknown) =>
    new BusinessRuleError('REQUEST_LINES_LOCKED',
      `Baris Permintaan tidak dapat diubah karena Permintaan Barang berstatus ${s(parentStatus)}.`, -20121, 'BR-LIN-01'),
  requestWithoutLines: () =>
    new BusinessRuleError('REQUEST_WITHOUT_LINES', 'Permintaan belum memiliki baris item.', -20201, 'BR-APR-04'),
  notFound: (what: string, rule: string) =>
    new BusinessRuleError('NOT_FOUND', `${what} tidak ditemukan.`, -1403, rule),
  numberingCapacity: (docType: string, period: string) =>
    new BusinessRuleError('NUMBERING_CAPACITY_EXCEEDED',
      `Nomor dokumen ${docType} periode ${period} melebihi 9999.`, null, 'BR-DOC-03'),
  configDrift: (docType: string, detail: string) =>
    new BusinessRuleError('DOC_TYPE_CONFIG_DRIFT',
      `Konfigurasi jenis dokumen ${docType} tidak sesuai dengan implementasi yang direview: ${detail}`, null, 'BR-APR-02'),
  unauthenticated: () =>
    new BusinessRuleError('UNAUTHENTICATED', 'Pengguna belum terautentikasi.', null, 'BR-SEC-01'),
  forbidden: (message: string) => new BusinessRuleError('FORBIDDEN', message, null, 'BR-SEC-05'),
  invalidInput: (message: string) => new BusinessRuleError('INVALID_INPUT', message, null, 'BR-GEN-01'),
};
