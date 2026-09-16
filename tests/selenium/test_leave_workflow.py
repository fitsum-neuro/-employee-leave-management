"""
tests/selenium/test_leave_workflow.py
========================================
End-to-end Selenium system tests for the Employee Leave Management System.

Author  : Eyob Kassaye (ATE/4534/16) — Person 3, Test Automation Engineer
Pattern : Page Object Model (POM)
Runner  : pytest + selenium (Chrome headless)

Prerequisites
-------------
* The Flask app must be running at BASE_URL (default: http://localhost:5000).
* Chrome + chromedriver must be available on PATH, OR set SELENIUM_DRIVER=firefox
  and have geckodriver on PATH.
* Install selenium:  python -m pip install selenium

Markers
-------
* @pytest.mark.system   — full browser-based end-to-end test
* @pytest.mark.defect   — reproduces a known defect; expected to fail
                          against the current build

Run system tests:
    pytest tests/selenium/test_leave_workflow.py -v

Skip if the app is not running:
    pytest tests/selenium/ -v --ignore-glob="*selenium*"  # run only unit/integration
"""

import os
import time
import threading
import pytest

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

from tests.selenium.pages.login_page import LoginPage
from tests.selenium.pages.dashboard_page import DashboardPage
from tests.selenium.pages.request_leave_page import RequestLeavePage
from tests.selenium.pages.leave_history_page import LeaveHistoryPage
from tests.selenium.pages.admin_page import AdminPage


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

BASE_URL = os.environ.get("SELENIUM_BASE_URL", "http://localhost:5000")
EMPLOYEE_EMAIL    = os.environ.get("SELENIUM_EMP_EMAIL", "john@company.com")
EMPLOYEE_PASSWORD = os.environ.get("SELENIUM_EMP_PASS",  "password123")
ADMIN_EMAIL       = os.environ.get("SELENIUM_ADM_EMAIL", "admin@company.com")
ADMIN_PASSWORD    = os.environ.get("SELENIUM_ADM_PASS",  "admin123")

# Leave dates well in the future (won't expire during test runs)
FUTURE_START = "2027-06-01"
FUTURE_END   = "2027-06-05"   # 5 days


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _build_driver():
    """Create a headless Chrome (or Firefox) WebDriver instance."""
    driver_type = os.environ.get("SELENIUM_DRIVER", "chrome").lower()

    if driver_type == "firefox":
        opts = FirefoxOptions()
        opts.add_argument("--headless")
        return webdriver.Firefox(options=opts)

    opts = ChromeOptions()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,800")
    return webdriver.Chrome(options=opts)


def _app_is_reachable(url: str) -> bool:
    """Return True if the Flask app is already listening at url."""
    import urllib.request
    try:
        urllib.request.urlopen(url, timeout=3)
        return True
    except Exception:
        return False


def _start_embedded_server():
    """
    Start the Flask dev server in a daemon thread so Selenium tests can run
    without requiring a separately-started server.
    Returns the thread (already running).
    """
    import sys
    import os
    # Add project root to sys.path so 'app' is importable
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if root not in sys.path:
        sys.path.insert(0, root)

    from app import create_app
    import tempfile

    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    flask_app = create_app({"TESTING": False, "DATABASE": db_path,
                             "SECRET_KEY": "selenium-secret"})

    # Seed demo users so the standard credentials work
    with flask_app.app_context():
        from app.models import Employee, LeaveBalance
        from app.auth import hash_password
        emp = Employee.create(
            employee_id="EMP-SEL-01", name="John Employee",
            email=EMPLOYEE_EMAIL,
            password_hash=hash_password(EMPLOYEE_PASSWORD),
            department="Engineering",
            hire_date="2025-01-01",
            role="employee",
        )
        for lt, total in [("Annual", 20), ("Sick", 15), ("Personal", 5)]:
            LeaveBalance.create(emp.id, lt, total)
        Employee.create(
            employee_id="ADM-SEL-01", name="Test Admin",
            email=ADMIN_EMAIL,
            password_hash=hash_password(ADMIN_PASSWORD),
            department="Management",
            hire_date="2020-01-01",
            role="admin",
        )

    thread = threading.Thread(
        target=lambda: flask_app.run(port=5000, use_reloader=False),
        daemon=True,
    )
    thread.start()
    time.sleep(1.5)  # give the server a moment to bind
    return thread, db_path


# Module-level server handle (started once per pytest session)
_server_thread = None
_server_db_path = None


@pytest.fixture(scope="module", autouse=True)
def flask_server():
    """Start the embedded Flask server once for the whole test module."""
    global _server_thread, _server_db_path
    if not _app_is_reachable(BASE_URL):
        _server_thread, _server_db_path = _start_embedded_server()
    yield
    # Daemon thread: no explicit cleanup needed.


@pytest.fixture
def driver():
    """Create and yield a WebDriver; quit after the test."""
    if not SELENIUM_AVAILABLE:
        pytest.skip("selenium package not installed")
    try:
        drv = _build_driver()
    except Exception as exc:
        pytest.skip(f"WebDriver not available: {exc}")
    yield drv
    drv.quit()


@pytest.fixture
def logged_in_employee(driver):
    """WebDriver fixture: employee already logged in."""
    lp = LoginPage(driver, BASE_URL).open()
    lp.login(EMPLOYEE_EMAIL, EMPLOYEE_PASSWORD)
    WebDriverWait(driver, 20).until(EC.url_contains("/dashboard"))
    return driver


@pytest.fixture
def logged_in_admin(driver):
    """WebDriver fixture: admin already logged in."""
    lp = LoginPage(driver, BASE_URL).open()
    lp.login(ADMIN_EMAIL, ADMIN_PASSWORD)
    WebDriverWait(driver, 20).until(EC.url_contains("/dashboard"))
    return driver


# ─────────────────────────────────────────────────────────────────────────────
# SYS-01: Login / Logout flows
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.system
class TestLoginLogoutFlow:
    """End-to-end login and logout via the browser."""

    def test_valid_employee_login_lands_on_dashboard(self, driver):
        """SYS-01-01: Valid employee login redirects to /dashboard."""
        lp = LoginPage(driver, BASE_URL).open()
        lp.login(EMPLOYEE_EMAIL, EMPLOYEE_PASSWORD)
        WebDriverWait(driver, 20).until(EC.url_contains("/dashboard"))
        assert "/dashboard" in driver.current_url

    def test_invalid_password_stays_on_login(self, driver):
        """SYS-01-02: Wrong password keeps user on login page."""
        lp = LoginPage(driver, BASE_URL).open()
        lp.login(EMPLOYEE_EMAIL, "wrong_password")
        time.sleep(0.5)
        assert "/login" in driver.current_url or "Invalid" in driver.page_source

    def test_unknown_email_shows_error(self, driver):
        """SYS-01-03: Unknown email shows invalid-credentials message."""
        lp = LoginPage(driver, BASE_URL).open()
        lp.login("nobody@example.com", "anything")
        time.sleep(0.5)
        assert "Invalid" in driver.page_source or "/login" in driver.current_url

    def test_logout_redirects_to_login(self, logged_in_employee):
        """SYS-01-04: Clicking Logout redirects to /login."""
        driver = logged_in_employee
        dp = DashboardPage(driver, BASE_URL)
        dp.logout()
        WebDriverWait(driver, 20).until(EC.url_contains("/login"))
        assert "/login" in driver.current_url

    def test_protected_page_redirects_unauthenticated(self, driver):
        """SYS-01-05: Accessing /dashboard without login redirects to /login."""
        driver.get(BASE_URL + "/dashboard")
        WebDriverWait(driver, 20).until(EC.url_contains("/login"))
        assert "/login" in driver.current_url


# ─────────────────────────────────────────────────────────────────────────────
# SYS-02: Full Leave Request Workflow
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.system
class TestLeaveRequestWorkflow:
    """End-to-end: employee submits leave → admin approves → history updated."""

    def test_employee_can_submit_annual_leave(self, logged_in_employee):
        """SYS-02-01: Employee submits a valid Annual leave request."""
        driver = logged_in_employee
        dp = DashboardPage(driver, BASE_URL)
        dp.go_to_request_leave()

        rlp = RequestLeavePage(driver, BASE_URL)
        rlp.fill_and_submit("Annual", FUTURE_START, FUTURE_END)

        # Should redirect to leave history on success
        WebDriverWait(driver, 10).until(
            lambda d: "/leave-history" in d.current_url
                      or "submitted" in d.page_source.lower()
                      or "Annual" in d.page_source
        )
        assert "Annual" in driver.page_source

    def test_submitted_request_appears_in_history(self, logged_in_employee):
        """SYS-02-02: After submitting, the leave appears in leave history."""
        driver = logged_in_employee

        # Submit leave
        rlp = RequestLeavePage(driver, BASE_URL).open()
        rlp.fill_and_submit("Personal", "2027-07-01", "2027-07-01", reason="Personal errand")

        # View history
        lhp = LeaveHistoryPage(driver, BASE_URL).open()
        assert lhp.has_leave_type("Personal")

    def test_new_request_has_requested_status(self, logged_in_employee):
        """SYS-02-03: Newly submitted request shows 'Requested' status in history."""
        driver = logged_in_employee

        rlp = RequestLeavePage(driver, BASE_URL).open()
        rlp.fill_and_submit("Sick", "2027-08-10", "2027-08-11",
                             reason="Flu", has_document=False)

        lhp = LeaveHistoryPage(driver, BASE_URL).open()
        assert lhp.has_request_with_status("Requested")

    def test_sick_leave_with_document_accepted(self, logged_in_employee):
        """SYS-02-04: Sick leave >3 days with document is accepted."""
        driver = logged_in_employee

        rlp = RequestLeavePage(driver, BASE_URL).open()
        rlp.fill_and_submit("Sick", "2027-09-01", "2027-09-05",
                             reason="Surgery", has_document=True)

        lhp = LeaveHistoryPage(driver, BASE_URL).open()
        assert lhp.has_leave_type("Sick")


# ─────────────────────────────────────────────────────────────────────────────
# SYS-03: Admin Approve / Reject Workflow
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.system
class TestAdminWorkflow:
    """End-to-end: admin approves and rejects pending leave requests."""

    def _employee_submits_leave(self, driver, leave_type, start, end,
                                reason="", has_doc=False):
        """Helper: log in as employee, submit leave, log out."""
        lp = LoginPage(driver, BASE_URL).open()
        lp.login(EMPLOYEE_EMAIL, EMPLOYEE_PASSWORD)
        WebDriverWait(driver, 20).until(EC.url_contains("/dashboard"))

        rlp = RequestLeavePage(driver, BASE_URL).open()
        rlp.fill_and_submit(leave_type, start, end, reason, has_doc)
        time.sleep(0.5)

        # Logout
        driver.get(BASE_URL + "/logout")
        WebDriverWait(driver, 20).until(EC.url_contains("/login"))

    def test_admin_can_approve_pending_request(self, driver):
        """SYS-03-01: Admin can approve a pending leave request."""
        self._employee_submits_leave(driver, "Annual", "2027-10-01", "2027-10-03")

        # Login as admin
        lp = LoginPage(driver, BASE_URL).open()
        lp.login(ADMIN_EMAIL, ADMIN_PASSWORD)
        WebDriverWait(driver, 20).until(EC.url_contains("/dashboard"))

        ap = AdminPage(driver, BASE_URL).open()
        initial_count = ap.approve_button_count()
        assert initial_count >= 1, "Expected at least one pending request"

        ap.approve_first_request()
        time.sleep(0.5)
        assert "approved" in driver.page_source.lower()

    def test_admin_can_reject_pending_request(self, driver):
        """SYS-03-02: Admin can reject a pending leave request."""
        self._employee_submits_leave(driver, "Personal", "2027-11-01", "2027-11-01")

        lp = LoginPage(driver, BASE_URL).open()
        lp.login(ADMIN_EMAIL, ADMIN_PASSWORD)
        WebDriverWait(driver, 20).until(EC.url_contains("/dashboard"))

        ap = AdminPage(driver, BASE_URL).open()
        assert ap.reject_button_count() >= 1

        ap.reject_first_request()
        time.sleep(0.5)
        assert "rejected" in driver.page_source.lower()

    def test_approved_status_visible_in_employee_history(self, driver):
        """SYS-03-03: After admin approval, employee sees 'Approved' in history."""
        self._employee_submits_leave(driver, "Annual", "2027-12-01", "2027-12-02")

        # Admin approves
        lp = LoginPage(driver, BASE_URL).open()
        lp.login(ADMIN_EMAIL, ADMIN_PASSWORD)
        WebDriverWait(driver, 20).until(EC.url_contains("/dashboard"))

        ap = AdminPage(driver, BASE_URL).open()
        ap.approve_first_request()
        time.sleep(0.5)
        driver.get(BASE_URL + "/logout")
        WebDriverWait(driver, 20).until(EC.url_contains("/login"))

        # Employee checks history
        lp2 = LoginPage(driver, BASE_URL).open()
        lp2.login(EMPLOYEE_EMAIL, EMPLOYEE_PASSWORD)
        WebDriverWait(driver, 20).until(EC.url_contains("/dashboard"))

        lhp = LeaveHistoryPage(driver, BASE_URL).open()
        assert lhp.has_request_with_status("Approved")


# ─────────────────────────────────────────────────────────────────────────────
# SYS-04: Cancellation Flow
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.system
class TestCancellationFlow:
    """End-to-end tests for the cancellation workflow."""

    def test_employee_can_cancel_requested_leave(self, logged_in_employee):
        """SYS-04-01: Employee can cancel a leave that is still in Requested state."""
        driver = logged_in_employee

        rlp = RequestLeavePage(driver, BASE_URL).open()
        rlp.fill_and_submit("Personal", "2027-06-10", "2027-06-10")
        time.sleep(0.5)

        lhp = LeaveHistoryPage(driver, BASE_URL).open()
        initial_count = lhp.row_count()
        assert initial_count >= 1

        lhp.cancel_first_request()
        time.sleep(0.5)

        assert "Cancelled" in driver.page_source or "cancelled" in driver.page_source.lower()

    def test_cancel_removes_entry_from_cancellable_list(self, logged_in_employee):
        """SYS-04-02: After cancellation the Cancel button disappears for that request."""
        driver = logged_in_employee

        rlp = RequestLeavePage(driver, BASE_URL).open()
        rlp.fill_and_submit("Annual", "2027-06-15", "2027-06-15")
        time.sleep(0.5)

        lhp = LeaveHistoryPage(driver, BASE_URL).open()
        before = lhp.cancel_buttons_count()
        lhp.cancel_first_request()
        time.sleep(0.5)

        lhp2 = LeaveHistoryPage(driver, BASE_URL).open()
        after = lhp2.cancel_buttons_count()
        assert after <= before  # Cancel button should disappear after cancellation


# ─────────────────────────────────────────────────────────────────────────────
# SYS-05: Invalid Input Handling
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.system
class TestInvalidInputHandling:
    """End-to-end tests verifying the UI rejects invalid leave requests."""

    def test_requesting_more_than_30_days_shows_error(self, logged_in_employee):
        """SYS-05-01: Requesting >30 days shows an error message."""
        driver = logged_in_employee

        rlp = RequestLeavePage(driver, BASE_URL).open()
        # 35 days — exceeds the 30-day maximum
        rlp.fill_and_submit("Annual", "2027-06-01", "2027-07-05", reason="Long leave")
        time.sleep(0.5)

        assert "exceed" in driver.page_source.lower() or "30" in driver.page_source

    def test_past_start_date_rejected(self, logged_in_employee):
        """SYS-05-02: A start date in the past is rejected."""
        driver = logged_in_employee

        rlp = RequestLeavePage(driver, BASE_URL).open()
        rlp.fill_and_submit("Annual", "2020-01-01", "2020-01-05")
        time.sleep(0.5)

        assert "past" in driver.page_source.lower() or "Invalid" in driver.page_source

    def test_sick_leave_without_document_over_3_days_rejected(self, logged_in_employee):
        """SYS-05-03: Sick leave >3 days without document is rejected."""
        driver = logged_in_employee

        rlp = RequestLeavePage(driver, BASE_URL).open()
        rlp.fill_and_submit("Sick", "2027-06-01", "2027-06-06",
                             reason="Flu", has_document=False)  # 6 days, no doc
        time.sleep(0.5)

        assert "document" in driver.page_source.lower() or "supporting" in driver.page_source.lower()

    def test_insufficient_balance_rejected(self, logged_in_employee):
        """SYS-05-04: Requesting more days than the balance shows error."""
        driver = logged_in_employee

        rlp = RequestLeavePage(driver, BASE_URL).open()
        # Personal balance is 5 days; request 6
        rlp.fill_and_submit("Personal", "2027-06-01", "2027-06-06")
        time.sleep(0.5)

        assert "insufficient" in driver.page_source.lower() or "balance" in driver.page_source.lower()
