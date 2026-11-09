import { ApiError } from '../lib/api';
import { processMessage } from '../lib/spec';

/** APEX success message after a dialog closed (flash key "page:PROCESS" -> process success message). */
export function SuccessMessage({ flash }: { flash?: string }) {
  const text = processMessage(flash);
  return text ? <div className="alert alert-success" role="status">{text}</div> : null;
}

/** APEX error page / inline notification for an API error. */
export function ErrorRegion({ error }: { error: unknown }) {
  if (error instanceof ApiError) {
    return <div className="alert alert-error denied" role="alert" data-error-code={error.body.code}>{error.body.message}</div>;
  }
  throw error;
}
