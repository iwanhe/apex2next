# APEX Extraction Worker

The worker provides two safe, static source-ingestion paths. Neither executes source code.

## 1. Oracle APEX SQL export

    PYTHONPATH=workers/extraction-worker/src \
      python -m apex2next_extractor path/to/fxxx.sql --output build/apex-export.json

The SQL-export parser scans a subset of APEX import API calls and preserves raw argument expressions and source locations. It is not a PL/SQL interpreter or a complete APEX metadata extractor.

## 2. APEXLang source directory

    PYTHONPATH=workers/extraction-worker/src \
      python -m apex2next_extractor.apexlang_cli ./path/to/apexlang-project \
      --output build/apexlang-inventory.json

The directory should contain .apx files and may contain .apex/apexlang.json. The parser emits the apex2next.apexlang-inventory.v1 contract with declaration inventory, page list, direct scalar properties, lexical @reference inventory, source file/line locations, and diagnostics.

### Initial declaration categories

Application, page, page group, region, column, page item, button, process, validation, dynamic action, LOV, authentication, authorization, list, breadcrumb, theme, build option, component setting, static file, and supporting objects.

### Version handling

The parser reports the .apex/apexlang.json mmdVersion value as apexlang_mmd_version. This metadata value is not assumed to identify the Oracle APEX runtime release. Confirm the actual APEX runtime version separately from the source environment.

### Safety and limitations

- Files are read as UTF-8 text; no APEXLang, SQL, PL/SQL, JavaScript, or deployment instructions are executed.
- Comments and quoted literals are masked during declaration/reference discovery to avoid counting text that resembles syntax.
- This is an initial declaration inventory, not a complete APEXLang grammar or normalized application IR.
- Nested declarations and property values are represented conservatively; recursive object/array parsing is available for supported brace/bracket forms. SQL/PLSQL semantics, plug-in behavior, and dynamic references are not fully modeled.
- @references are collected lexically; target resolution and dangling-reference validation are not implemented.
- A successful parse does not prove semantic parity or conversion readiness. Unsupported behavior must remain visible for review.

## 3. Normalized IR schema validation (initial slice)

The shared JSON Schema contract is maintained at `packages/ir-schema/schema/apex2next.application-ir.v1.schema.json` (JSON Schema Draft 2020-12, IR version 1.0.0). Python callers can use:

```python
from apex2next_extractor.ir_schema import validate_ir_document

diagnostics = validate_ir_document(ir_document)
if diagnostics:
    raise ValueError(diagnostics)
```

The validator checks structure only. A schema-valid document is not evidence of complete extraction, reference resolution, conversion readiness, or semantic parity. Unknown source properties and expressions should remain represented in the IR.

## 4. Normalized Application IR v1 adapters

The first adapter implementation is available through the Python API:

```python
from apex2next_extractor import adapt_apexlang_directory, adapt_apex_export

apexlang_ir = adapt_apexlang_directory("./path/to/apexlang-project")
export_ir = adapt_apex_export(
    open("f100.sql", encoding="utf-8").read(),
    source_name="f100.sql",
)
```

Both adapters emit the shared `apex2next.application-ir.v1` shape. Stable object IDs are derived from source format, canonical type, source-native identifier, and parent scope where applicable. Fingerprints are content-derived and intentionally separate from identity. Source artifact SHA-256 hashes and source locators are retained.

The APEXLang adapter retains each declaration's raw body in extensions, maps recognized declarations, and collects lexical `@reference` candidates as PENDING. The SQL-export adapter maps supported import API calls and preserves every raw argument; unknown routines remain UNKNOWN objects with diagnostics. Neither adapter executes source content.

Current limitations:
- APEXLang parsing remains a static inventory parser, not a complete grammar. Nested declaration relationships are inferred from source indentation and must be validated against representative real projects.
- The APEX SQL-export parser recognizes only its current import API routine subset. It does not model every export call or establish all parent-child relationships.
- References are candidates only; the scope-aware resolver is a subsequent work package.
- Fallback identities without a stable source-native key are less robust than IDs based on native identifiers.
- The adapters do not claim semantic parity, conversion readiness, or runtime behavior.

The initial scope-aware resolver is also available:

```python
from apex2next_extractor import resolve_references

resolved_ir = resolve_references(apexlang_ir)
```

It resolves only exact source-native identifier matches inside the declared application scope. A single candidate becomes RESOLVED and creates an EXPLICIT dependency; zero candidates become DANGLING; multiple candidates become AMBIGUOUS. Unsupported syntax and invalid source/scope data receive diagnostics. The function returns a deep copy and does not mutate the input snapshot. Name similarity, fuzzy matching, and guessed targets are deliberately not used.

Validate an emitted document with `validate_ir_document(document)`; schema validity proves contract shape only.


### APEXLang typed property extraction

The APEXLang parser now exposes `property_details` alongside the backward-compatible `properties` map. The Normalized IR adapter decodes only unambiguous scalar literals:

- Single- and double-quoted strings
- Boolean literals
- Null literals
- Integer, decimal, and scientific-notation numbers

Each normalized property includes a property-level source locator with file, line, column, and source artifact hash. Values that are not recognized as scalar literals are preserved as `valueType: UNKNOWN` with their original `rawExpression`; they are never evaluated. Direct properties inside nested blocks are not flattened into the parent object. The full raw declaration body remains available in `extensions.rawDeclarationBody`.

This is intentionally a conservative first pass. Nested property-path normalization and full expression grammar coverage remain future work. A conservative lexical classifier now labels only high-confidence SQL, PL/SQL, and JavaScript expressions; HTML, CSS, and APEX substitution forms are recorded as language metadata while retaining UNKNOWN valueType.


### Nested APEXLang properties

Multiline brace-delimited property blocks are normalized recursively as `OBJECT` values. For example, a `navigation` block containing a `homeUrl` block and a numeric `page` property becomes nested property records; each node keeps its own `valueType` and source locator. Non-literal leaf expressions remain `UNKNOWN` with the original `rawExpression`. The complete declaration body is still retained as the lossless source fallback.

This parser pass intentionally does not claim support for every inline/mixed brace form or multiline expression grammar. It does not evaluate any source expression.


### Multiline APEXLang property expressions

Property extraction preserves a multiline expression as one raw value until the next sibling property or enclosing block/declaration boundary. The IR property locator includes start and end line/column coordinates. Property declarations are recognized only through an explicit colon or a brace-delimited object opener, so nested component declarations such as region/process blocks are not treated as property values.

This is a conservative line-boundary heuristic, not a complete APEXLang expression grammar. Ambiguous continuation layouts, inline/mixed blocks, arrays, and semantic SQL/PLSQL parsing remain unsupported. Expressions are never evaluated.


### Conservative expression classification and cross-format mapping

Both source adapters use the same expression-property normalizer. When a raw expression matches a high-signal syntax pattern, the IR records a language, confidence, and versioned rule ID. SQL, PL/SQL, and JavaScript use the corresponding IR expression value types. HTML, CSS, and APEX substitution patterns retain `valueType: UNKNOWN` and expose their language only as metadata because the current schema has no dedicated value types for them.

The original `rawExpression` is always preserved. Ambiguous snippets such as `return status` or `status = 'OPEN'` remain UNKNOWN; the classifier does not infer a language from property names, evaluate expressions, or claim semantic validity. The rules are lexical first-pass evidence and need grammar-backed expansion plus representative production fixtures.


### Expression classification and canonical property mapping

Normalized properties retain both `sourcePropertyName` and `canonicalPropertyName`. The first alias set is intentionally narrow and object-specific: APEX SQL Export PAGE `p_source` maps to canonical `source`; REGION `p_plug_source` maps to `source`. APEXLang property names are preserved as their canonical names. This mapping does not claim semantic equivalence beyond these explicit aliases.

Expression properties include `expressionLanguage`, `classificationConfidence`, and `classificationRule`. The lexical classifier recognizes a limited set of SQL, PL/SQL, JavaScript, APEX substitution, HTML, and CSS forms. Unmatched expressions remain UNKNOWN and all raw expressions are retained; no source expression is executed. This remains an initial classifier, not a full language parser.


### APEXLang grammar and AST foundation (incremental)

A first structural parsing layer is available alongside the existing inventory parser:

- Grammar source: `workers/extraction-worker/grammar/ApexLang.g4`.
- Python API: `parse_apexlang_ast(source)` and `tokenize_apexlang(source)`.
- Token records preserve exact source offsets and start/end line-column spans.
- Declaration AST nodes preserve the raw declaration body and represent nested declarations as children.
- Quoted strings, comments, and fenced SQL/text blocks are handled atomically so declaration-like text inside them is not counted as syntax.
- Parentheses inside multiline expressions are balanced separately from declaration delimiters.
- Unterminated strings, comments, fenced blocks, and declarations produce structured AST diagnostics.

This is an incremental grammar/AST foundation, not yet the production parser for the adapters. It models declaration structure, typed property nodes, recursive supported object/array values, and lossless source spans. The Python AST parser remains dependency-free and is not generated from the maintained ANTLR grammar. Full APEXLang coverage, comprehensive recovery, and AST-to-IR semantic parity remain qualification work; the adapter now consumes typed AST properties when explicit parity checks pass.


### Typed APEXLang property AST (WP2 initial slice)

The AST declaration model now exposes a `properties` collection of typed `ApexLangProperty` nodes:

- Scalar types: STRING, NUMBER, BOOLEAN, NULL.
- Multiline brace-delimited OBJECT values with recursively parsed child properties.
- Bracket-delimited ARRAY values, including nested arrays and arrays of object values.
- Non-literal source remains EXPRESSION with its original raw value; it is never evaluated.
- Duplicate property keys are retained in source order and reported as `AST102`.
- Unterminated object/array values produce `AST101`.
- Property and nested property nodes retain source spans in the original source file.
- Property collection is scoped to the direct declaration level, so child declaration properties are not copied into their parent.

Public API: `parse_apexlang_ast`, `parse_apexlang_properties`, and the `ApexLangProperty` / `SourceSpan` models.

Current boundaries: supported inline and nested object/array values are parsed recursively, but this is not a complete APEXLang expression grammar. Error recovery is conservative and diagnostic-driven; parser limits are enforced, while a sanitized representative real-source corpus and AST-to-IR semantic parity remain outstanding. Seeded generated-value tests and declaration-inventory parity against committed synthetic fixtures are included.


### Parser hardening (WP3 initial completion)

The structural AST parser now supports recursive object/array values, including arrays of objects, nested arrays, and inline object properties. Non-literal expressions remain raw source and are never executed. Duplicate keys remain in source order and produce AST102; malformed object/array containers produce AST101; unsupported object members produce AST104; excessive property nesting produces AST103.

The public AST entry point applies configurable defaults of 2,000,000 source characters, 250,000 tokens, and 128 delimiter-nesting levels. Limit violations return deterministic AST900, AST901, or AST903 errors rather than attempting unbounded parsing. The recursive property parser separately caps nesting at 128.

CI validates the maintained ANTLR grammar by generating a Python parser with the pinned ANTLR 4.13.2 tool. This is grammar validation only: the production Python parser is intentionally dependency-free and is not generated by or runtime-backed by ANTLR. Synthetic malformed-input regression cases are included; seeded generated-value/property-style regression tests are included; a sanitized real-project corpus remains outstanding.


### APEXLang AST-to-Normalized IR integration (WP4)

The APEXLang adapter now parses each `.apx` file through both the existing inventory parser and the typed AST parser. The inventory parser remains authoritative for declaration discovery, object taxonomy, identity, containment, and reference extraction. AST properties become the IR property source only when the ordered direct-property names match the inventory output exactly.

If the two parsers disagree, the adapter retains the legacy inventory mapping and emits `IRAST001`. Missing declaration matches and AST-only declarations are reported as `IRAST002` and `IRAST003`; the adapter does not synthesize objects from an unverified AST declaration. AST parser diagnostics are retained with file and source-span provenance. AST errors mark affected objects as parse PARTIAL.

Recursive object/array properties map to the existing IR property contract. Expressions use the shared conservative classifier without execution. Exact AST property source remains available under `extensions.rawSourceValue`; declaration source remains available under `extensions.rawDeclarationBody`. IR metadata records the AST parser version, integration mode, declaration match count, property adaptation count, legacy fallback count, and AST diagnostic count.

This is a parity-guarded typed-property integration, not a complete replacement of the inventory parser. Real-project coverage and semantic equivalence remain unverified until a sanitized representative APEXLang project is available.


WP4 lossless duplicate-property safeguard: because the IR `properties` field is a unique-key map, repeated direct APEXLang property names are additionally preserved in source order under `extensions.duplicateProperties` and reported with `IRAST004`. For nested OBJECT properties, duplicate child names and their typed payloads are preserved in the nested property's `extensions.duplicateProperties` / `duplicatePropertyNames`. Consumers should inspect these extensions whenever duplicate-property diagnostics are present.

### Dependency graph and impact analysis (WP5)

After resolving references, build a deterministic dependency graph:

```python
from apex2next_extractor import analyze_dependency_graph, resolve_references

resolved_ir = resolve_references(apexlang_ir)
graph = analyze_dependency_graph(resolved_ir)
```

The graph contract is `apex2next.dependency-graph.v1`. Each edge points from a dependent object (`sourceObjectId`) to its prerequisite (`targetObjectId`); `migrationOrder` is therefore dependency-first. The report includes graph nodes/edges, strongly connected cycles, blocked nodes, deterministic migration order for the acyclic portion, per-node direct/transitive impact, and diagnostics.

Only explicit IR dependency records and uniquely resolved references become edges. PENDING, DANGLING, AMBIGUOUS, UNSUPPORTED, and INVALID references are excluded from ordering and reported. Missing or duplicate object identities and invalid endpoints are diagnosed. Cycles and downstream blocked objects are distinguished.

The analyzer intentionally does not infer dependencies from names, SQL/PLSQL text, arbitrary property values, or parent-child containment. Its result is a structural planning aid; real-project coverage and typed APEX dependency semantics still require a sanitized representative application corpus.


### WP6 — semantic analysis and transformation planning

```python
from apex2next_extractor import analyze_semantics, analyze_dependency_graph
graph = analyze_dependency_graph(ir_document)
plan = analyze_semantics(ir_document, graph)
print(plan["summary"])
```

The API classifies components as AUTOMATIC, ASSISTED, MANUAL, or UNSUPPORTED and returns expression-level plans, rule IDs, confidence, provenance, preservation metadata, and SEM001–SEM008 diagnostics. No component is currently AUTOMATIC. Unknown expressions, plug-ins, security behavior, unresolved references, and PL/SQL require review. The report is deterministic and non-mutating; source expressions are never executed and no target code is generated.

See `docs/architecture/wp6-semantic-analysis.md` for mapping, diagnostics, and qualification limits. The initial rules require validation against a sanitized representative APEX application before production code generation.


## 5. WP7 — Target project generation

Generate a buildable Next.js/NestJS/PostgreSQL scaffold from a schema-valid Normalized IR snapshot:

```bash
PYTHONPATH=workers/extraction-worker/src python -m apex2next_extractor.generator_cli \
  build/application-ir.json --output build/generated-target
```

Python API:

```python
from apex2next_extractor import generate_project
result = generate_project(ir_document, "build/generated-target")
```

The generator validates IR, re-runs WP5 dependency analysis and WP6 semantic analysis, then emits deterministic Next.js App Router page shells, a NestJS health API, a PostgreSQL baseline migration, source/semantic/dependency reports, manual-review diagnostics, and a SHA-256 generation manifest. It refuses a non-empty output directory unless overwrite is explicitly enabled.

The current implementation intentionally does not generate business tables from UI metadata, execute or translate arbitrary SQL/PL/SQL/JavaScript, reproduce APEX session/security semantics, or claim functional parity. SQL/PLSQL and unsupported/plugin/security behavior remain review items. Schema conversion, data transfer, business service generation, and authentication implementation require their own validated source contracts and work packages.

Generated project checks: pnpm install, pnpm build, pnpm test, and pnpm typecheck. The generated project is a structural starting point, not a production cutover artifact.


### WP7 follow-on scaffolding

The generator also emits disabled placeholder controls for page items whose parent page is explicit in IR, page-item DTO classes with unknown field types, per-process NestJS service stubs that throw NotImplementedException, and authentication/authorization scaffolding that fails closed with ServiceUnavailableException. These are explicit review placeholders, not migrated business behavior. No process endpoint is exposed and no login provider is configured.


## 5. WP8.6 — Generated PostgreSQL runtime baseline

The generator emits a reusable PostgreSQL runtime foundation, not application-specific business repositories:
- pg Pool provider requiring DATABASE_URL, bounded by DB_POOL_MAX, with connection timeouts.
- NestJS database module and graceful shutdown.
- /health liveness and /health/ready database-readiness endpoints.
- Parameterized generic repository primitives. SQL values are bind parameters; table and column identifiers must match a strict lowercase allowlist and configured writable-column list.
- Explicit transaction helper with rollback on failure and guaranteed client release.
- pnpm db:migrate applies only checked-in target-owned SQL migrations in deterministic order, using a PostgreSQL advisory lock and per-file transaction.

Start local PostgreSQL with docker compose up -d postgres, then run pnpm db:migrate. Set DATABASE_URL before starting the API. The generated integration test verifies CRUD, bind-parameter handling, identifier/column rejection, and transaction rollback against a disposable PostgreSQL database.

No business schema, entity, or service is guessed from page items. Application-specific runtime generation requires reviewed schema/domain metadata and approved service contracts. Production qualification still requires TLS/secrets management, pool sizing, observability, load testing, and representative application data.
