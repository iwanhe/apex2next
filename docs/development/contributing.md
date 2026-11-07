# Contributing

## Workflow
1. Start from the current integration branch and create a focused feature/fix branch.
2. Keep each PR limited to one coherent change.
3. Add or update tests and documentation with the implementation.
4. Run the checks listed below locally.
5. Open a PR with scope, risk, test evidence, data/schema impact, and rollback notes.
6. Address review feedback; do not merge failing or unreviewed changes.

## Branch naming
- `feat/<short-name>`
- `fix/<short-name>`
- `docs/<short-name>`
- `chore/<short-name>`

## Commit messages
Use Conventional Commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`, `build:`, `ci:`.

## Local checks
```bash
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
python -m ruff check workers tests
python -m pytest
```

## Pull request checklist
- [ ] Scope and behavior are explained.
- [ ] Tests/fixtures cover expected and edge behavior.
- [ ] No secrets or production data are included.
- [ ] Security and authorization implications are addressed.
- [ ] Schema/API compatibility and migration impact are documented.
- [ ] Diagnostics are stable and source-traceable where applicable.
- [ ] Logs and metrics are sufficient to troubleshoot.
- [ ] Rollback/recovery approach is documented for risky changes.
