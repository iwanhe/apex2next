"""WP9.6 parity journeys (J-01 .. J-05), executed on the target exactly as they were executed on APEX (oracleapex.com).

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
        texts = page.locator(".alert-error .alert-title, .alert-error li, .alert-error.denied p, .alert-success, .field .error").all_inner_texts()
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


def run_j01(browser, base: str, rec: Recorder) -> None:
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


def open_ir_row(page: Page, base: str, path: str, text: str):
    go(page, base, path)
    page.locator("tbody tr", has_text=text).first.get_by_role("link", name="Edit").click()
    page.wait_for_load_state("networkidle")
    page.locator("form[data-version]").first.wait_for()


def run_j02(browser, base: str, rec: Recorder) -> None:
    """J-02 master data (DEMO_WH) and administration (DEMO_ADMIN)."""
    wh = login(browser, base, "demo_wh")
    go(wh, base, "/departments/new")
    wh.fill("#P201_DEPT_CODE", "wp96")
    wh.fill("#P201_DEPT_NAME", "WP96 Dept")
    submit(wh, "CREATE")
    rec.note("J2A dept create", wh)
    go(wh, base, "/departments/new")
    wh.fill("#P201_DEPT_CODE", "ops")
    wh.fill("#P201_DEPT_NAME", "Duplicate")
    submit(wh, "CREATE")
    rec.note("J2A dept duplicate", wh)
    go(wh, base, "/items/new")
    wh.select_option("#P211_CATEGORY", "ATK")
    wh.fill("#P211_ITEM_CODE", "wp96-01")
    wh.fill("#P211_ITEM_NAME", "WP96 Item")
    wh.fill("#P211_UOM", "pcs")
    wh.fill("#P211_STD_PRICE", "-5")
    submit(wh, "CREATE")
    rec.note("J2A item price -5", wh)
    wh.fill("#P211_STD_PRICE", "1000")
    submit(wh, "CREATE")
    rec.note("J2A item create", wh)
    go(wh, base, "/items")
    wh.get_by_role("link", name="WP96-01").click()
    wh.wait_for_url("**/items/*")
    wh.locator("form[data-version]").first.wait_for()
    wh.fill("#P211_STD_PRICE", "1500")
    submit(wh, "SAVE")
    rec.note("J2A item update", wh)
    wh.get_by_role("link", name="WP96-01").click()
    wh.wait_for_url("**/items/*")
    wh.locator("form[data-version]").first.wait_for()
    submit(wh, "DELETE", confirm=True)
    rec.note("J2A item delete", wh)
    open_ir_row(wh, base, "/departments", "WP96 Dept")
    submit(wh, "DELETE", confirm=True)
    rec.note("J2A dept delete", wh)

    admin = login(browser, base, "demo_admin")
    go(admin, base, "/admin/users/new")
    rec.steps.append({"step": "J2B user role default", "messages": [f"P501_USERNAME={admin.input_value('#P501_USERNAME')}"],
                      "url": admin.url.split("/", 3)[-1]})
    admin.fill("#P501_USERNAME", "wp96.user")
    admin.select_option("#P501_ROLE_CODE", "REQUESTER")
    submit(admin, "CREATE")
    rec.note("J2B user role create", admin)
    open_ir_row(admin, base, "/admin/users", "WP96.USER")
    submit(admin, "DELETE", confirm=True)
    rec.note("J2B user role delete", admin)
    open_ir_row(admin, base, "/admin/document-types", "REQ")
    submit(admin, "SAVE")
    rec.note("J2B doc type unchanged", admin)


def open_approval(page: Page, base: str, request_no: str, role: str):
    go(page, base, "/approvals")
    row = page.get_by_test_id("report-approvalInbox").locator("tbody tr", has_text=request_no).filter(has_text=role).first
    row.get_by_role("link", name="Edit").click()
    page.locator("form[data-version]").first.wait_for()
    page.wait_for_load_state("networkidle")


def run_j03(browser, base: str, rec: Recorder) -> None:
    """J-03 two-level approval: amount above LEVEL2_LIMIT, MANAGER then DIRECTOR; MANAGER cannot act on level 2."""
    req = login(browser, base, "demo_req")
    go(req, base, "/requests/new")
    req.select_option("#P301_DEPARTMENT_ID", label="IT - Information Technology")
    req.fill("#P301_NEED_DATE", NEED)
    req.fill("#P301_PURPOSE", "WP96 parity C")
    submit(req, "CREATE")
    rec.note("J3A create", req)
    go(req, base, "/requests/detail")
    req.get_by_test_id("master-list").get_by_role("link", name="REQ-2026-0005").click()
    req.wait_for_load_state("networkidle")
    req.get_by_role("link", name="Tambah").click()
    req.wait_for_load_state("networkidle")
    req.select_option("#P311_ITEM_ID", label="IT-001 - Laptop 14 inch (UNIT)")
    req.fill("#P311_QTY", "1")
    req.fill("#P311_UNIT_PRICE", "12500000")
    submit(req, "CREATE")
    rec.note("J3A line", req)
    req.get_by_role("link", name="Edit", exact=True).click()
    req.wait_for_load_state("networkidle")
    submit(req, "SUBMIT", confirm=True)
    rec.note("J3A submit", req)

    mgr = login(browser, base, "demo_mgr")
    open_approval(mgr, base, "REQ-2026-0005", "MANAGER")
    mgr.fill("#P191_NOTE", "WP96 L1 ok")
    submit(mgr, "APPROVE")
    rec.note("J3B approve level 1", mgr)
    open_approval(mgr, base, "REQ-2026-0005", "DIRECTOR")
    buttons = mgr.locator("button[name=request]").all_inner_texts()
    rec.steps.append({"step": "J3B level 2 as manager", "messages": [f"buttons={','.join(b.strip() for b in buttons) or '-'}"],
                      "url": mgr.url.split("/", 3)[-1]})

    director = login(browser, base, "demo_dir")
    open_approval(director, base, "REQ-2026-0005", "DIRECTOR")
    buttons = director.locator("button[name=request]").all_inner_texts()
    rec.steps.append({"step": "J3C level 2 as director", "messages": [f"buttons={','.join(sorted(b.strip() for b in buttons)) or '-'}"],
                      "url": director.url.split("/", 3)[-1]})
    director.fill("#P191_NOTE", "WP96 L2 ok")
    submit(director, "APPROVE")
    rec.note("J3C approve level 2", director)


def _table_rows(page: Page, test_id: str) -> str:
    rows = []
    for tr in page.get_by_test_id(test_id).locator("tbody tr").all():
        cells = [c for c in tr.locator("td").all() if not c.locator("a[aria-label=Edit]").count()]
        rows.append("|".join(c.inner_text().strip() for c in cells))
    return "rows=" + " ; ".join(rows)


def _facets(page: Page) -> list[str]:
    out = []
    for fs in page.locator("form[aria-label=Filter] fieldset").all():
        values = []
        for lab in fs.locator("label").all():
            count = lab.locator(".count").inner_text().strip()
            values.append(f"{lab.inner_text().strip()[: -len(count)].strip()} {count}")
        out.append(f"facet {fs.locator('legend').inner_text().strip()}=" + ", ".join(values))
    return out


def _ir(rec: Recorder, step: str, page: Page, test_id: str):
    rec.steps.append({"step": step, "messages": [_table_rows(page, test_id), "range=" + page.get_by_test_id("row-range").inner_text().strip()],
                      "url": page.url.split("/", 3)[-1]})


def _csv(rec: Recorder, step: str, page: Page, base: str):
    link = page.get_by_role("link", name="Download CSV")
    href = link.get_attribute("href")
    with page.expect_download() as d:
        link.click()
    body = Path(d.value.path()).read_bytes().decode("utf-8")  # strict: a BOM would show up as U+FEFF
    rec.steps.append({"step": step, "messages": [f"file={d.value.suggested_filename}", "csv=" + body], "url": href})


def _ir_search(page: Page, text: str):
    page.get_by_role("search").get_by_role("searchbox").fill(text)
    page.get_by_role("search").get_by_role("button", name="Go").click()
    page.wait_for_url(f"**q={text}**")
    page.wait_for_load_state("networkidle")


def _ir_sort(page: Page, test_id: str, label: str, direction: str):
    for _ in range(2):
        header = page.get_by_test_id(test_id).locator("thead a", has_text=label)
        if direction == "desc" and header.inner_text().endswith("▼") or direction == "asc" and header.inner_text().endswith("▲"):
            return
        header.click()
        page.wait_for_url("**dir=**")
        page.wait_for_load_state("networkidle")


def _faceted(rec: Recorder, step: str, page: Page, content: list[str]):
    rec.steps.append({"step": step, "messages": content + _facets(page), "url": page.url.split("/", 3)[-1]})


def _cards(page: Page) -> str:
    cards = [" | ".join(x.strip() for x in c.inner_text().split("\n") if x.strip() and x.strip() != "◆")
             for c in page.locator("[data-testid=cards] article").all()]
    return "cards=" + " ; ".join(cards)


def _facet_click(page: Page, value: str):
    with page.expect_navigation():
        page.locator(f"form[aria-label=Filter] input[type=checkbox][value='{value}']").check()
    page.wait_for_load_state("networkidle")


def _facet_search(page: Page, item: str, text: str):
    page.fill(f"#{item}", text)
    with page.expect_navigation():
        page.press(f"#{item}", "Enter")
    page.wait_for_load_state("networkidle")


def run_j04(browser, base: str, rec: Recorder) -> None:
    """J-04 read-only reports: IR search/sort/CSV (pages 310, 400) and faceted search (pages 300, 210) on snapshot S3."""
    admin = login(browser, base, "demo_admin")
    go(admin, base, "/request-lines")
    _ir(rec, "J4A lines default", admin, "report-requestLines")
    _ir_search(admin, "laptop")
    _ir(rec, "J4A lines search laptop", admin, "report-requestLines")
    _ir_sort(admin, "report-requestLines", "Jumlah", "desc")
    _ir(rec, "J4A lines search laptop, sort Jumlah desc", admin, "report-requestLines")
    _csv(rec, "J4A lines CSV", admin, base)
    go(admin, base, "/reports/requests")
    _ir(rec, "J4B summary default", admin, "report-requestSummary")
    _ir_sort(admin, "report-requestSummary", "Total", "asc")
    _ir(rec, "J4B summary sort Total asc", admin, "report-requestSummary")
    _ir_search(admin, "OPERATIONS")
    _ir(rec, "J4B summary sort Total asc, search OPERATIONS", admin, "report-requestSummary")
    _csv(rec, "J4B summary CSV", admin, base)

    go(admin, base, "/requests")
    rng = lambda: "range=" + admin.get_by_test_id("row-range").inner_text().strip()  # noqa: E731
    _faceted(rec, "J4C requests default", admin, [_table_rows(admin, "report-requests"), rng()])
    _facet_click(admin, "P300_STATUS:DRAFT")
    _faceted(rec, "J4C requests Status DRAFT", admin, [_table_rows(admin, "report-requests"), rng()])
    _facet_search(admin, "P300_SEARCH", "laptop")
    _faceted(rec, "J4C requests Status DRAFT, search laptop", admin, [_table_rows(admin, "report-requests"), rng()])
    go(admin, base, "/items")
    _faceted(rec, "J4D items default", admin, [_cards(admin)])
    _facet_click(admin, "P210_CATEGORY:IT")
    _faceted(rec, "J4D items Kategori IT", admin, [_cards(admin)])
    go(admin, base, "/items")
    _facet_search(admin, "P210_SEARCH", "toner")
    _faceted(rec, "J4D items search toner", admin, [_cards(admin)])


def _region_text(page: Page) -> str:
    return page.locator("main").inner_text()


def run_j05(browser, base: str, rec: Recorder) -> None:
    """J-05 negative authorization (DEMO_REQ on admin and master data pages) and lost update between two tabs."""
    req = login(browser, base, "demo_req")
    for path, step in (("/admin/users", "J5A users page as requester"), ("/admin/document-types", "J5A document types page as requester")):
        go(req, base, path)
        rec.note(step, req)
    for path, step, test_id in (("/departments", "J5A departments as requester", "report-departments"),):
        go(req, base, path)
        rec.steps.append({"step": step, "messages": [_table_rows(req, test_id).split("|")[0] and f"rows={req.get_by_test_id(test_id).locator('tbody tr').count()}",
                                                     "range=" + req.get_by_test_id("row-range").inner_text().strip(),
                                                     f"create={req.get_by_role('link', name='Create', exact=True).count()}"],
                          "url": req.url.split("/", 3)[-1]})
    go(req, base, "/items")
    rec.steps.append({"step": "J5A items as requester", "messages": [f"cards={req.locator('[data-testid=cards] article').count()}",
                                                                     f"create={req.get_by_role('link', name='Create', exact=True).count()}"],
                      "url": req.url.split("/", 3)[-1]})

    go(req, base, "/requests/new")
    req.select_option("#P301_DEPARTMENT_ID", label="OPS - Operations")
    req.fill("#P301_NEED_DATE", NEED)
    req.fill("#P301_PURPOSE", "WP96 parity D")
    submit(req, "CREATE")
    rec.note("J5B create", req)
    # round 1 (as on APEX): a second tab saves while the first one stays open without saving
    tab_a = req
    open_request(tab_a, base, "REQ-2026-0006")
    tab_b = req.context.new_page()
    open_request(tab_b, base, "REQ-2026-0006")
    tab_b.fill("#P301_PURPOSE", "WP96 parity D tab B")
    submit(tab_b, "SAVE")
    rec.note("J5B round 1 tab B save", tab_b)
    # round 2: both tabs open on the same version; A saves, then B saves its stale form
    open_request(tab_a, base, "REQ-2026-0006")
    open_request(tab_b, base, "REQ-2026-0006")
    tab_a.fill("#P301_PURPOSE", "WP96 parity D tab A")
    submit(tab_a, "SAVE")
    rec.note("J5B round 2 tab A save", tab_a)
    tab_b.fill("#P301_NOTES", "stale edit from tab B")
    submit(tab_b, "SAVE")
    rec.note("J5B round 2 tab B stale save", tab_b)


JOURNEYS = {"J-01": run_j01, "J-02": run_j02, "J-03": run_j03, "J-04": run_j04, "J-05": run_j05}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--journey", choices=sorted(JOURNEYS), default="J-01")
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
            JOURNEYS[args.journey](browser, f"http://127.0.0.1:{web_port}", rec)
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
    report = {"journey": args.journey, "s0": {"name": args.s0.name, "sha256": parse_snapshot(args.s0.read_text(encoding="utf-8")).sha256},
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
