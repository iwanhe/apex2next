# Extractor and Schema Analyzer — Initial POC

## Goal
Establish safe, testable ingestion components before connecting to a live Oracle database or accepting a real APEX export as a migration baseline.

## APEX export extractor
- Input: text APEX export SQL file.
- Processing: scan calls to APEX import APIs; identify routine/object category; preserve named/raw arguments, simple scalar values, and source line/column.
- Output contract: `apex2next.apex-export.v1`.
- Diagnostics: stable parser codes for malformed/unterminated structures.
- Safety: never executes the export or evaluates PL/SQL expressions.

## Oracle DDL analyzer
- Input: DDL text exported from application-owned Oracle schemas.
- Processing: tokenize a sanitized view of the script, identify common CREATE headers, and collect explicit REFERENCES edges.
- Output contract: `apex2next.oracle-ddl-inventory.v1`.
- Diagnostics/limitations: explicitly state unsupported grammar and unresolved dependencies.

## Current test coverage
Synthetic fixtures cover:
- Nested argument expressions and comma-containing string literals.
- Oracle alternative quoting in APEX export arguments.
- Comments/string contents that resemble API calls or DDL.
- Common CREATE object categories and REFERENCES dependencies.
- Unterminated APEX call diagnostics.

## Required next validation
1. Select a non-production APEX application with representative pages, regions, items, validations, processes, dynamic actions, LOVs, shared components, and authorization.
2. Export it from the actual source APEX version and sanitize secrets, endpoints, user data, and proprietary values.
3. Compare extracted call inventory with APEX Builder export metadata and source database dictionary inventory.
4. Add version-specific fixtures and diagnostics for every missing construct.
5. Only then extend the normalized IR and conversion mapping.

## Important boundary
This POC is not yet a full APEX application extractor or Oracle schema analyzer. It establishes the first static parsing/inventory slice; live Oracle dictionary extraction, complete metadata modeling, dependency resolution, and completeness certification remain future work.
