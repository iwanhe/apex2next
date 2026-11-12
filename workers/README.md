# Durable Workers

- extraction-worker: source ingestion, APEX metadata, Oracle inventory.
- conversion-worker: AST/IR transformation and target code generation.
- data-worker: chunked ETL, checkpointing, retry, reconciliation.
- validation-worker: schema, data, functional, security, and performance evidence.

Workers must be restartable, observable, bounded in memory, and safe to retry. Do not run long migration jobs inside short-lived HTTP/serverless requests.
