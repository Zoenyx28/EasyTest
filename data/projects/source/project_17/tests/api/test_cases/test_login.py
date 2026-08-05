import pytest

from api.apis.auth_api import auth_api
from common.assert_util import assertion
from common.http_client import http_client
from common.base_log import logger
from common.file_handler import load_testcase


class TestLogin:

    @pytest.fixture()
    def case_data(self):
        """懒加载登录测试数据"""
        return load_testcase("login.yaml")

    @pytest.mark.login
    @pytest.mark.api
    @pytest.mark.smoke
    def test_login_success(self, case_data):
        """系统管理员登录成功（密码base64编码）"""
        case = case_data["test_login_success"]
        logger.info(f"========== {case['description']} ==========")

        response = auth_api.login(
            username=case["request"]["username"],
            password=case["request"]["password"],
            encode_password=case["request"]["encode_password"]
        )

        assertion.assert_response(response, case["expect"])

        data = response.json().get("data")
        if data and data.get("access_token"):
            http_client.set_token(data["access_token"])
            logger.info("登录成功，token已设置")

    @pytest.mark.login
    @pytest.mark.api
    @pytest.mark.parametrize("case_key", [
        "test_login_password_not_base64",
        "test_login_wrong_password",
        "test_login_empty_username",
        "test_login_empty_password",
    ])
    def test_login_failure(self, case_key, case_data):
        """登录失败场景（数据驱动）"""
        case = case_data[case_key]
        logger.info(f"========== {case['description']} ==========")

        response = auth_api.login(
            username=case["request"]["username"],
            password=case["request"]["password"],
            encode_password=case["request"]["encode_password"]
        )

        assertion.assert_response(response, case["expect"])
