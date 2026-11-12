# WP6 — Semantic Analysis & Transformation Rules

**Status:** Implemented baseline | **Analyzer:** 0.1.0 | **Ruleset:** 1.0.0

## Purpose and public API

WP6 adds a conservative semantic planning stage between Normalized IR/dependency analysis and code generation. It classifies source components, proposes target responsibilities, records expression transformation plans, and emits diagnostics. It never executes SQL, PL/SQL, JavaScript, HTML, CSS, APEX substitutions, or source expressions, and it does not generate target code.

```python
from apex2next_extractor import analyze_semantics, analyze_dependency_graph
graph = analyze_dependency_graph(ir_document)
plan = analyze_semantics(ir_document, graph)
```

The input snapshot is not mutated. Output ordering and transformation IDs are deterministic.

## Classification policy

- **AUTOMATIC:** reserved for behavior proven safely representable. No current component mapping is AUTOMATIC.
- **ASSISTED:** explicit target mapping exists, but developer review/configuration is required.
- **MANUAL:** behavior needs redesign or cannot be translated safely by current rules.
- **UNSUPPORTED:** no canonical component mapping is registered.

Confidence measures mapping evidence, not runtime correctness or parity.

## Component mapping matrix

| APEX IR type | Target responsibility | Classification |
|---|---|---|
| APPLICATION, PAGE, PAGE_GROUP | Next.js shell, App Router route, route group | Assisted |
| REGION, ITEM, BUTTON, BRANCH | React component/control/action/navigation | Assisted |
| VALIDATION | NestJS DTO/domain validator | Assisted |
| PROCESS | NestJS application/domain service | Manual |
| DYNAMIC_ACTION, DYNAMIC_ACTION_ACTION | React handler/state or API command | Assisted |
| LIST, LIST_ITEM, BREADCRUMB | Navigation configuration/components | Assisted |
| LOV | PostgreSQL lookup + API + select control | Assisted |
| AUTHENTICATION | NestJS identity provider adapter | Manual |
| AUTHORIZATION | NestJS guard/policy service | Assisted |
| THEME | Design tokens/shared UI theme | Assisted |
| PLUGIN | Custom adapter or replacement assessment | Manual |
| COLUMN, SUPPORTING_OBJECT | PostgreSQL schema/API provider (type-dependent) | Assisted / Manual |
| DISPLAY_COLUMN, CHART_SERIES, CHART_AXIS | React table/chart configuration | Assisted |
| STATIC_FILE | Public asset or object storage | Assisted |
| BUILD_OPTION, COMPONENT_SETTING | Build-time flag/typed configuration | Assisted |
| SAVED_REPORT, REPORT_SORT, PARAMETER | Report/query config and typed DTO | Assisted |

## Expression mapping

The analyzer consumes language metadata already in IR and never guesses from property names or evaluates raw source.

| IR language | Target responsibility | Classification |
|---|---|---|
| SQL | PostgreSQL query/repository | Assisted |
| PL_SQL | NestJS service/repository transaction logic | Manual |
| JAVASCRIPT | TypeScript/React handler or utility | Assisted |
| HTML | React JSX component | Assisted |
| CSS | CSS module/design token | Assisted |
| APEX | Explicit route/session/config adapter | Manual |
| UNKNOWN | Preserve raw expression and request manual review | Manual |

Nested OBJECT properties are traversed using stable property paths. Transformation records retain source object, property path, source value type, rule ID, confidence, preservation flag, and source locator. Unknown expressions produce SEM002. PL/SQL produces SEM003 because package state, transaction boundaries, exception handling, and Oracle-specific database behavior need explicit redesign.

## Security, plug-ins, references, and dependencies

- Authentication/authorization produce SEM005 review diagnostics; no identity/session equivalence is assumed.
- Plug-ins produce SEM004 and require adapter/replacement assessment.
- Non-RESOLVED references produce SEM006; no guessed binding is proposed.
- Dependency cycles and blocked objects produce SEM007/SEM008.

## Diagnostic catalogue

| Code | Severity | Meaning |
|---|---|---|
| SEM001 | Warning | No component mapping registered |
| SEM002 | Warning | Expression language/semantics unknown |
| SEM003 | Warning | PL/SQL requires behavior-aware redesign |
| SEM004 | Warning | Plug-in requires dedicated adapter/replacement |
| SEM005 | Warning | Security behavior requires identity/session/policy review |
| SEM006 | Warning | Reference is not uniquely resolved |
| SEM007 | Error | Dependency cycle blocks transformation order |
| SEM008 | Error | Object blocked by dependency ordering |

## Safety, determinism, and boundaries

- Object/property output is sorted deterministically; rule IDs and versions are explicit.
- Source IR is not mutated; raw expressions are not executed.
- WP6 emits a semantic plan only; target code generation belongs to WP7.
- The rule set is an initial mapping baseline, not a complete APEX semantic catalogue. Plug-ins, dynamic actions, session state, page computations, validations, process points, interactive reports/grids, REST sources, ORDS, and Oracle-specific SQL/PLSQL need finer rules and representative fixtures.
- A sanitized representative application from the actual APEX runtime is required before production qualification or automatic code generation.

## Acceptance evidence

Public API export, mapping registry, diagnostics, nested-property handling, deterministic/non-mutating behavior, cycle integration, tests, lint, and CI on the final branch HEAD.
