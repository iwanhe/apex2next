import type { FieldError } from './api';

/** Serializable description of one APEX form dialog, bound to the server action by the page. */
export interface FormBinding {
  /** API form name: request, requestLine, department, item, userRole, docType, approval. */
  readonly form: string;
  readonly id: string | null;
  readonly returnTo: string;
  /** Columns posted for this render (read-only items are not submitted, like APEX). */
  readonly columns: string[];
  /** Database action of each submit button (create_page_button p_database_action), for any button name. */
  readonly dml?: Readonly<Record<string, 'INSERT' | 'UPDATE' | 'DELETE'>>;
}

export interface FormState {
  readonly error: string | null;
  readonly fieldErrors: FieldError[];
  readonly values: Record<string, string> | null;
  readonly version: number;
}
