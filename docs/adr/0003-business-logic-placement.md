# ADR-0003: Business logic placement

- **Status:** Accepted
- **Date:** 2026-11-06
- **Decision owners:** Project owner

## Context
APEX applications commonly distribute behavior across page processes, validations, dynamic actions, database packages, and triggers.

## Decision
Place presentation in Next.js; authorization, orchestration, and business services in NestJS; data integrity and set-based/data-proximate logic in PostgreSQL; durable scheduled work in background workers. Do not move business rules into browser code.

## Consequences
Logic placement is explicit and testable. Some package/session-state patterns require redesign rather than direct translation. Transaction boundaries and concurrency behavior must be validated.
