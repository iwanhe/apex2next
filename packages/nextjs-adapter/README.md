# @apex2next/nextjs-adapter

Reusable React server-component-compatible UI adapters for generated Next.js App Router applications.

## Included

- `RuntimeForm`: renders typed APEX page items, required labels, display-only values, LOV options, help text and inline validation messages.
- `RuntimeReportTable`: renders visible report columns, row values and an accessible empty state.
- Components are server-rendering compatible and contain no client-side state, arbitrary expression evaluation, or direct database access.

## Boundaries

- The NestJS/API layer remains responsible for authorization, validation, transaction boundaries and report query execution.
- Do not pass untrusted HTML or source expressions to these components.
- Interactive Report sorting, search, facets, dialogs, dynamic actions, navigation and download behavior are adapter extensions planned for subsequent R2 slices.
- Styling is intentionally minimal; generated applications may wrap the components with their own design system.
