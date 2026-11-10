import { ApiError } from './api';

/** Rethrows anything that is not an API error (redirects, crashes); API errors are rendered by the page. */
export function apiErrorOnly(e: unknown): ApiError {
  if (e instanceof ApiError) return e;
  throw e;
}
