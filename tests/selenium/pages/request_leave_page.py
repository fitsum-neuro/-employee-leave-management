"""
tests/selenium/pages/request_leave_page.py
============================================
Page Object for the Request Leave page (/request-leave).

Author : Eyob Kassaye (ATE/4534/16) — Person 3
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC


class RequestLeavePage:
    """Encapsulates all interactions with the /request-leave page."""

    URL_PATH = "/request-leave"

    # --- Locators ---
    LEAVE_TYPE_SELECT  = (By.ID, "leave_type")
    START_DATE_INPUT   = (By.ID, "start_date")
    END_DATE_INPUT     = (By.ID, "end_date")
    REASON_INPUT       = (By.ID, "reason")
    HAS_DOCUMENT_CB    = (By.ID, "has_document")
    SUBMIT_BUTTON      = (By.CSS_SELECTOR, "button[type='submit']")
    FLASH_MESSAGE      = (By.CSS_SELECTOR, ".alert")

    def __init__(self, driver, base_url: str):
        self.driver = driver
        self.base_url = base_url.rstrip("/")
        self.wait = WebDriverWait(driver, 10)

    # --- Navigation ---

    def open(self):
        self.driver.get(self.base_url + self.URL_PATH)
        self.wait.until(EC.presence_of_element_located(self.LEAVE_TYPE_SELECT))
        return self

    # --- Actions ---

    def select_leave_type(self, leave_type: str):
        """Select a leave type from the dropdown (e.g. 'Annual', 'Sick', 'Personal')."""
        select = Select(
            self.wait.until(EC.presence_of_element_located(self.LEAVE_TYPE_SELECT))
        )
        select.select_by_visible_text(leave_type)
        return self

    def enter_start_date(self, date_str: str):
        """Enter a start date (YYYY-MM-DD)."""
        field = self.wait.until(EC.element_to_be_clickable(self.START_DATE_INPUT))
        field.clear()
        field.send_keys(date_str)
        return self

    def enter_end_date(self, date_str: str):
        field = self.wait.until(EC.element_to_be_clickable(self.END_DATE_INPUT))
        field.clear()
        field.send_keys(date_str)
        return self

    def enter_reason(self, reason: str):
        field = self.wait.until(EC.element_to_be_clickable(self.REASON_INPUT))
        field.clear()
        field.send_keys(reason)
        return self

    def check_has_document(self, check: bool = True):
        cb = self.wait.until(EC.presence_of_element_located(self.HAS_DOCUMENT_CB))
        if check and not cb.is_selected():
            cb.click()
        elif not check and cb.is_selected():
            cb.click()
        return self

    def submit(self):
        self.wait.until(EC.element_to_be_clickable(self.SUBMIT_BUTTON)).click()
        return self

    def fill_and_submit(self, leave_type: str, start: str, end: str,
                        reason: str = "", has_document: bool = False):
        """Convenience: fill the entire form and submit."""
        self.select_leave_type(leave_type)
        self.enter_start_date(start)
        self.enter_end_date(end)
        self.enter_reason(reason)
        self.check_has_document(has_document)
        self.submit()
        return self

    # --- Queries ---

    def get_flash_message(self) -> str:
        try:
            el = self.wait.until(EC.presence_of_element_located(self.FLASH_MESSAGE))
            return el.text
        except Exception:
            return ""

    def is_on_request_page(self) -> bool:
        return "/request-leave" in self.driver.current_url

    def is_on_history_page(self) -> bool:
        return "/leave-history" in self.driver.current_url
