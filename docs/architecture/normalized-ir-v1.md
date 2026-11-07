# Normalized Application IR v1 — Detailed Technical Design

- **Status:** Proposed implementation contract
- **IR version:** 1.0.0
- **Schema dialect:** JSON Schema Draft 2020-12
- **Scope:** Static metadata normalization for Oracle APEX SQL Export and APEXLang
- **Safety:** Parsing and normalization never execute SQL, PL/SQL, JavaScript, or deployment instructions.

## 1. Goals and non-goals

### Goals
1. Define one source-independent application model consumed by analysis and conversion stages.
2. Preserve source identity, locations, raw expressions, unknown object types, and unknown properties.
3. Represent structural relationships separately from semantic references and dependencies.
4. Resolve references only when a unique, context-valid target exists.
5. Make snapshots deterministic, immutable after publication, and traceable to source artifacts.
6. Provide diagnostics with stable machine-readable codes.

### Non-goals for v1
- Complete Oracle APEX or APEXLang grammar coverage.
- Executing or evaluating source expressions.
- Claiming behavioral or semantic parity.
- Resolving arbitrary dynamic SQL, runtime-generated identifiers, plugin behavior, or every implicit APEX reference.
- Defining target Next.js/NestJS/PostgreSQL code-generation contracts.

## 2. Architectural boundaries

`source parser -> source adapter -> normalized IR -> validators/resolver -> validated IR -> conversion engine`

- **Parser:** recognizes syntax and source constructs; emits parser-native inventory.
- **Adapter:** maps parser-native records into canonical IR types and retains source-specific fields.
- **IR schema:** authoritative cross-language contract.
- **Resolver:** processes typed references against a snapshot-scoped object index.
- **Diagnostics:** reports uncertainty and invalidity without silently dropping source content.
- **Generator:** consumes validated IR and must not depend on parser-specific structures.

Python parsers and TypeScript platform services MUST validate against the same JSON Schema. Generated language types may be derived from the schema; handwritten duplicate contracts are prohibited.

## 3. Top-level document

Required top-level members:
- `irVersion`: semantic version of the IR contract.
- `application`: application identity and source metadata.
- `objects`: canonical object inventory.
- `relationships`: structural relationships.
- `references`: explicit or lexical references and their resolution outcomes.
- `dependencies`: typed dependency edges.
- `diagnostics`: parse, normalization, validation, and resolution diagnostics.
- `metadata`: source artifact hashes and producer information.

Unknown top-level extension data must be preserved under `extensions`; implementations must not silently discard unrecognized fields during read/modify/write operations.

## 4. Canonical object taxonomy

Initial canonical types:
- APPLICATION
- PAGE
- REGION
- ITEM
- BUTTON
- BRANCH
- VALIDATION
- PROCESS
- DYNAMIC_ACTION
- DYNAMIC_ACTION_ACTION
- LIST
- LIST_ITEM
- BREADCRUMB
- LOV
- AUTHENTICATION
- AUTHORIZATION
- THEME
- PLUGIN
- COLUMN
- DISPLAY_COLUMN
- COMPONENT_ENTRY
- PAGE_GROUP
- STATIC_FILE
- BUILD_OPTION
- COMPONENT_SETTING
- SUPPORTING_OBJECT
- SAVED_REPORT
- REPORT_SORT
- PARAMETER
- CHART_SERIES
- CHART_AXIS
- UNKNOWN

The canonical `type` is stable across source formats. `sourceType` preserves the original declaration/API category. Unmapped types use `UNKNOWN` and retain the original value in `sourceType` and `extensions`.

## 5. Identity, fingerprint, and locator

These concepts MUST remain separate:

| Field | Meaning | Stability |
|---|---|---|
| `id` | Canonical object identity within the platform | Stable across content-only edits where source-native identity is stable |
| `fingerprint` | Hash of canonicalized object content | Changes when relevant content changes |
| `sourceLocator` | File/API call/source position | May change when files are reorganized |

Identity strategy, in order:
1. A source-native immutable identifier, when its stability and scope are known.
2. A deterministic canonical identity composed from application scope, canonical type, and source-native key.
3. A deterministic fallback from normalized source path and declaration identity.
4. A provisional identity with an explicit low-confidence diagnostic when the source does not provide enough information.

Do not use content hash as the primary identity. Do not resolve name-only collisions globally. Identity collision must produce a diagnostic, not an arbitrary winner.

Initial adapter implementation (version 0.1.0) uses a deterministic SHA-256-derived identifier over source format, canonical object type, parent identity, and source-native identifier. Application roots have no parent. When no native identifier exists, the adapter falls back to parent-scoped name; if neither is available, it uses a source locator fallback and emits a low-confidence diagnostic. The digest is shortened for the public IR ID; collision detection remains a required resolver/validation hardening item.

The content fingerprint is a separate SHA-256 over canonical JSON containing canonical type, source type, name, and normalized properties. It excludes source locator and generated metadata. Artifact hashes are full SHA-256 values and are retained in object provenance and snapshot metadata.

For cross-snapshot comparison, implementations must retain the source-native key and identity strategy used. UUID database primary keys may wrap canonical identities, but must not replace the deterministic identity contract.

## 6. Properties and expression preservation

Properties are represented as named records with:
- `valueType`
- `value` when safely decoded
- `rawExpression` when the source is an unevaluated expression
- `sourceLocator`
- optional `extensions`

Supported value types: STRING, NUMBER, BOOLEAN, NULL, ARRAY, OBJECT, SQL_EXPRESSION, PL_SQL_EXPRESSION, JAVASCRIPT_EXPRESSION, UNKNOWN.

A parser may decode only unambiguous scalar literals. The initial APEXLang adapter decodes single- and double-quoted strings, booleans, null, integers, and decimal/scientific numeric literals. Each extracted property includes its own source locator (file, start line/column, end line/column, and artifact hash). Multiline values are retained as one raw expression until the next sibling property or enclosing block/declaration boundary; continuation lines are not independently interpreted as properties. Property recognition requires an explicit colon or a brace-delimited object opener, preventing nested component declarations from being misclassified as properties.

Brace-delimited nested property blocks are represented recursively as `OBJECT` properties whose `value` is a map of child property records. Each child retains its own type and source locator. For example, `navigation { homeUrl: { page: 10 } }` becomes `navigation.value.homeUrl.value.page`, with `OBJECT` at each block level and `NUMBER` at the leaf.

All other values are retained as `UNKNOWN` with their exact `rawExpression`; no SQL, PL/SQL, JavaScript, or APEXLang expression is evaluated. Nested blocks are no longer flattened or discarded. The complete raw declaration body remains in object extensions as the lossless fallback. The initial block parser supports multiline brace-delimited blocks and multiline raw expressions with start/end source spans. It uses a conservative line-boundary heuristic rather than a complete APEXLang expression grammar; inline/mixed block syntax, arrays, and complex expressions whose continuation resembles a sibling property remain outside this pass.

## 7. Provenance

Every object must have provenance identifying:
- source format (APEXLANG or APEX_SQL_EXPORT);
- relative source file/artifact identifier;
- line and column when available;
- end line/column when available;
- source artifact SHA-256;
- object fingerprint;
- source-native identifier/API routine when available.

Property-level provenance should be recorded when the parser can provide it. Missing coordinates are represented as null/omitted with a diagnostic; they must not be fabricated.

Large raw source text should remain in a source artifact store. IR stores the artifact hash and locator rather than duplicating entire files.

## 8. Relationships, references, and dependencies

These are separate concepts:

- **Relationship:** structural containment or ordering, e.g. application contains page, page contains region.
- **Reference:** a source expression/identifier that appears to point to another object, e.g. an item references an LOV.
- **Dependency:** an edge used for analysis or conversion ordering, derived from an explicit relationship/reference or a separately labeled inference.

Every edge includes a type, source object, target object if resolved, origin, and provenance. Inferred dependencies must be marked `INFERRED`; they must never be represented as explicit source facts.

### Reference statuses
- PENDING
- RESOLVED
- DANGLING
- AMBIGUOUS
- UNSUPPORTED
- INVALID

Reference resolution algorithm:
1. Collect reference candidates from parser output without interpreting arbitrary expression semantics.
2. Normalize only syntax-specific wrappers that are documented by the source adapter.
3. Determine reference context and expected target type.
4. Search source-native IDs in the correct application/scope.
5. Search canonical IDs and documented scoped aliases.
6. Evaluate candidate count: zero = DANGLING; one valid candidate = RESOLVED; multiple = AMBIGUOUS.
7. Persist the resolution outcome and diagnostic.
8. Create dependency edges only for resolved references.

Name-only matching is permitted only when the reference type and scope make the candidate set unambiguous. Resolver must never guess.

## 9. Diagnostics and conversion classification

Diagnostic fields:
- stable `code`;
- `severity` (INFO, WARNING, ERROR);
- `category`;
- human-readable `message`;
- affected object/reference ID;
- source locator;
- structured `details`;
- optional remediation `suggestion`.

Initial diagnostic catalogue:
- IR001 invalid IR structure (ERROR)
- IR002 unknown object type preserved (WARNING)
- IR003 unknown property preserved (WARNING)
- IR004 identity collision (ERROR)
- SRC001 incomplete source provenance (WARNING)
- SRC002 runtime version not established (INFO)
- REF001 dangling reference (ERROR)
- REF002 ambiguous reference (ERROR)
- REF003 unsupported reference syntax (WARNING)
- DEP001 circular dependency (WARNING by default; severity depends on dependency class)
- DEP002 invalid relationship endpoint (ERROR)

Conversion statuses remain: AUTO, AUTO_TEST, REVIEW, BLOCKED, ERROR. AUTO_TEST is allowed only after the relevant generated artifact tests have actually passed. IR validity alone does not imply conversion readiness or semantic parity.

## 10. Snapshot and determinism rules

- A published IR snapshot is immutable.
- Re-ingestion creates a new snapshot with source artifact hashes and adapter/schema versions.
- The same source bytes, adapter version, and schema version must produce semantically identical canonical IR, excluding explicitly volatile generation metadata.
- Object ordering, property ordering, and diagnostics ordering must be deterministic.
- Snapshot comparison uses identity for object matching and fingerprint for content change detection.
- Failed parsing may produce a diagnostic-bearing partial snapshot, but it must not be labeled complete.

## 11. Internal persistence guidance

Recommended relational storage:
- `ir_snapshots`: application, IR version, source hashes, adapter version, lifecycle state.
- `ir_objects`: snapshot, canonical identity, type, source type, fingerprint, provenance.
- `ir_properties`: object, property name, typed JSONB value, raw expression, provenance.
- `ir_relationships`: source/target object and relationship type.
- `ir_references`: source object, reference type/value, target, resolution status.
- `ir_dependencies`: source/target object, dependency type, origin/confidence.
- `ir_diagnostics`: snapshot/object/reference, code, severity, details.

Use relational columns for frequently queried identifiers/statuses and JSONB for heterogeneous property payloads. Enforce snapshot-scoped foreign keys and uniqueness constraints. Do not make a single opaque JSONB document the only persistence model.

## 12. Security and safety

- Never execute source SQL, PL/SQL, JavaScript, shell commands, or deployment metadata during extraction/normalization.
- Treat source files and metadata as untrusted input.
- Apply file size, nesting-depth, declaration-count, and processing-time limits.
- Reject path traversal and do not follow symlinks outside the selected source root.
- Avoid logging secrets or complete source expressions by default.
- Keep raw artifacts access-controlled and redact credentials/endpoints in diagnostic output where applicable.

## 13. Acceptance criteria

1. Both source adapters produce schema-valid IR documents.
2. Same logical object maps to a stable identity across content-only edits where source-native identity remains stable.
3. Fingerprint changes when canonicalized object content changes.
4. Unknown object types/properties and raw expressions survive normalization.
5. Provenance is retained or a diagnostic explains why it is unavailable.
6. Resolver returns RESOLVED only for one scope-valid candidate.
7. Missing and multiple candidates produce DANGLING and AMBIGUOUS respectively.
8. Structural relationships, explicit references, and inferred dependencies remain distinguishable.
9. Snapshot output is deterministic for fixed inputs and tool versions.
10. Parsing/normalization does not execute source code.
11. Invalid input returns actionable diagnostics and never a false success status.

## 14. Implementation sequence

See [Normalized IR v1 Development Backlog](../development/normalized-ir-v1-backlog.md). Implement the schema and contract tests first, then identity/provenance, adapters, resolver, and diagnostics. Keep each work package independently reviewable.


## 15. Conservative expression classification

The initial expression classifier is shared by the APEXLang and Oracle APEX SQL Export adapters so both formats emit the same IR property contract.

- Preserve the exact extracted source in `rawExpression`; classification never rewrites or evaluates it.
- Set `valueType` to `SQL_EXPRESSION`, `PL_SQL_EXPRESSION`, or `JAVASCRIPT_EXPRESSION` only for recognized leading syntax patterns.
- Record `expressionLanguage`, `classificationConfidence`, and a versioned `classificationRule` on expression properties.
- Recognize a small set of high-signal HTML, CSS, and APEX substitution forms as language metadata while retaining `valueType: UNKNOWN`, because the current IR value-type enum has no dedicated values for those languages.
- Leave ambiguous expressions as `UNKNOWN` with `classificationConfidence: NONE`. Property names, surrounding object types, and substring matches are not sufficient evidence.
- This is lexical classification, not a parser, validator, execution engine, or semantic equivalence proof. Extend the rule set only with positive and negative regression fixtures from representative source versions.


## 6.1 Expression classification and cross-format property names (initial)

The initial classifier assigns a language only when a conservative syntax-led rule matches: SQL, PL/SQL, JavaScript, APEX substitution syntax, HTML element syntax, or selected CSS at-rules. Every classification carries a stable rule identifier and confidence value. Unmatched expressions remain `UNKNOWN`; this is not a grammar-backed parser and must not be treated as proof of executable language semantics.

For cross-format comparison, every normalized property retains its source key in `sourcePropertyName` and receives a `canonicalPropertyName`. The initial alias catalogue is deliberately small: APEX SQL Export `PAGE.p_source` maps to `source`, and `REGION.p_plug_source` maps to `source`. APEXLang property names remain unchanged. No source key is removed, and no alias is inferred from similarity. Expand this catalogue only with documented, object-type-specific evidence and regression fixtures.

Expression metadata fields are defined in the schema: `expressionLanguage`, `classificationConfidence`, and `classificationRule`. The original `rawExpression` remains authoritative and must be preserved byte-for-byte at the decoded source-text level; classifiers must never evaluate it. HTML, CSS, and APEX forms remain `valueType: UNKNOWN` until dedicated typed semantics are designed.


## 16. APEXLang grammar and AST foundation

The repository maintains an ANTLR grammar specification at `workers/extraction-worker/grammar/ApexLang.g4` and a dependency-free Python tokenizer/AST implementation at `apex2next_extractor.apexlang_ast`.

The AST layer:
- Retains source offsets and 1-based line/column spans for declarations and typed properties.
- Treats comments, quoted strings, and fenced blocks atomically during tokenization.
- Builds nested declaration nodes and preserves raw declaration bodies.
- Parses supported scalar, recursive OBJECT, and ARRAY values, including inline objects, arrays of objects, and nested arrays.
- Preserves unrecognized expressions as raw source; it never evaluates source expressions.
- Emits deterministic diagnostics for malformed containers, duplicate keys, and resource-limit violations.

The ANTLR grammar is validated in CI using the pinned ANTLR 4.13.2 tool. The runtime parser remains dependency-free Python and is not generated from or runtime-backed by ANTLR. Grammar validation is not proof of complete syntax coverage.

## 17. APEXLang AST-to-IR integration (WP4)

The APEXLang Normalized IR adapter now parses each source artifact through both the existing inventory parser and the typed AST parser. The inventory parser remains authoritative for declaration discovery, canonical object types, stable identity, containment, and reference extraction. AST property nodes are used for IR properties only when the declaration key and ordered direct-property names match the inventory parser exactly.

When parity cannot be established, the adapter falls back to the legacy inventory property mapping and emits `IRAST001` with both property-name lists. This prevents partial AST coverage from silently dropping existing source properties. AST parser diagnostics are carried into IR diagnostics with file and source-span provenance; file-level AST errors mark affected objects as parse `PARTIAL`.

AST properties map to the existing IR property contract:
- Scalars retain typed `valueType`, `value`, `sourceLocator`, and original raw source in `extensions.rawSourceValue`.
- Objects recursively map child properties; duplicate child names are reported and their original text remains available in raw source extensions.
- Arrays retain ordered items as typed property records, including nested objects and arrays.
- Expressions pass through the shared conservative classifier. The normalized logical expression is exposed as `rawExpression`, while exact AST source formatting remains in `extensions.rawSourceValue`.
- Source property names and canonical names remain separate; APEXLang names are not aliased by guesswork.

The adapter records `metadata.apexlangAstParserVersion`, `metadata.apexlangAstIntegration`, and a parity summary. The AST is therefore integrated as a typed property source with explicit fallback, not as the sole declaration parser.

This integration is structural, not semantic parity. The committed fixture corpus is synthetic. A sanitized representative real APEXLang project is still required before production coverage or semantic equivalence can be assessed.


Duplicate property handling in WP4: the canonical IR `properties` object is a unique-key map and cannot itself represent repeated source keys. The adapter therefore retains every duplicate occurrence, in source order with occurrence number and full typed property payload, under `extensions.duplicateProperties`, and emits `IRAST004`. Nested OBJECT values also carry duplicate names and occurrence payloads in their own extensions. Consumers must inspect this extension and must not assume the unique-key map alone is a lossless representation when `IRAST004` is present.
