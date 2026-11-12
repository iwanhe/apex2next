# @apex2next/runtime-web

Shared Next.js (App Router, React 19) runtime for applications converted from Oracle APEX (roadmap **R2**).
It was extracted from the pilot app 170134 without changing behaviour. The acceptance gate was the e2e tests and the parity journeys J-01…J-05, all passing after the move.

## What it contains

| Path | Purpose |
|---|---|
| `spec` | `createAppSpec(UI_SPEC)`: app title, navigation, breadcrumbs, pages, items, buttons, LOVs, APEX process messages |
| `api`, `session`, `guard` | Server-side API client (forwards the session cookie), current session, page guard (APEX-style "Access denied") |
| `authz` | `buttonAllowed(spec, pageId, button)`: honours button authorization schemes |
| `format` | APEX-compatible number and date formatting |
| `routes` | `first`, `all`, `qs`, `safeReturn` (no open redirects) |
| `forms`, `form-types`, `form-submit` | APEX form model and `submitApexForm` (CREATE/SAVE/DELETE plus app-defined requests) |
| `facets-view` | Faceted search view model |
| `download` | `downloadRegion(req, region, titles)`: Interactive Report download (CSV, HTML) in the APEX format |
| `components/*` | `Shell`, `PageHeader`, `NavLink`, `Alerts`, `ApexForm`, `FormDialog`, `Dialog`, `IrPage`, `FacetedPage`, `ReportTable`, `Facets`, `Charts` |

Components that need app data take an `app: AppRuntime` prop (`{spec, routes, submit}`).
`IrPage`, `FacetedPage` and `FormDialog` are the page patterns that `apex2next generate` writes pages for (R3).

## How an app uses it

1. Add the dependency `"@apex2next/runtime-web": "workspace:*"`.
2. In `next.config.ts`, set `transpilePackages: ['@apex2next/runtime-web']`. The package ships TypeScript source.
3. In `tsconfig.json`, use `"moduleResolution": "bundler"`.
4. Bind the runtime once:
   ```ts
   // lib/app.ts
   export const APP: AppRuntime = { spec: createAppSpec(UI_SPEC), routes: PAGE_ROUTES, submit: submitApexForm };
   ```
   `submitApexForm` is the app's own `'use server'` action, which wraps the package function with the app's extra requests.
5. Add thin wrappers in `components/` that inject `APP`. The pilot shows the pattern.

## Test

`pnpm --filter @apex2next/runtime-web test` runs the formatting tests.
