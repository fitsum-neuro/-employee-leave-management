"""
tests/selenium/pages/admin_page.py
=====================================
Page Object for the Admin Panel page (/admin).

Author : Eyob Kassaye (ATE/4534/16) — Person 3
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class AdminPage:
    """Encapsulates all interactions with the /admin panel page."""

    URL_PATH = "/admin"

    # --- Locators ---
    PENDING_ROWS    = (By.CSS_SELECTOR, "table tbody tr")
    APPROVE_BUTTONS = (By.CSS_SELECTOR, "form[action*='/admin/approve'] button")
    REJECT_BUTTONS  = (By.CSS_SELECTOR, "form[action*='/admin/reject'] button")
    TAKEN_BUTTONS   = (By.CSS_SELECTOR, "form[action*='/admin/mark-taken'] button")
    FLASH_MESSAGE   = (By.CSS_SELECTOR, ".alert")
    NO_PENDING_MSG  = (By.CSS_SELECTOR, ".no-pending, p")

    def __init__(self, driver, base_url: str):
        self.driver = driver
        self.base_url = base_url.rstrip("/")
        self.wait = WebDriverWait(driver, 10)

    # --- Navigation ---

    def open(self):
        self.driver.get(self.base_url + self.URL_PATH)
        self.wait.until(EC.url_contains("/admin"))
        return self

    # --- Actions ---

    def approve_first_request(self):
        """Click Approve on the first pending request."""
        buttons = self.wait.until(
            EC.presence_of_all_elements_located(self.APPROVE_BUTTONS)
        )
        if buttons:
            buttons[0].click()
        return self

    def approve_request_by_index(self, index: int = 0):
        buttons = self.driver.find_elements(*self.APPROVE_BUTTONS)
        if index < len(buttons):
            buttons[index].click()
        return self

    def reject_first_request(self):
        """Click Reject on the first pending request."""
        buttons = self.wait.until(
            EC.presence_of_all_elements_located(self.REJECT_BUTTONS)
        )
        if buttons:
            buttons[0].click()
        return self

    def reject_request_by_index(self, index: int = 0):
        buttons = self.driver.find_elements(*self.REJECT_BUTTONS)
        if index < len(buttons):
            buttons[index].click()
        return self

    def mark_taken_first_request(self):
        """Click Mark as Taken on the first approved request."""
        buttons = self.wait.until(
            EC.presence_of_all_elements_located(self.TAKEN_BUTTONS)
        )
        if buttons:
            buttons[0].click()
        return self

    # --- Queries ---

    def get_page_text(self) -> str:
        return self.driver.find_element(By.TAG_NAME, "body").text

    def pending_count(self) -> int:
        try:
            rows = self.driver.find_elements(*self.PENDING_ROWS)
            return len(rows)
        except Exception:
            return 0

    def approve_button_count(self) -> int:
        return len(self.driver.find_elements(*self.APPROVE_BUTTONS))

    def reject_button_count(self) -> int:
        return len(self.driver.find_elements(*self.REJECT_BUTTONS))

    def get_flash_message(self) -> str:
        try:
            el = self.wait.until(EC.presence_of_element_located(self.FLASH_MESSAGE))
            return el.text
        except Exception:
            return ""

    def is_on_admin_page(self) -> bool:
        return "/admin" in self.driver.current_url
