# Applications

- `migration-dashboard/`: Next.js control-plane UI.
- `migration-api/`: NestJS orchestration/API service.
- `generated-app/`: isolated output workspace/template for migrated applications.

Keep the generated application boundary separate from the migration platform itself. Generated code must be reproducible and must not overwrite user-owned extensions.
