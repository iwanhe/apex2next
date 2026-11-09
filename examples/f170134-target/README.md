# Pilot target — Demo Permintaan Barang (170134)

The PostgreSQL + NestJS target for the WP9 pilot. It is **not** production-ready, and it is not approved for shared environments.

| Path | Origin |
|---|---|
| `db/migrations/0001_wp93_schema.sql` | **Generated** (schema-plan, runner format) from `install.sql` + WP9.3b dictionary override |
| `db/migrations/0002_wp94_business_functions.sql` | **Hand-written, reviewed**: principal and role functions, `app.can_act_yn` |
| `db/migrations/0003_wp94_deferred_views.sql` | **Generated**: views that need the reviewed functions (via `db/function-mappings.json`) |
| `db/schema-plan.json`, `db/post-load-identity-alignment.sql` | Generated plan and post-load identity alignment |
| `apps/api/src/database`, `main.ts`, `health.controller.ts`, `scripts/migrate.mjs` | Copied from the WP7 generator runtime |
| `apps/api/src/business/**` | **Hand-written** WP9.4 business services ([rule catalog](../../docs/migration/wp9.4-business-logic-f170134.md)) |

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
