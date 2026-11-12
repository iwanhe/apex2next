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
  | 'PASSWORD_CHANGE_REQUIRED'
  | 'TOO_MANY_ATTEMPTS'
  | 'FORBIDDEN'
  | 'INVALID_INPUT'
  | 'VALIDATION_FAILED'
  | 'LOST_UPDATE'
  | 'ACTION_NOT_AVAILABLE'
  | 'DB_UNIQUE_VIOLATION'
  | 'DB_FOREIGN_KEY_VIOLATION'
  | 'DB_CHECK_VIOLATION'
  | 'DB_NOT_NULL_VIOLATION'
  | 'DB_VALUE_TOO_LARGE'
  | 'DB_APPLICATION_ERROR';

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
  PASSWORD_CHANGE_REQUIRED: 403,
  TOO_MANY_ATTEMPTS: 429,
  FORBIDDEN: 403,
  INVALID_INPUT: 422,
  VALIDATION_FAILED: 422,
  LOST_UPDATE: 409,
  ACTION_NOT_AVAILABLE: 409,
  DB_UNIQUE_VIOLATION: 409,
  DB_FOREIGN_KEY_VIOLATION: 409,
  DB_CHECK_VIOLATION: 422,
  DB_NOT_NULL_VIOLATION: 422,
  DB_VALUE_TOO_LARGE: 422,
  DB_APPLICATION_ERROR: 422,
};

/** One APEX inline error, attached to a page item (field) or shown on the page (field null). */
export interface FieldError {
  readonly field: string | null;
  readonly message: string;
}

export class BusinessRuleError extends Error {
  readonly httpStatus: number;

  constructor(
    readonly code: BusinessErrorCode,
    message: string,
    /** Oracle error code of the source behavior, e.g. -20101 or -1403. */
    readonly oracleCode: number | null,
    /** Business rule identifier in docs/migration/wp9.4-business-logic-f170134.md. */
    readonly rule: string,
    /** Inline errors for VALIDATION_FAILED (APEX shows every failed validation at once). */
    readonly fieldErrors: FieldError[] = [],
  ) {
    super(message);
    this.name = 'BusinessRuleError';
    this.httpStatus = HTTP_STATUS[code];
  }

  toJSON() {
    return {
      code: this.code, oracleCode: this.oracleCode, rule: this.rule, message: this.message,
      ...(this.fieldErrors.length ? { fieldErrors: this.fieldErrors } : {}),
    };
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
  /** WP9.5: APEX page validations (item required/number/date and page validations), all reported at once. */
  validation: (fieldErrors: FieldError[]) =>
    new BusinessRuleError('VALIDATION_FAILED', fieldErrors.map((e) => e.message).join('\n'), null, 'UI-VAL-01', fieldErrors),
  /** WP9.5: APEX form region lost-update check (p_lost_update_check_type VALUES); APEX runtime message. */
  lostUpdate: () =>
    new BusinessRuleError('LOST_UPDATE',
      'Current version of data in database has changed since user initiated update process.', null, 'UI-FRM-02'),
  /** WP9.5 DEV-06: a page action whose button condition is false is refused on the server. */
  actionNotAvailable: (action: string, reason: string) =>
    new BusinessRuleError('ACTION_NOT_AVAILABLE', `Aksi ${action} tidak tersedia: ${reason}`, null, 'UI-BTN-01'),
  database: (code: 'DB_UNIQUE_VIOLATION' | 'DB_FOREIGN_KEY_VIOLATION' | 'DB_CHECK_VIOLATION' | 'DB_NOT_NULL_VIOLATION'
    | 'DB_VALUE_TOO_LARGE' | 'DB_APPLICATION_ERROR', message: string, oracleCode: number) =>
    new BusinessRuleError(code, message, oracleCode, 'UI-DB-01'),
};
