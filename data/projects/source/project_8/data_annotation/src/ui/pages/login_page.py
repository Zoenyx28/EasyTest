from core.ui_core.page_action import PageAction
from core.ui_core.ui_assert import UiAssert
from core.log_handler import logger


class LoginPage:
    def __init__(self, page):
        self.page = page
        self.page_action = PageAction(page)
        self.ui_assert = UiAssert(page)
        self.locators = {
            "username_input": "#username",
            "password_input": "#password",
            "login_button": "button[type='submit']",
            "error_message": ".error-message",
            "welcome_text": ".welcome-text",
            "logout_button": ".logout-btn"
        }

    def open(self, url: str):
        logger.info("【UI】Opening login page")
        self.page.goto(url, wait_until="networkidle")

    def enter_username(self, username: str):
        logger.info(f"【UI】Entering username: {username}")
        self.page_action.input_text(self.locators["username_input"], username)

    def enter_password(self, password: str):
        logger.info(f"【UI】Entering password: {password}")
        self.page_action.input_text(self.locators["password_input"], password)

    def click_login(self):
        logger.info("【UI】Clicking login button")
        self.page_action.click(self.locators["login_button"])

    def login(self, username: str, password: str):
        logger.info(f"【UI】Performing login with username: {username}")
        self.enter_username(username)
        self.enter_password(password)
        self.click_login()

    def assert_login_success(self):
        logger.info("【UI】Asserting login success")
        self.ui_assert.assert_element_visible(self.locators["welcome_text"])
        self.ui_assert.assert_element_visible(self.locators["logout_button"])

    def assert_login_failure(self, expected_message: str = None):
        logger.info("【UI】Asserting login failure")
        self.ui_assert.assert_element_visible(self.locators["error_message"])
        if expected_message:
            self.ui_assert.assert_text_contains(self.locators["error_message"], expected_message)

    def get_error_message(self) -> str:
        return self.page_action.get_text(self.locators["error_message"])

    def click_logout(self):
        logger.info("【UI】Clicking logout button")
        self.page_action.click(self.locators["logout_button"])