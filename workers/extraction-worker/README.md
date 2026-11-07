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
- Nested property blocks, complex values, SQL/PLSQL semantics, plug-in behavior, and dynamic references are not fully modeled.
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
