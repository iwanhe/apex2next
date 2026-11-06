# APEX Export Extractor — POC

A static parser for Oracle APEX application export SQL. It scans APEX import API calls, extracts a first metadata subset, and emits normalized JSON with source locations and raw argument expressions.

## Run

```bash
PYTHONPATH=workers/extraction-worker/src \
  python -m apex2next_extractor path/to/fxxx.sql --output build/apex-export.json
```

## Initial recognized objects
Application, page, region, item, button, branch, validation, process, dynamic-action event/action, list/list item, LOV, authentication, authorization, theme, and plug-in calls. Other APEX import calls are retained as `OTHER` instead of discarded.

## Safety and limitations
- Export SQL is parsed as text; it is never executed.
- Nested parentheses, quoted strings, comments, and Oracle alternative quoting are handled for call-boundary detection.
- Argument expressions are preserved as raw text when they cannot be decoded as simple scalar literals.
- This is not a complete PL/SQL parser and does not yet resolve all cross-object semantics, page processes, plug-in behavior, or APEX version differences.
- A real sanitized APEX export is required to validate coverage against the target APEX version.
