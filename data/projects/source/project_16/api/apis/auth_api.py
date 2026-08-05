import base64

from api.apis.data_api import api_client
from common.base_log import logger
from config.settings import env_handler
from common.http_client import http_client

from config.settings import DEFAULT_PASSWORD


# ======================== 账号配置 ========================

ACCOUNTS = {
    "admin": {
        "username_env": "ADMIN_USERNAME",
        "password_env": "ADMIN_PASSWORD",
        "role": "系统管理员",
    },
    "admin_sys2": {
        "username_env": "ADMIN_SYS2_USERNAME",
        "password_env": "ADMIN_SYS2_PASSWORD",
        "role": "系统管理员",
    },
}

# token缓存，避免同一账号重复登录
_token_cache: dict[str, dict] = {}


# ======================== 认证业务层 ========================

class AuthApi:
    """认证接口业务层"""

    def login(self, username: str, password: str, encode_password: bool = True):
        """
        用户登录
        :param username: 用户名
        :param password: 密码
        :param encode_password: 是否对密码进行base64编码
        """
        if encode_password:
            password = base64.b64encode(password.encode('utf-8')).decode('utf-8')
            logger.info("密码已Base64编码")

        logger.info(f"登录请求: username={username}")
        response = api_client.post_login(
            username=username, password=password
        )
        return response

    def get_current_user(self):
        """获取当前登录用户信息"""
        logger.info("获取当前用户信息")
        return api_client.get_auth_me()


auth_api = AuthApi()


# ======================== 鉴权工具方法 ========================

def _do_login(username: str, password: str) -> dict:
    """
    执行登录请求（内部方法），返回 {"token": "xxx", "username": "xxx"}
    密码由 auth_api.login 统一处理 Base64 编码
    """
    logger.info(f"登录请求: {username}")

    response = auth_api.login(username=username, password=password, encode_password=True)

    resp_json = response.json()
    if resp_json.get("code") != 0:
        raise AssertionError(f"登录失败({username}): {resp_json.get('msg')}")

    token = resp_json.get("data", {}).get("access_token")
    if not token:
        raise AssertionError(f"登录响应中未找到access_token({username})")

    logger.info(f"登录成功: {username}")
    return {"token": token, "username": username}


def _login(account_key: str) -> dict:
    """
    使用预配置账号登录（内部方法）
    :param account_key: 账号标识（admin/pm/spadm/tadm/user）
    :return: {"token": "xxx", "username": "xxx", "role": "xxx", "account_key": "xxx"}
    """
    if account_key in _token_cache:
        logger.info(f"使用缓存的token: {account_key}")
        return _token_cache[account_key]

    account = ACCOUNTS.get(account_key)
    if not account:
        raise ValueError(f"未知账号标识: {account_key}，可选值: {list(ACCOUNTS.keys())}")

    username = env_handler.get_env_variable(account["username_env"])
    password = env_handler.get_env_variable(account["password_env"])

    if not username or not password:
        raise ValueError(f"账号 {account_key} 的用户名或密码未配置，请检查 .env 文件")

    login_result = _do_login(username, password)
    result = {
        "token": login_result["token"],
        "username": login_result["username"],
        "role": account["role"],
        "account_key": account_key,
    }
    _token_cache[account_key] = result
    return result


def login_as(account_key: str) -> dict:
    """
    使用环境配置中的系统管理员账号登录并切换 http_client 的 token
    仅用于需要创建组织等必须系统管理员权限的场景

    :param account_key: 账号标识，当前仅支持 "admin"
    :return: {"token": "xxx", "username": "xxx", "role": "xxx", "account_key": "xxx"}

    使用示例:
        from api.apis.auth_api import login_as
        login_as("admin")   # 切换为系统管理员身份
    """
    token_info = _login(account_key)
    http_client.set_token(token_info["token"])
    logger.info(f"切换鉴权身份: {token_info['role']}({token_info['username']})")
    return token_info


def login_with(username: str, password: str=DEFAULT_PASSWORD) -> dict:
    """
    直接指定账号密码进行登录并切换 http_client 的 token
    适用于动态创建的用户（如测试中新建的PM、供应商管理员等）

    :param username: 用户名
    :param password: 密码（明文，自动Base64编码），默认值为 DEFAULT_PASSWORD
    :return: {"token": "xxx", "username": "xxx"}

    使用示例:
        from api.apis.auth_api import login_with
        login_with("new_pm_user", "admin123")  # 切换为新创建的PM用户
    """
    token_info = _do_login(username, password)
    http_client.set_token(token_info["token"])
    logger.info(f"切换鉴权身份: {username}")
    return token_info


def clear_token_cache():
    """清空token缓存"""
    _token_cache.clear()
