import pytest

from core.log_handler import logger


@pytest.fixture(scope="session")
def page():
    """UI 测试浏览器页面实例"""
    from core.ui_core.browser_driver import browser_driver

    logger.info("【UI】初始化浏览器...")
    browser_driver.init_driver()
    yield browser_driver.get_page()

    logger.info("【UI】关闭浏览器...")
    browser_driver.quit()


def pytest_runtest_makereport(item, call):
    """UI 用例失败时自动截图"""
    if call.when == "call" and call.excinfo is not None and "page" in item.fixturenames:
        try:
            from core.ui_core.browser_driver import browser_driver

            page = item.funcargs.get("page")
            if page is not None:
                browser_driver.screenshot(f"{item.name}.png")
        except Exception as e:
            logger.error(f"【UI】失败截图失败: {e}")
