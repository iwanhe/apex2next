/** Framework-neutral contracts shared by generated Next.js and NestJS applications. */
export type ApexDataType = 'VARCHAR2' | 'NUMBER' | 'DATE' | 'TIMESTAMP' | 'CLOB' | 'BLOB';
export type ApexItemKind =
  | 'TEXT' | 'TEXTAREA' | 'NUMBER' | 'DATE' | 'SELECT' | 'RADIO'
  | 'CHECKBOX' | 'DISPLAY' | 'HIDDEN' | 'FILE' | 'PASSWORD';

export interface RuntimeApplication {
  readonly id: string;
  readonly name: string;
  readonly version: string;
  readonly language: string;
  readonly dateFormat: string;
  readonly timeZone: string;
  readonly defaultPage: number;
  readonly authenticationRequired: boolean;
  readonly authorizationPolicyId?: string;
}

export interface RuntimePage {
  readonly id: number;
  readonly name: string;
  readonly title: string;
  readonly route: string;
  readonly public: boolean;
  readonly authorizationPolicyId?: string;
  readonly items: readonly RuntimeItem[];
  readonly regions: readonly RuntimeRegion[];
  readonly buttons: readonly RuntimeButton[];
}

export interface RuntimeItem {
  readonly id: string;
  readonly name: string;
  readonly label: string;
  readonly kind: ApexItemKind;
  readonly dataType: ApexDataType;
  readonly required: boolean;
  readonly writable: boolean;
  readonly trimSpaces: 'BOTH' | 'LEADING' | 'TRAILING' | 'NONE';
  readonly minValue?: number;
  readonly maxValue?: number;
  readonly maxLength?: number;
  readonly formatMask?: string;
  readonly lovId?: string;
  readonly defaultValue?: string | null;
}

export interface RuntimeRegion {
  readonly id: string;
  readonly name: string;
  readonly title: string;
  readonly type: 'FORM' | 'INTERACTIVE_REPORT' | 'CLASSIC_REPORT' | 'FACETED_SEARCH' | 'CARDS' | 'CHART' | 'STATIC';
  readonly sourceId?: string;
  readonly authorizationPolicyId?: string;
}

export interface RuntimeButton {
  readonly id: string;
  readonly name: string;
  readonly label: string;
  readonly action: 'SUBMIT' | 'REDIRECT' | 'DIALOG' | 'DOWNLOAD' | 'CANCEL';
  readonly authorizationPolicyId?: string;
  readonly conditionId?: string;
  readonly confirmationMessage?: string;
}

export interface AuthorizationPolicy {
  readonly id: string;
  readonly mode: 'ANY_ROLE' | 'ALL_ROLES' | 'REGISTERED';
  readonly roles: readonly string[];
  readonly message: string;
}

export interface RuntimePrincipal {
  readonly subject: string;
  readonly roles: readonly string[];
  readonly authenticated: boolean;
  readonly attributes?: Readonly<Record<string, string>>;
}

export interface RuntimeFieldError {
  readonly field: string;
  readonly message: string;
}

export interface RuntimeValidationResult {
  readonly values: Readonly<Record<string, string | null>>;
  readonly errors: readonly RuntimeFieldError[];
}

export interface RuntimeReportColumn {
  readonly name: string;
  readonly label: string;
  readonly dataType: 'STRING' | 'NUMBER' | 'DATE';
  readonly sortable: boolean;
  readonly searchable: boolean;
  readonly hidden?: boolean;
}

export interface RuntimeReportDefinition {
  readonly id: string;
  readonly columns: readonly RuntimeReportColumn[];
  readonly defaultSort: { readonly column: string; readonly direction: 'ASC' | 'DESC' };
  readonly defaultPageSize: number;
  readonly maxPageSize: number;
  readonly searchable: boolean;
}

export interface RuntimeReportQuery {
  readonly search?: string;
  readonly sort?: string;
  readonly direction?: string;
  readonly page?: number;
  readonly pageSize?: number;
}

export interface RuntimeReportPlan {
  readonly search: string;
  readonly sort: string;
  readonly direction: 'ASC' | 'DESC';
  readonly page: number;
  readonly pageSize: number;
  readonly offset: number;
}

export interface RuntimeMessage {
  readonly code: string;
  readonly severity: 'SUCCESS' | 'INFO' | 'WARNING' | 'ERROR';
  readonly text: string;
}

export interface RuntimeEventAction {
  readonly id: string;
  readonly event: 'CHANGE' | 'CLICK' | 'DIALOG_CLOSED' | 'PAGE_LOAD' | 'SUBMIT';
  readonly action: 'SHOW' | 'HIDE' | 'SET_VALUE' | 'REFRESH' | 'ENABLE' | 'DISABLE' | 'SUBMIT';
  readonly targetIds: readonly string[];
  readonly sequence: number;
}

export interface RuntimeLovOption {
  readonly display: string;
  readonly value: string;
}

export interface RuntimeLovDefinition {
  readonly id: string;
  readonly source: 'STATIC' | 'PROVIDER';
  readonly options?: readonly RuntimeLovOption[];
  readonly providerId?: string;
  readonly searchable: boolean;
  readonly maxRows: number;
}

export interface RuntimeNavigationEntry {
  readonly id: string;
  readonly label: string;
  readonly href: string;
  readonly pageId?: number;
  readonly sequence: number;
  readonly public: boolean;
  readonly authorizationPolicyId?: string;
}

export interface RuntimeSessionClaims {
  readonly sessionId: string;
  readonly subject: string;
  readonly issuedAtEpochSeconds: number;
  readonly expiresAtEpochSeconds: number;
  readonly authVersion: number;
}

export interface RuntimeSessionPolicy {
  readonly maxAgeSeconds: number;
  readonly clockSkewSeconds: number;
}

export interface RuntimeSessionRecord {
  readonly claims: RuntimeSessionClaims;
  readonly createdAtEpochSeconds: number;
  readonly lastSeenAtEpochSeconds: number;
}

export interface RuntimeSessionStore {
  create(record: RuntimeSessionRecord): Promise<void>;
  read(sessionId: string): Promise<RuntimeSessionRecord | null>;
  revoke(sessionId: string): Promise<void>;
  revokeAll(subject: string): Promise<void>;
}

export interface RuntimeTransaction {
  query<T = unknown>(sql: string, parameters?: readonly unknown[]): Promise<{
    readonly rows: readonly T[];
    readonly rowCount: number;
  }>;
}

export interface RuntimeTransactionRunner {
  run<T>(
    principal: RuntimePrincipal,
    work: (transaction: RuntimeTransaction) => Promise<T>,
  ): Promise<T>;
}
