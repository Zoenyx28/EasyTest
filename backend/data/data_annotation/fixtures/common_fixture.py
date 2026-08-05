"""会话级公共 Fixtures

提供：
- setup_session: 会话级自动 fixture，用于初始化 http_client 和清理数据
- admin_token / admin_sys2_token: 预配置账号的 session 级别 token
- as_admin / as_admin_sys2: 快速切换鉴权的 function 级别 fixture
- default_auth: 每个用例自动以系统管理员身份执行
- pytest_configure: 注册自定义 markers
- pytest_collection_modifyitems: 处理中文 nodeid
- pytest_runtest_makereport: 测试失败日志
"""
import pytest
import os
import sys

from common.http_client import http_client
from config.settings import env_handler
from common.base_log import logger
from api.apis.auth_api import _login, login_as, clear_token_cache
from common.db_util import pg_db
from utils.tear_down import cleanup_test_data


# ======================== 会话管理 ========================

@pytest.fixture(scope="session", autouse=True)
def setup_session():
    logger.info("========== 测试会话开始 ==========")

    # 会话开始前清理上一轮可能残留的测试数据（表结构不匹配时跳过，不阻塞用例）
    try:
        cleanup_test_data()
    except Exception as e:
        logger.warning(f"测试数据清理失败（跳过）: {e}")

    base_url = env_handler.get_base_url()
    timeout = env_handler.get_timeout()
    headers = env_handler.get_request_headers()

    http_client.set_base_url(base_url)
    http_client.set_timeout(timeout)
    http_client.set_headers(headers)

    logger.info(f"环境: {env_handler.current_env}")
    logger.info(f"基础URL: {base_url}")
    logger.info(f"超时时间: {timeout}s")

    yield

    clear_token_cache()
    http_client.close()

    # 测试会话结束后统一清理本轮产生的测试数据（表结构不匹配时跳过）
    try:
        cleanup_test_data()
    except Exception as e:
        logger.warning(f"测试数据清理失败（跳过）: {e}")
    logger.info("========== 测试会话结束 ==========")




# ======================== 鉴权Fixture ========================

@pytest.fixture(scope="session")
def admin_token():
    """系统管理员(admin)鉴权"""
    return _login("admin")


@pytest.fixture(scope="session")
def admin_sys2_token():
    """第二个系统管理员(admin_sys2)鉴权"""
    return _login("admin_sys2")


def _make_auth_fixture(token_fixture_name: str):
    """
    工厂函数：生成鉴权fixture
    :param token_fixture_name: 依赖的session级token fixture名
    """
    @pytest.fixture()
    def auth_fixture(request):
        token_info = request.getfixturevalue(token_fixture_name)
        http_client.set_token(token_info["token"])
        return token_info
    return auth_fixture


as_admin = _make_auth_fixture("admin_token")
as_admin.__doc__ = "切换为系统管理员身份"

as_admin_sys2 = _make_auth_fixture("admin_sys2_token")
as_admin_sys2.__doc__ = "切换为第二个系统管理员身份(admin_sys2)"


# ======================== 日志与报告 ========================

@pytest.fixture(scope="function", autouse=True)
def default_auth():
    """
    默认鉴权：每个用例自动以系统管理员身份执行。
    其他角色（PM/SPADM/TADM/MEMBER）需在用例中动态创建后通过 login_with 切换。
    """
    login_as("admin")


@pytest.fixture(scope="module", autouse=True)
def cleanup_module():
    """
    模块级清理：每个测试模块结束后执行一次数据清理，
    避免中间失败导致数据残留到下一轮用例。
    会话级 setup_session 仍会在首尾做兜底清理。
    """
    yield
    try:
        cleanup_test_data()
    except Exception as e:
        logger.warning(f"模块级数据清理失败（跳过）: {e}")


@pytest.fixture(scope="function", autouse=True)
def setup_function(request):
    logger.info(f"\n---------- 开始执行测试: {request.function.__name__} ----------")
    yield
    logger.info(f"---------- 测试执行结束: {request.function.__name__} ----------")


def pytest_configure(config):
    config.addinivalue_line("markers", "login: 登录相关测试")
    config.addinivalue_line("markers", "system: 系统管理相关测试")
    config.addinivalue_line("markers", "task: 任务中心相关测试")
    config.addinivalue_line("markers", "dataset: 数据集相关测试")

    config.addinivalue_line("markers", "api: 接口测试")
    config.addinivalue_line("markers", "ui: UI测试")
    config.addinivalue_line("markers", "mix: 混合测试")
    config.addinivalue_line("markers", "smoke: 冒烟测试")


def pytest_collection_modifyitems(session, config, items):
    for item in items:
        item.name = item.name.encode("utf-8").decode("unicode_escape")
        item._nodeid = item.nodeid.encode("utf-8").decode("unicode_escape")


def pytest_runtest_makereport(item, call):
    if call.when == "call":
        if call.excinfo is not None:
            logger.error(f"测试失败: {item.name}")
            logger.error(f"失败原因: {call.excinfo.value}")
        else:
            logger.info(f"测试通过: {item.name}")
