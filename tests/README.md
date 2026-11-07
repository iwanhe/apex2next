# Test Strategy

- `fixtures/`: sanitized Oracle/APEX source snippets and expected IR/target outputs.
- `regression/`: deterministic conversion and semantic regression suites.
- `e2e/`: generated application journeys using Playwright.

Every conversion rule requires positive and negative fixtures. Critical business routines require semantic parity tests; parser success or target compilation alone is not sufficient.


## Functional parity evidence

- \`fixtures/parity/\`: synthetic paired source/target observations for the parity engine contract.
- The offline comparator never executes source or target code. Playwright source/target capture is documented separately and remains gated on approved test environments and identities.
