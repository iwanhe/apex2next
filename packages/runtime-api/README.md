# @apex2next/runtime-api

Shared NestJS runtime for applications converted from Oracle APEX (roadmap **R2**).
It was extracted from the pilot app 170134 without changing behaviour. The acceptance gate was the API tests, the e2e tests and the parity journeys J-01…J-05, all passing after the move.

## What it contains

| Module | Exports | Notes |
|---|---|---|
| `errors`, `context` | `BusinessRuleError`, `errors`, `Principal`, `BusinessDatabase`/`BusinessTx`, `clockFromEnv` | `APP_CLOCK_START` (test clock) is refused when `NODE_ENV=production` |
| `database/*` | `PostgresDatabase`, `PostgresRepository`, `DatabaseModule`, `DatabaseHealthService` | Publishes the principal per transaction (`app.username`). Uses `jit=off` unless `PG_JIT=on`. `application_name` comes from `PG_APPLICATION_NAME` (default `apex2next-api`) |
| `http/error.filter` | `ApiErrorFilter`, `mapDatabaseError(error, {oracleSchema})` | Maps PostgreSQL errors to APEX/Oracle-style messages. The app passes its source schema name |
| `http/access-log` | `accessLog()` | One JSON line per request: time, request id, method, path without query string, status, duration, user. `ACCESS_LOG=off` disables it |
| `auth/*` | `AuthModule`, `AuthGuard`, `AccountsService`, password/session helpers | `AUTH_MODE=dev` (refused in production) or `local` (schema `iam`: scrypt, forced change, temporary-password expiry, lockout, rate limit, session revocation, audit) |
| `reports/report` | Report engine | Interactive/classic reports: search, sort on the source column, paging (rows per page from the definition), facets |
| `reports/region-source` | `RegionSource`, `LovSource`, `bindRegionSources(spec, {schema})` → `{regionColumns, regionDefaultSort, reportDef, lovSql}` | Turns the generated region and LOV sources (R3) into report definitions and LOV SQL |
| `forms/forms` | `bindUiSpec(spec)` → `{formDef, result}` | Form definitions read from the app's generated UI spec |
| `generic/interactive-grid` | `applyInteractiveGridChanges(tx, form, changes)` | Bounded (max 100) transactional grid changes; caller owns authorization and transaction |

## How an app uses it

```ts
import { ApiErrorFilter, bindUiSpec } from '@apex2next/runtime-api';

export const { formDef, result } = bindUiSpec(UI_SPEC);
// app.module.ts
{ provide: APP_FILTER, useFactory: () => new ApiErrorFilter({ oracleSchema: process.env.DB_ERROR_SCHEMA ?? 'WKSP_KCSI' }) }
```

The app keeps what is specific to it: business services, page/report definitions and migrations.
The `iam` schema migrations still live in the app (`db/migrations/0004*`, `0005*`).

## Build

The package is compiled with `tsc` to CommonJS in `dist/`. Build it before the app: `pnpm --filter @apex2next/runtime-api build`. The pilot's `pnpm typecheck` does this first.
NestJS and `pg` are peer dependencies, so the app and the package share one instance.


## Interactive Grid DML primitive (R4a)

The runtime exports `applyInteractiveGridChanges(tx, form, changes)`. It accepts a bounded batch of insert/update/delete operations, validates submitted columns through the native form rules, and requires the existing lost-update checksum for update/delete. Duplicate row IDs are rejected.

This is intentionally **not** an HTTP endpoint and does not infer authorization. An application page service must check its page/process authorization first and call the helper inside `BusinessDatabase.run`; the enclosing transaction provides all-or-nothing commit/rollback. Do not call it with a client-created `FormDef`: use the form definition bound to the trusted generated UI spec. Editable IG generation remains gated until source metadata, row authorization, and parity behavior are mapped.
