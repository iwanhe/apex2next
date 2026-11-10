# @apex2next/shared-runtime

Framework-neutral runtime contracts and deterministic policy helpers shared by generated APEX2NEXT applications.

## Included in R2 foundation

- Runtime contracts for applications, pages, page items, regions, buttons, authorization policies, principals, reports, messages, and event actions.
- APEX-style item normalization and validation (empty string to NULL, trim policy, required, numeric bounds, ISO date validation, maximum length).
- Fail-closed authorization evaluation (ANY_ROLE, ALL_ROLES, REGISTERED).
- Safe report request planning (allowlisted sortable columns, validated direction, bounded page size, stable offset).

This package deliberately does **not** execute PL/SQL, SQL fragments, APEX condition expressions, or dynamic-action source expressions. Database-specific SQL generation and framework adapters remain separate layers.

## Development

```bash
pnpm --filter @apex2next/shared-runtime typecheck
pnpm --filter @apex2next/shared-runtime test
```

## Compatibility notes

The validation helper currently supports ISO `YYYY-MM-DD` dates only. APEX format-mask parsing, LOV resolution, authorization scheme extraction, dynamic-action execution, transaction orchestration, and UI adapters are follow-on R2 slices. Do not claim full APEX parity from this foundation package.
