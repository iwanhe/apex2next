"""Conservative deterministic target-project generator."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any

from .dependency_graph import analyze_dependency_graph
from .ir_schema import validate_ir_document
from .semantic_analysis import analyze_semantics
from .runtime_templates import build_runtime_files
from .ui_generator import build_ui_generator_files

GENERATOR_VERSION = "0.3.0"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def _slug(value: str, fallback: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:48] or fallback


def _route(obj: dict[str, Any]) -> str:
    identity = str(obj.get("id", "unknown"))
    return f"{_slug(str(obj.get('name') or ''), 'page')}-{hashlib.sha256(identity.encode()).hexdigest()[:8]}"


def _tsx(value: Any) -> str:
    return html.escape(str(value), quote=False)


def _files(doc: dict[str, Any], sem: dict[str, Any], graph: dict[str, Any]) -> dict[str, str]:
    app = doc["application"]
    name = str(app.get("name") or "Migrated APEX application")
    pages = sorted((o for o in doc.get("objects", []) if o.get("type") == "PAGE"),
                   key=lambda o: str(o.get("id", "")))
    routes = [(o, _route(o)) for o in pages]
    links = "\n".join(
        f'        <li><a href="/pages/{path}">{_tsx(o.get("name") or o.get("id"))}</a></li>'
        for o, path in routes
    ) or "        <li>No extracted pages; inspect the migration report.</li>"
    manual = [
        f"- {o['objectId']} ({o['objectType']}): {o['component']['classification']} — "
        f"{o['component'].get('reason', o['component'].get('target') or 'No mapping')}"
        for o in sem["objects"] if o["component"]["classification"] in {"MANUAL", "UNSUPPORTED"}
    ]
    diagnostics = [f"- [{d['severity']}] {d['code']}: {d['message']}" for d in sem["diagnostics"]]
    summary = {
        "applicationId": app.get("id"), "pageCount": len(pages),
        "objectCount": sem["summary"]["objectCount"],
        "classificationCounts": sem["summary"]["classificationCounts"],
        "diagnosticCounts": sem["summary"]["diagnosticCounts"],
        "manualOrUnsupportedObjectIds": [o["objectId"] for o in sem["objects"]
            if o["component"]["classification"] in {"MANUAL", "UNSUPPORTED"}],
        "generatedBusinessSchema": False, "generatedBusinessLogic": False,
    }
    files = {
        "README.md": f"""# Generated APEX2NEXT target project

Application: {name}

This deterministic scaffold is not proof of behavioral equivalence or production readiness.

- apps/web: Next.js App Router frontend.
- apps/api: NestJS API scaffold and health endpoint.
- db/migrations: PostgreSQL baseline migration only.
- migration-report: preserved IR, semantic plan, dependencies, and diagnostics.

Requirements: Node.js 22+, pnpm 10+, Docker.
Install dependencies with pnpm install, start PostgreSQL with docker compose up -d postgres,
then run pnpm dev. Web is on port 3000; API health is on port 3001/health.
Run pnpm build, pnpm test, and pnpm typecheck before deployment.

Generated routes are structural placeholders. Arbitrary SQL, PL/SQL, JavaScript,
plug-in code, authorization rules, and business processes are not executed or
silently translated. No business tables are guessed from UI metadata. Review
migration-report/manual-review.md and semantic-analysis.json before extending.
""",
        "package.json": _json({"name": "apex2next-generated-project", "private": True,
            "version": "0.1.0", "packageManager": "pnpm@10.0.0", "engines": {"node": ">=22"},
            "scripts": {"dev": "pnpm --parallel --filter @generated/web --filter @generated/api dev",
                "build": "pnpm -r build", "test": "pnpm -r test", "typecheck": "pnpm -r typecheck"}}) + "\n",
        "pnpm-workspace.yaml": "packages:\n  - 'apps/*'\n",
        "tsconfig.base.json": _json({"compilerOptions": {"target": "ES2022", "module": "commonjs",
            "moduleResolution": "node", "strict": True, "esModuleInterop": True, "skipLibCheck": True}}) + "\n",
        ".gitignore": "node_modules/\ndist/\n.next/\n.env\ncoverage/\n",
        ".env.example": "DATABASE_URL=postgresql://apex2next:apex2next@localhost:5432/apex2next\nAPI_PORT=3001\n",
        "docker-compose.yml": """services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: apex2next
      POSTGRES_USER: apex2next
      POSTGRES_PASSWORD: apex2next
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
volumes:
  postgres_data:
""",
        "apps/web/package.json": _json({"name": "@generated/web", "private": True, "version": "0.1.0",
            "scripts": {"dev": "next dev -p 3000", "build": "next build", "test": "node --test",
                "typecheck": "tsc --noEmit"},
            "dependencies": {"next": "^15.5.0", "react": "^19.1.0", "react-dom": "^19.1.0"},
            "devDependencies": {"@types/node": "^22.0.0", "@types/react": "^19.0.0",
                "@types/react-dom": "^19.0.0", "typescript": "^5.7.2"}}) + "\n",
        "apps/web/tsconfig.json": _json({"extends": "../../tsconfig.base.json",
            "compilerOptions": {"lib": ["dom", "dom.iterable", "esnext"], "noEmit": True,
                "jsx": "preserve", "incremental": True, "plugins": [{"name": "next"}]},
            "include": ["next-env.d.ts", ".next/types/**/*.ts", "**/*.ts", "**/*.tsx"],
            "exclude": ["node_modules"]}) + "\n",
        "apps/web/next-env.d.ts": '/// <reference types="next" />\n/// <reference types="next/image-types/global" />\n',
        "apps/web/next.config.ts": "import type { NextConfig } from 'next';\nconst config: NextConfig = {};\nexport default config;\n",
        "apps/web/app/globals.css": "body{margin:0;background:#f7f8fa;color:#172033;font-family:Arial,sans-serif}.container{max-width:960px;margin:0 auto;padding:3rem 1.5rem}.muted{color:#52627a}a{color:#1457b8}\n",
        "apps/web/app/layout.tsx": f"""import type {{ Metadata }} from 'next';
import './globals.css';
export const metadata: Metadata = {{ title: {json.dumps(name)}, description: 'Generated APEX2NEXT scaffold' }};
export default function RootLayout({{ children }}: Readonly<{{ children: React.ReactNode }}>) {{
  return <html lang="en"><body>{{children}}</body></html>;
}}
""",
        "apps/web/app/page.tsx": f"""export default function HomePage() {{
  return <main className="container"><h1>{_tsx(name)}</h1>
    <p>Generated from a Normalized IR snapshot.</p><h2>Extracted pages</h2><ul>
{links}
    </ul><p className="muted">Structural placeholders only. Review migration report.</p>
  </main>;
}}
""",
        "apps/api/package.json": _json({"name": "@generated/api", "private": True, "version": "0.1.0",
            "scripts": {"dev": "tsx watch src/main.ts", "build": "tsc -p tsconfig.build.json",
                "start": "node dist/main.js", "test": "node --test", "typecheck": "tsc --noEmit"},
            "dependencies": {"@nestjs/common": "^11.0.0", "@nestjs/core": "^11.0.0",
                "@nestjs/platform-express": "^11.0.0", "reflect-metadata": "^0.2.2", "rxjs": "^7.8.1"},
            "devDependencies": {"@types/node": "^22.0.0", "tsx": "^4.19.0", "typescript": "^5.7.2"}}) + "\n",
        "apps/api/tsconfig.json": _json({"extends": "../../tsconfig.base.json",
            "compilerOptions": {"declaration": True, "sourceMap": True, "outDir": "./dist",
                "incremental": True, "experimentalDecorators": True, "emitDecoratorMetadata": True},
            "include": ["src/**/*.ts"], "exclude": ["node_modules", "dist", "test"]}) + "\n",
        "apps/api/tsconfig.build.json": _json({"extends": "./tsconfig.json",
            "compilerOptions": {"noEmit": False, "incremental": False},
            "exclude": ["node_modules", "dist", "test"]}) + "\n",
        "apps/api/src/main.ts": """import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.enableShutdownHooks();
  await app.listen(Number(process.env.API_PORT ?? 3001), '0.0.0.0');
}
void bootstrap();
""",
        "apps/api/src/app.module.ts": """import { Module } from '@nestjs/common';
import { HealthController } from './health.controller';
@Module({ controllers: [HealthController] })
export class AppModule {}
""",
        "apps/api/src/health.controller.ts": """import { Controller, Get } from '@nestjs/common';
@Controller()
export class HealthController {
  @Get('health')
  health() { return { status: 'ok', service: 'apex2next-generated-api' }; }
}
""",
        "db/migrations/0001_baseline.sql": """-- Business tables are not inferred from UI metadata.
CREATE SCHEMA IF NOT EXISTS app;
CREATE TABLE IF NOT EXISTS app.schema_migrations (
  version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO app.schema_migrations(version) VALUES ('0001_baseline')
ON CONFLICT (version) DO NOTHING;
""",
        "migration-report/README.md": """# Migration report

- source-ir.json: preserved Normalized IR snapshot.
- semantic-analysis.json: WP6 component and expression plan.
- dependency-graph.json: WP5 ordering and cycle metadata.
- summary.json: compact generation summary.
- manual-review.md: manual/unsupported objects and diagnostics.

This report does not certify runtime equivalence.
""",
        "migration-report/summary.json": _json(summary) + "\n",
        "migration-report/semantic-analysis.json": _json(sem) + "\n",
        "migration-report/dependency-graph.json": _json(graph) + "\n",
        "migration-report/source-ir.json": _json(doc) + "\n",
        "migration-report/manual-review.md": "# Manual review required\n\n"
            + ("\n".join(manual) if manual else "- No manual/unsupported component objects.")
            + "\n\n## Diagnostics\n\n"
            + ("\n".join(diagnostics) if diagnostics else "- No semantic diagnostics.") + "\n",
    }
    for obj, path in routes:
        title = _tsx(obj.get("name") or f"APEX page {obj.get('id')}")
        oid = _tsx(obj.get("id"))
        files[f"apps/web/app/pages/{path}/page.tsx"] = f"""export default function Page() {{
  return <main className="container"><h1>{title}</h1>
    <p className="muted">Source object: <code>{oid}</code></p>
    <p>Structural scaffold only. Review migration report before implementing behavior.</p>
  </main>;
}}
"""
    return files



def _extend_files(files: dict[str, str], doc: dict[str, Any]) -> None:
    """Add fail-closed security scaffolds, explicit process stubs, and typed placeholder DTOs."""
    objects = doc.get("objects", [])
    auth_service = """import { Injectable, ServiceUnavailableException } from '@nestjs/common';
@Injectable()
export class AuthService {
  login(): never {
    throw new ServiceUnavailableException('Configure an identity provider before enabling authentication.');
  }
}
"""
    auth_guard = """import { CanActivate, ExecutionContext, Injectable, ServiceUnavailableException } from '@nestjs/common';
@Injectable()
export class AuthorizationReviewGuard implements CanActivate {
  canActivate(_context: ExecutionContext): never {
    throw new ServiceUnavailableException('Authorization is not migrated; access remains fail-closed.');
  }
}
"""
    files["apps/api/src/auth/auth.service.ts"] = auth_service
    files["apps/api/src/auth/authorization-review.guard.ts"] = auth_guard
    imports = ["import { AuthService } from './auth/auth.service';"]
    providers = ["AuthService"]
    for obj in sorted((o for o in objects if o.get("type") == "PROCESS"),
                      key=lambda o: str(o.get("id", ""))):
        identity = str(obj.get("id", "process"))
        suffix = hashlib.sha256(identity.encode()).hexdigest()[:8]
        class_name = "Generated" + "".join(p.title() for p in re.findall(r"[A-Za-z0-9]+", str(obj.get("name") or "Process"))) + suffix
        file_name = _slug(str(obj.get("name") or ""), "process") + "-" + suffix
        imports.append(f"import {{ {class_name} }} from './processes/{file_name}.service';")
        providers.append(class_name)
        files[f"apps/api/src/processes/{file_name}.service.ts"] = (
            "import { Injectable, NotImplementedException } from '@nestjs/common';\n"
            "@Injectable()\n"
            f"export class {class_name} {{\n"
            "  execute(): never {\n"
            f"    throw new NotImplementedException('Source process {identity} needs manual business-logic conversion.');\n"
            "  }\n}\n"
        )
    files["apps/api/src/app.module.ts"] = (
        "import { Module } from '@nestjs/common';\n"
        "import { HealthController } from './health.controller';\n"
        + "\n".join(imports) + "\n"
        + "@Module({ controllers: [HealthController], providers: [" + ", ".join(providers) + "] })\n"
        + "export class AppModule {}\n"
    )
    files["apps/api/test/generated-scaffold.test.js"] = (
        "const test = require('node:test');\n"
        "const assert = require('node:assert/strict');\n"
        "const fs = require('node:fs');\n"
        "const path = require('node:path');\n"
        "test('API scaffold includes health and fail-closed security files', () => {\n"
        "  for (const file of ['src/health.controller.ts','src/auth/auth.service.ts',"
        "'src/auth/authorization-review.guard.ts','src/app.module.ts']) "
        "assert.ok(fs.existsSync(path.join(__dirname, '..', file)), file);\n"
        "});\n"
    )
    files["apps/web/test/generated-routes.test.js"] = (
        "const test = require('node:test');\n"
        "const assert = require('node:assert/strict');\n"
        "const fs = require('node:fs');\n"
        "const path = require('node:path');\n"
        "test('generated root route exists', () => {\n"
        "  assert.ok(fs.existsSync(path.join(__dirname, '../app/page.tsx')));\n"
        "});\n"
    )
    for page in (o for o in objects if o.get("type") == "PAGE"):
        items = sorted((o for o in objects if o.get("type") == "ITEM"
                        and o.get("parentId") == page.get("id")),
                       key=lambda o: str(o.get("id", "")))
        if not items:
            continue
        route = _route(page)
        fields = []
        controls = []
        for item in items:
            label = html.escape(str(item.get("name") or item.get("id")), quote=True)
            field = _slug(str(item.get("name") or ""), "field").replace("-", "_")
            if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", field):
                field = "field_" + field
            field_id = _slug(str(item.get("id") or field), "field")
            fields.append(f"  readonly {field}?: unknown;")
            controls.append(f'<div><label htmlFor="{field_id}">{label}</label> <input id="{field_id}" name="{field}" disabled aria-label="{label}" /></div>')
        dto_id = hashlib.sha256(str(page.get("id")).encode()).hexdigest()[:8].upper()
        dto_name = "Page" + dto_id + "GeneratedDto"
        files[f"apps/api/src/dto/{route}.dto.ts"] = (
            "/** Unknown field types are intentional until database/domain metadata is reviewed. */\n"
            f"export class {dto_name} {{\n" + "\n".join(fields) + "\n}\n"
        )
        route_file = f"apps/web/app/pages/{route}/page.tsx"
        if route_file in files:
            markup = "\n    <form aria-label='Migrated item inventory'>\n      " + "\n      ".join(controls) + "\n    </form>\n"
            files[route_file] = files[route_file].replace("</main>", markup + "  </main>")


def generate_project(document: dict[str, Any], output_dir: str | Path,
                     *, overwrite: bool = False) -> dict[str, Any]:
    errors = validate_ir_document(document)
    if errors:
        raise ValueError(f"Invalid Normalized IR document: {_json(errors)}")
    output = Path(output_dir).expanduser().resolve()
    if output.exists() and any(output.iterdir()) and not overwrite:
        raise FileExistsError(f"Output directory is not empty: {output}")
    graph = analyze_dependency_graph(document)
    sem = analyze_semantics(document, graph)
    files = _files(document, sem, graph)
    _extend_files(files, document)
    files.update(build_runtime_files(files))
    files.update(build_ui_generator_files(document))
    manifest = {"manifestVersion": "1.0.0", "generatorVersion": GENERATOR_VERSION,
        "applicationId": document["application"]["id"], "fileCount": len(files) + 1,
        "files": {p: "sha256:" + hashlib.sha256(c.encode()).hexdigest()
                  for p, c in sorted(files.items())}}
    files["generation-manifest.json"] = _json(manifest) + "\n"
    output.mkdir(parents=True, exist_ok=True)
    for relative, content in sorted(files.items()):
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    return {"outputDir": str(output), "fileCount": len(files),
        "pageCount": sum(o.get("type") == "PAGE" for o in document.get("objects", [])),
        "classificationCounts": sem["summary"]["classificationCounts"],
        "diagnosticCounts": sem["summary"]["diagnosticCounts"],
        "manifest": str(output / "generation-manifest.json")}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Next.js/NestJS/PostgreSQL from Normalized IR.")
    parser.add_argument("ir", help="Normalized IR JSON file")
    parser.add_argument("--output", required=True, help="Output project directory")
    parser.add_argument("--overwrite", action="store_true", help="Allow non-empty output directory")
    args = parser.parse_args()
    doc = json.loads(Path(args.ir).read_text(encoding="utf-8"))
    print(_json(generate_project(doc, args.output, overwrite=args.overwrite)))


if __name__ == "__main__":
    main()
