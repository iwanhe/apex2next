import { ApiError, displayError } from '../api';
import type { AppRuntime } from '../app';

/** APEX success message after a dialog closed (flash key "page:PROCESS" -> process success message). */
export function SuccessMessage({ app, flash }: { app: AppRuntime; flash?: string }) {
  const text = app.spec.processMessage(flash);
  return text ? <div className="alert alert-success" role="status">{text}</div> : null;
}

/** APEX error page / inline notification for an API error. */
export function ErrorRegion({ error }: { error: unknown }) {
  if (error instanceof ApiError && error.body.code === 'FORBIDDEN') {
    // A page authorization scheme failed: APEX shows the scheme message and "Access denied by Page security check" (J-05).
    return (
      <div className="alert alert-error denied" role="alert" data-error-code="FORBIDDEN">
        <p className="alert-title">{displayError(error.body)}</p>
        <p>Access denied by Page security check</p>
      </div>
    );
  }
  if (error instanceof ApiError) {
    return <div className="alert alert-error denied" role="alert" data-error-code={error.body.code}>{displayError(error.body)}</div>;
  }
  throw error;
}
