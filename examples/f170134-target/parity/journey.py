"""WP9.6 parity journey J-01, executed on the target exactly as it was executed on APEX (oracleapex.com).

Usage (disposable database; schema "app" is dropped):
  DATABASE_URL=... python parity/journey.py --s0 snapshot-s0.csv --s1 snapshot-s1.csv \
      --apex-observations parity/apex-observations-j01.json --output build/parity-j01.json

Steps: migrate + load S0 (snapshot_migration, all checks must pass) -> start API and web (AUTH_MODE=dev)
-> run J-01 with Playwright as DEMO_REQ / DEMO_MGR, recording every message shown -> compare the database
with the later source snapshot S1 (compare_state, natural keys, clock/surrogate columns excluded)
-> compare the recorded messages with the messages observed on APEX.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "workers" / "schema-analyzer" / "src"))
sys.path.insert(0, str(ROOT / "e2e"))

from apex2next_schema_analyzer.snapshot_migration import (  # noqa: E402
    compare_state, compare_views_after, migrate, parse_snapshot,
)
from conftest import DEV_PASSWORD, _free_port, _wait  # noqa: E402
from playwright.sync_api import Page, sync_playwright  # noqa: E402

NEED_TOO_EARLY = "2026-11-01"
NEED = "2026-11-30"


class Recorder:
    def __init__(self):
        self.steps: list[dict] = []

    def note(self, step: str, page: Page):
        if "msg=" in page.url:  # redirected with a success message: wait until the parent page rendered it
            page.locator(".alert-success").first.wait_for(timeout=10000)
        texts = page.locator(".alert-error .alert-title, .alert-error li, .alert-success, .field .error").all_inner_texts()
        msgs = list(dict.fromkeys(t.strip() for t in texts if t.strip()))
        self.steps.append({"step": step, "messages": msgs, "url": page.url.split("/", 3)[-1]})


def submit(page: Page, request: str, confirm: bool | None = None):
    """Click a page button and wait until the page shows its outcome (redirect to the parent, or re-render with errors)."""
    if confirm is not None:
        page.once("dialog", lambda d: d.accept() if confirm else d.dismiss())
    version = page.locator("form[data-version]").first.get_attribute("data-version")  # waits for the form
    url = page.url
    page.click(f"button[name=request][value={request}]")
    page.wait_for_function(
        "([url, v]) => location.href !== url || (document.querySelector('form[data-version]')?.dataset.version ?? v) !== v",
        arg=[url, version])
    page.wait_for_load_state("networkidle")


def login(browser, base: str, user: str) -> Page:
    page = browser.new_context().new_page()
    page.set_default_timeout(15000)
    page.goto(base + "/login")
    page.fill("#P9999_USERNAME", user)
    page.fill("#P9999_PASSWORD", DEV_PASSWORD)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    return page


def go(page: Page, base: str, path: str):
    page.goto(base + path)
    page.wait_for_load_state("networkidle")


def open_request(page: Page, base: str, request_no: str):
    go(page, base, "/requests")
    page.get_by_role("link", name=request_no).click()
    page.wait_for_url("**/requests/*")
    page.wait_for_load_state("networkidle")


def run_journey(browser, base: str, rec: Recorder) -> None:
    req = login(browser, base, "demo_req")
    # J1 create with an invalid need date, then valid
    go(req, base, "/requests/new")
    req.select_option("#P301_DEPARTMENT_ID", label="OPS - Operations")
    req.fill("#P301_NEED_DATE", NEED_TOO_EARLY)
    req.fill("#P301_PURPOSE", "WP96 parity A")
    submit(req, "CREATE")
    rec.note("J1 create, need date before request date", req)
    req.fill("#P301_NEED_DATE", NEED)
    submit(req, "CREATE")
    rec.note("J1 create", req)
    # J2 lines through page 302
    go(req, base, "/requests/detail")
    req.get_by_test_id("master-list").get_by_role("link", name="REQ-2026-0003").click()
    req.wait_for_load_state("networkidle")
    for item, qty, price, bad in (("ATK-001 - Kertas A4 80gsm (RIM)", "3", "55000", "abc"),
                                  ("IT-002 - Mouse Wireless (UNIT)", "1", "150000", None)):
        req.get_by_role("link", name="Tambah").click()
        req.wait_for_load_state("networkidle")
        req.select_option("#P311_ITEM_ID", label=item)
        req.fill("#P311_UNIT_PRICE", price)
        if bad:
            req.fill("#P311_QTY", bad)
            submit(req, "CREATE")
            rec.note(f"J2 line {item} qty {bad}", req)
        req.fill("#P311_QTY", qty)
        submit(req, "CREATE")
        rec.note(f"J2 line {item}", req)
    # J3 submit from the header dialog
    req.get_by_role("link", name="Edit", exact=True).click()
    req.wait_for_load_state("networkidle")
    submit(req, "SUBMIT", confirm=True)
    rec.note("J3 submit", req)
    # J4 create and delete a DRAFT
    go(req, base, "/requests/new")
    req.select_option("#P301_DEPARTMENT_ID", label="IT - Information Technology")
    req.fill("#P301_NEED_DATE", NEED)
    req.fill("#P301_PURPOSE", "WP96 parity B")
    submit(req, "CREATE")
    open_request(req, base, "REQ-2026-0004")
    submit(req, "DELETE", confirm=True)
    rec.note("J4 delete draft", req)

    mgr = login(browser, base, "demo_mgr")
    # J5 reject without and with a note
    go(mgr, base, "/approvals")
    mgr.get_by_test_id("report-approvalInbox").locator("tbody tr", has_text="REQ-2026-0003").get_by_role("link", name="Edit").click()
    mgr.wait_for_load_state("networkidle")
    submit(mgr, "REJECT", confirm=True)
    rec.note("J5 reject without note", mgr)
    mgr.fill("#P191_NOTE", "WP96 revisi")
    submit(mgr, "REJECT", confirm=True)
    rec.note("J5 reject", mgr)
    # J6 requester revises and resubmits
    open_request(req, base, "REQ-2026-0003")
    req.fill("#P301_PURPOSE", "WP96 parity A rev")
    submit(req, "SUBMIT", confirm=True)
    rec.note("J6 resubmit", req)
    # J7 manager approves the new step
    go(mgr, base, "/approvals")
    row = mgr.get_by_test_id("report-approvalInbox").locator("tbody tr", has_text="PENDING").first
    row.get_by_role("link", name="Edit").click()
    mgr.wait_for_load_state("networkidle")
    mgr.fill("#P191_NOTE", "WP96 ok")
    submit(mgr, "APPROVE")
    rec.note("J7 approve", mgr)
    # J8 manager (REQUESTER scheme includes MANAGER) sets FULFILLED, as on APEX
    open_request(mgr, base, "REQ-2026-0003")
    mgr.select_option("#P301_STATUS", "FULFILLED")
    submit(mgr, "SAVE")
    rec.note("J8 fulfilled", mgr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--s0", type=Path, required=True)
    ap.add_argument("--s1", type=Path, required=True)
    ap.add_argument("--apex-observations", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    import psycopg

    db = os.environ["DATABASE_URL"]
    env = {**os.environ, "ALLOW_DB_RESET": "1"}
    with psycopg.connect(db, autocommit=True) as c:
        c.execute("DROP SCHEMA IF EXISTS app CASCADE")
    subprocess.run(["node", "apps/api/scripts/migrate.mjs"], cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
    plan = json.loads((ROOT / "db" / "schema-plan.json").read_text(encoding="utf-8"))
    with psycopg.connect(db) as conn:
        load = migrate(conn, parse_snapshot(args.s0.read_text(encoding="utf-8")), plan, snapshot_name=args.s0.name)
    if not load.get("committed"):
        print(json.dumps(load["checks"]), file=sys.stderr)
        return 2
    api_port, web_port = _free_port(), _free_port()
    api = subprocess.Popen(["node", "dist/main.js"], cwd=ROOT / "apps/api", stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
                           env={**env, "AUTH_MODE": "dev", "DEV_LOGIN_PASSWORD": DEV_PASSWORD, "API_PORT": str(api_port),
                                "SESSION_SECRET": "parity-session-secret-0123456789abcdef"})
    web = subprocess.Popen(["node", "node_modules/next/dist/bin/next", "start", "-p", str(web_port), "-H", "127.0.0.1"],
                           cwd=ROOT / "apps/web", stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
                           env={**os.environ, "API_URL": f"http://127.0.0.1:{api_port}", "NEXT_TELEMETRY_DISABLED": "1"})
    rec = Recorder()
    try:
        _wait(f"http://127.0.0.1:{api_port}/health")
        _wait(f"http://127.0.0.1:{web_port}/login")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, channel=os.environ.get("E2E_BROWSER_CHANNEL") or None)
            run_journey(browser, f"http://127.0.0.1:{web_port}", rec)
            browser.close()
    finally:
        for proc in (web, api):
            proc.terminate()
        time.sleep(0.5)
    s1 = parse_snapshot(args.s1.read_text(encoding="utf-8"))
    if s1.problems:
        print(json.dumps(s1.problems), file=sys.stderr)
        return 2
    with psycopg.connect(db) as conn:
        state = compare_state(conn, s1)
        views = compare_views_after(conn, s1)
    apex = json.loads(args.apex_observations.read_text(encoding="utf-8"))
    messages = []
    for step in rec.steps:
        expected = next((s for s in apex["steps"] if s["step"] == step["step"]), None)
        messages.append({"step": step["step"], "url": step["url"], "target": step["messages"], "apex": expected and expected["messages"],
                         "equal": bool(expected) and sorted(expected["messages"]) == sorted(step["messages"])})
    state_diffs = sum(len(t["differences"]) for t in state.values()) + sum(
        len(v["differences"]) for v in views["views"].values())
    report = {"journey": "J-01", "s0": {"name": args.s0.name, "sha256": parse_snapshot(args.s0.read_text(encoding="utf-8")).sha256},
              "s1": {"name": args.s1.name, "sha256": s1.sha256, "session": s1.session},
              "load": load["checks"], "state": state, "views": views, "messages": messages,
              "result": "PASS" if state_diffs == 0 and all(m["equal"] for m in messages) else "FAIL"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(report["result"], f"state differences: {state_diffs}",
          f"message mismatches: {sum(not m['equal'] for m in messages)}")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
