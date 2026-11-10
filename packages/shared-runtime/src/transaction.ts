/** Raised when a form submits a stale version token (lost-update protection). */
export class RuntimeVersionMismatchError extends Error {
  readonly code = 'LOST_UPDATE';

  constructor() {
    super('Current version of data has changed since it was loaded.');
    this.name = 'RuntimeVersionMismatchError';
  }
}

/** Compares an opaque server-issued version token; missing tokens fail closed. */
export function assertRuntimeVersion(expected: unknown, actual: unknown): void {
  if (typeof expected !== 'string' || expected.length === 0
    || typeof actual !== 'string' || actual.length === 0
    || expected !== actual) {
    throw new RuntimeVersionMismatchError();
  }
}
