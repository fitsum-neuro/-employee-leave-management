"""
tests/selenium/pages/dashboard_page.py
========================================
Page Object for the Dashboard page (/dashboard).

Author : Eyob Kassaye (ATE/4534/16) — Person 3
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class DashboardPage:
    """Encapsulates all interactions with the /dashboard page."""

    URL_PATH = "/dashboard"

    # --- Locators ---
    NAV_REQUEST_LEAVE  = (By.LINK_TEXT, "Request Leave")
    NAV_LEAVE_HISTORY  = (By.LINK_TEXT, "Leave History")
    NAV_ADMIN_PANEL    = (By.LINK_TEXT, "Admin Panel")
    NAV_LOGOUT         = (By.LINK_TEXT, "Logout")
    BALANCE_ROWS       = (By.CSS_SELECTOR, "table tbody tr")
    WELCOME_HEADING    = (By.CSS_SELECTOR, "h1, h2, .welcome")
    FLASH_MESSAGE      = (By.CSS_SELECTOR, ".alert")

    def __init__(self, driver, base_url: str):
        self.driver = driver
        self.base_url = base_url.rstrip("/")
        self.wait = WebDriverWait(driver, 10)

    # --- Navigation ---

    def open(self):
        self.driver.get(self.base_url + self.URL_PATH)
        self.wait.until(EC.url_contains("/dashboard"))
        return self

    def go_to_request_leave(self):
        self.wait.until(EC.element_to_be_clickable(self.NAV_REQUEST_LEAVE)).click()
        return self

    def go_to_leave_history(self):
        self.wait.until(EC.element_to_be_clickable(self.NAV_LEAVE_HISTORY)).click()
        return self

    def go_to_admin_panel(self):
        self.wait.until(EC.element_to_be_clickable(self.NAV_ADMIN_PANEL)).click()
        return self

    def logout(self):
        self.wait.until(EC.element_to_be_clickable(self.NAV_LOGOUT)).click()
        return self

    # --- Queries ---

    def is_on_dashboard(self) -> bool:
        return "/dashboard" in self.driver.current_url

    def get_page_text(self) -> str:
        return self.driver.find_element(By.TAG_NAME, "body").text

    def get_balance_table_text(self) -> str:
        try:
            rows = self.driver.find_elements(*self.BALANCE_ROWS)
            return "\n".join(r.text for r in rows)
        except Exception:
            return ""

    def get_flash_message(self) -> str:
        try:
            el = self.wait.until(EC.presence_of_element_located(self.FLASH_MESSAGE))
            return el.text
        except Exception:
            return ""
