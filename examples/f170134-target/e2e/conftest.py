"""WP9.5 end-to-end harness: disposable PostgreSQL + built API + built web, driven by Playwright (Chromium).

Required: DATABASE_URL (disposable; schema "app" is dropped). Optional: E2E_BROWSER_CHANNEL (e.g. "chrome").
The API and web apps must be built (pnpm -r build) before running.
"""
from __future__ import annotations

import os
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DEV_PASSWORD = "e2e-dev-password-123"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait(url: str, timeout: float = 60) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:  # noqa: S310 - local test server
                if r.status < 500:
                    return
        except Exception:  # noqa: BLE001 - server still starting
            time.sleep(0.5)
    raise RuntimeError(f"server at {url} did not become ready")


@pytest.fixture(scope="session")
def servers():
    db = os.environ.get("DATABASE_URL")
    if not db:
        pytest.fail("DATABASE_URL (disposable PostgreSQL) is required for the WP9.5 E2E tests")
    env = {**os.environ, "DATABASE_URL": db, "ALLOW_DB_RESET": "1"}
    subprocess.run(["node", "apps/api/scripts/reset-dev-db.mjs"], cwd=ROOT, env=env, check=True)
    api_port, web_port = _free_port(), _free_port()
    api_env = {**env, "AUTH_MODE": "dev", "DEV_LOGIN_PASSWORD": DEV_PASSWORD,
               "SESSION_SECRET": "e2e-session-secret-0123456789abcdef", "API_PORT": str(api_port)}
    web_env = {**os.environ, "API_URL": f"http://127.0.0.1:{api_port}", "NEXT_TELEMETRY_DISABLED": "1"}
    logs = ROOT / "e2e" / ".logs"
    logs.mkdir(exist_ok=True)
    api = subprocess.Popen(["node", "dist/main.js"], cwd=ROOT / "apps/api", env=api_env,
                           stdout=open(logs / "api.log", "w"), stderr=subprocess.STDOUT)
    web = subprocess.Popen(["node", "node_modules/next/dist/bin/next", "start", "-p", str(web_port), "-H", "127.0.0.1"],
                           cwd=ROOT / "apps/web", env=web_env, stdout=open(logs / "web.log", "w"), stderr=subprocess.STDOUT)
    try:
        _wait(f"http://127.0.0.1:{api_port}/health")
        _wait(f"http://127.0.0.1:{web_port}/login")
        yield {"base": f"http://127.0.0.1:{web_port}", "api": f"http://127.0.0.1:{api_port}"}
    finally:
        for proc in (web, api):
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


@pytest.fixture(scope="session")
def browser(servers) -> Browser:
    with sync_playwright() as p:
        channel = os.environ.get("E2E_BROWSER_CHANNEL") or None
        b = p.chromium.launch(headless=True, channel=channel)
        yield b
        b.close()


class App:
    """One signed-in browser context per user."""

    def __init__(self, browser: Browser, base: str):
        self.browser, self.base = browser, base
        self.pages: dict[str, Page] = {}

    def login(self, username: str, password: str = DEV_PASSWORD) -> Page:
        ctx = self.browser.new_context()
        page = ctx.new_page()
        page.set_default_timeout(15000)
        page.goto(self.base + "/login")
        page.fill("#P9999_USERNAME", username)
        page.fill("#P9999_PASSWORD", password)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        return page

    def as_user(self, username: str) -> Page:
        if username not in self.pages:
            self.pages[username] = self.login(username)
            assert "/login" not in self.pages[username].url, f"login failed for {username}"
        return self.pages[username]

    def go(self, page: Page, path: str) -> Page:
        page.goto(self.base + path)
        page.wait_for_load_state("networkidle")
        return page


@pytest.fixture(scope="session")
def app(browser, servers) -> App:
    return App(browser, servers["base"])
