# Pilot target — Demo Permintaan Barang (170134)

The PostgreSQL + NestJS + Next.js target for the WP9 pilot. It is **not** production-ready, and it is not approved for shared environments.

| Path | Origin |
|---|---|
| `db/migrations/0001_wp93_schema.sql` | **Generated** (schema-plan, runner format) from `install.sql` + WP9.3b dictionary override |
| `db/migrations/0002_wp94_business_functions.sql` | **Hand-written, reviewed**: principal and role functions, `app.can_act_yn` |
| `db/migrations/0003_wp94_deferred_views.sql` | **Generated**: views that need the reviewed functions (via `db/function-mappings.json`) |
| `db/schema-plan.json`, `db/post-load-identity-alignment.sql` | Generated plan and post-load identity alignment |
| `apps/api/src/database`, `main.ts`, `health.controller.ts`, `scripts/migrate.mjs` | Copied from the WP7 generator runtime |
| `apps/api/src/business/**` | **Hand-written** WP9.4 business services ([rule catalog](../../docs/migration/wp9.4-business-logic-f170134.md)) |
| `ui/apex-page-inventory.json` | **Generated** from the APEX SQL export (`apex2next_extractor.page_inventory`) |
| `apps/*/…/ui-spec.generated.ts` | **Generated** from the inventory (`node scripts/generate-ui-spec.mjs`; `--check` in CI) |
| `ui/coverage.json` | **Reviewed** mapping of every inventory component to its target ([WP9.5](../../docs/migration/wp9.5-ui-f170134.md)) |
| `apps/api/src/auth`, `apps/api/src/pages`, `apps/api/src/http` | **Hand-written** WP9.5 session auth, page layer and error mapping |
| `apps/web/**` | **Hand-written** WP9.5 Next.js pages |
| `db/seed/dev-seed.sql` | Development/test seed (roles, REQ document type, test users). Not production data |
| `e2e/` | Playwright end-to-end journeys (Python) |

Generated files are pinned by tests to the plan. Change rules, overrides or mappings and regenerate; never edit them by hand:

```bash
export PYTHONPATH=workers/schema-analyzer/src:workers/extraction-worker/src
T=examples/f170134-target/db
python -m apex2next_schema_analyzer.schema_plan /path/to/install.sql --source-name install.sql \
  --overrides docs/migration/wp9.3/f170134/dictionary-overrides.json --function-mappings $T/function-mappings.json \
  --runner-format --apex-export /path/to/f170134/application --output $T/schema-plan.json \
  --sql-output $T/migrations/0001_wp93_schema.sql --deferred-sql-output $T/migrations/0003_wp94_deferred_views.sql \
  --post-load-output $T/post-load-identity-alignment.sql
```

Run the tests against a **disposable** database. They drop schema `app`:

```bash
cd examples/f170134-target
pnpm install --frozen-lockfile
DATABASE_URL=postgresql://user:pass@localhost:5432/disposable pnpm test
```

`APP_TIME_ZONE` (default `UTC`) sets the clock policy for every business timestamp. The API publishes the authenticated principal to PostgreSQL per transaction (`app.username`). Without a principal, every role check fails closed.

## Run the application locally (development only)

```bash
cd examples/f170134-target
pnpm install --frozen-lockfile && pnpm build
export DATABASE_URL=postgresql://user:pass@localhost:5432/disposable
ALLOW_DB_RESET=1 node apps/api/scripts/reset-dev-db.mjs          # drops schema app, migrates, seeds
(cd apps/api && AUTH_MODE=dev SESSION_SECRET=<32+ random chars> DEV_LOGIN_PASSWORD=<12+ chars> node dist/main.js) &
(cd apps/web && API_URL=http://127.0.0.1:3001 npx next start -p 3000)
```

Sign in at http://localhost:3000 with a seeded user (`ADMIN1`, `REQ1`, `REQ2`, `MGR1`, `DIR1`, `WH1`) and the dev password. `AUTH_MODE=dev` is refused when `NODE_ENV=production`. The production identity provider is WP9-009.

End-to-end tests (they start their own API and web servers on free ports):

```bash
pip install pytest playwright && python -m playwright install chromium
DATABASE_URL=postgresql://…/disposable python -m pytest e2e -p no:cacheprovider
```
