# WP9.2 — PostgreSQL Conversion Dispositions: Demo Permintaan Barang (170134)

## Disposition policy

- AUTOMATIC: only where syntax and behavior are demonstrated equivalent. No business PL/SQL behavior is AUTOMATIC in this assessment.
- ASSISTED: candidate mapping exists but requires review and tests.
- MANUAL: redesign/business decision required.
- UNSUPPORTED: no safe direct target equivalent currently defined.

## Table dispositions

| Table | Source features | Current converter | Disposition / action |
|---|---|---|---|
| ROLES | VARCHAR2, PK | Eligible | ASSISTED — review collation/case/empty-string behavior |
| DOC_TYPES | VARCHAR2, NUMBER, defaults, two role FKs | Eligible | ASSISTED — review configuration governance |
| DOC_SEQ | Composite PK, NUMBER default | Eligible | ASSISTED — atomic concurrent numbering |
| USER_ROLES | Identity, unique, FK, audit | Blocked identity | ASSISTED — map BY DEFAULT ON NULL identity and audit |
| APPROVALS | Identity, status CHECK, FK, DATE | Blocked identity | ASSISTED — identity/check/timestamp/workflow review |
| DEPARTMENTS | Identity, unique, CHECK | Blocked identity | ASSISTED — identity and check preservation |
| ITEMS | Identity, unique, 3 CHECKs | Blocked identity | ASSISTED — identity and check preservation |
| REQUESTS | Identity, unique, status CHECK, DATE | Blocked identity | ASSISTED — identity, check, date and state model |
| REQUEST_LINES | Identity, virtual generated column, 2 CHECKs, cascade FK | Blocked identity/generated | MANUAL — stored generated value or computed projection; preserve cascade |

The SQL draft emits only ROLES, DOC_TYPES and DOC_SEQ. No table is production-qualified because no Oracle dictionary or data evidence is available.

## SQL feature dispositions

| Oracle construct | Candidate target | Disposition | Review |
|---|---|---|---|
| VARCHAR2(n) | varchar(n) | ASSISTED | BYTE/CHAR semantics; empty string |
| NUMBER(p,0) | integer/bigint/numeric by range | ASSISTED | Actual precision and scale |
| Unqualified NUMBER | numeric | ASSISTED | Range and arithmetic |
| DATE | timestamp without time zone or date | MANUAL | Oracle DATE stores time-of-day |
| DEFAULT SYSDATE | explicit target clock | MANUAL | Timezone/clock policy |
| BY DEFAULT ON NULL IDENTITY | PostgreSQL identity | ASSISTED | Explicit-ID load and sequence reset |
| Virtual qty*unit_price | stored generated or computed | ASSISTED | Expression/precision semantics |
| CHECK | PostgreSQL CHECK | ASSISTED | Preserve all 8 predicates |
| ON DELETE CASCADE | FK cascade | ASSISTED | Trigger interaction |
| FORCE VIEW | ordinary view after dependencies | MANUAL | No direct FORCE equivalent |
| DUAL | no-FROM SELECT / VALUES | ASSISTED | Rewrite KPI view |
| NVL | COALESCE | ASSISTED | Empty-string/type coercion |
| PL/SQL boolean function in SQL | SQL function or service/query | MANUAL | No assumed semantic equivalence |
| DBMS_ASSERT | closed identifier registry | MANUAL | Not a generic sanitizer port |
| APEX SYS_CONTEXT | trusted authenticated principal | MANUAL | Auth/request-context design |
| Package global state | request-scoped service/transaction context | MANUAL | Avoid pooled-session leakage |
| Row triggers | domain/service invariants or narrow triggers | MANUAL | One authoritative write path |
| MERGE | INSERT ON CONFLICT | ASSISTED | Concurrency/update semantics |
| RAISE_APPLICATION_ERROR | typed domain/API errors | MANUAL | Preserve stable error contract |
| %TYPE/%ROWTYPE | explicit target types/models | MANUAL | Resolve precision/nullability |
| ORA-04091 mutating-table pattern | explicit cascade/delete semantics | UNSUPPORTED as direct port | Oracle-specific exception behavior |

## PL/SQL unit dispositions

| Unit | Responsibility | Disposition | Target design |
|---|---|---|---|
| SEC_PKG | principal, bootstrap, role checks | MANUAL | NestJS authorization; fail closed |
| DOC_PKG | document numbering | ASSISTED | Atomic upsert/update-returning |
| APPROVAL_PKG | submit/approve/reject, maker-checker, threshold | MANUAL | NestJS workflow service, explicit transaction/locking |
| REQUEST_PKG | require at least one request line | ASSISTED | Domain validation in submit transaction |
| Audit triggers | audit and normalization | ASSISTED | Centralized hooks or narrow DB trigger |
| REQUESTS_TRG | state and immutable-field guards | MANUAL | Explicit state machine/invariants |
| REQUEST_LINES_TRG | parent-state guard/cascade handling | MANUAL | Parent lock and transactional domain service |

## Critical review findings

- **SEC-001:** bootstrap mode currently accepts all role checks if no ADMIN assignment exists. Replace with one-time, time-bounded bootstrap and deny-by-default.
- **SEC-002:** package spec exposes SET_BYPASS, which controls package-global trigger bypass state. Verify grants and call paths; never accept a client-controlled equivalent.
- **CONC-001:** SUBMIT reads document status without FOR UPDATE before updating status and inserting approval. Lock the document and enforce one pending approval per document/level.
- **CONC-002:** DOC_PKG uses MERGE-create then UPDATE-increment. Target should use one atomic INSERT ... ON CONFLICT ... DO UPDATE ... RETURNING.
- **DYN-001:** APPROVAL_PKG has four EXECUTE IMMEDIATE sites. DBMS_ASSERT guards identifiers, but AMOUNT_EXPR is executable SQL text. Review configuration writers and replace free-form SQL with a closed handler registry.
- **TX-001:** packages do not COMMIT; caller owns transaction. Define atomicity and test rollback at every intermediate failure.
- **AUTH-001:** APEX APP_USER context must become a trusted server-side principal.
- **TRG-001:** test audit stamps, state transitions, immutable fields, line guards and cascade delete behavior.
