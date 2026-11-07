# ADR-0004: Data migration and reconciliation

- **Status:** Accepted
- **Date:** 2026-11-06
- **Decision owners:** Project owner

## Context
A successful database load does not prove source/target equivalence. Data migration must be restartable and verifiable.

## Decision
Start with offline snapshot migration using bounded chunks, durable checkpoints, retry-safe loading, PostgreSQL COPY/batched writes, and reconciliation. Add initial-plus-delta or CDC only after the source/target strategy is validated. CDC must use log-based or vendor-supported capture; polling is not CDC.

WP8.3 establishes a bounded JSONL chunk and checkpoint contract. The source extraction must use a stable Oracle snapshot SCN and deterministic unique-key keyset pagination. The target adapter must atomically apply a chunk and register its migration/chunk/checksum identity. The local checkpoint is committed only after the target confirms success. This makes target-side idempotency mandatory for the commit/checkpoint crash window.

WP8.4 compares normalized source and target evidence offline. The contract includes row counts, exact primary-key coverage (single and composite keys), configured COUNT/SUM/MIN/MAX aggregates, chunk checksums and row counts, FK violation baselines, and LOB row counts/byte lengths/SHA-256. The report is deterministic and emits PASS/WARN/FAIL plus diagnostic codes. Missing evidence is WARN, never an implicit PASS. Aggregate tolerance is explicit and applies only to SUM.

## Consequences
The first release has a manageable operating model. Low-downtime migration is a later capability with additional infrastructure and testing. Generated SQL and extracted data are never executed or loaded automatically by the offline analyzer. Operational chunk files and checkpoint state require encryption, access control, backup, and retention policies.

A reconciliation PASS means only that the supplied evidence matches under the declared comparison rules. It does not establish SQL semantic equivalence, timezone/collation compatibility, Oracle empty-string behavior, LOB canonicalization correctness, or application/business behavior. Representative sanitized Oracle and disposable PostgreSQL validation remains mandatory before production qualification.
