import os
import yaml
from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
from typing import Optional

from core.log_handler import logger
from core.env_handler import env_handler


class BrowserDriver:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.browser_config = self._load_browser_config()

    def _load_browser_config(self):
        return env_handler.get_browser_config()

    def init_driver(self):
        browser_type = self.browser_config.get("type", "chromium")
        headless = self.browser_config.get("headless", False)
        window_size = self.browser_config.get("window_size", "1920x1080")
        viewport_width, viewport_height = map(int, window_size.split("x"))

        logger.info(f"【UI】Initializing browser: {browser_type}, headless: {headless}")

        self.playwright = sync_playwright().start()

        if browser_type.lower() == "chromium":
            self.browser = self.playwright.chromium.launch(
                headless=headless,
                args=self.browser_config.get("options", {}).get("arguments", [])
            )
        elif browser_type.lower() == "firefox":
            self.browser = self.playwright.firefox.launch(
                headless=headless,
                args=self.browser_config.get("options", {}).get("arguments", [])
            )
        elif browser_type.lower() == "webkit":
            self.browser = self.playwright.webkit.launch(
                headless=headless,
                args=self.browser_config.get("options", {}).get("arguments", [])
            )
        else:
            raise ValueError(f"Unsupported browser type: {browser_type}")

        self.context = self.browser.new_context(
            viewport={"width": viewport_width, "height": viewport_height},
            downloads_path=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "downloads")
        )
        self.page = self.context.new_page()
        self.page.set_default_timeout(self.browser_config.get("timeout", {}).get("explicit_wait", 30) * 1000)

        logger.info("【UI】Browser initialized successfully")

    def get(self, url: str):
        logger.info(f"【UI】Navigating to: {url}")
        self.page.goto(url, wait_until="networkidle")

    def quit(self):
        if self.page:
            try:
                self.page.close()
            except Exception as e:
                logger.error(f"【UI】Failed to close page: {e}")
            self.page = None

        if self.context:
            try:
                self.context.close()
            except Exception as e:
                logger.error(f"【UI】Failed to close context: {e}")
            self.context = None

        if self.browser:
            logger.info("【UI】Closing browser")
            try:
                self.browser.close()
            except Exception as e:
                logger.error(f"【UI】Failed to close browser: {e}")
            self.browser = None

        if self.playwright:
            try:
                self.playwright.stop()
            except Exception as e:
                logger.error(f"【UI】Failed to stop playwright: {e}")
            self.playwright = None

    def screenshot(self, filename: str) -> str:
        screenshot_dir = self.browser_config.get("screenshot", {}).get("save_path", "reports/screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        filepath = os.path.join(screenshot_dir, filename)
        self.page.screenshot(path=filepath, full_page=True)
        logger.info(f"【UI】Screenshot saved to: {filepath}")
        return filepath

    def get_page(self) -> Page:
        return self.page

    def new_page(self) -> Page:
        if self.context:
            self.page = self.context.new_page()
            return self.page
        return None


browser_driver = BrowserDriver()