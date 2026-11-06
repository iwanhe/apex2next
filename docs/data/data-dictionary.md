# APEX2NEXT — Core Data Dictionary

This is the initial logical dictionary for the migration control-plane database. Physical DDL and detailed constraints will be delivered as versioned migrations.

## Conventions

- Primary keys: UUID.
- Timestamps: TIMESTAMPTZ in UTC.
- Statuses: constrained text or PostgreSQL enum only after lifecycle values stabilize.
- JSONB: variable metadata/evidence, not core relational keys.
- Sensitive connection details: secret reference only; never plaintext credentials.

## platform.project

| Column | Type | Rules / description |
|---|---|---|
| id | UUID | PK |
| project_code | VARCHAR(50) | Unique, required |
| project_name | VARCHAR(200) | Required |
| description | TEXT | Optional |
| status | VARCHAR(30) | Draft, active, paused, completed, archived |
| created_at | TIMESTAMPTZ | Required |
| updated_at | TIMESTAMPTZ | Required |

## source.application

| Column | Type | Rules / description |
|---|---|---|
| id | UUID | PK |
| project_id | UUID | FK platform.project |
| app_id | VARCHAR(100) | Source APEX application identifier |
| app_name | VARCHAR(255) | Required |
| apex_version | VARCHAR(50) | Nullable until detected |
| source_schema | VARCHAR(128) | Source schema |
| export_hash | CHAR(64) | SHA-256 of imported export, when present |
| metadata | JSONB | Version-specific extracted metadata |
| created_at | TIMESTAMPTZ | Required |

## source.source_object

| Column | Type | Rules / description |
|---|---|---|
| id | UUID | PK |
| application_id | UUID | FK source.application |
| object_type | VARCHAR(80) | Table, package, page, region, process, etc. |
| object_name | VARCHAR(512) | Required |
| source_hash | CHAR(64) | Hash of normalized source representation |
| source_location | JSONB | Export path, schema, page/item coordinates |
| metadata | JSONB | Type-specific attributes |
| disposition | VARCHAR(20) | AUTO, AUTO_TEST, REVIEW, BLOCKED, ERROR |

## analysis.dependency

| Column | Type | Rules / description |
|---|---|---|
| id | UUID | PK |
| source_object_id | UUID | FK source.source_object |
| target_object_id | UUID | FK source.source_object |
| dependency_type | VARCHAR(80) | Calls, reads, writes, renders, authorizes, etc. |
| confidence | NUMERIC(5,4) | 0.0000–1.0000 |
| evidence | JSONB | Evidence/source location |
| UNIQUE | — | source_object_id, target_object_id, dependency_type |

## conversion.result

| Column | Type | Rules / description |
|---|---|---|
| id | UUID | PK |
| run_id | UUID | FK migration.run |
| source_object_id | UUID | FK source.source_object |
| target_type | VARCHAR(80) | Target artifact category |
| generated_path | TEXT | Artifact path or object storage URI |
| target_hash | CHAR(64) | Generated artifact hash |
| rule_set_version | VARCHAR(80) | Required |
| status | VARCHAR(20) | AUTO, AUTO_TEST, REVIEW, BLOCKED, ERROR |
| created_at | TIMESTAMPTZ | Required |

## migration.run and migration.task

| Column | Type | Rules / description |
|---|---|---|
| migration.run.id | UUID | PK |
| migration.run.project_id | UUID | FK platform.project |
| migration.run.run_number | INTEGER | Unique within project |
| migration.run.status | VARCHAR(30) | Queued, running, failed, completed, cancelled |
| migration.run.started_at | TIMESTAMPTZ | Nullable until started |
| migration.run.completed_at | TIMESTAMPTZ | Nullable until terminal |
| migration.task.id | UUID | PK |
| migration.task.run_id | UUID | FK migration.run |
| migration.task.task_type | VARCHAR(80) | Stage/action |
| migration.task.status | VARCHAR(30) | Queued, running, retrying, failed, completed |
| migration.task.idempotency_key | VARCHAR(255) | Required for retry-safe tasks |

## migration.data_transfer and validation.data_validation

| Column | Type | Rules / description |
|---|---|---|
| data_transfer.id | UUID | PK |
| data_transfer.run_id | UUID | FK migration.run |
| data_transfer.source_table | TEXT | Qualified source table |
| data_transfer.target_table | TEXT | Qualified target table |
| data_transfer.rows_migrated | BIGINT | Non-negative |
| data_transfer.checksum | TEXT | Aggregate/chunk checksum reference |
| data_validation.id | UUID | PK |
| data_validation.transfer_id | UUID | FK migration.data_transfer |
| data_validation.validation_type | VARCHAR(80) | Count, checksum, aggregate, orphan, LOB |
| data_validation.source_value | JSONB | Source-side evidence |
| data_validation.target_value | JSONB | Target-side evidence |
| data_validation.status | VARCHAR(20) | Passed, failed, warning, skipped |

## deployment.target_environment and deployment.release

| Column | Type | Rules / description |
|---|---|---|
| target_environment.id | UUID | PK |
| target_environment.project_id | UUID | FK platform.project |
| target_environment.environment_name | VARCHAR(30) | Local, DEV, QA, UAT, STAGING, PROD |
| target_environment.config_ref | TEXT | Secret/config reference, not secret value |
| release.id | UUID | PK |
| release.environment_id | UUID | FK deployment.target_environment |
| release.release_version | VARCHAR(80) | Required |
| release.status | VARCHAR(30) | Prepared, deployed, failed, rolled_back |

## audit.audit_event

| Column | Type | Rules / description |
|---|---|---|
| id | UUID | PK |
| project_id | UUID | FK platform.project, nullable for global events |
| actor_id | UUID | Identity reference |
| action | VARCHAR(120) | Required |
| resource_type | VARCHAR(80) | Optional |
| resource_id | UUID | Optional |
| details | JSONB | Redacted event metadata |
| occurred_at | TIMESTAMPTZ | Required; append-only |

The physical schema must add indexes, foreign keys, check constraints, retention rules, and partitioning where justified by measured volume.
