#!/usr/bin/env python3
"""Smoke test of a converted application (R4a).

Signs in with a local account on a DISPOSABLE database, changes its temporary password, opens every generated
page and, optionally, creates / edits / deletes one row through a generated form. The application must be built
(pnpm build). Passwords are generated here and never printed.

  python tools/app_smoke.py APP_DIR --database-url URL [--api-port 3201] [--web-port 3200]
      [--crud '{"list": "/categories", "new": "/categories/new", "item": "P8_CATEGORY_NAME"}']
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import signal
import subprocess
import time
import urllib.request
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("app", type=Path)
    ap.add_argument("--database-url", required=True)
    ap.add_argument("--api-port", default="3201")
    ap.add_argument("--web-port", default="3200")
    ap.add_argument("--user", default="SMOKE")
    ap.add_argument("--crud", help="JSON: list route, create route, a required text item; optional extra items")
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright

    app = a.app
    env = {**os.environ, "DATABASE_URL": a.database_url, "AUTH_MODE": "local", "SESSION_SECRET": secrets.token_hex(32),
           "API_PORT": a.api_port, "API_URL": f"http://127.0.0.1:{a.api_port}", "NODE_ENV": "production",
           "ACCESS_LOG": "off"}
    accounts = ["node", "apps/api/scripts/accounts.mjs"]
    out = subprocess.run([*accounts, "reset", a.user], cwd=app, env=env, capture_output=True, text=True)
    if out.returncode:
        out = subprocess.run([*accounts, "create", a.user], cwd=app, env=env, capture_output=True, text=True)
    found = re.search(r"temporary password: (\S+)", out.stdout)
    if not found:
        print("could not create the smoke account:", out.stderr.strip()[:300])
        return 2
    temp = found.group(1)
    logs = app / ".smoke"
    logs.mkdir(exist_ok=True)
    procs = [subprocess.Popen(["node", "apps/api/dist/main.js"], cwd=app, env=env, stdout=subprocess.DEVNULL,
                              stderr=open(logs / "api.log", "w"), start_new_session=True),
             subprocess.Popen(["pnpm", "--filter", "./apps/web", "exec", "next", "start", "-p", a.web_port], cwd=app,
                              env=env, stdout=subprocess.DEVNULL, stderr=open(logs / "web.log", "w"),
                              start_new_session=True)]
    base = f"http://127.0.0.1:{a.web_port}"
    results: list[tuple[str, bool, str]] = []
    try:
        for _ in range(120):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{a.api_port}/health")
                urllib.request.urlopen(f"{base}/login")
                break
            except Exception:
                time.sleep(0.5)
        report = json.loads((app / "ui/generation-report.json").read_text(encoding="utf-8"))
        routes_ts = (app / "apps/web/lib/app-routes.generated.ts").read_text(encoding="utf-8")
        login = dict(re.findall(r"(\w+): '([^']*)'", re.search(r"LOGIN_PAGE = \{(.*?)\}", routes_ts).group(1)))
        with sync_playwright() as p:
            page = p.chromium.launch().new_page()
            page.on("dialog", lambda d: d.accept())
            page.goto(f"{base}/login")
            page.wait_for_timeout(800)  # hydration
            page.fill(f"#{login['username']}", a.user)
            page.fill(f"#{login['password']}", temp)
            page.click("button[type=submit]")
            page.wait_for_url(lambda u: "/login" not in u, timeout=15000)
            if "/account/password" in page.url:
                new = secrets.token_urlsafe(18) + "9a"
                page.wait_for_timeout(800)
                page.fill("#pw_current", temp)
                page.fill("#pw_next", new)
                page.fill("#pw_confirm", new)
                page.locator("main form button[type=submit], .panel form button[type=submit]").last.click()
                page.wait_for_url(lambda u: "/account/password" not in u, timeout=15000)
            results.append(("sign in and change the temporary password", "/login" not in page.url, page.url))
            for f in report["files"]:
                m = re.match(r"apps/web/app/\(app\)(/.*)?/page\.tsx$", f)
                if not m or "[" in f:
                    continue
                route = m.group(1) or "/"
                r = page.goto(f"{base}{route}")
                page.wait_for_timeout(300)
                err = page.locator(".alert-error").all_inner_texts()
                landed = page.url.split("?")[0].removeprefix(base) or "/"
                results.append((f"open {route}", bool(r) and r.status == 200 and not err and landed == route,
                                f"{r.status if r else '-'} {landed} {err[:1]}"))
            if a.crud:
                crud = json.loads(a.crud)
                name = "Smoke " + secrets.token_hex(3)

                def back_on_list(timeout: int = 15000):
                    page.wait_for_url(lambda u: u.split("?")[0].endswith(crud["list"]), timeout=timeout)
                    page.wait_for_timeout(400)

                page.goto(f"{base}{crud['new']}")
                page.wait_for_timeout(800)
                page.fill(f"#{crud['item']}", name)
                for k, v in crud.get("extra", {}).items():
                    page.fill(f"#{k}", v)
                page.locator("button[name=request]").first.click()
                back_on_list()
                results.append(("create through the form", page.locator("tr", has_text=name).count() > 0,
                                " | ".join(page.locator(".alert-success, .alert-error").all_inner_texts())))
                page.locator("tr", has_text=name).first.locator("a").first.click()
                page.wait_for_timeout(800)
                page.fill(f"#{crud['item']}", name + " edited")
                page.locator("button[name=request][value]").filter(has_not_text=re.compile("Delete", re.I)).last.click()
                back_on_list()
                results.append(("update through the form", page.locator("tr", has_text=name + " edited").count() > 0, page.url))
                page.locator("tr", has_text=name + " edited").first.locator("a").first.click()
                page.wait_for_timeout(800)
                page.locator("button[name=request]", has_text=re.compile("Delete", re.I)).first.click()
                back_on_list()
                results.append(("delete through the form", page.locator("tr", has_text=name).count() == 0, page.url))
    finally:
        for pr in procs:
            try:
                os.killpg(pr.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    for label, ok, detail in results:
        print("PASS" if ok else "FAIL", label, "" if ok else detail)
    ok = bool(results) and all(r[1] for r in results)
    print("SMOKE", "PASS" if ok else "FAIL", f"({sum(r[1] for r in results)}/{len(results)})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
