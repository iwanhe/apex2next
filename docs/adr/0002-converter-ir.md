# ADR-0002: Converter architecture and intermediate representation

- **Status:** Accepted
- **Date:** 2026-11-06
- **Decision owners:** Project owner

## Context
Direct text-to-text conversion is fragile for nested SQL/PLSQL and APEX metadata with dependencies.

## Decision
Use parser → AST → normalized intermediate representation (IR) → versioned transformation rules → target generators. Preserve source locations, dependencies, hashes, diagnostics, and rule-set version in the conversion record.

ANTLR-based grammars are preferred where suitable and maintained. Regular expressions are not the primary parser for nested language constructs.

## Consequences
The IR adds initial implementation work but supports multiple generators, traceability, deterministic conversion, and regression testing. Grammar coverage and semantic modeling remain explicit risks.
