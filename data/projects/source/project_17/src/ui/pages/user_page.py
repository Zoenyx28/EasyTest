from core.ui_core.page_action import PageAction
from core.ui_core.ui_assert import UiAssert
from core.log_handler import logger


class UserPage:
    def __init__(self, page):
        self.page = page
        self.page_action = PageAction(page)
        self.ui_assert = UiAssert(page)
        self.locators = {
            "user_list_table": "#user-list-table",
            "add_user_button": "button:has-text('添加用户')",
            "username_input": "#username",
            "email_input": "#email",
            "password_input": "#password",
            "save_button": "button:has-text('保存')",
            "success_message": ".success-message",
            "user_row": ".user-row",
            "edit_button": "button:has-text('编辑')",
            "delete_button": "button:has-text('删除')",
            "confirm_delete_button": "button:has-text('确定删除')",
            "search_input": "#search-input",
            "search_button": "button:has-text('搜索')"
        }

    def open(self, url: str):
        logger.info("【UI】Opening user page")
        self.page.goto(url, wait_until="networkidle")

    def click_add_user(self):
        logger.info("【UI】Clicking add user button")
        self.page_action.click(self.locators["add_user_button"])

    def enter_username(self, username: str):
        logger.info(f"【UI】Entering username: {username}")
        self.page_action.input_text(self.locators["username_input"], username)

    def enter_email(self, email: str):
        logger.info(f"【UI】Entering email: {email}")
        self.page_action.input_text(self.locators["email_input"], email)

    def enter_password(self, password: str):
        logger.info(f"【UI】Entering password")
        self.page_action.input_text(self.locators["password_input"], password)

    def click_save(self):
        logger.info("【UI】Clicking save button")
        self.page_action.click(self.locators["save_button"])

    def add_user(self, username: str, email: str, password: str):
        logger.info(f"【UI】Adding user: {username}")
        self.click_add_user()
        self.enter_username(username)
        self.enter_email(email)
        self.enter_password(password)
        self.click_save()

    def assert_user_added(self, expected_message: str = "添加成功"):
        logger.info("【UI】Asserting user added successfully")
        self.ui_assert.assert_element_visible(self.locators["success_message"])
        self.ui_assert.assert_text_contains(self.locators["success_message"], expected_message)

    def search_user(self, keyword: str):
        logger.info(f"【UI】Searching user: {keyword}")
        self.page_action.input_text(self.locators["search_input"], keyword)
        self.page_action.click(self.locators["search_button"])

    def get_user_count(self) -> int:
        elements = self.page_action.find_elements(self.locators["user_row"])
        return len(elements)

    def assert_user_exists(self, username: str):
        logger.info(f"【UI】Asserting user exists: {username}")
        self.search_user(username)
        count = self.get_user_count()
        assert count > 0, f"User {username} not found"

    def delete_user(self, username: str):
        logger.info(f"【UI】Deleting user: {username}")
        self.search_user(username)
        self.page_action.click(self.locators["delete_button"])
        self.page_action.click(self.locators["confirm_delete_button"])

    def assert_user_deleted(self, username: str):
        logger.info(f"【UI】Asserting user deleted: {username}")
        self.search_user(username)
        count = self.get_user_count()
        assert count == 0, f"User {username} still exists"