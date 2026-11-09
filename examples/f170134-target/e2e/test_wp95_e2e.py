"""WP9.5 end-to-end journeys over the Next.js UI (tests run in file order and share one database)."""
from __future__ import annotations

import datetime as dt
import re

from playwright.sync_api import Page, expect

YEAR = dt.datetime.now(dt.timezone.utc).year
REQ1_NO = f"REQ-{YEAR}-0001"


def submit(page: Page, request: str, *, confirm: bool | None = None) -> None:
    """Click an APEX submit button (name=request); accept/dismiss its confirm dialog when it has one."""
    if confirm is not None:
        page.once("dialog", lambda d: d.accept() if confirm else d.dismiss())
    page.click(f"button[name=request][value={request}]")
    page.wait_for_load_state("networkidle")


def test_login_and_navigation_by_role(app):
    page = app.login("req1", "wrong-password")
    expect(page.locator(".alert-error")).to_have_text("Invalid Login Credentials")
    expect(page).to_have_title("Demo Permintaan Barang - Log In")
    req1 = app.as_user("req1")
    expect(req1.get_by_test_id("app-user")).to_have_text("REQ1")
    nav = req1.get_by_role("navigation", name="Navigation menu")
    for label in ["Home", "Approval Inbox", "Departments", "Items", "Permintaan Barang", "Detail Permintaan",
                  "Baris Permintaan", "Rekap Permintaan"]:
        expect(nav.get_by_role("link", name=label, exact=True)).to_be_visible()
    expect(nav.get_by_text("Administration")).to_have_count(0)
    admin = app.as_user("admin1")
    nav = admin.get_by_role("navigation", name="Navigation menu")
    expect(nav.get_by_role("link", name="Users & Roles")).to_be_visible()
    expect(nav.get_by_role("link", name="Document Types & Approval")).to_be_visible()


def test_user_without_role_is_refused(app):
    page = app.login("nobody")
    expect(page.locator("[data-error-code=FORBIDDEN]")).to_contain_text("Akses ditolak: akun NOBODY belum punya role")


def test_page_authorization_scheme_message(app):
    req1 = app.as_user("req1")
    app.go(req1, "/departments/new")
    expect(req1.locator("[data-error-code=FORBIDDEN]")).to_have_text("Akses ditolak: hanya untuk role WAREHOUSE.")
    app.go(req1, "/admin/users")
    expect(req1.locator("[data-error-code=FORBIDDEN]")).to_have_text("Akses ditolak: hanya untuk role ADMIN.")


def test_create_request_with_validation(app):
    req1 = app.go(app.as_user("req1"), "/requests")
    expect(req1.get_by_text("Tidak ada data.")).to_be_visible()
    req1.click("text=Create")
    req1.wait_for_load_state("networkidle")
    expect(req1.get_by_role("dialog")).to_be_visible()
    expect(req1.locator("#P301_STATUS")).to_have_text("Draft")
    req1.fill("#P301_NEED_DATE", "2000-01-01")
    submit(req1, "CREATE")
    expect(req1.locator(".alert-error")).to_have_text("3 errors have occurred")
    expect(req1.locator("#P301_DEPARTMENT_ID_error")).to_have_text("Department must have some value.")
    expect(req1.locator("#P301_PURPOSE_error")).to_have_text("Keperluan must have some value.")
    expect(req1.locator("#P301_NEED_DATE_error")).to_have_text("Tanggal dibutuhkan tidak boleh sebelum tanggal permintaan.")
    req1.select_option("#P301_DEPARTMENT_ID", label="OPS - Operations")
    req1.fill("#P301_NEED_DATE", "")
    req1.fill("#P301_PURPOSE", "  ATK kantor ")
    submit(req1, "CREATE")
    expect(req1).to_have_url(re.compile(r"/requests$"))
    row = req1.get_by_test_id("report-requests").locator("tbody tr").first
    expect(row).to_contain_text(REQ1_NO)
    expect(row).to_contain_text("ATK kantor")
    expect(row).to_contain_text("DRAFT")
    expect(req1.get_by_test_id("total-row-count")).to_have_text("1 baris")


def test_master_detail_add_line_and_submit(app):
    req1 = app.go(app.as_user("req1"), "/requests/detail")
    expect(req1.get_by_test_id("not-selected")).to_be_visible()
    req1.get_by_test_id("master-list").get_by_role("link", name=REQ1_NO).click()
    req1.wait_for_load_state("networkidle")
    expect(req1.get_by_test_id("header-purpose")).to_have_text("ATK kantor")
    expect(req1.get_by_text("Belum ada Baris Permintaan.")).to_be_visible()
    req1.get_by_role("link", name="Tambah").click()
    req1.wait_for_load_state("networkidle")
    expect(req1.locator("#P311_REQUEST_ID")).to_have_value(re.compile(r"^\d+$"))
    req1.select_option("#P311_ITEM_ID", label="ATK-001 - Kertas A4 80gsm (RIM)")
    req1.fill("#P311_QTY", "3,5")
    submit(req1, "CREATE")
    expect(req1.locator("#P311_QTY_error")).to_have_text("Qty must be Numeric.")
    req1.fill("#P311_QTY", "3")
    req1.fill("#P311_UNIT_PRICE", "55000")
    submit(req1, "CREATE")
    lines = req1.get_by_test_id("detail-lines")
    expect(lines.locator("tbody tr")).to_have_count(1)
    expect(lines.locator("tbody tr").first).to_contain_text("3.00")
    expect(lines.locator("tbody tr").first).to_contain_text("165,000")

    req1.get_by_role("link", name="Edit", exact=True).click()
    req1.wait_for_load_state("networkidle")
    expect(req1.locator("button[value=DELETE]")).to_be_visible()
    req1.fill("#P301_NOTES", "mohon segera")
    submit(req1, "SUBMIT", confirm=False)
    expect(req1.get_by_role("dialog")).to_be_visible()  # dismissed confirm: nothing submitted
    submit(req1, "SUBMIT", confirm=True)
    expect(req1.get_by_role("status")).to_have_text("Dokumen diajukan untuk approval.")
    expect(req1.get_by_test_id("header-status")).to_have_text("SUBMITTED")
    expect(req1.get_by_role("link", name="Tambah")).to_have_count(0)

    req1.get_by_role("link", name="Edit", exact=True).click()
    req1.wait_for_load_state("networkidle")
    for name in ["SAVE", "SUBMIT", "DELETE", "CREATE"]:
        expect(req1.locator(f"button[value={name}]")).to_have_count(0)
    expect(req1.locator("#P301_PURPOSE")).to_have_text("ATK kantor")


def test_approval_inbox_reject_needs_note_then_approve(app):
    mgr = app.go(app.as_user("mgr1"), "/")
    expect(mgr.get_by_test_id("kpis")).to_contain_text("1Approval Menunggu Anda")
    app.go(mgr, "/approvals")
    table = mgr.get_by_test_id("report-approvalInbox")
    expect(table.locator("tbody tr")).to_have_count(1)
    expect(table.locator("tbody tr").first).to_contain_text(REQ1_NO)
    expect(table.locator("tbody tr").first).to_contain_text("165,000")
    table.get_by_role("link", name="Edit").first.click()
    mgr.wait_for_load_state("networkidle")
    expect(mgr.locator("#P191_CAN_ACT_YN")).to_have_text("Y")
    submit(mgr, "REJECT", confirm=True)
    expect(mgr.locator(".alert-error")).to_contain_text("Alasan penolakan wajib diisi.")
    mgr.fill("#P191_NOTE", "ok")
    submit(mgr, "APPROVE")
    expect(mgr).to_have_url(re.compile(r"/approvals\?msg="))
    expect(mgr.get_by_role("status")).to_have_text("Dokumen disetujui.")
    expect(table.locator("tbody tr").first).to_contain_text("APPROVED")

    req1 = app.go(app.as_user("req1"), "/approvals")
    req1.get_by_test_id("report-approvalInbox").get_by_role("link", name="Edit").first.click()
    req1.wait_for_load_state("networkidle")
    expect(req1.locator("button[value=APPROVE]")).to_have_count(0)


def test_status_after_approval_and_lost_update(app):
    req1 = app.go(app.as_user("req1"), "/requests")
    req1.get_by_role("link", name=REQ1_NO).click()
    req1.wait_for_url(re.compile(r"/requests/\d+"))
    req1.wait_for_load_state("networkidle")
    url = req1.url
    other = app.login("mgr1")
    other.goto(url)
    other.wait_for_load_state("networkidle")
    expect(req1.locator("#P301_PURPOSE")).to_have_text("ATK kantor")  # read-only after approval
    req1.select_option("#P301_STATUS", "FULFILLED")
    submit(req1, "SAVE")
    expect(req1.get_by_test_id("report-requests").locator("tbody tr").first).to_contain_text("FULFILLED")
    other.select_option("#P301_STATUS", "CLOSED")
    submit(other, "SAVE")
    expect(other.locator(".alert-error")).to_have_text(
        "Current version of data in database has changed since user initiated update process.")


def test_master_data_departments_and_items(app):
    wh = app.go(app.as_user("wh1"), "/departments")
    wh.click("text=Create")
    wh.wait_for_load_state("networkidle")
    expect(wh.locator("#P201_ACTIVE_YN")).to_have_value("Y")
    wh.fill("#P201_DEPT_CODE", "ops")
    wh.fill("#P201_DEPT_NAME", "Duplicate")
    submit(wh, "CREATE")
    expect(wh.locator(".alert-error")).to_have_text("ORA-00001: unique constraint (APX_DEMO_DEPARTMENTS_U1) violated")
    wh.fill("#P201_DEPT_CODE", "qa")
    wh.fill("#P201_DEPT_NAME", "Quality")
    submit(wh, "CREATE")
    table = wh.get_by_test_id("report-departments")
    expect(table).to_contain_text("QA")
    row = table.locator("tbody tr", has_text="Quality")
    row.get_by_role("link", name="Edit").click()
    wh.wait_for_load_state("networkidle")
    submit(wh, "DELETE", confirm=True)
    expect(table.locator("tbody tr", has_text="Quality")).to_have_count(0)

    app.go(wh, "/items")
    cards = wh.get_by_test_id("cards")
    expect(cards.locator("article")).to_have_count(2)
    wh.get_by_role("checkbox", name=re.compile("^Perangkat IT")).check()
    wh.wait_for_url(re.compile(r"facet=P210_CATEGORY"))
    wh.wait_for_load_state("networkidle")
    expect(cards.locator("article")).to_have_count(1)
    expect(cards).to_contain_text("IT-001")
    cards.get_by_role("link", name="IT-001").click()
    wh.wait_for_load_state("networkidle")
    expect(wh.locator("#P211_CATEGORY")).to_have_value("IT")


def test_reports_search_sort_download(app):
    mgr = app.go(app.as_user("mgr1"), "/reports/requests")
    table = mgr.get_by_test_id("report-requestSummary")
    expect(table.locator("tbody tr")).to_have_count(1)
    expect(table).to_contain_text("165,000")
    mgr.fill("input[name=q]", "nothing-matches")
    mgr.click("text=Go")
    mgr.wait_for_load_state("networkidle")
    expect(mgr.get_by_text("Tidak ada data.")).to_be_visible()
    app.go(mgr, "/reports/requests?q=atk")
    expect(table.locator("tbody tr")).to_have_count(1)
    mgr.get_by_role("link", name=re.compile("^Total")).click()
    mgr.wait_for_load_state("networkidle")
    expect(mgr).to_have_url(re.compile(r"sort=total_amount"))
    with mgr.expect_download() as d:
        mgr.click("text=Download CSV")
    content = open(d.value.path(), encoding="utf-8-sig").read()
    assert content.splitlines()[0] == "No. Permintaan,Department,Tanggal,Keperluan,Jml Baris,Total,Status"
    assert f"{REQ1_NO},Operations," in content and '"165,000"' in content


def test_admin_forms(app):
    admin = app.go(app.as_user("admin1"), "/admin/users")
    admin.click("text=Create")
    admin.wait_for_load_state("networkidle")
    expect(admin.locator("#P501_USERNAME")).to_have_value("ADMIN1")
    admin.fill("#P501_USERNAME", "new.user")
    admin.select_option("#P501_ROLE_CODE", "REQUESTER")
    submit(admin, "CREATE")
    expect(admin.get_by_test_id("report-userRoles")).to_contain_text("NEW.USER")
    app.go(admin, "/admin/document-types")
    admin.get_by_test_id("report-docTypes").get_by_role("link", name="Edit").first.click()
    admin.wait_for_load_state("networkidle")
    expect(admin.locator("button[value=DELETE]")).to_have_count(0)
    admin.fill("#P511_LEVEL2_LIMIT", "20000000")
    submit(admin, "SAVE")
    expect(admin.get_by_test_id("report-docTypes")).to_contain_text("20,000,000")


def test_home_charts_and_sign_out(app):
    req1 = app.go(app.as_user("req1"), "/")
    expect(req1.get_by_role("img", name="Permintaan per Status")).to_be_visible()
    expect(req1.get_by_role("img", name="Nilai per Department")).to_be_visible()
    req1.click("text=Sign Out")
    req1.wait_for_load_state("networkidle")
    expect(req1).to_have_url(re.compile(r"/login$"))
    app.go(req1, "/requests")
    expect(req1).to_have_url(re.compile(r"/login$"))
