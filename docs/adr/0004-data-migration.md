# ADR-0004: Data migration and reconciliation

- **Status:** Accepted
- **Date:** 2026-11-06
- **Decision owners:** Project owner

## Context
A successful database load does not prove source/target equivalence. Data migration must be restartable and verifiable.

## Decision
Start with offline snapshot migration using bounded chunks, durable checkpoints, retry-safe loading, PostgreSQL COPY/batched writes, and reconciliation. Add initial-plus-delta or CDC only after the source/target strategy is validated. CDC must use log-based or vendor-supported capture; polling is not CDC.

Reconciliation includes row counts, key coverage, business aggregates, chunk checksums, LOB length/hash, and referential integrity.

## Consequences
The first release has a manageable operating model. Low-downtime migration is a later capability with additional infrastructure and testing.
