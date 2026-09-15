"""
tests/selenium/pages/leave_history_page.py
============================================
Page Object for the Leave History page (/leave-history).

Author : Eyob Kassaye (ATE/4534/16) — Person 3
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class LeaveHistoryPage:
    """Encapsulates all interactions with the /leave-history page."""

    URL_PATH = "/leave-history"

    # --- Locators ---
    HISTORY_TABLE   = (By.CSS_SELECTOR, "table")
    TABLE_ROWS      = (By.CSS_SELECTOR, "table tbody tr")
    CANCEL_BUTTONS  = (By.CSS_SELECTOR, "form[action*='/cancel'] button")
    FLASH_MESSAGE   = (By.CSS_SELECTOR, ".alert")

    def __init__(self, driver, base_url: str):
        self.driver = driver
        self.base_url = base_url.rstrip("/")
        self.wait = WebDriverWait(driver, 10)

    # --- Navigation ---

    def open(self):
        self.driver.get(self.base_url + self.URL_PATH)
        self.wait.until(EC.url_contains("/leave-history"))
        return self

    # --- Actions ---

    def cancel_first_request(self):
        """Click the Cancel button on the first cancellable leave request."""
        buttons = self.wait.until(
            EC.presence_of_all_elements_located(self.CANCEL_BUTTONS)
        )
        if buttons:
            buttons[0].click()
        return self

    def cancel_request_by_index(self, index: int = 0):
        """Click the Cancel button for a specific request by index."""
        buttons = self.wait.until(
            EC.presence_of_all_elements_located(self.CANCEL_BUTTONS)
        )
        if index < len(buttons):
            buttons[index].click()
        return self

    # --- Queries ---

    def get_page_text(self) -> str:
        return self.driver.find_element(By.TAG_NAME, "body").text

    def get_all_rows_text(self) -> list:
        """Return the text of every row in the history table."""
        try:
            rows = self.driver.find_elements(*self.TABLE_ROWS)
            return [r.text for r in rows]
        except Exception:
            return []

    def row_count(self) -> int:
        return len(self.get_all_rows_text())

    def has_request_with_status(self, status: str) -> bool:
        """Check whether any table row contains the given status text."""
        return any(status in row for row in self.get_all_rows_text())

    def has_leave_type(self, leave_type: str) -> bool:
        """Check whether the page contains a row with the given leave type."""
        return leave_type in self.get_page_text()

    def cancel_buttons_count(self) -> int:
        try:
            buttons = self.driver.find_elements(*self.CANCEL_BUTTONS)
            return len(buttons)
        except Exception:
            return 0

    def get_flash_message(self) -> str:
        try:
            el = self.wait.until(EC.presence_of_element_located(self.FLASH_MESSAGE))
            return el.text
        except Exception:
            return ""

    def is_on_history_page(self) -> bool:
        return "/leave-history" in self.driver.current_url
