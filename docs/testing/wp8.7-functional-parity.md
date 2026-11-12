# WP8.7 — APEX-to-target functional parity harness

## Objective

Compare paired observations captured from the source APEX application and the migrated Next.js/NestJS target. The harness evaluates evidence supplied by test runners; it does not execute SQL/PLSQL, invoke application endpoints, automate browsers, or infer expected behavior.

## Delivered offline baseline (CI-verified: 132 Python tests; all four CI jobs passed)

- Versioned JSON input contract: \`apex2next.functional-parity-input.v1\`.
- Six comparison domains: FUNCTIONAL, API, DATA, WORKFLOW, SECURITY, and UI.
- Exact JSON/scalar comparison, explicit numeric tolerance, and unordered-set comparison.
- Evidence references required on both sides. Missing observations or references produce \`NOT_VERIFIED\`, never PASS.
- Per-check and per-domain status plus deterministic aggregate report: \`apex2next.functional-parity.v1\`.
- Stable diagnostics: \`PARITY001\` missing source evidence, \`PARITY002\` missing target evidence, \`PARITY003\` mismatch.
- CLI exit codes: 0 PASS, 1 FAIL, 2 invalid input/I/O, 3 NOT_VERIFIED.
- Deterministic input SHA-256 and report output. Input is not mutated.

## Run

From repository root:

\`\`\`bash
PYTHONPATH=workers/extraction-worker/src python -m apex2next_extractor.parity_cli \\
  tests/fixtures/parity/synthetic-orders.json \\
  --output /tmp/orders-parity-report.json
\`\`\`

The checked-in synthetic example includes six paired observations, one per domain, and is expected to PASS. It is a contract/engine fixture only, not evidence that a real APEX app has matching behavior.

## Evidence contract

Each check contains a unique \`id\`, a category, a human-readable description, a comparator, and paired source/target evidence:

- \`value\`: observed JSON value captured by an approved test runner.
- \`evidenceRef\`: immutable artifact locator (for example a test result ID, trace ID, or retained JSON artifact path).

Comparators:
- \`EXACT\`: canonical JSON equality; array order matters.
- \`NUMERIC_TOLERANCE\`: numeric comparison with an explicitly declared finite, non-negative tolerance.
- \`UNORDERED_SET\`: array comparison ignoring order while retaining duplicate multiplicity.

No arbitrary expression, SQL, JavaScript, shell, URL fetch, or dynamic comparator is accepted. Evidence payloads must be sanitized before entering the manifest.

## Playwright journey adapter contract

The browser test suite is intentionally a separate capture layer. For each named journey, implement the same test contract against source and target environments using separate base URLs and test identities:

1. Record application/build identity, environment, role, journey ID, and test-data seed.
2. Perform user-visible interactions only; assert navigation, labels, validation messages, and resulting state.
3. Capture response status/body for documented API calls, with secrets and personal data redacted.
4. Capture screenshots/traces on failure and a compact JSON observation artifact on success.
5. Publish source and target observations with the same stable check IDs and evidence references into the input manifest.
6. Run the parity comparator only after both evidence sets exist.

Suggested Playwright projects: \`source-apex\` and \`target-next\`. Keep credentials in CI secrets; use isolated synthetic data and least-privilege test accounts. Do not copy session cookies, passwords, tokens, or production personal data into parity artifacts. Do not treat screenshot pixel equality as functional equivalence; use semantic locators and explicit assertions.

The current repository does not yet contain a sanitized real APEX application, source runtime credentials, stable target pilot, or approved journey catalogue. Therefore Playwright capture jobs are specified but not wired to execute against either application. This is deliberate: no URLs, credentials, selectors, business outcomes, or workflows are invented.

## Acceptance and limitations

- Overall PASS only when every supplied check passes.
- Any mismatch yields FAIL.
- Missing source/target observation or evidence reference yields NOT_VERIFIED.
- A zero-exit CLI result is not a production sign-off; the journey catalogue must be approved and coverage reviewed by business owners.
- Current synthetic fixtures verify comparator correctness, not actual APEX-to-Next.js semantic parity.
- Authentication/authorization parity requires equivalent test identities, policy contexts, and explicit allow/deny assertions.
- Data parity requires consistent source/target snapshots and reviewed canonicalization for timezone, decimal, collation, empty-string, and LOB semantics.
- Workflow parity requires matching starting state, actor role, event sequence, and terminal state.
- API parity requires documented contracts; transport status alone is insufficient for business equivalence.
- UI parity checks accessible names, labels, validation, and navigation. Visual baselines are supplemental.

## Next qualification inputs

1. Sanitized representative APEX export and source-side test environment.
2. Reviewed critical-journey catalogue with business expected outcomes.
3. Target pilot deployment and stable synthetic data seed/reset procedure.
4. Approved Playwright identities and environment-specific secret configuration.
5. API contract and data canonicalization rules.
6. Business-owner acceptance criteria and evidence retention policy.
