# Normalized IR v1 — Development Backlog

This backlog implements [Normalized Application IR v1](../architecture/normalized-ir-v1.md). Work remains on the existing feature branch and draft PR until explicitly changed by the project owner.

## Delivery strategy

Deliver in small, testable work packages. The JSON Schema is the cross-language source of truth. Do not implement target code generation in this milestone.

| ID | Work package | Main deliverables | Depends on | Priority | Status |
|---|---|---|---|---|---|
| IRV1-01 | Contract and taxonomy | JSON Schema, canonical object taxonomy, version policy, valid/invalid fixtures | — | P0 | Initial contract in place |
| IRV1-02 | Core types and validators | Generated TS types, Python schema validation, contract test harness | IRV1-01 | P0 | Python validator in place; TS types/tests pending |
| IRV1-03 | Identity and provenance | Canonical identity builder, fingerprinting, source locator model | IRV1-01 | P0 | Initial implementation + regression tests |
| IRV1-04 | APEXLang adapter | Inventory-to-IR mapping, raw property preservation, provenance | IRV1-02, 03 | P0 | AST typed-property integration with parity-guarded legacy fallback implemented; real-project corpus pending |
| IRV1-05 | APEX SQL Export adapter | Export-call-to-IR mapping, raw argument preservation, provenance | IRV1-02, 03 | P0 | Initial implementation + fixture tests |
| IRV1-06 | Reference resolver | Scope-aware candidate index, typed resolver, resolution diagnostics | IRV1-04, 05 | P1 | Initial exact-ID resolver + tests; broader type/context rules pending |
| IRV1-07 | Relationships and dependency graph | Typed graph edges, cycle detection, explicit/inferred distinction | IRV1-06 | P1 | Partial structural containment only |
| IRV1-08 | Diagnostics catalog | Stable diagnostic codes, severity, details, suggestions | IRV1-02, 06 | P1 | Initial source/schema diagnostics; resolver codes pending |
| IRV1-09 | Regression and acceptance suite | Cross-format fixtures, determinism, preservation, resolver, safety tests | IRV1-04..08 | P1 | Partial; resolver and broad safety coverage pending |
| IRV1-10 | Documentation and PR evidence | Usage examples, coverage matrix, limitations, CI evidence | IRV1-09 | P1 | In progress |\n| IRV1-11 | Expression classification and cross-format mapping | Conservative language classifier, shared APEXLang/export property mapping, confidence/rule metadata, regression fixtures | IRV1-04, 05 | P1 | Initial lexical classifier + explicit canonical aliases + schema/tests implemented; grammar-backed coverage pending |

## Detailed tasks and acceptance evidence

### IRV1-01 — Contract and taxonomy
- [ ] Add JSON Schema Draft 2020-12 for the top-level IR document.
- [ ] Define canonical object types and extension/preservation policy.
- [ ] Define required vs optional fields and nullability.
- [ ] Add valid minimal, valid unknown-object, and invalid fixtures.
- [ ] Validate schema with a standards-compliant validator.

**Done when:** schema validation passes and fixtures prove unknown source metadata can be retained without weakening required structural fields.

### IRV1-02 — Core types and validators
- [ ] Generate TypeScript types from the JSON Schema.
- [ ] Add Python validation using a pinned JSON Schema validator dependency.
- [ ] Add cross-language contract fixtures consumed by Python and TypeScript tests.
- [ ] Add schema compatibility/version checks.

**Done when:** both runtimes accept the same valid fixture and reject the same invalid fixture.

### IRV1-03 — Identity and provenance
- [ ] Define deterministic canonical identity rules per object category.
- [ ] Keep identity, fingerprint, and source locator separate.
- [ ] Hash source artifacts with SHA-256.
- [ ] Record file, line, column, parser/adapter version, and source-native identifiers when available.
- [ ] Emit low-confidence/missing-provenance diagnostics instead of inventing values.

**Done when:** content-only edits preserve identity where the source-native key is stable while changing the fingerprint.

### IRV1-04 — APEXLang adapter
- [ ] Map current APEXLang inventory declarations to canonical object types.
- [x] Preserve declaration kind, names, scalar properties, unknown properties, and raw expressions.
- [x] Decode unambiguous string, boolean, null, integer, decimal, and scientific numeric literals.
- [x] Record property-level file, line, column, and source artifact hash.
- [x] Normalize multiline brace-delimited nested property blocks into recursive OBJECT values with child locators.
- [x] Preserve multiline raw expressions with property-level start/end line and column locators.
- [ ] Support inline/mixed block syntax, arrays, and grammar-backed expression boundaries.
- [ ] Build parent-child relationships only where source structure proves containment.
- [ ] Retain lexical references as unresolved typed candidates; do not claim semantic resolution.
- [ ] Add source file and declaration location provenance.

**Done when:** current synthetic APEXLang fixture produces schema-valid IR and all parser inventory records are either represented or reported.

### IRV1-05 — APEX SQL Export adapter
- [ ] Map supported import API routines to canonical object types.
- [ ] Preserve raw named and positional arguments.
- [ ] Keep source API routine and call location.
- [ ] Add adapter diagnostics for unknown API routines and incomplete call parsing.
- [ ] Avoid inventing parent-child relationships from insufficient evidence.

**Done when:** current SQL Export fixtures produce schema-valid IR and all extracted calls are represented or diagnosed.

### IRV1-06 — Reference resolver
- [ ] Define reference type and scope model.
- [ ] Build snapshot-scoped indexes by source-native ID and canonical identity.
- [ ] Implement unique-candidate resolution.
- [ ] Emit DANGLING, AMBIGUOUS, UNSUPPORTED, and INVALID outcomes.
- [ ] Add deterministic tests for collisions and scope isolation.

**Done when:** no unresolved or ambiguous reference is silently assigned a target.

### IRV1-07 — Relationships and dependency graph
- [ ] Model structural relationships separately from references.
- [ ] Derive dependency edges from resolved references and explicit structural rules.
- [ ] Label inferred edges and record inference rule/version.
- [ ] Detect cycles and classify them by dependency type.
- [ ] Keep graph output deterministic.

**Done when:** tests distinguish structural containment, explicit references, and inferred dependencies.

### IRV1-08 — Diagnostics catalog
- [ ] Implement stable diagnostic codes and categories.
- [ ] Include object/reference IDs and source locators when available.
- [ ] Ensure diagnostics are deterministically ordered.
- [ ] Map diagnostics to conversion readiness without conflating parsing success and semantic parity.

**Done when:** every failure/uncertainty path has an actionable diagnostic and stable code.

### IRV1-09 — Regression and acceptance suite
- [ ] Test unknown property preservation and raw expression retention.
- [ ] Test deterministic output and snapshot comparison.
- [ ] Test invalid input, nesting limits, malformed metadata, and path safety.
- [ ] Test resolver positive, dangling, ambiguous, and out-of-scope cases.
- [ ] Test cycle detection and explicit/inferred edge labels.
- [ ] Test no source-code execution.

**Done when:** acceptance criteria in the DTD are automated and CI passes.

### IRV1-11 — Expression classification and cross-format mapping\n- [x] Add shared conservative classifier for SQL, PL/SQL, JavaScript, HTML, CSS, and APEX substitution patterns.\n- [x] Map high-confidence SQL/PLSQL/JavaScript expressions to existing IR value types.\n- [x] Preserve exact raw source and record language, confidence, and rule ID.\n- [x] Use the same property mapping helper in APEXLang and APEX SQL Export adapters.\n- [x] Add positive and negative classification tests and a cross-format SQL contract test.\n- [ ] Replace lexical rules with grammar-backed classification where required; expand coverage only with representative source fixtures.\n\n**Done when:** both adapters produce the same expression-property contract for equivalent source expressions and ambiguous expressions remain UNKNOWN.\n\n### IRV1-10 — Documentation and PR evidence
- [ ] Update architecture and parser documentation.
- [ ] Add example IR payload and CLI invocation.
- [ ] Document actual parser coverage and limitations.
- [ ] Record CI run URL, commit SHA, changed files, and known gaps in the PR.
- [ ] Keep the PR draft and unmerged unless explicitly authorized.

## Quality gates

- Ruff and pytest for Python workers.
- TypeScript lint, typecheck, and unit tests for packages that are implemented.
- JSON Schema validation in CI.
- Cross-language contract tests.
- Regression fixtures.
- No credentials or production source artifacts in fixtures.
- No claim of semantic parity based solely on schema validity or compilation.

## Scope boundary

The milestone establishes a normalized structural model and deterministic reference handling for supported constructs. It does not certify complete APEX extraction, complete PL/SQL semantics, runtime behavior, or production migration readiness. A sanitized representative real application export is required before coverage can be measured credibly.


### IRV1-11 — Expression classification and cross-format mapping (initial slice)
- [x] Add conservative syntax-led language labels with confidence and stable rule IDs.
- [x] Preserve unclassified expressions as UNKNOWN with raw source text.
- [x] Add explicit canonical property names while retaining source property names.
- [x] Add narrowly scoped APEX SQL Export aliases for PAGE.p_source and REGION.p_plug_source.
- [x] Define classification and canonical-name metadata in the shared JSON Schema.
- [x] Add cross-format and unknown-expression regression tests.
- [ ] Replace lexical classification with grammar-backed classification where required.
- [ ] Expand aliases only from documented APEX API semantics and representative export fixtures.
- [ ] Add corpus-based precision/recall evaluation against sanitized real APEX exports and APEXLang projects.

**Done when:** source property names remain lossless, supported aliases compare deterministically, unsupported expressions remain UNKNOWN, and all outputs validate against the shared IR schema.


### WP PARSER-01 — APEXLang grammar and AST foundation (initial slice)
- [x] Add a version-controlled ANTLR grammar specification for declaration, property, literal, reference, and expression-token structure.
- [x] Add a dependency-free tokenizer with source offsets and 1-based line/column spans.
- [x] Add declaration AST nodes with nested declaration children and raw-body preservation.
- [x] Treat comments, strings, and fenced blocks atomically during tokenization.
- [x] Balance parentheses inside expression bodies independently from declaration boundaries.
- [x] Emit diagnostics for unterminated strings, comments, fenced blocks, and declarations.
- [x] Export the AST/tokenizer API and document its current boundary.
- [ ] Parse property declarations into typed AST nodes, including colon-prefixed object blocks.
- [ ] Implement complete arrays, inline/mixed brace blocks, and balanced expression AST nodes.
- [ ] Add deterministic error recovery, nesting/file-size limits, and fuzz/property-based tests.
- [ ] Compare grammar and parser behavior against sanitized real APEXLang project fixtures.
- [ ] Integrate AST output into the Normalized IR adapter only after parity tests show no loss versus the current inventory parser.

**Done when:** the grammar/AST layer can represent supported declarations and nested structures with exact source spans, preserves all unparsed source, reports malformed syntax, and passes the real-source regression corpus. This initial slice is not the production parser and does not claim complete APEXLang syntax support.


### WP PARSER-02 — Typed property AST and nested values (initial slice)
- [x] Add typed property node model with source spans.
- [x] Attach property nodes to declaration AST nodes.
- [x] Parse scalar string, number, boolean, and null literals conservatively.
- [x] Parse multiline brace-delimited object values recursively.
- [x] Parse bracket-delimited arrays of scalar values.
- [x] Preserve unrecognized expressions without execution.
- [x] Detect duplicate property names while retaining source order.
- [x] Scope property extraction to the direct declaration level.
- [x] Preserve multiline balanced-parenthesis expressions.
- [ ] Support nested object/array values and inline/mixed brace syntax.
- [ ] Add grammar-driven property parsing and parser recovery.
- [ ] Add resource limits, fuzz tests, and real APEXLang corpus comparisons.
- [ ] Compare AST property output with existing inventory adapter property records.

**Done when:** supported scalar/object/array values are represented as typed AST nodes with source spans, unknown expressions remain lossless, duplicate keys are diagnosed, and regression fixtures pass. This initial slice is not full APEXLang syntax coverage.


### WP PARSER-03 — Parser hardening and grammar integration

- [x] Parse recursive nested OBJECT and ARRAY values, including arrays of objects and nested arrays.
- [x] Support inline object/array forms within the supported key/value syntax subset.
- [x] Preserve non-literal and multiline expression source without evaluation.
- [x] Preserve duplicate properties and report AST102 at every parsed object scope.
- [x] Emit deterministic diagnostics for malformed containers and unsupported object members.
- [x] Add source-character, token-count, delimiter-depth, and recursive-property-depth limits.
- [x] Add malformed-input regression corpus and nested-value/source-span tests.
- [x] Validate the maintained ANTLR grammar by generating a Python parser with pinned ANTLR 4.13.2 in CI.
- [x] Keep the Python parser dependency-free and explicitly separate from ANTLR code generation/runtime.
- [x] Add seeded generated-value/property-style tests over recursive objects and arrays, plus deterministic malformed-input cases.
- [x] Compare AST declaration preorder with the existing inventory parser over the committed synthetic APEXLang fixture corpus.
- [ ] Validate behavior against a sanitized representative real APEXLang project corpus.
- [ ] Expand deterministic recovery for malformed nested declarations and delimiter mismatch reporting.

**Done for this incremental WP3 slice when:** recursive values, conservative expression preservation, bounded input, regression tests, and grammar-generation validation are in place. This is not production certification or complete APEXLang syntax support. Corpus-based accuracy and adapter parity remain explicit gates.


### WP IRV1-12 — APEXLang AST-to-Normalized IR integration (WP4)

- [x] Parse each `.apx` artifact through the bounded AST parser in addition to the existing inventory parser.
- [x] Preserve the inventory parser as authority for declaration discovery, object taxonomy, stable identity, containment, and lexical reference extraction.
- [x] Match AST declarations to inventory declarations by file, source line, declaration kind, and name.
- [x] Use AST typed properties only when ordered direct-property names exactly match the inventory property records.
- [x] Fall back to legacy property records on any property-name parity mismatch; emit `IRAST001` with both lists.
- [x] Emit `IRAST002` when an inventory declaration has no AST counterpart and `IRAST003` when the AST finds a declaration absent from inventory.
- [x] Map scalar, recursive OBJECT, and ARRAY values into the existing IR property contract.
- [x] Preserve raw source text for every AST property in `extensions.rawSourceValue`; retain full declaration body in object extensions.
- [x] Preserve expression text and run only the conservative, non-evaluating shared classifier.
- [x] Add source locators to AST properties, including property-key start and value end coordinates.
- [x] Carry AST parser diagnostics into IR and mark objects PARTIAL when their source artifact has AST ERROR diagnostics.
- [x] Record AST parser version, integration mode, matched declaration count, AST property count, fallback count, and parser diagnostic count in IR metadata.
- [x] Add tests for nested arrays/objects, expression mapping, parity fallback, schema validity, and deterministic output.
- [x] Preserve every occurrence of duplicate direct and nested property names in `extensions.duplicateProperties`; emit `IRAST004` when the unique-key IR property map cannot represent all direct occurrences.
- [ ] Validate against a sanitized representative real APEXLang project and evaluate semantic coverage.

**Done for WP4 implementation:** typed AST properties are connected to IR with deterministic metadata and source provenance, unmatched or uncertain syntax is explicitly diagnosed or handled by the legacy fallback, and duplicate property occurrences are retained outside the unique-key property map. This is not full declaration-parser replacement or semantic parity certification.

### WP IRV1-13 — Dependency Graph & Impact Analysis (WP5)

- [x] Build a deterministic graph from explicit Normalized IR dependency records.
- [x] Add resolved references as explicit edges when the resolver has supplied a unique target.
- [x] Keep edge direction explicit: source object depends on target object; migration order is dependency-first.
- [x] Validate missing, duplicate, and out-of-snapshot endpoints with DEP001–DEP002 diagnostics.
- [x] Exclude PENDING, DANGLING, AMBIGUOUS, UNSUPPORTED, and INVALID references from migration-order edges and report DEP003.
- [x] Collapse duplicate semantic edges deterministically while retaining source locator provenance.
- [x] Detect strongly connected components and self-cycles; distinguish cycle members from downstream blocked objects (DEP005–DEP006).
- [x] Produce a stable topological migration order for the acyclic portion of the graph.
- [x] Produce direct and transitive dependent impact lists for each graph node.
- [x] Add regression tests for ordering, transitive impact, cycles, downstream blocking, unresolved references, resolved references, invalid endpoints, duplicate identities, and deterministic output.
- [x] Export the analyzer through the extraction worker public API and document its contract.
- [ ] Validate graph accuracy against a sanitized representative APEX application and typed dependency semantics.

**WP5 implementation boundary:** the analyzer consumes only explicit dependency records and uniquely resolved references. It deliberately does not infer dependencies from component names, SQL/PLSQL text, arbitrary property values, or containment relationships. The graph and migration order are structural planning aids, not proof of semantic or runtime dependency completeness. Cycles block their members and transitive dependents; the acyclic remainder retains a deterministic dependency-first order.


## WP6 — Semantic Analysis & Transformation Rules

**Status:** Implemented baseline  
**Public API:** `analyze_semantics(document, dependency_graph=None)`

- [x] Explicit component mapping registry for UI, API, data, security, configuration, and assets.
- [x] AUTOMATIC / ASSISTED / MANUAL / UNSUPPORTED classification; AUTOMATIC remains unused until behavior parity is proven.
- [x] SQL, PL/SQL, JavaScript, HTML, CSS, APEX substitution, and UNKNOWN expression planning from existing IR metadata.
- [x] Recursive nested OBJECT property traversal and deterministic property paths.
- [x] Stable transformation IDs, rule IDs, confidence, source provenance, and raw-source preservation metadata.
- [x] SEM001–SEM008 diagnostics for unmapped components, unknown expressions, PL/SQL, plug-ins, security, unresolved references, cycles, and blocked objects.
- [x] WP5 dependency graph integration and dependency-first order propagation.
- [x] Non-mutating deterministic report, tests, and documentation.

**Qualification boundary:** This closes the implementation baseline and test contract, not behavior-level equivalence, complete APEX component coverage, complete PL/SQL conversion, or production readiness. A sanitized real APEX export and runtime-version-specific fixtures remain required.


## WP7 — Target Code Generation

**Status:** Implemented baseline; final CI passed on `bcec64cb97effb9bf7bb6176036b10bd8b3a7a35`.

- [x] Add deterministic Python generator API and CLI.
- [x] Validate Normalized IR before writing target files.
- [x] Generate Next.js App Router shell and stable routes for extracted PAGE objects.
- [x] Generate NestJS API scaffold with health endpoint and per-process fail-closed service stubs.
- [x] Generate page-item DTO placeholders without guessing field types.
- [x] Generate authentication/authorization scaffolding that fails closed until provider and policy configuration is reviewed.
- [x] Generate basic target-side scaffold contract tests.
- [x] Generate PostgreSQL baseline schema and migration ledger without guessing business tables.
- [x] Include source IR, WP5 graph, WP6 semantic plan, summary, and manual-review diagnostics.
- [x] Preserve manual/unsupported classifications; never execute source expressions.
- [x] Add non-empty output protection and explicit overwrite option.
- [x] Add SHA-256 manifest and deterministic generation tests.
- [x] Document target workspace and CLI/API usage.
- [x] Validate generated target workspace with pnpm install/build/test/typecheck in CI.
- [ ] Expand generator coverage only after sanitized APEX and database schema fixtures are available.

**Qualification boundary:** WP7 initial generator scaffold is not a full APEX application converter. Business schema, data migration, functional APIs, authentication/authorization, dynamic actions, reports/grids, and PL/SQL behavior remain outside this implementation slice.


**WP7 final CI evidence:** Run 42359828215 passed on final branch HEAD `bcec64cb97effb9bf7bb6176036b10bd8b3a7a35`. Ruff passed; pytest 75 passed; ANTLR grammar validation passed; Node workspace baseline passed; generated target project installation, Next.js/NestJS build, generated scaffold tests, and TypeScript typecheck all passed.
