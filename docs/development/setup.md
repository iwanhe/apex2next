# Development Setup

## Prerequisites
- Git
- Node.js 22+
- pnpm 10+
- Python 3.12+
- Docker Engine/Desktop with Compose

## Bootstrap
```bash
git clone https://github.com/iwanhe/apex2next.git
cd apex2next
corepack enable
pnpm install
cp .env.example .env
docker compose up -d postgres
```

This repository currently establishes the workspace and local PostgreSQL service. App/package entry points will be added incrementally.

## Local database
```bash
docker compose ps
docker compose logs -f postgres
```

Change the sample password before exposing PostgreSQL beyond localhost. Never commit real .env files or production data.

## Engineering rules
- Keep source and generated artifacts distinguishable.
- Add parser/converter fixtures for every newly supported construct.
- Add regression tests for semantic defects.
- Every diagnostic has a stable code and severity.
- Do not place secrets or production data in fixtures.
- Run format, lint, typecheck, tests, and security checks before PR.
