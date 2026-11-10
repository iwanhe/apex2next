import { PoolClient } from 'pg';
import { PostgresDatabase } from './database/postgres-database';
import { errors } from './errors';

/**
 * Authenticated principal. Replaces APEX APP_USER / SYS_CONTEXT('APEX$SESSION','APP_USER') and the
 * test-only APX_DEMO_SEC_PKG.SET_TEST_USER override (BR-SEC-01). Built only from a verified identity
 * (WP9-009), never from client-supplied fields.
 */
export interface Principal {
  readonly username: string;
}

export function principal(username: string | null | undefined): Principal {
  const normalized = (username ?? '').trim().toUpperCase();
  if (!normalized) throw errors.unauthenticated();
  if (normalized.length > 255) throw errors.invalidInput('Username melebihi 255 karakter.');
  return { username: normalized };
}

/**
 * One clock policy for every business timestamp (replaces SYSDATE). Oracle DATE columns became
 * timestamp(0) without time zone, so the wall-clock value is computed in a single configured zone.
 * Default 'UTC' matches the source database (oracleapex.com SYSTIMESTAMP offset +00:00); the
 * owner decision on timezone policy (WP9.3 decision 3) may change APP_TIME_ZONE.
 */
export interface Clock {
  now(): Date;
}

export const systemClock: Clock = { now: () => new Date() };

/**
 * APP_CLOCK_START (ISO instant; tests and parity replays only): the business clock starts at that instant and runs
 * forward in real time, so a journey recorded on APEX on one day can be replayed later with the same dates.
 * Refused with NODE_ENV=production.
 */
export function clockFromEnv(env: NodeJS.ProcessEnv = process.env, realNow: () => number = Date.now): Clock {
  const start = env.APP_CLOCK_START;
  if (!start) return systemClock;
  if (env.NODE_ENV === 'production') throw new Error('APP_CLOCK_START is refused when NODE_ENV=production.');
  const t = Date.parse(start);
  if (Number.isNaN(t) || !/T.*(Z|[+-]\d\d:\d\d)$/.test(start)) throw new Error('APP_CLOCK_START must be an ISO instant with a zone, e.g. 2026-11-09T07:45:00Z.');
  const offset = t - realNow();
  return { now: () => new Date(realNow() + offset) };
}

export function wallClock(date: Date, timeZone: string): { timestamp: string; date: string; year: string } {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
  }).formatToParts(date);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? '';
  const day = `${get('year')}-${get('month')}-${get('day')}`;
  return { timestamp: `${day} ${get('hour')}:${get('minute')}:${get('second')}`, date: `${day} 00:00:00`, year: get('year') };
}

export interface BusinessConfig {
  readonly timeZone: string;
}

export function businessConfigFromEnv(env: NodeJS.ProcessEnv = process.env): BusinessConfig {
  const timeZone = env.APP_TIME_ZONE ?? 'UTC';
  try {
    new Intl.DateTimeFormat('en-CA', { timeZone });
  } catch {
    throw new Error(`APP_TIME_ZONE ${timeZone} is not a valid IANA time zone.`);
  }
  return { timeZone };
}

/** Transaction-scoped business context: the database client, the principal and the clock. */
export class BusinessTx {
  private cachedNow?: ReturnType<typeof wallClock>;

  constructor(
    readonly client: PoolClient,
    readonly principal: Principal,
    private readonly clock: Clock,
    private readonly config: BusinessConfig,
  ) {}

  /** One timestamp per transaction, like repeated SYSDATE calls in one short PL/SQL call. */
  get now(): ReturnType<typeof wallClock> {
    this.cachedNow ??= wallClock(this.clock.now(), this.config.timeZone);
    return this.cachedNow;
  }

  query<Row extends Record<string, any> = Record<string, any>>(text: string, values: unknown[] = []) {
    return this.client.query<Row>(text, values);
  }
}

/**
 * Runs business work in one transaction with the principal published to PostgreSQL as the
 * transaction-local setting app.username (read by app.current_username(), app.has_role(),
 * app.can_act_yn() and the approvals view).
 */
export class BusinessDatabase {
  constructor(
    private readonly database: PostgresDatabase,
    private readonly clock: Clock = systemClock,
    private readonly config: BusinessConfig = businessConfigFromEnv(),
  ) {}

  run<T>(actor: Principal, work: (tx: BusinessTx) => Promise<T>): Promise<T> {
    if (!actor || !actor.username) throw errors.unauthenticated();
    return this.database.transaction(async (client) => {
      await client.query("SELECT set_config('app.username', $1, true)", [actor.username]);
      return work(new BusinessTx(client, actor, this.clock, this.config));
    });
  }
}
