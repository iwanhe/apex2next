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
