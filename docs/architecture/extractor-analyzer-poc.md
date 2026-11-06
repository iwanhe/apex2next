# Extractor and Schema Analyzer — Initial POC

## Goal

Establish safe, testable ingestion components before connecting to a live Oracle database or accepting a real APEX export as a migration baseline.

## Oracle APEX SQL export extractor

- Input: text APEX export SQL file.
- Processing: scan a subset of APEX import API calls; identify routine/object category; preserve named/raw arguments, simple scalar values, and source locations.
- Output contract: apex2next.apex-export.v1.
- Safety: never executes the export or evaluates PL/SQL expressions.

## APEXLang source extractor

- Input: directory containing .apx source files and optional .apex/apexlang.json metadata.
- Processing: statically inventory known declaration headers, direct scalar properties, lexical @references, file paths, and line numbers.
- Output contract: apex2next.apexlang-inventory.v1.
- Version metadata: preserve mmdVersion as apexlang_mmd_version; do not infer the Oracle APEX runtime release from it.
- Safety: no source expression or deployment instruction is executed.

## Oracle DDL analyzer

- Input: DDL text exported from application-owned Oracle schemas.
- Processing: tokenize a sanitized view of the script, identify common CREATE headers, and collect explicit REFERENCES edges.
- Output contract: apex2next.oracle-ddl-inventory.v1.
- Diagnostics/limitations: explicitly state unsupported grammar and unresolved dependencies.

## Current test coverage

Synthetic fixtures cover:
- Nested APEX export arguments and comma-containing string literals.
- Oracle alternative quoting in APEX export arguments.
- APEXLang declarations, nested blocks, scalar properties, comments, string literals, references, and malformed declaration diagnostics.
- Comments/string contents that resemble API calls or DDL.
- Common CREATE object categories and REFERENCES dependencies.

## Required next validation

1. Select a non-production APEX application with representative pages, regions, items, validations, processes, dynamic actions, LOVs, shared components, and authorization.
2. Export it from the actual source APEX version and sanitize secrets, endpoints, user data, and proprietary values.
3. Compare extracted call/declaration inventory with APEX Builder metadata and source database dictionary inventory.
4. Add version-specific fixtures and diagnostics for every missing construct.
5. Extend the normalized IR and conversion mapping only after coverage gaps are understood.

## Important boundary

These components are not yet full APEX application extractors or Oracle schema analyzers. They establish the first static parsing/inventory slice; live Oracle dictionary extraction, complete metadata modeling, dependency resolution, and completeness certification remain future work.
