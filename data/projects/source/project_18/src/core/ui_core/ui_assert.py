from playwright.sync_api import Page, expect, Locator
from typing import Optional

from core.log_handler import logger


class UiAssert:
    def __init__(self, page: Page):
        self.page = page

    def assert_element_exists(self, locator: str, timeout: int = 30):
        try:
            expect(self.page.locator(locator)).to_have_count(1, timeout=timeout * 1000)
            logger.info(f"【UI】Assertion passed: Element exists - {locator}")
        except Exception:
            logger.error(f"【UI】Assertion failed: Element does not exist - {locator}")
            raise AssertionError(f"Element does not exist: {locator}")

    def assert_element_not_exists(self, locator: str, timeout: int = 5):
        try:
            expect(self.page.locator(locator)).to_have_count(0, timeout=timeout * 1000)
            logger.info(f"【UI】Assertion passed: Element not exists - {locator}")
        except Exception:
            logger.error(f"【UI】Assertion failed: Element still exists - {locator}")
            raise AssertionError(f"Element still exists: {locator}")

    def assert_element_visible(self, locator: str, timeout: int = 30):
        try:
            expect(self.page.locator(locator)).to_be_visible(timeout=timeout * 1000)
            logger.info(f"【UI】Assertion passed: Element visible - {locator}")
        except Exception:
            logger.error(f"【UI】Assertion failed: Element not visible - {locator}")
            raise AssertionError(f"Element not visible: {locator}")

    def assert_element_invisible(self, locator: str, timeout: int = 30):
        try:
            expect(self.page.locator(locator)).to_be_hidden(timeout=timeout * 1000)
            logger.info(f"【UI】Assertion passed: Element invisible - {locator}")
        except Exception:
            logger.error(f"【UI】Assertion failed: Element still visible - {locator}")
            raise AssertionError(f"Element still visible: {locator}")

    def assert_text_equals(self, locator: str, expected_text: str, timeout: int = 30):
        try:
            expect(self.page.locator(locator)).to_have_text(expected_text, timeout=timeout * 1000)
            logger.info(f"【UI】Assertion passed: Text equals '{expected_text}'")
        except Exception:
            actual_text = self.page.locator(locator).text_content(timeout=timeout * 1000)
            logger.error(f"【UI】Assertion failed: Expected '{expected_text}', got '{actual_text}'")
            raise AssertionError(f"Text mismatch: Expected '{expected_text}', got '{actual_text}'")

    def assert_text_contains(self, locator: str, expected_text: str, timeout: int = 30):
        try:
            expect(self.page.locator(locator)).to_contain_text(expected_text, timeout=timeout * 1000)
            logger.info(f"【UI】Assertion passed: Text contains '{expected_text}'")
        except Exception:
            actual_text = self.page.locator(locator).text_content(timeout=timeout * 1000)
            logger.error(f"【UI】Assertion failed: Text '{actual_text}' does not contain '{expected_text}'")
            raise AssertionError(f"Text does not contain: Expected '{expected_text}' in '{actual_text}'")

    def assert_title_equals(self, expected_title: str):
        actual_title = self.page.title()
        if actual_title == expected_title:
            logger.info(f"【UI】Assertion passed: Title equals '{expected_title}'")
        else:
            logger.error(f"【UI】Assertion failed: Expected title '{expected_title}', got '{actual_title}'")
            raise AssertionError(f"Title mismatch: Expected '{expected_title}', got '{actual_title}'")

    def assert_title_contains(self, expected_text: str):
        actual_title = self.page.title()
        if expected_text in actual_title:
            logger.info(f"【UI】Assertion passed: Title contains '{expected_text}'")
        else:
            logger.error(f"【UI】Assertion failed: Title '{actual_title}' does not contain '{expected_text}'")
            raise AssertionError(f"Title does not contain: Expected '{expected_text}' in '{actual_title}'")

    def assert_url_equals(self, expected_url: str):
        actual_url = self.page.url
        if actual_url == expected_url:
            logger.info(f"【UI】Assertion passed: URL equals '{expected_url}'")
        else:
            logger.error(f"【UI】Assertion failed: Expected URL '{expected_url}', got '{actual_url}'")
            raise AssertionError(f"URL mismatch: Expected '{expected_url}', got '{actual_url}'")

    def assert_url_contains(self, expected_text: str):
        actual_url = self.page.url
        if expected_text in actual_url:
            logger.info(f"【UI】Assertion passed: URL contains '{expected_text}'")
        else:
            logger.error(f"【UI】Assertion failed: URL '{actual_url}' does not contain '{expected_text}'")
            raise AssertionError(f"URL does not contain: Expected '{expected_text}' in '{actual_url}'")

    def assert_element_enabled(self, locator: str, timeout: int = 30):
        try:
            expect(self.page.locator(locator)).to_be_enabled(timeout=timeout * 1000)
            logger.info(f"【UI】Assertion passed: Element enabled - {locator}")
        except Exception:
            logger.error(f"【UI】Assertion failed: Element disabled - {locator}")
            raise AssertionError(f"Element is disabled: {locator}")

    def assert_element_disabled(self, locator: str, timeout: int = 30):
        try:
            expect(self.page.locator(locator)).to_be_disabled(timeout=timeout * 1000)
            logger.info(f"【UI】Assertion passed: Element disabled - {locator}")
        except Exception:
            logger.error(f"【UI】Assertion failed: Element enabled - {locator}")
            raise AssertionError(f"Element is enabled: {locator}")

    def assert_element_selected(self, locator: str, timeout: int = 30):
        try:
            expect(self.page.locator(locator)).to_be_checked(timeout=timeout * 1000)
            logger.info(f"【UI】Assertion passed: Element selected - {locator}")
        except Exception:
            logger.error(f"【UI】Assertion failed: Element not selected - {locator}")
            raise AssertionError(f"Element is not selected: {locator}")

    def assert_element_count(self, locator: str, expected_count: int, timeout: int = 30):
        try:
            expect(self.page.locator(locator)).to_have_count(expected_count, timeout=timeout * 1000)
            logger.info(f"【UI】Assertion passed: Element count is {expected_count}")
        except Exception:
            actual_count = self.page.locator(locator).count()
            logger.error(f"【UI】Assertion failed: Expected {expected_count} elements, got {actual_count}")
            raise AssertionError(f"Element count mismatch: Expected {expected_count}, got {actual_count}")

    def assert_attribute_value(self, locator: str, attribute: str, expected_value: str, timeout: int = 30):
        try:
            expect(self.page.locator(locator)).to_have_attribute(attribute, expected_value, timeout=timeout * 1000)
            logger.info(f"【UI】Assertion passed: Attribute '{attribute}' equals '{expected_value}'")
        except Exception:
            actual_value = self.page.locator(locator).get_attribute(attribute)
            logger.error(f"【UI】Assertion failed: Attribute '{attribute}' expected '{expected_value}', got '{actual_value}'")
            raise AssertionError(f"Attribute mismatch: '{attribute}' expected '{expected_value}', got '{actual_value}'")