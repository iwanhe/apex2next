# ADR-0001: Target stack and migration boundary

- **Status:** Accepted
- **Date:** 2026-11-06
- **Decision owners:** Project owner

## Context
The goal is to migrate Oracle APEX and Oracle Database applications to a modern web stack while removing Oracle runtime dependency after cutover.

## Decision
Use Next.js + TypeScript for UI, NestJS + TypeScript for APIs/orchestration, and PostgreSQL as the target operational database. Support local and cloud deployment. Oracle remains a source platform during migration only.

## Options considered
- Retain Oracle Database and replace only APEX.
- Move UI/API but retain Oracle database.
- Move application and database to PostgreSQL.

## Consequences
The selected approach enables a single PostgreSQL operational target but requires comprehensive data, PL/SQL, integration, security, and semantic migration. Oracle-specific runtime behavior must be identified and replaced before cutover.
