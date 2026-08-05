from playwright.sync_api import Page, Locator, expect
from typing import Optional, List

from core.log_handler import logger


class PageAction:
    def __init__(self, page: Page):
        self.page = page

    def find_element(self, locator: str, timeout: int = 30) -> Locator:
        logger.info(f"【UI】Finding element: {locator}")
        element = self.page.locator(locator)
        element.wait_for(state="visible", timeout=timeout * 1000)
        return element

    def find_elements(self, locator: str, timeout: int = 30) -> List[Locator]:
        logger.info(f"【UI】Finding elements: {locator}")
        elements = self.page.locator(locator)
        elements.wait_for(state="visible", timeout=timeout * 1000)
        count = elements.count()
        return [elements.nth(i) for i in range(count)]

    def click(self, locator: str, timeout: int = 30):
        element = self.find_element(locator, timeout)
        logger.info(f"【UI】Clicking element: {locator}")
        element.click()

    def input_text(self, locator: str, text: str, timeout: int = 30):
        element = self.find_element(locator, timeout)
        logger.info(f"【UI】Inputting text '{text}' to: {locator}")
        element.fill(text)

    def get_text(self, locator: str, timeout: int = 30) -> str:
        element = self.find_element(locator, timeout)
        text = element.text_content()
        logger.info(f"【UI】Got text '{text}' from: {locator}")
        return text

    def get_attribute(self, locator: str, attribute: str, timeout: int = 30) -> str:
        element = self.find_element(locator, timeout)
        value = element.get_attribute(attribute)
        logger.info(f"【UI】Got attribute '{attribute}'='{value}' from: {locator}")
        return value

    def wait_for_text(self, locator: str, text: str, timeout: int = 30):
        logger.info(f"【UI】Waiting for text '{text}' in element: {locator}")
        expect(self.page.locator(locator)).to_have_text(text, timeout=timeout * 1000)

    def wait_for_element_visible(self, locator: str, timeout: int = 30):
        logger.info(f"【UI】Waiting for element visible: {locator}")
        expect(self.page.locator(locator)).to_be_visible(timeout=timeout * 1000)

    def wait_for_element_invisible(self, locator: str, timeout: int = 30):
        logger.info(f"【UI】Waiting for element invisible: {locator}")
        expect(self.page.locator(locator)).to_be_hidden(timeout=timeout * 1000)

    def switch_to_frame(self, locator: Optional[str] = None, index: int = 0):
        if locator:
            logger.info(f"【UI】Switching to frame: {locator}")
            self.page.frame_locator(locator)
        else:
            logger.info(f"【UI】Switching to frame by index: {index}")
            self.page.frames[index]

    def switch_to_default_content(self):
        logger.info("【UI】Switching to default content")
        self.page.main_frame

    def handle_alert(self, accept: bool = True, timeout: int = 10) -> str:
        logger.info(f"【UI】Handling alert, accept: {accept}")
        alert_text = None
        try:
            with self.page.expect_dialog(timeout=timeout * 1000) as dialog_info:
                pass
            dialog = dialog_info.value
            alert_text = dialog.message
            logger.info(f"【UI】Alert text: {alert_text}")
            if accept:
                dialog.accept()
            else:
                dialog.dismiss()
        except Exception:
            logger.warning("【UI】No alert found")
        return alert_text

    def upload_file(self, locator: str, file_path: str, timeout: int = 30):
        element = self.find_element(locator, timeout)
        logger.info(f"【UI】Uploading file: {file_path}")
        element.set_input_files(file_path)

    def scroll_to_element(self, locator: str, timeout: int = 30):
        element = self.find_element(locator, timeout)
        logger.info(f"【UI】Scrolling to element: {locator}")
        element.scroll_into_view_if_needed()

    def execute_script(self, script: str, *args):
        logger.info(f"【UI】Executing script: {script[:50]}...")
        return self.page.evaluate(script, *args)

    def refresh(self):
        logger.info("【UI】Refreshing page")
        self.page.reload()

    def go_back(self):
        logger.info("【UI】Going back")
        self.page.go_back()

    def go_forward(self):
        logger.info("【UI】Going forward")
        self.page.go_forward()

    def select_dropdown_by_text(self, locator: str, text: str, timeout: int = 30):
        element = self.find_element(locator, timeout)
        logger.info(f"【UI】Selecting dropdown option: {text}")
        element.select_option(label=text)

    def select_dropdown_by_value(self, locator: str, value: str, timeout: int = 30):
        element = self.find_element(locator, timeout)
        logger.info(f"【UI】Selecting dropdown value: {value}")
        element.select_option(value=value)

    def hover(self, locator: str, timeout: int = 30):
        element = self.find_element(locator, timeout)
        logger.info(f"【UI】Hovering over element: {locator}")
        element.hover()

    def double_click(self, locator: str, timeout: int = 30):
        element = self.find_element(locator, timeout)
        logger.info(f"【UI】Double clicking element: {locator}")
        element.dblclick()

    def right_click(self, locator: str, timeout: int = 30):
        element = self.find_element(locator, timeout)
        logger.info(f"【UI】Right clicking element: {locator}")
        element.click(button="right")

    def press_key(self, key: str):
        logger.info(f"【UI】Pressing key: {key}")
        self.page.keyboard.press(key)