# @apex2next/nestjs-adapter

NestJS boundary adapters for the framework-neutral `@apex2next/shared-runtime` package.

## Included

- `RuntimePolicyGuard`: resolves a named authorization policy and evaluates it against an authenticated request principal. Missing policy metadata is denied by default.
- `RequireRuntimePolicy(id)`: attaches the policy ID to a controller or route handler.
- `PublicRuntimeRoute()`: explicitly opts a route out of authorization checks (use only for intentional public endpoints).
- `RuntimePageItemsPipe`: normalizes and validates submitted APEX page items using the shared validation engine, returning structured HTTP 400 errors.

## Integration

Register a provider for `RUNTIME_POLICY_RESOLVER` in the consuming NestJS module and register `RuntimePolicyGuard` as a global or route guard. Authentication middleware/guards must populate `request.user` with a verified `RuntimePrincipal` before this guard executes.

```ts
{
  provide: RUNTIME_POLICY_RESOLVER,
  useExisting: ApplicationPolicyService,
}
```

```ts
@UseGuards(RuntimePolicyGuard)
@RequireRuntimePolicy('APP_USERS')
@Get()
list() { /* ... */ }

@PublicRuntimeRoute()
@Get('health')
health() { /* ... */ }
```

Do not treat client-supplied role values as trusted identity claims. The request principal must come from a verified authentication layer.
