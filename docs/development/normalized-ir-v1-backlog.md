# Normalized IR v1 — Development Backlog

This backlog implements [Normalized Application IR v1](../architecture/normalized-ir-v1.md). Work remains on the existing feature branch and draft PR until explicitly changed by the project owner.

## Delivery strategy

Deliver in small, testable work packages. The JSON Schema is the cross-language source of truth. Do not implement target code generation in this milestone.

| ID | Work package | Main deliverables | Depends on | Priority |
|---|---|---|---|---|
| IRV1-01 | Contract and taxonomy | JSON Schema, canonical object taxonomy, version policy, valid/invalid fixtures | — | P0 |
| IRV1-02 | Core types and validators | Generated TS types, Python schema validation, contract test harness | IRV1-01 | P0 |
| IRV1-03 | Identity and provenance | Canonical identity builder, fingerprinting, source locator model | IRV1-01 | P0 |
| IRV1-04 | APEXLang adapter | Inventory-to-IR mapping, raw property preservation, provenance | IRV1-02, 03 | P0 |
| IRV1-05 | APEX SQL Export adapter | Export-call-to-IR mapping, raw argument preservation, provenance | IRV1-02, 03 | P0 |
| IRV1-06 | Reference resolver | Scope-aware candidate index, typed resolver, resolution diagnostics | IRV1-04, 05 | P1 |
| IRV1-07 | Relationships and dependency graph | Typed graph edges, cycle detection, explicit/inferred distinction | IRV1-06 | P1 |
| IRV1-08 | Diagnostics catalog | Stable diagnostic codes, severity, details, suggestions | IRV1-02, 06 | P1 |
| IRV1-09 | Regression and acceptance suite | Cross-format fixtures, determinism, preservation, resolver, safety tests | IRV1-04..08 | P1 |
| IRV1-10 | Documentation and PR evidence | Usage examples, coverage matrix, limitations, CI evidence | IRV1-09 | P1 |

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
- [ ] Preserve declaration kind, names, scalar properties, unknown properties, and raw expressions.
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

### IRV1-10 — Documentation and PR evidence
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
