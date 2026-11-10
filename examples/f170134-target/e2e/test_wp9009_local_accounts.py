"""WP9-009 local accounts in the browser: temporary password -> forced change -> app -> sign out revokes.

A second API (AUTH_MODE=local) and web pair runs on the database the session fixture prepared; the dev-mode pair
is untouched. Accounts are created with the operator CLI (scripts/accounts.mjs), as in operations.
"""
from __future__ import annotations

import os
import re
import subprocess

import pytest
from playwright.sync_api import Browser, expect

from conftest import ROOT, _free_port, _wait


def _cli(*args: str) -> str:
    return subprocess.run(["node", "apps/api/scripts/accounts.mjs", *args, "--by", "E2E"], cwd=ROOT, check=True,
                          capture_output=True, text=True, env={**os.environ}).stdout


def _temp(out: str) -> str:
    return re.search(r"temporary password: (\S+)", out).group(1)


@pytest.fixture(scope="module")
def local(servers):
    api_port, web_port = _free_port(), _free_port()
    api_env = {**os.environ, "AUTH_MODE": "local", "SESSION_SECRET": "e2e-local-secret-0123456789abcdef0123",
               "API_PORT": str(api_port), "LOGIN_MAX_FAILURES": "3"}
    web_env = {**os.environ, "API_URL": f"http://127.0.0.1:{api_port}", "NEXT_TELEMETRY_DISABLED": "1"}
    logs = ROOT / "e2e" / ".logs"
    api = subprocess.Popen(["node", "dist/main.js"], cwd=ROOT / "apps/api", env=api_env,
                           stdout=open(logs / "api-local.log", "w"), stderr=subprocess.STDOUT)
    web = subprocess.Popen(["node", "node_modules/next/dist/bin/next", "start", "-p", str(web_port), "-H", "127.0.0.1"],
                           cwd=ROOT / "apps/web", env=web_env, stdout=open(logs / "web-local.log", "w"), stderr=subprocess.STDOUT)
    try:
        _wait(f"http://127.0.0.1:{api_port}/health")
        _wait(f"http://127.0.0.1:{web_port}/login")
        yield f"http://127.0.0.1:{web_port}"
    finally:
        for proc in (web, api):
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


def test_local_account_lifecycle(local, browser: Browser):
    out = _cli("create", "req1")
    temp = _temp(out) if "temporary password" in out else _temp(_cli("reset", "req1"))
    ctx = browser.new_context()
    page = ctx.new_page()
    page.set_default_timeout(15000)

    def login(password: str):
        page.goto(f"{local}/login")
        page.fill("#P9999_USERNAME", "req1")
        page.fill("#P9999_PASSWORD", password)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")

    login("wrong-password-1")
    expect(page.locator(".alert-error")).to_have_text("Invalid Login Credentials")

    # temporary password -> forced change; the application itself is not reachable yet
    login(temp)
    expect(page).to_have_url(re.compile(r"/account/password$"))
    expect(page.locator("[data-page=change-password] .alert")).to_contain_text("Password sementara harus diganti")
    page.goto(f"{local}/requests")
    expect(page).to_have_url(re.compile(r"/account/password$"))

    page.fill("#pw_current", temp)
    page.fill("#pw_next", "short")
    page.fill("#pw_confirm", "short")
    page.get_by_role("button", name="Ganti Password").click()
    expect(page.locator("#pw_next_err")).to_contain_text("Password minimal 10 karakter.")

    page.fill("#pw_current", temp)
    page.fill("#pw_next", "Permintaan2026")
    page.fill("#pw_confirm", "Permintaan2026")
    page.get_by_role("button", name="Ganti Password").click()
    page.wait_for_url(re.compile(r"/$"))
    expect(page.get_by_test_id("app-user")).to_have_text("REQ1")
    expect(page.get_by_role("link", name="Ganti Password")).to_be_visible()

    # sign out revokes the session: a copied cookie no longer works
    cookie = next(c for c in ctx.cookies() if c["name"] == "a2n_session")
    page.get_by_role("button", name="Sign Out").click()
    page.wait_for_url(re.compile(r"/login$"))
    other = browser.new_context()
    other.add_cookies([cookie])
    p2 = other.new_page()
    p2.goto(f"{local}/requests")
    expect(p2).to_have_url(re.compile(r"/login$"))
    other.close()

    login("Permintaan2026")
    expect(page.get_by_test_id("app-user")).to_have_text("REQ1")
    ctx.close()
