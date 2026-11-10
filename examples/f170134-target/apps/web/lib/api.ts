import 'server-only';
import { redirect } from 'next/navigation';
import { sessionToken } from './session';

/**
 * Server-side client of the NestJS API. The browser never talks to the API directly; the session token
 * travels from the httpOnly cookie to the Authorization header here.
 */
const API_URL = process.env.API_URL ?? 'http://127.0.0.1:3001';

export interface FieldError { field: string | null; message: string }
export interface ApiErrorBody { code: string; message: string; oracleCode?: number | null; rule?: string; fieldErrors?: FieldError[] }

/**
 * Text APEX shows for an error: errors raised with RAISE_APPLICATION_ERROR keep their "ORA-2xxxx: " prefix
 * (observed on oracleapex.com, WP9.6); other messages already carry their ORA code or none.
 */
export function displayError(body: ApiErrorBody): string {
  const code = body.oracleCode;
  return typeof code === 'number' && code <= -20000 && code >= -20999 ? `ORA-${-code}: ${body.message}` : body.message;
}

export class ApiError extends Error {
  constructor(readonly status: number, readonly body: ApiErrorBody) {
    super(body.message);
  }
}

async function call<T>(method: string, path: string, body?: unknown, token?: string | null, extra: Record<string, string> = {}): Promise<T> {
  const auth = token === undefined ? await sessionToken() : token;
  const res = await fetch(`${API_URL}${path}`, {
    method, cache: 'no-store',
    headers: { ...extra, ...(auth ? { authorization: `Bearer ${auth}` } : {}), ...(body !== undefined ? { 'content-type': 'application/json' } : {}) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  const json = text ? JSON.parse(text) : null;
  if (!res.ok) throw new ApiError(res.status, json ?? { code: 'HTTP_ERROR', message: res.statusText });
  return json as T;
}

/** GET without the redirects of apiGet (for the change-password page itself). */
export function apiGetRaw<T>(path: string): Promise<T> {
  return call<T>('GET', path);
}

/** GET for server components: an expired/missing session sends the user to the login page. */
export async function apiGet<T>(path: string): Promise<T> {
  try {
    return await call<T>('GET', path);
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) redirect('/login');
    if (e instanceof ApiError && e.body.code === 'PASSWORD_CHANGE_REQUIRED') redirect('/account/password');
    throw e;
  }
}

export function apiSend<T>(method: 'POST' | 'PUT' | 'DELETE', path: string, body?: unknown, token?: string | null,
  headers?: Record<string, string>): Promise<T> {
  return call<T>(method, path, body ?? {}, token, headers);
}

export interface Session {
  username: string;
  schemes: Record<string, boolean>;
  appAccessDenied: string | null;
  /** 'local': accounts in schema iam (Change Password available); 'dev': test mode. */
  authMode?: 'local' | 'dev';
}

export interface ReportColumn {
  name: string; type: 'STRING' | 'NUMBER' | 'DATE'; hidden: boolean;
  label?: string | null; format?: string | null; align?: string | null; order?: number;
}
export interface ReportResult {
  rows: Record<string, string | null>[];
  total: number; page: number; rowsPerPage: number;
  sort: { column: string; dir: 'ASC' | 'DESC' };
  facets: { item: string; values: { value: string; count: number }[] }[];
  columns: ReportColumn[];
}
export interface FormResponse {
  values: Record<string, string | null>;
  checksum: string | null;
  buttons: Record<string, boolean>;
  readOnly?: Record<string, boolean>;
}
export interface LovEntry { display: string; value: string }
