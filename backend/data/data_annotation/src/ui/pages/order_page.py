from core.ui_core.page_action import PageAction
from core.ui_core.ui_assert import UiAssert
from core.log_handler import logger


class OrderPage:
    def __init__(self, page):
        self.page = page
        self.page_action = PageAction(page)
        self.ui_assert = UiAssert(page)
        self.locators = {
            "order_list_table": "#order-list-table",
            "create_order_button": "button:has-text('创建订单')",
            "product_select": "#product-select",
            "quantity_input": "#quantity",
            "address_select": "#address-select",
            "submit_button": "button:has-text('提交订单')",
            "success_message": ".success-message",
            "order_number": ".order-number",
            "order_row": ".order-row",
            "order_status": ".order-status",
            "cancel_button": "button:has-text('取消订单')",
            "confirm_cancel_button": "button:has-text('确定取消')",
            "order_id_input": "#order-id-input",
            "search_button": "button:has-text('查询')"
        }

    def open(self, url: str):
        logger.info("【UI】Opening order page")
        self.page.goto(url, wait_until="networkidle")

    def click_create_order(self):
        logger.info("【UI】Clicking create order button")
        self.page_action.click(self.locators["create_order_button"])

    def select_product(self, product_name: str):
        logger.info(f"【UI】Selecting product: {product_name}")
        self.page_action.select_dropdown_by_text(self.locators["product_select"], product_name)

    def enter_quantity(self, quantity: int):
        logger.info(f"【UI】Entering quantity: {quantity}")
        self.page_action.input_text(self.locators["quantity_input"], str(quantity))

    def select_address(self, address_name: str):
        logger.info(f"【UI】Selecting address: {address_name}")
        self.page_action.select_dropdown_by_text(self.locators["address_select"], address_name)

    def click_submit(self):
        logger.info("【UI】Clicking submit button")
        self.page_action.click(self.locators["submit_button"])

    def create_order(self, product_name: str, quantity: int, address_name: str):
        logger.info(f"【UI】Creating order for product: {product_name}")
        self.click_create_order()
        self.select_product(product_name)
        self.enter_quantity(quantity)
        self.select_address(address_name)
        self.click_submit()

    def assert_order_created(self, expected_message: str = "订单创建成功"):
        logger.info("【UI】Asserting order created successfully")
        self.ui_assert.assert_element_visible(self.locators["success_message"])
        self.ui_assert.assert_text_contains(self.locators["success_message"], expected_message)

    def get_order_number(self) -> str:
        return self.page_action.get_text(self.locators["order_number"])

    def search_order(self, order_id: str):
        logger.info(f"【UI】Searching order: {order_id}")
        self.page_action.input_text(self.locators["order_id_input"], order_id)
        self.page_action.click(self.locators["search_button"])

    def get_order_status(self) -> str:
        return self.page_action.get_text(self.locators["order_status"])

    def assert_order_status(self, expected_status: str):
        logger.info(f"【UI】Asserting order status: {expected_status}")
        actual_status = self.get_order_status()
        self.ui_assert.assert_text_equals(self.locators["order_status"], expected_status)

    def cancel_order(self, order_id: str):
        logger.info(f"【UI】Cancelling order: {order_id}")
        self.search_order(order_id)
        self.page_action.click(self.locators["cancel_button"])
        self.page_action.click(self.locators["confirm_cancel_button"])

    def assert_order_cancelled(self):
        logger.info("【UI】Asserting order cancelled")
        self.ui_assert.assert_text_contains(self.locators["order_status"], "已取消")