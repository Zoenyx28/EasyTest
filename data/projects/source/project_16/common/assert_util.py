import json
from jsonpath_ng import parse
from jsonschema import validate
from typing import Any, Optional, Dict, List
from requests import Response

from common.base_log import logger


class Assertion:
    """统一断言类，包含基础断言和响应断言"""

    # ======================== 基础断言 ========================

    @staticmethod
    def assert_equal(actual: Any, expected: Any, msg: str = ""):
        assert actual == expected, f"{msg} | Expected: {expected}, Actual: {actual}"
        logger.info(f"Assert equal passed: {actual} == {expected}")

    @staticmethod
    def assert_not_equal(actual: Any, expected: Any, msg: str = ""):
        assert actual != expected, f"{msg} | Expected not equal to: {expected}, Actual: {actual}"
        logger.info(f"Assert not equal passed: {actual} != {expected}")

    @staticmethod
    def assert_true(condition: bool, msg: str = ""):
        assert condition, f"{msg} | Expected True, Actual False"
        logger.info(f"Assert true passed")

    @staticmethod
    def assert_false(condition: bool, msg: str = ""):
        assert not condition, f"{msg} | Expected False, Actual True"
        logger.info(f"Assert false passed")

    @staticmethod
    def assert_contains(actual: str, expected: str, msg: str = ""):
        assert expected in actual, f"{msg} | Expected '{expected}' in '{actual}'"
        logger.info(f"Assert contains passed")

    @staticmethod
    def assert_not_contains(actual: str, expected: str, msg: str = ""):
        assert expected not in actual, f"{msg} | Expected not '{expected}' in '{actual}'"
        logger.info(f"Assert not contains passed")

    @staticmethod
    def assert_length(actual: Any, expected_length: int, msg: str = ""):
        assert len(actual) == expected_length, f"{msg} | Expected length: {expected_length}, Actual length: {len(actual)}"
        logger.info(f"Assert length passed: {len(actual)} == {expected_length}")

    @staticmethod
    def assert_greater_than(actual: Any, expected: Any, msg: str = ""):
        assert actual > expected, f"{msg} | Expected greater than: {expected}, Actual: {actual}"
        logger.info(f"Assert greater than passed")

    @staticmethod
    def assert_less_than(actual: Any, expected: Any, msg: str = ""):
        assert actual < expected, f"{msg} | Expected less than: {expected}, Actual: {actual}"
        logger.info(f"Assert less than passed")

    @staticmethod
    def assert_is_not_none(actual: Any, msg: str = ""):
        assert actual is not None, f"{msg} | Expected not None, Actual: {actual}"
        logger.info(f"Assert is not None passed")

    @staticmethod
    def assert_is_none(actual: Any, msg: str = ""):
        assert actual is None, f"{msg} | Expected None, Actual: {actual}"
        logger.info(f"Assert is None passed")

    # ======================== HTTP响应断言 ========================

    @staticmethod
    def assert_status_code(response: Response, expected_status: int):
        actual_status = response.status_code
        assert actual_status == expected_status, f"Expected status code: {expected_status}, Actual: {actual_status}"
        logger.info(f"Assert status code passed: {actual_status} == {expected_status}")

    # ======================== JSONPath断言 ========================

    @staticmethod
    def extract_by_jsonpath(response: Response, jsonpath_expr: str) -> Optional[Any]:
        try:
            data = response.json()
            expr = parse(jsonpath_expr)
            result = expr.find(data)
            return result[0].value if result else None
        except Exception as e:
            logger.error(f"Extract by jsonpath failed: {e}")
            return None

    @staticmethod
    def assert_jsonpath_value(response: Response, jsonpath_expr: str, expected_value: Any, msg: str = ""):
        actual_value = Assertion.extract_by_jsonpath(response, jsonpath_expr)
        Assertion.assert_equal(actual_value, expected_value, msg)

    # ======================== Schema校验 ========================

    @staticmethod
    def assert_json_schema(response: Response, schema: Dict[str, Any], msg: str = ""):
        try:
            data = response.json()
            validate(instance=data, schema=schema)
            logger.info("Assert json schema passed")
        except Exception as e:
            raise AssertionError(f"{msg} | Json schema validation failed: {e}")

    # ======================== 响应断言（便捷方法）========================

    @staticmethod
    def assert_response(response, expect: dict):
        """
        根据期望数据字典对API响应进行完整断言

        :param response: requests.Response 对象
        :param expect: 期望值字典，支持以下特殊值:
            - status_code: HTTP状态码
            - code: 响应业务码
            - msg: 响应消息
            - data: 数据字段（支持嵌套断言）
                - 字段值为 "not_none": 验证字段不为空
                - 字段值为 null/None: 验证字段为空
                - 其他值: 精确匹配
        """
        if "status_code" in expect:
            Assertion.assert_status_code(response, expect["status_code"])

        response_json = response.json()

        for key, expected_value in expect.items():
            if key == "status_code":
                continue
            if key == "data":
                Assertion._assert_data_field(response_json.get("data"), expected_value)
            else:
                actual_value = response_json.get(key)
                Assertion.assert_equal(actual_value, expected_value, f"{key} 字段验证失败")

    @staticmethod
    def _assert_data_field(actual_data, expected_data):
        """递归断言data字段"""
        if expected_data is None:
            Assertion.assert_is_none(actual_data, "data 字段应为null")
            return

        if actual_data is None:
            Assertion.assert_is_not_none(actual_data, "data 字段不能为空")
            return

        for key, expected_value in expected_data.items():
            actual_value = actual_data.get(key)
            if expected_value == "not_none":
                Assertion.assert_is_not_none(actual_value, f"data.{key} 字段不能为空")
            elif expected_value is None:
                Assertion.assert_is_none(actual_value, f"data.{key} 字段应为null")
            else:
                Assertion.assert_equal(actual_value, expected_value, f"data.{key} 字段验证失败")

    # ======================== 分页断言 ========================

    @staticmethod
    def assert_pagination(response: Response, expected_page: int = None, expected_page_size: int = None, msg: str = ""):
        """
        验证分页结构
        :param response: requests.Response 对象
        :param expected_page: 期望页码
        :param expected_page_size: 期望每页数量
        :param msg: 断言失败时的提示信息
        """
        response_json = response.json()
        data = response_json.get("data")
        Assertion.assert_is_not_none(data, f"{msg} | 分页数据不能为空")

        page = data.get("page")
        page_size = data.get("page_size")
        total = data.get("total")

        Assertion.assert_is_not_none(page, f"{msg} | 页码page不能为空")
        Assertion.assert_is_not_none(page_size, f"{msg} | 每页数量page_size不能为空")
        Assertion.assert_is_not_none(total, f"{msg} | 总数total不能为空")

        if expected_page is not None:
            Assertion.assert_equal(page, expected_page, f"{msg} | 页码不匹配")
        if expected_page_size is not None:
            Assertion.assert_equal(page_size, expected_page_size, f"{msg} | 每页数量不匹配")

        Assertion.assert_true(total >= 0, f"{msg} | 总数不能为负数")
        logger.info(f"Assert pagination passed: page={page}, page_size={page_size}, total={total}")

    @staticmethod
    def assert_list_length(response: Response, expected_length: int, msg: str = ""):
        """
        验证列表数据长度
        :param response: requests.Response 对象
        :param expected_length: 期望长度
        :param msg: 断言失败时的提示信息
        """
        response_json = response.json()
        data = response_json.get("data")
        items = data.get("items") if data else None
        if items is None:
            items = data.get("list") if data else None
        if items is None:
            items = response_json.get("items")

        Assertion.assert_is_not_none(items, f"{msg} | 列表数据不能为空")
        Assertion.assert_length(items, expected_length, msg)

    # ======================== 响应时间断言 ========================

    @staticmethod
    def assert_response_time(response: Response, max_seconds: float = 30.0, msg: str = ""):
        """
        验证响应时间在允许范围内
        :param response: requests.Response 对象
        :param max_seconds: 最大允许时间（秒），默认30秒
        :param msg: 断言失败时的提示信息
        """
        elapsed = response.elapsed.total_seconds()
        Assertion.assert_less_than(elapsed, max_seconds, f"{msg} | 响应时间过长")
        logger.info(f"Assert response time passed: {elapsed:.2f}s < {max_seconds}s")

    def assert_response_success(self,
        response: Response,
        expected_code:int | None,
        expected_msg:str | None,
    ):
        Assertion.assert_equal(response.json().get('code'), expected_code)
        Assertion.assert_equal(response.json().get('msg'), expected_msg)

# 全局单例
assertion = Assertion()
