"""
tests/selenium/conftest.py
===========================
Shared fixtures and configuration for Selenium system tests.

Author : Eyob Kassaye (ATE/4534/16) — Person 3, Test Automation Engineer

Provides:
  - BASE_URL constant (from env or default localhost:5000)
  - Seeded test credentials
  - WebDriver factory (Chrome headless by default, Firefox via env var)
"""

import os
import pytest

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


# ── Configuration ────────────────────────────────────────────────────────────

BASE_URL          = os.environ.get("SELENIUM_BASE_URL", "http://localhost:5000")
EMPLOYEE_EMAIL    = os.environ.get("SELENIUM_EMP_EMAIL", "john@company.com")
EMPLOYEE_PASSWORD = os.environ.get("SELENIUM_EMP_PASS",  "password123")
ADMIN_EMAIL       = os.environ.get("SELENIUM_ADM_EMAIL", "admin@company.com")
ADMIN_PASSWORD    = os.environ.get("SELENIUM_ADM_PASS",  "admin123")


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _build_driver():
    """Return a configured WebDriver (Chrome headless by default)."""
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


@pytest.fixture(scope="function")
def driver():
    """Provide a WebDriver instance; quit after each test function."""
    if not SELENIUM_AVAILABLE:
        pytest.skip("selenium package is not installed — run: pip install selenium")
    try:
        drv = _build_driver()
    except Exception as exc:
        pytest.skip(f"WebDriver unavailable: {exc}")
    yield drv
    drv.quit()


@pytest.fixture(scope="function")
def logged_in_employee(driver):
    """WebDriver already authenticated as the seeded employee account."""
    from tests.selenium.pages.login_page import LoginPage
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    LoginPage(driver, BASE_URL).open().login(EMPLOYEE_EMAIL, EMPLOYEE_PASSWORD)
    WebDriverWait(driver, 10).until(EC.url_contains("/dashboard"))
    return driver


@pytest.fixture(scope="function")
def logged_in_admin(driver):
    """WebDriver already authenticated as the seeded admin account."""
    from tests.selenium.pages.login_page import LoginPage
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    LoginPage(driver, BASE_URL).open().login(ADMIN_EMAIL, ADMIN_PASSWORD)
    WebDriverWait(driver, 10).until(EC.url_contains("/dashboard"))
    return driver
