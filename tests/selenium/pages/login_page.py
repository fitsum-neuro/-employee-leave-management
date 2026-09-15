"""
tests/selenium/pages/login_page.py
====================================
Page Object for the Login page (/login).

Author : Eyob Kassaye (ATE/4534/16) — Person 3
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class LoginPage:
    """Encapsulates all interactions with the /login page."""

    URL_PATH = "/login"

    # --- Locators ---
    EMAIL_INPUT    = (By.ID, "email")
    PASSWORD_INPUT = (By.ID, "password")
    SUBMIT_BUTTON  = (By.CSS_SELECTOR, "button[type='submit']")
    FLASH_MESSAGE  = (By.CSS_SELECTOR, ".alert")

    def __init__(self, driver, base_url: str):
        self.driver = driver
        self.base_url = base_url.rstrip("/")
        self.wait = WebDriverWait(driver, 10)

    # --- Navigation ---

    def open(self):
        """Navigate to the login page."""
        self.driver.get(self.base_url + self.URL_PATH)
        self.wait.until(
            EC.presence_of_element_located(self.EMAIL_INPUT)
        )
        return self

    # --- Actions ---

    def enter_email(self, email: str):
        field = self.wait.until(EC.element_to_be_clickable(self.EMAIL_INPUT))
        field.clear()
        field.send_keys(email)
        return self

    def enter_password(self, password: str):
        field = self.wait.until(EC.element_to_be_clickable(self.PASSWORD_INPUT))
        field.clear()
        field.send_keys(password)
        return self

    def click_login(self):
        self.wait.until(EC.element_to_be_clickable(self.SUBMIT_BUTTON)).click()
        return self

    def login(self, email: str, password: str):
        """Convenience: fill and submit the login form."""
        self.enter_email(email)
        self.enter_password(password)
        self.click_login()
        return self

    # --- Queries ---

    def get_flash_message(self) -> str:
        """Return the text of the first flash message on the page, or ''."""
        try:
            el = self.wait.until(EC.presence_of_element_located(self.FLASH_MESSAGE))
            return el.text
        except Exception:
            return ""

    def is_on_login_page(self) -> bool:
        return "/login" in self.driver.current_url

    def is_on_dashboard(self) -> bool:
        return "/dashboard" in self.driver.current_url
