# Consolidation of draft PRs #2 and #3 into the Foundation branch (2026-11-12)

Owner decision 2026-11-12: `feat/foundation-and-architecture-docs` is the single integration line. PR #2
(`feat/r2-shared-runtime`, head 51ebf56) and PR #3 (`feat/r3-ui-generator`, head 35d640e) were not rebased:
both duplicate work that Foundation already carries in a later, tested form. The pieces Foundation lacked were
ported into the existing packages with tests; the PRs are closed with a link to this note.

## State before consolidation

| PR | Merge base | Only in PR | Only in Foundation | Merge conflicts with d963bfe | CI at head |
|---|---|---|---|---|---|
| #2 R2 shared runtime | 852c19e | 60 commits, 38 files, +1420 | 6 commits | 5 files (pilot forms.ts, package.json, lockfile, workspace, packages/README) | no check run |
| #3 R3 UI generator | 6cdb61d | 33 commits, 10 files, +597 | 4 commits | 1 file (docs/panduan/README.md) | 7/7 green |

PR #2 adds `packages/shared-runtime`, `packages/nestjs-adapter` and `packages/nextjs-adapter`. Foundation has had
`@apex2next/runtime-api` and `@apex2next/runtime-web` since 6cdb61d; the pilot (J-01..J-05, e2e 12/12) and every
application created by `apex2next new` run on them. PR #3 extends the R1 normalized-IR generator
(`extraction-worker/generator.py`); Foundation's R3 generator (`schema-analyzer/app_generator.py` with the
region SQL translator) supersedes that path.

## Ported (in `@apex2next/runtime-api`, tests in `examples/f170134-target/apps/api/test/unit.test.js`)

| From PR #2 | Gap in Foundation | Now |
|---|---|---|
| `validation.ts` trim policy (BOTH / LEADING / TRAILING) | Text items were always trimmed on both sides; 67 of 510 text items in the 26.2 sample apps have `trim_spaces` NONE | `normalizeValue()` honours the item's `trim_spaces` attribute (BOTH default; numbers and dates always trimmed because they are parsed); `''` stays NULL. Used by `validateItems` and the entered key of `validateForInsert` |
| `report.ts` safe paging arithmetic | `?page=Infinity` or a huge page put a non-integer OFFSET into the SQL (HTTP 500) | `runReport` refuses a page whose offset is not a safe integer (INVALID_INPUT, HTTP 422); garbage still falls back to page 1 as before |
| `report.ts` hidden columns not sortable | A user could sort by a hidden column (reveals the order of values the region does not show) | A hidden column is refused as an explicit sort unless it is the region's default sort |
| `session.ts` issued-in-future / max-age checks | Only signature and expiry were checked | `verifySession(..., { maxLifetimeSeconds, clockSkewSeconds })`: tokens with `iat` more than 60 s ahead or `exp - iat` above the configured `SESSION_TTL_SECONDS` are refused, so shrinking the TTL also shortens tokens already issued. `AuthGuard` passes the TTL |

## Already covered in Foundation (not ported)

- Required / numeric / range / ISO date validation and unknown-or-non-writable field rejection: `validateItems`,
  with the APEX runtime messages (`must be a number between …`, `does not match format …`), which PR #2 did not have.
- Lost-update protection: `lockForChange` (checksum, fail closed) instead of `assertRuntimeVersion`.
- Navigation filtered by authorization scheme, relative-path-only return targets: `Shell`, `safeReturn`.
- Fail-closed authorization: `evaluateScheme` (no rule = deny). PR #2's `ALL_ROLES` mode is not an APEX scheme
  type (APEX "is in role or group" is any-of), so it was not added.
- LOVs: static LOVs and translated SQL LOVs are generated (`LOV_SOURCES`, `staticLov`), never caller SQL.
- PR #3 query-migration plan and static LOV adapters: covered by the R3 region/LOV SQL translator and
  `ui/generation-report.json`. PR #3's UI metadata allowlist aims to keep SQL out of the browser; in Foundation
  the UI spec is only imported by server components (checked: no SQL text in the pilot's `.next/static` chunks).

## Kept as input for later work (not ported)

- PR #2 `events.ts` (dynamic-action allowlist per event, target check, ordered sequences): no consumer yet;
  to be revisited when the generator supports declarative dynamic actions.
- PR #2 `contracts.ts` / IR JSON schema changes: `packages/ir-schema` in Foundation is unchanged and remains
  the IR contract.

## Verification after the port

Pilot API 66/66 (63 + 3 new unit tests), runtime-web 3/3, pilot e2e 12/12, parity journeys J-01..J-05 PASS
(0 state differences, 0 message mismatches), Python suite 289 passed (4 skips by policy: source exports not
committed), Forms Patterns repacked with the new runtime: `apex2next smoke` 9/9.
