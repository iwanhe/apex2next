"""R4a project skeleton: a runnable Next.js + NestJS application directory around the generated sources.

``apex2next new APP_DIR`` copies ``templates/app`` of this repository into an application directory that already
holds the page inventory (ui/) and the schema plan (db/). The template is the pilot's application shell with
everything specific to the pilot removed: sign-in with local accounts, the generic page layer (regions, LOVs,
native form DML), authorization schemes evaluated from the generated rules, the APEX-style components.

Existing files are never overwritten; they are listed instead.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TEMPLATE = ROOT / "templates" / "app"
PACKAGES = ROOT / "packages"
TEXT_SUFFIXES = {".ts", ".tsx", ".mjs", ".js", ".json", ".yaml", ".yml", ".sql", ".css", ".md", ".svg"}


def slug(text: str) -> str:
    s = "-".join(w.lower() for w in re.findall(r"[A-Za-z0-9]+", text or ""))
    return s or "apex-app"


def pack_runtime(app: Path) -> dict[str, str]:
    """Pack the runtime packages into APP/vendor: the application depends on a fixed copy, not on this checkout."""
    if not (PACKAGES / "runtime-api/node_modules").exists():
        raise SystemExit("packages/runtime-api has no dependencies installed: run `pnpm install` in "
                         "examples/f170134-target first (packing builds it with its TypeScript)")
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        raise SystemExit("pnpm not found; install pnpm or use --runtime link")
    vendor = app / "vendor"
    vendor.mkdir(parents=True, exist_ok=True)
    out = {}
    for pkg in ("runtime-api", "runtime-web"):
        before = set(vendor.glob("*.tgz"))
        for old in vendor.glob(f"apex2next-{pkg}-*.tgz"):
            old.unlink()
        done = subprocess.run([pnpm, "pack", "--pack-destination", str(vendor.resolve())], cwd=PACKAGES / pkg,
                              capture_output=True, text=True)  # runtime-api: prepack builds dist
        if done.returncode != 0:
            raise SystemExit(f"pnpm pack failed in packages/{pkg}:\n{done.stdout}{done.stderr}")
        made = sorted(set(vendor.glob(f"apex2next-{pkg}-*.tgz")) - before) or sorted(vendor.glob(f"apex2next-{pkg}-*.tgz"))
        # the content hash in the name makes pnpm install a changed runtime of the same version
        digest = hashlib.sha256(made[-1].read_bytes()).hexdigest()[:12]
        named = made[-1].with_name(made[-1].name.replace(".tgz", f"-{digest}.tgz"))
        made[-1].rename(named)
        out[f"@apex2next/{pkg}"] = named.name
    return out


def create_project(app: Path, *, oracle_schema: str, name: str | None = None, runtime: str = "pack") -> dict[str, list[str]]:
    inventory = json.loads((app / "ui/apex-page-inventory.json").read_text(encoding="utf-8"))
    if not (app / "db/0001_schema.sql").exists():
        raise SystemExit(f"{app / 'db/0001_schema.sql'} not found: run schema-plan with --out {app / 'db'} first")
    if not re.fullmatch(r"[A-Z][A-Z0-9_$#]*", oracle_schema):
        raise SystemExit("--oracle-schema must be an Oracle schema name such as WKSP_KCSI")
    application = inventory.get("application", {})
    app_slug = slug(name or application.get("alias") or application.get("name") or app.name)
    packages = os.path.relpath(PACKAGES, app.resolve()).replace(os.sep, "/")
    values = {"__APP_SLUG__": app_slug, "__ORACLE_SCHEMA__": oracle_schema, "__RUNTIME_PACKAGES__": packages}
    written: list[str] = []
    kept: list[str] = []

    def put(rel: str, data: bytes) -> None:
        target = app / rel
        if target.exists():
            kept.append(rel)
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        written.append(rel)

    for src in sorted(p for p in TEMPLATE.rglob("*") if p.is_file()):
        rel = src.relative_to(TEMPLATE).as_posix()
        data = src.read_bytes()
        if src.suffix in TEXT_SUFFIXES:
            text = data.decode("utf-8")
            for k, v in values.items():
                text = text.replace(k, v)
            data = text.encode("utf-8")
        put(rel, data)
    if runtime == "pack":
        tarballs = pack_runtime(app)
        for rel, depth in (("apps/api/package.json", 2), ("apps/web/package.json", 2)):
            if (app / rel).exists():  # also on a re-run: point to the fresh copy of the runtime
                pkg = json.loads((app / rel).read_text(encoding="utf-8"))
                for dep, tgz in tarballs.items():
                    if dep in pkg.get("dependencies", {}):
                        pkg["dependencies"][dep] = "file:" + "../" * depth + "vendor/" + tgz
                (app / rel).write_text(json.dumps(pkg, indent=2) + "\n", encoding="utf-8")
        if "pnpm-workspace.yaml" in written:
            (app / "pnpm-workspace.yaml").write_text("packages:\n  - 'apps/*'\n", encoding="utf-8")
        if "package.json" in written:
            root = json.loads((app / "package.json").read_text(encoding="utf-8"))
            root["scripts"]["typecheck"] = "pnpm -r typecheck"
            (app / "package.json").write_text(json.dumps(root, indent=2) + "\n", encoding="utf-8")
    stale: list[str] = []

    def put_migration(rel: str, data: bytes) -> None:
        # an applied migration never changes: a newer schema plan is reported, not copied over the old file
        if (app / rel).exists() and (app / rel).read_bytes() != data:
            stale.append(rel)
        put(rel, data)

    put_migration("db/migrations/0001_schema.sql", (app / "db/0001_schema.sql").read_bytes())
    deferred = app / "db/0003_deferred_views.sql"
    if deferred.exists() and deferred.read_text(encoding="utf-8").strip():
        put_migration("db/migrations/0003_deferred_views.sql", deferred.read_bytes())
    return {"written": written, "kept": kept, "slug": [app_slug], "stale": stale}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the runnable application skeleton around generated sources")
    parser.add_argument("app", type=Path, help="application directory with ui/apex-page-inventory.json and db/")
    parser.add_argument("--oracle-schema", required=True, help="parsing schema of the APEX application (error messages)")
    parser.add_argument("--name", help="package name (default: the application alias)")
    parser.add_argument("--runtime", choices=["pack", "link"], default="pack",
                        help="pack: copies of the runtime packages in vendor/ (default); link: pnpm workspace link to "
                             "this repository (only for applications inside the repository)")
    args = parser.parse_args()
    if not TEMPLATE.is_dir():
        raise SystemExit(f"template not found: {TEMPLATE}")
    out = create_project(args.app, oracle_schema=args.oracle_schema, name=args.name, runtime=args.runtime)
    print(f"{len(out['written'])} file(s) written, {len(out['kept'])} existing file(s) kept unchanged")
    for rel in out["kept"]:
        print(f"  kept: {rel}")
    for rel in out["stale"]:
        print(f"  NOTE {rel} differs from the current schema plan and was not replaced (an applied migration never "
              "changes). On a disposable database: delete it and run new again. Otherwise add the difference as a new "
              "migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
