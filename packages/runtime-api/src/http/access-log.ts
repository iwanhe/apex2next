import { randomUUID } from 'node:crypto';
import type { NextFunction, Request, Response } from 'express';

/**
 * One JSON line per request on stdout (WP9.7 operations): time, request id, method, path (no query string, so search
 * terms stay out of the log), status, duration and the authenticated user. The request id is taken from a valid
 * x-request-id header (the web tier may pass one) or generated, and echoed in the response. ACCESS_LOG=off disables it.
 */
export function accessLog(write: (line: string) => void = (l) => process.stdout.write(`${l}\n`)) {
  return (req: Request, res: Response, next: NextFunction) => {
    const header = req.header('x-request-id');
    const id = header && /^[\w.-]{1,64}$/.test(header) ? header : randomUUID();
    res.setHeader('x-request-id', id);
    const start = process.hrtime.bigint();
    res.on('finish', () => {
      const principal = (req as Request & { principal?: { username?: string } }).principal;
      write(JSON.stringify({
        t: new Date().toISOString(), id, method: req.method, path: req.path, status: res.statusCode,
        ms: Number((process.hrtime.bigint() - start) / 100000n) / 10, user: principal?.username ?? null,
      }));
    });
    next();
  };
}
