# Oracle → PostgreSQL / APEX → Next.js Migration Rules

## 1. Rule governance

Every conversion rule has: stable rule ID, source construct, target construct, preconditions, transformation, semantic caveats, test fixtures, severity, and version. Rule changes must run regression fixtures. A rule must not report AUTO if semantic equivalence is uncertain.

## 2. Oracle data type mapping

| Oracle | PostgreSQL starting point | Review notes |
|---|---|---|
| NUMBER(p,0) | SMALLINT / INTEGER / BIGINT / NUMERIC | Choose by precision and range; avoid narrowing |
| NUMBER(p,s) | NUMERIC(p,s) | Preserve precision/scale |
| NUMBER unconstrained | NUMERIC | Assess actual range and performance |
| VARCHAR2 / NVARCHAR2 | VARCHAR / TEXT | Validate character semantics and length |
| CHAR / NCHAR | CHAR | Review padding and collation |
| CLOB / NCLOB | TEXT | Validate encoding and size |
| BLOB / RAW | BYTEA | Preserve binary bytes |
| LONG | TEXT | Legacy type; verify extraction support |
| DATE | TIMESTAMP(0) | Oracle DATE includes time-of-day |
| TIMESTAMP | TIMESTAMP | Precision and timezone assumptions must be explicit |
| TIMESTAMP WITH TIME ZONE | TIMESTAMPTZ | Validate normalization and original zone requirements |
| INTERVAL | INTERVAL | Validate supported fields/precision |
| BINARY_FLOAT | REAL | Check precision tolerance |
| BINARY_DOUBLE | DOUBLE PRECISION | Check precision tolerance |
| XMLTYPE | XML or TEXT | Depends on operations and indexing |
| UROWID | TEXT | Review whether value is persisted or transient |

## 3. SQL mappings

| Oracle construct | PostgreSQL approach | Caveat |
|---|---|---|
| NVL | COALESCE | Type resolution can differ |
| DECODE | CASE | Check null and implicit conversion behavior |
| SYSDATE | CURRENT_TIMESTAMP / LOCALTIMESTAMP | Choose transaction/timezone semantics |
| SYSTIMESTAMP | CURRENT_TIMESTAMP | Validate precision/timezone |
| DUAL | Remove | No equivalent needed for scalar SELECT |
| ROWNUM | LIMIT / ROW_NUMBER | Ordering and nesting matter |
| CONNECT BY / START WITH | Recursive CTE | Preserve cycle/order/path semantics |
| Oracle outer join (+) | Explicit JOIN | Rewrite predicate placement carefully |
| LISTAGG | STRING_AGG | Ordering, overflow, distinct semantics |
| INSTR | POSITION or helper | Argument semantics differ |
| SUBSTR | SUBSTRING | Negative indexes/length need tests |
| ADD_MONTHS | Date arithmetic/helper | End-of-month behavior must be tested |
| TO_DATE / TO_CHAR | PostgreSQL format functions | Format model differences |
| MERGE | INSERT ON CONFLICT / MERGE | Match conditions and concurrency semantics |
| MINUS | EXCEPT | Duplicate semantics |
| RAWTOHEX | ENCODE(..., 'hex') | Binary input |
| HEXTORAW | DECODE(..., 'hex') | Validate malformed input behavior |

## 4. PL/SQL mapping

| Oracle | Target strategy | Review trigger |
|---|---|---|
| Procedure/function | PL/pgSQL or NestJS service | Placement based on transaction/data proximity |
| Package | PostgreSQL schema/functions or NestJS service | Package state, initialization, overloads |
| Cursor/ref cursor | Cursor or API result/stream | Lifetime and transaction semantics |
| RECORD | Composite type or TypeScript interface | Nullability and field typing |
| Collections | Arrays, JSONB, temp/relational tables | Choose based on access/update semantics |
| BULK COLLECT | Set-based query/array/stream | Memory and ordering |
| FORALL | Set-based SQL/batch | Per-row error behavior |
| SAVE EXCEPTIONS | Explicit batch error collection | Preserve partial success semantics |
| PRAGMA EXCEPTION_INIT | Exception mapping | SQLSTATE mapping |
| RAISE_APPLICATION_ERROR | RAISE EXCEPTION or typed HTTP error | Error contract |
| DBMS_OUTPUT | Structured logger | Do not use as business output |
| DBMS_SCHEDULER / DBMS_JOB | Durable job/worker scheduler | Retry, timezone, overlap semantics |
| EXECUTE IMMEDIATE | Parameterized dynamic SQL | Identifiers must be allowlisted |
| Autonomous transaction | Separate transaction/service design | Not a direct mechanical translation |
| DBMS_LOB | TEXT/BYTEA operations | Large-object streaming |
| DBMS_LOCK | PostgreSQL advisory locks | Lock scope and transaction behavior |

## 5. APEX UI mappings

| APEX feature | Next.js/NestJS target | Review trigger |
|---|---|---|
| Page | App Router route | Page lifecycle and session state |
| Region | React component | Region plug-in/custom template |
| Page item | Typed form/state field | Session state and protection |
| Form | React Hook Form + Zod + API | DML/process side effects |
| Interactive Report | TanStack Table | Saved reports, filters, exports |
| Interactive Grid | Editable table + API | Row processing, validations, concurrency |
| LOV | Select/autocomplete API | Cascading LOV and authorization |
| Dynamic Action | React handler/hook + API | PL/SQL/AJAX/condition side effects |
| Branch | Router navigation | Conditional branch behavior |
| Validation | Zod + server-side domain validation | Must not rely on client validation alone |
| Authorization Scheme | Server-side permission guard | Unknown rule defaults to deny |
| Chart | Chart component | Aggregation and drill-down parity |
| Shared Component | Shared package/config | Dependency and application scope |

## 6. Semantic traps that require tests

- Oracle treats empty string as NULL for character values; PostgreSQL distinguishes them.
- NULL concatenation, three-valued logic, and implicit conversions differ.
- Oracle DATE contains time-of-day.
- Sequence behavior and identity synchronization differ.
- Transaction boundaries, exception propagation, and autonomous transactions differ.
- Package-level state and APEX session state have no automatic one-to-one equivalent.
- Timezone, NLS settings, collation, numeric formatting, and date format models differ.
- Identifier folding/case and reserved words differ.
- Dynamic SQL, database links, external calls, file access, scheduler, and custom plugins require explicit dependency treatment.

## 7. Compatibility policy

Prefer native PostgreSQL and explicit application code. Orafce may be evaluated for selected compatibility functions, but it is not a complete semantic compatibility guarantee. Any compatibility function must be documented, tested, and scheduled for ownership/maintenance.

## 8. Status policy

- AUTO: deterministic and semantics understood.
- AUTO_TEST: generated, targeted parity tests mandatory.
- REVIEW: human decision or modification required.
- BLOCKED: unsafe/unsupported until resolved.
- ERROR: execution failed.

No object may disappear from reports because parsing failed.
