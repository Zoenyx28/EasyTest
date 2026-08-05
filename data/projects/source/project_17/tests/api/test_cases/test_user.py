#!/usr/bin/env python3

import pytest

from api.apis.user_api import user_api
from api.apis.org_api import org_api
from api.apis.team_api import team_api
from api.apis.supplier_api import supplier_api
from utils.generate_data import faker_data
from common.db_util import pg_db
from common.assert_util import assertion
from common.base_log import logger
from api.apis.auth_api import login_as, login_with, auth_api
from config.settings import TEST_ORG_DESCRIPTION
from config.settings import UserType, USER_TYPE_ROLE_MAP, USER_TYPE_NAME_MAP
from fixtures.api_fixture import (
    _find_role_id,
    _find_role_id_by_user_type,
    _do_create_user,
    _assert_user_match,
)
from config.settings import DEFAULT_PASSWORD


# 模块级辅助方法

def _get_current_user_info() -> dict:
    """获取当前登录用户基本信息（id, username, org_id）"""
    resp = auth_api.get_current_user()
    assertion.assert_status_code(resp, 200)
    resp_json = resp.json()
    assertion.assert_equal(resp_json.get("code"), 0, "获取当前用户信息失败")
    data = resp_json.get("data", {})
    organization = data.get("organization") or {}
    role = data.get("role") or {}
    return {
        "user_id": data.get("id"),
        "username": data.get("username"),
        "org_id": organization.get("id"),
        "role_id": role.get("id")
    }


def _do_update_user(user_id: str, **kwargs) -> dict:
    """执行编辑用户请求，返回响应JSON；HTTP非200时返回包含status_code的异常结构"""
    resp = user_api.update_user(user_id=user_id, **kwargs)
    if resp.status_code != 200:
        return {"code": resp.status_code, "msg": resp.text or "http error", "data": None}
    return resp.json()


def _get_user_edit_context(user_id: str) -> dict:
    """获取用户编辑所需上下文（org_id, role_id, role_code, team_ids, supplier_id, username, display_name），默认以当前登录身份查询详情"""
    resp = user_api.get_user_detail_by_id(user_id)
    assertion.assert_status_code(resp, 200)
    data = resp.json().get("data") or {}
    org = data.get("organization") or {}
    role = data.get("role") or {}
    supplier = data.get("supplier") or {}
    teams = data.get("teams") or []
    return {
        "user_id": user_id,
        "username": data.get("username"),
        "display_name": data.get("display_name"),
        "org_id": org.get("id"),
        "role_id": role.get("id"),
        "role_code": role.get("code"),
        "team_ids": [t.get("id") for t in teams if t.get("id")],
        "supplier_id": supplier.get("id")
    }


def _assert_update_success(resp_json: dict, expected_username: str = None, msg_prefix: str = ""):
    """校验编辑用户成功响应"""
    assertion.assert_equal(resp_json.get("code"), 0, f"{msg_prefix}编辑用户应成功")
    data = resp_json.get("data")
    assertion.assert_is_not_none(data, f"{msg_prefix}响应data不能为空")
    if expected_username:
        assertion.assert_equal(data.get("username"), expected_username, f"{msg_prefix}用户名不匹配")


def _assert_update_fail(resp_json: dict, msg_prefix: str = ""):
    """校验编辑用户失败响应"""
    assertion.assert_true(resp_json.get("code") != 0, f"{msg_prefix}编辑用户应失败")


# ======================== 模块级Fixture ========================

@pytest.fixture()
def shared_supplier(shared_org, pm_user):
    """以项目管理员身份创建供应商（返回供应商ID字符串）"""
    login_with(pm_user["username"], DEFAULT_PASSWORD)
    resp = supplier_api.create_supplier(
        name=faker_data.random_name(pre="sup"),
        org_id=shared_org
    )
    assertion.assert_status_code(resp, 200)
    assertion.assert_equal(resp.json().get("code"), 0, "创建供应商失败")
    supplier_id = resp.json().get("data", {}).get("id")
    logger.info(f"共享供应商创建成功: {supplier_id}")
    return supplier_id


@pytest.fixture()
def another_supplier(another_org, another_pm_user):
    """以另一个组织PM身份创建另一个供应商（返回供应商ID字符串）"""
    login_with(another_pm_user["username"], DEFAULT_PASSWORD)
    resp = supplier_api.create_supplier(
        name=faker_data.random_name(pre="sup2"),
        org_id=another_org
    )
    assertion.assert_status_code(resp, 200)
    assertion.assert_equal(resp.json().get("code"), 0, "创建另一个供应商失败")
    supplier_id = resp.json().get("data", {}).get("id")
    logger.info(f"另一个供应商创建成功: {supplier_id}")
    return supplier_id


@pytest.fixture()
def org_team(shared_org, pm_user):
    """以项目管理员身份创建项目直属团队（无供应商），返回团队ID字符串"""
    login_with(pm_user["username"], DEFAULT_PASSWORD)
    resp = team_api.create_team(
        name=faker_data.random_name(pre="orgteam"),
        org_id=shared_org
    )
    assertion.assert_status_code(resp, 200)
    assertion.assert_equal(resp.json().get("code"), 0, "创建项目直属团队失败")
    team_id = resp.json().get("data", {}).get("id")
    logger.info(f"项目直属团队创建成功: {team_id}")
    return team_id


@pytest.fixture()
def another_org_team(another_org, another_pm_user):
    """以另一个组织PM身份创建另一个项目直属团队，返回团队ID字符串"""
    login_with(another_pm_user["username"], DEFAULT_PASSWORD)
    resp = team_api.create_team(
        name=faker_data.random_name(pre="orgteam2"),
        org_id=another_org
    )
    assertion.assert_status_code(resp, 200)
    assertion.assert_equal(resp.json().get("code"), 0, "创建另一个项目直属团队失败")
    team_id = resp.json().get("data", {}).get("id")
    logger.info(f"另一个项目直属团队创建成功: {team_id}")
    return team_id


@pytest.fixture()
def supplier_team(shared_org, shared_supplier, spadm_user):
    """以供应商管理员身份创建供应商团队"""
    login_with(spadm_user["username"], DEFAULT_PASSWORD)
    resp = team_api.create_team(
        name=faker_data.random_name(pre="supteam"),
        org_id=shared_org,
        supplier_id=shared_supplier
    )
    assertion.assert_status_code(resp, 200)
    assertion.assert_equal(resp.json().get("code"), 0, "创建供应商团队失败")
    data = resp.json().get("data", {})
    logger.info(f"供应商团队创建成功: {data.get('id')}")
    return {"id": data.get("id"), "supplier_id": data.get("supplier_id")}


@pytest.fixture()
def another_supplier_team(another_org, another_supplier, another_spadm_user):
    """以另一个供应商管理员身份创建另一个供应商团队"""
    login_with(another_spadm_user["username"], DEFAULT_PASSWORD)
    resp = team_api.create_team(
        name=faker_data.random_name(pre="supteam2"),
        org_id=another_org,
        supplier_id=another_supplier
    )
    assertion.assert_status_code(resp, 200)
    assertion.assert_equal(resp.json().get("code"), 0, "创建另一个供应商团队失败")
    data = resp.json().get("data", {})
    logger.info(f"另一个供应商团队创建成功: {data.get('id')}")
    return {"id": data.get("id"), "supplier_id": data.get("supplier_id")}


@pytest.fixture()
def created_user(shared_org, db_roles):
    """创建用户的工厂fixture，在当前token身份下执行创建"""
    def _create(user_type: str, team_id: str = None, supplier_id: str = None):
        return _do_create_user(user_type, shared_org, db_roles, team_id, supplier_id)
    return _create


@pytest.fixture()
def created_user_in_another_org(another_org, db_roles):
    """在另一个组织中创建用户的工厂fixture"""
    def _create(user_type: str, team_id: str = None, supplier_id: str = None):
        return _do_create_user(user_type, another_org, db_roles, team_id, supplier_id)
    return _create


@pytest.fixture()
def pm_user(created_user):
    """系统管理员创建PM用户，返回用户信息"""
    login_as("admin")
    resp, username, user_id = created_user(UserType.PM)
    assertion.assert_equal(resp.get("code"), 0, "创建PM失败")
    return {"user_id": user_id, "username": username}


@pytest.fixture()
def spadm_user(pm_user, created_user, shared_supplier):
    """以PM身份创建供应商管理员"""
    login_with(pm_user["username"], DEFAULT_PASSWORD)
    resp_json, username, user_id = created_user(UserType.SUPPLIER_ADMIN, supplier_id=shared_supplier)
    assertion.assert_equal(resp_json.get("code"), 0, "创建供应商管理员失败")
    data = resp_json.get("data", {})
    org = data.get("organization") or {}
    role = data.get("role") or {}
    return {
        "user_id": user_id,
        "username": username,
        "org_id": org.get("id"),
        "role_id": role.get("id"),
        "supplier_id": shared_supplier
    }


@pytest.fixture()
def org_team_admin_user(pm_user, created_user, org_team):
    """以PM身份创建项目直属团队管理员"""
    login_with(pm_user["username"], DEFAULT_PASSWORD)
    resp_json, username, user_id = created_user(UserType.ORG_TEAM_ADMIN, team_id=org_team)
    assertion.assert_equal(resp_json.get("code"), 0, "创建项目直属团队管理员失败")
    data = resp_json.get("data", {})
    org = data.get("organization") or {}
    role = data.get("role") or {}
    return {"user_id": user_id, "username": username, "team_id": org_team, "org_id": org.get("id"), "role_id": role.get("id")}


@pytest.fixture()
def org_team_member_user(org_team_admin_user, created_user):
    """以项目直属团队管理员身份创建项目直属团队成员"""
    login_with(org_team_admin_user["username"], DEFAULT_PASSWORD)
    resp_json, username, user_id = created_user(
        UserType.ORG_TEAM_MEMBER,
        team_id=org_team_admin_user["team_id"]
    )
    assertion.assert_equal(resp_json.get("code"), 0, "创建项目直属团队成员失败")
    data = resp_json.get("data", {})
    org = data.get("organization") or {}
    role = data.get("role") or {}
    return {"user_id": user_id, "username": username, "team_id": org_team_admin_user["team_id"], "org_id": org.get("id"), "role_id": role.get("id")}


@pytest.fixture()
def supplier_team_admin_user(spadm_user, created_user, supplier_team, shared_org):
    """以供应商管理员身份创建供应商团队管理员"""
    login_with(spadm_user["username"], DEFAULT_PASSWORD)
    resp_json, username, user_id = created_user(
        UserType.SUPPLIER_TEAM_ADMIN,
        team_id=supplier_team["id"],
        supplier_id=supplier_team["supplier_id"]
    )
    assertion.assert_equal(resp_json.get("code"), 0, "创建供应商团队管理员失败")
    data = resp_json.get("data", {})
    org = data.get("organization") or {}
    role = data.get("role") or {}
    return {"user_id": user_id, "username": username, "team_id": supplier_team["id"], "supplier_id": supplier_team["supplier_id"], "org_id": shared_org, "role_id": role.get("id")}


@pytest.fixture()
def supplier_team_member_user(supplier_team_admin_user, created_user):
    """以供应商团队管理员身份创建供应商团队成员"""
    login_with(supplier_team_admin_user["username"], DEFAULT_PASSWORD)
    resp_json, username, user_id = created_user(
        UserType.SUPPLIER_TEAM_MEMBER,
        team_id=supplier_team_admin_user["team_id"],
        supplier_id=supplier_team_admin_user["supplier_id"]
    )
    assertion.assert_equal(resp_json.get("code"), 0, "创建供应商团队成员失败")
    data = resp_json.get("data", {})
    org = data.get("organization") or {}
    role = data.get("role") or {}
    return {"user_id": user_id, "username": username, "team_id": supplier_team_admin_user["team_id"], "supplier_id": supplier_team_admin_user["supplier_id"], "org_id": org.get("id"), "role_id": role.get("id")}


@pytest.fixture()
def another_pm_user(created_user_in_another_org):
    """另一个组织下的PM用户"""
    login_as("admin")
    resp_json, username, user_id = created_user_in_another_org(UserType.PM)
    assertion.assert_equal(resp_json.get("code"), 0, "创建另一个组织PM失败")
    data = resp_json.get("data", {})
    org = data.get("organization") or {}
    role = data.get("role") or {}
    return {"user_id": user_id, "username": username, "org_id": org.get("id"), "role_id": role.get("id")}


@pytest.fixture()
def another_pm_in_same_org(created_user):
    """同一组织下的另一个PM用户（由admin创建）"""
    login_as("admin")
    resp_json, username, user_id = created_user(UserType.PM)
    assertion.assert_equal(resp_json.get("code"), 0, "创建同组织另一个PM失败")
    data = resp_json.get("data", {})
    org = data.get("organization") or {}
    role = data.get("role") or {}
    return {"user_id": user_id, "username": username, "org_id": org.get("id"), "role_id": role.get("id")}


@pytest.fixture()
def another_spadm_user(another_pm_user, created_user_in_another_org, another_supplier):
    """另一个供应商下的供应商管理员"""
    login_with(another_pm_user["username"], DEFAULT_PASSWORD)
    resp_json, username, user_id = created_user_in_another_org(UserType.SUPPLIER_ADMIN, supplier_id=another_supplier)
    assertion.assert_equal(resp_json.get("code"), 0, "创建另一个供应商管理员失败")
    data = resp_json.get("data", {})
    org = data.get("organization") or {}
    role = data.get("role") or {}
    return {"user_id": user_id, "username": username, "org_id": org.get("id"), "role_id": role.get("id"), "supplier_id": another_supplier}


@pytest.fixture()
def pm_user_in_editable_admin_org(db_roles):
    """使用另一个系统管理员账号admin_sys2创建组织及PM用户"""
    login_as("admin_sys2")

    # 1. admin_sys2 创建组织
    org_name = faker_data.random_name(pre="sys2org")
    resp = org_api.create_organization(name=org_name, description=TEST_ORG_DESCRIPTION)
    assertion.assert_status_code(resp, 200)
    resp_json = resp.json()
    assertion.assert_equal(resp_json.get("code"), 0, "admin_sys2创建组织失败")
    org_id = resp_json.get("data", {}).get("id")
    logger.info(f"admin_sys2创建组织成功: {org_id}")

    # 2. admin_sys2 在该组织下创建PM
    role_id = _find_role_id(db_roles, "PM")
    username = faker_data.random_username(pre="pm")
    display_name = faker_data.random_name(pre="pm")
    resp = user_api.create_user(
        username=username,
        display_name=display_name,
        password=DEFAULT_PASSWORD,
        organization_id=org_id,
        role_id=role_id
    )
    assertion.assert_status_code(resp, 200)
    resp_json = resp.json()
    assertion.assert_equal(resp_json.get("code"), 0, "admin_sys2创建PM失败")
    data = resp_json.get("data", {})
    logger.info(f"admin_sys2创建PM成功: {data.get('id')}")
    return {"user_id": data.get("id"), "username": username, "org_id": org_id, "role_id": role_id}


@pytest.fixture()
def editable_admin(db_roles):
    """
    使用内置的第二个系统管理员账号 admin_sys2/admin123 作为被编辑对象。
    通过登录后查询当前用户信息，获取 user_id、username、org_id、role_id。
    用例结束后通过数据库恢复 admin_sys2 的原始账号、角色和密码，避免影响后续用例。
    """
    sys_admin_role_id = _find_role_id(db_roles, "SYSTEM_ADMIN")

    # 先以 admin 身份查询 admin_sys2 的原始信息，用于后续恢复
    login_as("admin")
    original = pg_db.query_one(
        "SELECT id, username, display_name, hashed_password FROM dsp_user WHERE username=%s",
        ("admin_sys2",)
    )
    assertion.assert_true(original is not None, "无法获取 admin_sys2 原始信息用于恢复")
    original_member = pg_db.query_one(
        "SELECT role_id, organization_id FROM dsp_member WHERE user_id=%s",
        (original["id"],)
    )

    login_as("admin_sys2")
    resp = auth_api.get_current_user()
    assertion.assert_status_code(resp, 200)
    resp_json = resp.json()
    assertion.assert_equal(resp_json.get("code"), 0, "获取admin_sys2当前用户信息失败")
    data = resp_json.get("data") or {}
    org = data.get("organization") or {}
    role = data.get("role") or {}
    user_id = data.get("id")
    username = data.get("username")
    original_role_id = role.get("id") or sys_admin_role_id
    original_org_id = org.get("id")
    logger.info(f"可编辑系统管理员: {user_id}, username={username}")

    yield {
        "user_id": user_id,
        "username": username,
        "is_admin": True,
        "org_id": original_org_id,
        "role_id": original_role_id
    }

    # 通过数据库恢复 admin_sys2 的原始状态（绕过 API 对下划线用户名校验）
    pg_db.update(
        "dsp_user",
        {
            "username": original["username"],
            "display_name": original["display_name"],
            "hashed_password": original["hashed_password"],
            "is_active": True
        },
        "id=%s",
        (user_id,)
    )
    pg_db.update(
        "dsp_member",
        {
            "role_id": original_member["role_id"] if original_member else sys_admin_role_id,
            "organization_id": original_member["organization_id"] if original_member else None,
            "supplier_id": None,
            "team_id": None
        },
        "user_id=%s",
        (user_id,)
    )
    logger.info("恢复 admin_sys2: username=%s, role=SYSTEM_ADMIN", original["username"])


# ======================== 测试类：用户创建权限 ========================

class TestCreateUser:
    """用户管理-创建权限用例"""

    # ======================== 系统管理员权限 ========================

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.smoke
    def test_admin_can_create_pm(self, created_user):
        """系统管理员可以新增项目管理员"""
        resp_json, username, _ = created_user(UserType.PM)
        _assert_user_match(resp_json, username, "pm", "系统管理员创建PM")

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("user_type", [
        UserType.SUPPLIER_ADMIN,
        UserType.ORG_TEAM_ADMIN,
        UserType.ORG_TEAM_MEMBER,
        UserType.SUPPLIER_TEAM_ADMIN,
        UserType.SUPPLIER_TEAM_MEMBER
    ])
    def test_admin_cannot_create(self, created_user, user_type):
        """系统管理员无法新增供应商管理员/各类团队管理员/成员"""
        resp_json, _, _ = created_user(user_type)
        assertion.assert_equal(resp_json.get("code"), 400, "验证接口返回code失败")

    # ======================== 项目管理员权限 ========================

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("user_type", [
        UserType.SYSTEM_ADMIN,
        UserType.PM
    ])
    def test_pm_cannot_create(self, pm_user, created_user, user_type):
        """项目管理员无法新增系统管理员和项目管理员"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp_json, _, _ = created_user(user_type)
        assertion.assert_true(resp_json.get("code") != 0,
                              f"项目管理员不应能创建{USER_TYPE_NAME_MAP[user_type]}角色用户")

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("user_type,team_fixture_name", [
        (UserType.SUPPLIER_ADMIN, None),
        (UserType.ORG_TEAM_ADMIN, "org_team"),
        (UserType.ORG_TEAM_MEMBER, "org_team"),
        (UserType.SUPPLIER_TEAM_ADMIN, "supplier_team"),
        (UserType.SUPPLIER_TEAM_MEMBER, "supplier_team"),
    ])
    def test_pm_can_create_success(self, pm_user, created_user, request, user_type, team_fixture_name):
        """项目管理员可新增供应商管理员、项目直属/供应商团队管理员和成员"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        kwargs = {}
        if team_fixture_name:
            team_info = request.getfixturevalue(team_fixture_name)
            # 团队fixture会切换为admin，需要重新切回PM身份
            login_with(pm_user["username"], DEFAULT_PASSWORD)
            if isinstance(team_info, dict):
                kwargs["team_id"] = team_info["id"]
                kwargs["supplier_id"] = team_info["supplier_id"]
            else:
                kwargs["team_id"] = team_info

        resp_json, username, _ = created_user(user_type, **kwargs)
        expected_role_code = USER_TYPE_ROLE_MAP[user_type]
        _assert_user_match(resp_json, username, expected_role_code, f"项目管理员创建{USER_TYPE_NAME_MAP[user_type]}")

    # ======================== 供应商管理员权限 ========================

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("user_type", [
        UserType.PM,
        UserType.SYSTEM_ADMIN,
        UserType.SUPPLIER_ADMIN,
    ])
    def test_spadm_cannot_create(self, spadm_user, created_user, user_type):
        """供应商管理员无法新增项目管理员/系统管理员/供应商管理员"""
        login_with(spadm_user["username"], DEFAULT_PASSWORD)
        resp_json, _, _ = created_user(user_type)
        assertion.assert_true(resp_json.get("code") != 0,
                              f"供应商管理员不应能创建{USER_TYPE_NAME_MAP[user_type]}角色用户")

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("user_type", [
        UserType.SUPPLIER_TEAM_ADMIN,
        UserType.SUPPLIER_TEAM_MEMBER
    ])
    def test_spadm_can_create_success(self, spadm_user, created_user, supplier_team, user_type):
        """供应商管理员新增供应商团队管理员/成员 - 成功"""
        login_with(spadm_user["username"], DEFAULT_PASSWORD)
        resp_json, username, _ = created_user(
            user_type,
            team_id=supplier_team["id"],
            supplier_id=supplier_team["supplier_id"]
        )
        expected_role_code = USER_TYPE_ROLE_MAP[user_type]
        _assert_user_match(resp_json, username, expected_role_code, f"供应商管理员创建{USER_TYPE_NAME_MAP[user_type]}")

    # ======================== 项目直属团队管理员权限 ========================

    @pytest.mark.system
    @pytest.mark.api
    def test_org_team_admin_can_create_member(self, org_team_admin_user, created_user):
        """项目直属团队管理员新增项目直属团队成员 - 成功"""
        login_with(org_team_admin_user["username"], DEFAULT_PASSWORD)
        resp_json, username, _ = created_user(
            UserType.ORG_TEAM_MEMBER,
            team_id=org_team_admin_user["team_id"]
        )
        _assert_user_match(resp_json, username, "member", "项目直属团队管理员创建成员")

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("user_type", [
        UserType.SYSTEM_ADMIN,
        UserType.PM,
        UserType.SUPPLIER_ADMIN,
        UserType.ORG_TEAM_ADMIN,
        UserType.SUPPLIER_TEAM_ADMIN,
    ])
    def test_org_team_admin_cannot_create(self, org_team_admin_user, created_user, user_type):
        """项目直属团队管理员无法新增其他角色用户"""
        login_with(org_team_admin_user["username"], DEFAULT_PASSWORD)
        resp_json, _, _ = created_user(user_type, team_id=org_team_admin_user["team_id"])
        assertion.assert_true(resp_json.get("code") != 0,
                              f"项目直属团队管理员不应能创建{USER_TYPE_NAME_MAP[user_type]}角色用户")

    # ======================== 供应商团队管理员权限 ========================

    @pytest.mark.system
    @pytest.mark.api
    def test_supplier_team_admin_can_create_member(self, supplier_team_admin_user, created_user):
        """供应商团队管理员新增供应商团队成员 - 成功"""
        login_with(supplier_team_admin_user["username"], DEFAULT_PASSWORD)
        resp_json, username, _ = created_user(
            UserType.SUPPLIER_TEAM_MEMBER,
            team_id=supplier_team_admin_user["team_id"],
            supplier_id=supplier_team_admin_user["supplier_id"]
        )
        _assert_user_match(resp_json, username, "member", "供应商团队管理员创建成员")

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("user_type", [
        UserType.SYSTEM_ADMIN,
        UserType.PM,
        UserType.SUPPLIER_ADMIN,
        UserType.ORG_TEAM_ADMIN,
        UserType.SUPPLIER_TEAM_ADMIN
    ])
    def test_supplier_team_admin_cannot_create(self, supplier_team_admin_user, created_user, user_type):
        """供应商团队管理员无法新增其他角色用户"""
        login_with(supplier_team_admin_user["username"], DEFAULT_PASSWORD)
        resp_json, _, _ = created_user(
            user_type,
            team_id=supplier_team_admin_user["team_id"],
            supplier_id=supplier_team_admin_user["supplier_id"]
        )
        assertion.assert_true(resp_json.get("code") != 0,
                              f"供应商团队管理员不应能创建{USER_TYPE_NAME_MAP[user_type]}角色用户")

    # ======================== 必填字段校验 ========================

    @pytest.mark.system
    @pytest.mark.api
    def test_org_team_admin_create_member_without_team(self, org_team_admin_user, created_user):
        """项目直属团队管理员创建成员时，不传入团队ID应失败"""
        login_with(org_team_admin_user["username"], DEFAULT_PASSWORD)
        resp_json, _, _ = created_user(UserType.ORG_TEAM_MEMBER)
        assertion.assert_equal(resp_json.get("code"), 400,
                              "项目直属团队管理员创建成员时team_id应为必填")

    @pytest.mark.system
    @pytest.mark.api
    def test_supplier_team_admin_create_member_without_team(self, supplier_team_admin_user, db_roles):
        """供应商下团队管理员创建成员时，不传入团队ID应失败"""
        login_with(supplier_team_admin_user["username"], DEFAULT_PASSWORD)
        role_id = _find_role_id(db_roles, "MEMBER")
        username = faker_data.random_username(pre="suptmem")
        display_name = faker_data.random_name(pre="suptmem")
        # 供应商团队管理员创建成员时不传team_id（但传入supplier_id和organization_id）
        resp = user_api.create_user(
            username=username,
            display_name=display_name,
            password=DEFAULT_PASSWORD,
            organization_id=supplier_team_admin_user["org_id"],
            role_id=role_id,
            supplier_id=supplier_team_admin_user["supplier_id"]
        )
        resp_json = resp.json()
        assertion.assert_equal(resp_json.get("code"), 400,
                              "供应商团队管理员创建成员时team_id应为必填")

    @pytest.mark.system
    @pytest.mark.api
    def test_supplier_team_admin_create_member_without_org(self, supplier_team_admin_user, db_roles):
        """供应商下团队管理员创建成员时，不传入组织ID由后端自动填充"""
        login_with(supplier_team_admin_user["username"], DEFAULT_PASSWORD)
        role_id = _find_role_id(db_roles, "MEMBER")
        username = faker_data.random_username(pre="suptmem")
        display_name = faker_data.random_name(pre="suptmem")
        # 供应商团队管理员创建成员时不传organization_id（但传入team_id和supplier_id）
        resp = user_api.create_user(
            username=username,
            display_name=display_name,
            password=DEFAULT_PASSWORD,
            role_id=role_id,
            supplier_id=supplier_team_admin_user["supplier_id"],
            team_id=[supplier_team_admin_user["team_id"]]
        )
        resp_json = resp.json()
        assertion.assert_equal(resp_json.get("code"), 0,
                              "供应商团队管理员创建成员时organization_id应由后端自动填充")
        data = resp_json.get("data") or {}
        org = data.get("organization") or {}
        assertion.assert_equal(
            org.get("id"),
            supplier_team_admin_user["org_id"],
            "自动填充的组织ID应与供应商团队管理员所在组织一致"
        )

    @pytest.mark.system
    @pytest.mark.api
    def test_create_supplier_team_member_with_team_not_under_supplier(self, spadm_user, db_roles, another_supplier_team):
        """创建供应商团队下用户时，团队不属于该供应商下应失败"""
        login_with(spadm_user["username"], DEFAULT_PASSWORD)
        member_role_id = _find_role_id(db_roles, "MEMBER")
        username = faker_data.random_username(pre="suptmem")
        display_name = faker_data.random_name(pre="suptmem")
        resp = user_api.create_user(
            username=username,
            display_name=display_name,
            password=DEFAULT_PASSWORD,
            organization_id=spadm_user["org_id"],
            role_id=member_role_id,
            supplier_id=spadm_user["supplier_id"],
            team_id=[another_supplier_team["id"]]
        )
        resp_json = resp.json()
        assertion.assert_true(
            resp_json.get("code") != 0,
            "团队不属于当前供应商时，创建供应商团队成员应失败"
        )


# ======================== 测试类：用户状态切换权限 ========================

class TestUserStatus:
    """用户管理-状态切换权限用例"""

    @staticmethod
    def _assert_disabled_login(username: str, password: str = DEFAULT_PASSWORD):
        """校验用户被禁用后无法登录，返回403及指定提示"""
        resp = auth_api.login(username=username, password=password)
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        assertion.assert_equal(resp_json.get("code"), 403, f"禁用用户[{username}]登录应返回403")
        assertion.assert_equal(
            resp_json.get("msg"), "用户已被禁用，无权限登录",
            f"禁用用户[{username}]登录提示信息不匹配"
        )

    @staticmethod
    def _toggle_status(
            operator_info: dict,
            target_user: dict,
            should_success: bool = True,
            msg: str = "",
            verify_disabled_login: bool = True,
            expected_fail_code: int = 403
    ):
        """
        切换目标用户状态并校验结果
        :param operator_info: 操作者信息，包含 username
        :param target_user: 目标用户信息，包含 user_id、username
        :param should_success: 是否期望成功
        :param msg: 断言信息
        :param verify_disabled_login: 禁用成功后是否校验该用户无法登录
        :param expected_fail_code: 期望失败的业务code（默认403，禁用自己为400）
        :return: 响应JSON
        """
        login_with(operator_info["username"], DEFAULT_PASSWORD)
        resp = user_api.update_user_status(target_user["user_id"])
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        code = resp_json.get("code")
        if should_success:
            assertion.assert_equal(code, 0, f"{msg}应成功")
            # 若成功禁用，校验被禁用用户无法登录
            if verify_disabled_login and not resp_json.get("data", {}).get("is_active", True):
                TestUserStatus._assert_disabled_login(target_user["username"])
        else:
            assertion.assert_equal(code, expected_fail_code, f"{msg}应失败")
        return resp_json

    # ======================== 系统管理员 ========================
    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.smoke
    def test_admin_cannot_toggle_self(self, as_admin):
        """系统管理员不能修改自己的状态"""
        admin_info = _get_current_user_info()
        self._toggle_status(
            {"username": "admin"}, admin_info, False,
            "系统管理员切换自己的状态",
            expected_fail_code=400
        )

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.smoke
    def test_admin_can_toggle_pm_status(self, as_admin, shared_org, db_roles):
        """系统管理员创建组织→创建PM用户→切换禁用→验证→切换启用→验证"""
        # 创建PM用户
        resp_json, username, user_id = _do_create_user(UserType.PM, shared_org, db_roles)
        assertion.assert_equal(resp_json.get("code"), 0, "创建PM失败")
        pm_user = {"user_id": user_id, "username": username}

        # 切换到禁用
        res_data = self._toggle_status(
            {"username": "admin"}, pm_user, True,
            "系统管理员切换PM状态到禁用"
        )
        assertion.assert_equal(res_data.get("data", {}).get("is_active"), False, "用户状态应切换到禁用")

        # 切换回启用
        res_data = self._toggle_status(
            {"username": "admin"}, pm_user, True,
            "系统管理员切换PM状态到启用"
        )
        assertion.assert_equal(res_data.get("data", {}).get("is_active"), True, "用户状态应切换到启用")

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.smoke
    def test_admin_cannot_toggle_not_own_pm_status(self, pm_user_in_editable_admin_org):
        """系统管理员不能操作非自己创建的组织下的PM用户状态"""
        # 当前环境admin尝试切换admin_sys2组织下的PM用户状态，期望失败
        self._toggle_status(
            {"username": "admin"}, pm_user_in_editable_admin_org, False,
            "系统管理员切换非自己创建的PM状态"
        )

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("target_fixture", [
        "spadm_user",
        "org_team_admin_user",
        "org_team_member_user",
        "supplier_team_admin_user",
        "supplier_team_member_user"
    ])
    def test_admin_cannot_toggle_other_roles_status(self, target_fixture, request):
        """系统管理员不能切换非PM/非系统管理员的状态"""
        target_user = request.getfixturevalue(target_fixture)
        self._toggle_status(
            {"username": "admin"}, target_user, False,
            f"系统管理员切换{target_fixture}状态"
        )

    # ======================== 项目管理员 ========================

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("target_fixture", [
        "another_pm_in_same_org",
        "spadm_user",
        "org_team_admin_user",
        "org_team_member_user",
        "supplier_team_admin_user",
        "supplier_team_member_user"
    ])
    def test_pm_can_toggle_same_org_users_status(self, pm_user, target_fixture, request):
        """项目管理员可以切换自己组织下所有用户状态（不含自己）"""
        target_user = request.getfixturevalue(target_fixture)
        self._toggle_status(
            pm_user, target_user, True,
            f"项目管理员切换同组织{target_fixture}状态"
        )

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_cannot_toggle_other_org_user_status(self, pm_user, another_pm_user):
        """项目管理员不能切换其他组织用户状态"""
        self._toggle_status(
            pm_user, another_pm_user, False,
            "项目管理员切换其他组织PM状态"
        )

    # ======================== 供应商管理员 ========================

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("target_fixture", [
        "supplier_team_admin_user",
        "supplier_team_member_user"
    ])
    def test_spadm_can_toggle_same_supplier_users_status(self, spadm_user, target_fixture, request):
        """供应商管理员可以切换自己供应商下所有用户状态"""
        target_user = request.getfixturevalue(target_fixture)
        self._toggle_status(
            spadm_user, target_user, True,
            f"供应商管理员切换供应商下{target_fixture}状态"
        )

    @pytest.mark.system
    @pytest.mark.api
    def test_spadm_cannot_toggle_self(self, spadm_user):
        """供应商管理员不能切换自己的状态"""
        self._toggle_status(
            spadm_user, spadm_user, False,
            "供应商管理员切换自己的状态",
            expected_fail_code=400
        )

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("target_fixture", [
        "pm_user",
        "org_team_admin_user",
        "org_team_member_user"
    ])
    def test_spadm_cannot_toggle_non_supplier_users_status(self, spadm_user, target_fixture, request):
        """供应商管理员不能切换非自己供应商下的用户状态"""
        target_user = request.getfixturevalue(target_fixture)
        self._toggle_status(
            spadm_user, target_user, False,
            f"供应商管理员切换非供应商用户{target_fixture}状态"
        )

    # ======================== 项目直属团队管理员 ========================

    @pytest.mark.system
    @pytest.mark.api
    def test_org_team_admin_can_toggle_same_team_member_status(self, org_team_admin_user, org_team_member_user):
        """项目直属团队管理员可以切换自己创建的团队成员状态"""
        self._toggle_status(
            org_team_admin_user, org_team_member_user, True,
            "项目直属团队管理员切换自己创建的团队成员状态"
        )

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("target_fixture", [
        "pm_user",
        "spadm_user",
        "supplier_team_admin_user",
        "supplier_team_member_user"
    ])
    def test_org_team_admin_cannot_toggle_non_self_created_user_status(self, org_team_admin_user, target_fixture, request):
        """项目直属团队管理员不能切换非自己创建的用户状态（即使同组织可查看）"""
        target_user = request.getfixturevalue(target_fixture)
        self._toggle_status(
            org_team_admin_user, target_user, False,
            f"项目直属团队管理员切换非自己创建用户{target_fixture}状态"
        )

    # ======================== 供应商团队管理员 ========================

    @pytest.mark.system
    @pytest.mark.api
    def test_supplier_team_admin_can_toggle_same_team_member_status(self, supplier_team_admin_user, supplier_team_member_user):
        """供应商团队管理员可以切换自己创建的团队成员状态"""
        self._toggle_status(
            supplier_team_admin_user, supplier_team_member_user, True,
            "供应商团队管理员切换自己创建的团队成员状态"
        )

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("target_fixture", [
        "pm_user",
        "spadm_user",
        "org_team_admin_user",
        "org_team_member_user"
    ])
    def test_supplier_team_admin_cannot_toggle_non_self_created_user_status(self, supplier_team_admin_user, target_fixture, request):
        """供应商团队管理员不能切换非自己创建的用户状态（即使同供应商可查看）"""
        target_user = request.getfixturevalue(target_fixture)
        self._toggle_status(
            supplier_team_admin_user, target_user, False,
            f"供应商团队管理员切换非自己创建用户{target_fixture}状态"
        )


# ======================== 测试类：团队管理员查看范围 ========================

class TestTeamAdminViewScope:
    """团队管理员可查看所属供应商/组织下的用户，但不一定能操作"""

    @staticmethod
    def _view_user_detail_as(operator_info: dict, target_user_id: str) -> dict:
        """以指定身份查询用户详情"""
        login_with(operator_info["username"], DEFAULT_PASSWORD)
        resp = user_api.get_user_detail_by_id(target_user_id)
        assertion.assert_status_code(resp, 200)
        return resp.json()

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("target_fixture", [
        "pm_user",
        "spadm_user",
        "supplier_team_admin_user",
        "supplier_team_member_user"
    ])
    def test_org_team_admin_can_view_users_under_org(self, org_team_admin_user, target_fixture, request):
        """项目直属团队管理员可以查看同组织下的用户"""
        target_user = request.getfixturevalue(target_fixture)
        resp_json = self._view_user_detail_as(org_team_admin_user, target_user["user_id"])
        assertion.assert_equal(resp_json.get("code"), 0,
                               f"项目直属团队管理员应能查看同组织用户{target_fixture}")

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("target_fixture", [
        "spadm_user",
        "supplier_team_member_user"
    ])
    def test_supplier_team_admin_can_view_users_under_supplier(self, supplier_team_admin_user, target_fixture, request):
        """供应商团队管理员可以查看同供应商下的用户"""
        target_user = request.getfixturevalue(target_fixture)
        resp_json = self._view_user_detail_as(supplier_team_admin_user, target_user["user_id"])
        assertion.assert_equal(resp_json.get("code"), 0,
                               f"供应商团队管理员应能查看同供应商用户{target_fixture}")


# ======================== 测试类：编辑用户 ========================

class TestUpdateUser:
    """用户管理-编辑用户用例（含权限与字段校验）"""

    @staticmethod
    def _update_as(operator_info: dict, target_user: dict, **kwargs) -> dict:
        """以operator身份编辑目标用户，必填字段从上下文自动补全"""
        login_with(operator_info["username"], DEFAULT_PASSWORD)
        # 缺失org_id、role_id或role_code时，从上下文补全
        has_all = target_user.get("org_id") and target_user.get("role_id") and target_user.get("role_code")
        ctx = target_user if has_all else {**target_user, **_get_user_edit_context(target_user["user_id"])}
        # 系统管理员目标编辑时organization_id可传空
        is_system_admin = ctx.get("role_code") == "SYSTEM_ADMIN"
        default_org_id = None if is_system_admin else ctx.get("org_id")
        role_id = kwargs.pop("role_id", None) if "role_id" in kwargs else ctx.get("role_id")
        org_id = kwargs.pop("organization_id", None) if "organization_id" in kwargs else default_org_id
        team_id = kwargs.pop("team_id", None) if "team_id" in kwargs else (ctx.get("team_ids") if ctx.get("team_ids") else None)
        supplier_id = kwargs.pop("supplier_id", None) if "supplier_id" in kwargs else ctx.get("supplier_id")
        username = kwargs.pop("username", None) or ctx.get("username")
        display_name = kwargs.pop("display_name", None) or ctx.get("display_name")
        return _do_update_user(
            target_user["user_id"],
            username=username,
            display_name=display_name,
            organization_id=org_id,
            role_id=role_id,
            team_id=team_id,
            supplier_id=supplier_id,
            **kwargs
        )

    @staticmethod
    def _update_as_admin(target_user: dict, **kwargs) -> dict:
        """以admin身份编辑目标用户，调用 _update_as 复用相同逻辑"""
        return TestUpdateUser._update_as(
            {"username": "admin"},
            target_user,
            **kwargs
        )

    @staticmethod
    def _edit_user_login_check(ctx: dict, password: str):
        """编辑密码后校验新密码可登录，再恢复为默认密码"""
        try:
            login_with(ctx["username"], password)
        finally:
            login_as("admin")
            _do_update_user(
                ctx["user_id"],
                username=ctx["username"],
                password=DEFAULT_PASSWORD
            )

    # ======================== 系统管理员编辑权限 ========================

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.smoke
    def test_admin_can_edit_self(self, as_admin):
        """系统管理员可以编辑自己的非必填信息"""
        admin_info = _get_current_user_info()

        new_display_name = faker_data.random_name(pre="admin")
        new_phone = "13800138000"
        new_email = faker_data.random_email()
        new_remark = faker_data.random_sentence(length=20)[:200]

        resp_json = _do_update_user(
            admin_info["user_id"],
            username=admin_info["username"],
            organization_id=admin_info["org_id"],
            display_name=new_display_name,
            phone=new_phone,
            email=new_email,
            remark=new_remark
        )
        _assert_update_success(resp_json, msg_prefix="系统管理员编辑自己")
        data = resp_json.get("data", {})
        assertion.assert_equal(data.get("display_name"), new_display_name, "昵称未更新")
        assertion.assert_equal(data.get("phone"), new_phone, "电话未更新")
        assertion.assert_equal(data.get("email"), new_email, "邮箱未更新")
        assertion.assert_equal(data.get("remark"), new_remark, "备注未更新")

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.smoke
    def test_admin_can_edit_other_admin(self, as_admin, editable_admin):
        """系统管理员可以编辑其他系统管理员信息"""
        new_display_name = faker_data.random_name(pre="sys2")
        resp_json = _do_update_user(
            editable_admin["user_id"],
            organization_id=editable_admin["org_id"],
            role_id=editable_admin["role_id"],
            display_name=new_display_name
        )
        _assert_update_success(resp_json, msg_prefix="系统管理员编辑其他管理员")

    @pytest.mark.system
    @pytest.mark.api
    def test_admin_can_edit_all_required_fields(self, as_admin, editable_admin, db_roles):
        """系统管理员编辑其他管理员的必填项（账号、昵称、密码、角色）"""
        sys_admin_role_id = _find_role_id(db_roles, "SYSTEM_ADMIN")
        new_username = faker_data.random_username(pre="sysadm")
        new_display_name = faker_data.random_name(pre="sysadm")
        new_password = "admin1234"
        original_username = editable_admin["username"]

        try:
            resp_json = _do_update_user(
                editable_admin["user_id"],
                username=new_username,
                organization_id=editable_admin["org_id"],
                display_name=new_display_name,
                password=new_password,
                role_id=sys_admin_role_id
            )
            _assert_update_success(resp_json, expected_username=new_username, msg_prefix="编辑必填项")
            ctx = _get_user_edit_context(editable_admin["user_id"])
            self._edit_user_login_check(ctx, new_password)
        finally:
            # 还原账号，避免影响后续用例
            login_as("admin")
            _do_update_user(
                editable_admin["user_id"],
                username=original_username,
                organization_id=editable_admin["org_id"],
                password=DEFAULT_PASSWORD
            )

    @pytest.mark.system
    @pytest.mark.api
    def test_admin_can_edit_optional_fields(self, as_admin, editable_admin):
        """系统管理员可以编辑/清空其他系统管理员的非必填项"""
        new_phone = "13800138000"
        new_email = faker_data.random_email()
        new_remark = faker_data.random_sentence(length=20)[:200]
        resp_json = _do_update_user(
            editable_admin["user_id"],
            organization_id=editable_admin["org_id"],
            role_id=editable_admin["role_id"],
            phone=new_phone,
            email=new_email,
            remark=new_remark
        )
        _assert_update_success(resp_json, msg_prefix="编辑非必填项")
        data = resp_json.get("data", {})
        assertion.assert_equal(data.get("phone"), new_phone, "电话未更新")
        assertion.assert_equal(data.get("email"), new_email, "邮箱未更新")
        assertion.assert_equal(data.get("remark"), new_remark, "备注未更新")

    @pytest.mark.system
    @pytest.mark.api
    def test_admin_can_clear_optional_fields(self, as_admin, editable_admin):
        """系统管理员可以清空其他系统管理员的非必填项"""
        resp_json = _do_update_user(
            editable_admin["user_id"],
            organization_id=editable_admin["org_id"],
            role_id=editable_admin["role_id"],
            phone="",
            email="",
            remark=""
        )
        _assert_update_success(resp_json, msg_prefix="清空非必填项")

    @pytest.mark.system
    @pytest.mark.api
    def test_update_user_detail_is_updated(self, as_admin, editable_admin):
        """系统管理员编辑其他系统管理员后查询详情，字段已更新"""
        new_display_name = faker_data.random_name(pre="detail")
        new_phone = "13900139000"

        resp_json = _do_update_user(
            editable_admin["user_id"],
            organization_id=editable_admin["org_id"],
            role_id=editable_admin["role_id"],
            display_name=new_display_name,
            phone=new_phone
        )
        _assert_update_success(resp_json, msg_prefix="编辑后查询详情")

        detail_resp = user_api.get_user_detail_by_id(editable_admin["user_id"])
        assertion.assert_status_code(detail_resp, 200)
        detail_data = detail_resp.json().get("data", {})
        assertion.assert_equal(detail_data.get("display_name"), new_display_name, "详情中昵称未更新")
        assertion.assert_equal(detail_data.get("phone"), new_phone, "详情中电话未更新")

    @pytest.mark.system
    @pytest.mark.api
    def test_admin_can_edit_created_pm_user(self, as_admin, pm_user):
        """系统管理员可以编辑自己创建的项目管理员"""
        target_ctx = _get_user_edit_context(pm_user["user_id"])
        new_display_name = faker_data.random_name(pre="admin_pm")
        resp_json = self._update_as_admin(
            pm_user,
            username=target_ctx["username"],
            display_name=new_display_name
        )
        _assert_update_success(resp_json, msg_prefix="系统管理员编辑自己创建的PM")

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("target_fixture", [
        "spadm_user",
        "org_team_admin_user",
        "org_team_member_user",
        "supplier_team_admin_user",
        "supplier_team_member_user",
    ])
    def test_admin_cannot_edit_non_system_admin_user(self, as_admin, target_fixture, request):
        """系统管理员不能编辑非自己创建且非系统管理员的角色"""
        target_user = request.getfixturevalue(target_fixture)
        target_ctx = _get_user_edit_context(target_user["user_id"])
        resp_json = self._update_as_admin(
            target_user,
            username=target_ctx["username"],
            display_name=faker_data.random_name(pre="admin_noadmin")
        )
        _assert_update_fail(resp_json, msg_prefix=f"系统管理员编辑{target_fixture}应失败")

    # ======================== 项目管理员编辑权限 ========================

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_edit_self(self, pm_user):
        """项目管理员编辑自己（实际权限：自己未被自己创建，应失败）"""
        resp_json = self._update_as(pm_user, pm_user, display_name=faker_data.random_name(pre="pm_self"))
        _assert_update_fail(resp_json, msg_prefix="项目管理员编辑自己应失败")

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("target_fixture", [
        "spadm_user",
        "org_team_admin_user",
    ])
    def test_pm_can_edit_user_created_by_pm(self, pm_user, target_fixture, request):
        """项目管理员可以编辑自己创建的同组织用户"""
        target_user = request.getfixturevalue(target_fixture)
        target_ctx = _get_user_edit_context(target_user["user_id"])
        resp_json = self._update_as(pm_user, target_user, username=target_ctx["username"], display_name=faker_data.random_name(pre="pm_edit"))
        _assert_update_success(resp_json, msg_prefix=f"项目管理员编辑同组织{target_fixture}")

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("target_fixture", [
        "org_team_member_user",
        "supplier_team_admin_user",
        "supplier_team_member_user",
    ])
    def test_pm_can_edit_same_org_user_not_created_by_pm(self, pm_user, target_fixture, request):
        """项目管理员可以编辑同组织下非自己创建的用户（需求）"""
        target_user = request.getfixturevalue(target_fixture)
        target_ctx = _get_user_edit_context(target_user["user_id"])
        resp_json = self._update_as(pm_user, target_user, username=target_ctx["username"], display_name=faker_data.random_name(pre="pm_edit2"))
        _assert_update_success(resp_json, msg_prefix=f"项目管理员编辑同组织{target_fixture}")

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_cannot_edit_same_org_other_pm(self, pm_user, another_pm_in_same_org):
        """项目管理员不能编辑同组织下的其他项目管理员"""
        resp_json = self._update_as(pm_user, another_pm_in_same_org, display_name=faker_data.random_name(pre="pm_nopm"))
        _assert_update_fail(resp_json, msg_prefix="项目管理员编辑同组织其他PM应失败")

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_cannot_edit_other_org_user(self, pm_user, another_pm_user):
        """项目管理员不能编辑其他组织的用户"""
        resp_json = self._update_as(pm_user, another_pm_user, display_name=faker_data.random_name(pre="pm_other"))
        _assert_update_fail(resp_json, msg_prefix="项目管理员编辑其他组织用户应失败")

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_cannot_edit_system_admin(self, pm_user, as_admin):
        """项目管理员不能编辑系统管理员"""
        admin_info = _get_current_user_info()
        resp_json = self._update_as(pm_user, admin_info, display_name=faker_data.random_name(pre="pm_noadmin"))
        _assert_update_fail(resp_json, msg_prefix="项目管理员编辑系统管理员应失败")

    # ======================== 项目管理员可编辑字段 ========================

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_edit_required_fields_of_created_user(self, pm_user, created_user, org_team, shared_org):
        """项目管理员编辑自己创建用户的必填项（账号、昵称、密码）"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp_json, username, user_id = created_user(UserType.ORG_TEAM_MEMBER, team_id=org_team)
        assertion.assert_equal(resp_json.get("code"), 0, "PM创建成员失败")

        new_username = faker_data.random_username(pre="pmmem")
        new_display_name = faker_data.random_name(pre="pmmem")
        new_password = "admin1234"

        try:
            resp_json = self._update_as(
                pm_user,
                {"user_id": user_id, "username": username},
                username=new_username,
                display_name=new_display_name,
                password=new_password
            )
            _assert_update_success(resp_json, expected_username=new_username, msg_prefix="PM编辑必填项")
            ctx = _get_user_edit_context(user_id)
            self._edit_user_login_check(ctx, new_password)
        finally:
            login_as("admin")
            _do_update_user(user_id, username=new_username, password=DEFAULT_PASSWORD)

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_edit_optional_fields_of_created_user(self, pm_user, created_user, org_team):
        """项目管理员编辑自己创建用户的非必填项（电话、邮箱、备注）"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp_json, username, user_id = created_user(UserType.ORG_TEAM_MEMBER, team_id=org_team)
        assertion.assert_equal(resp_json.get("code"), 0, "PM创建成员失败")

        new_phone = "13800138000"
        new_email = faker_data.random_email()
        new_remark = faker_data.random_sentence(length=20)[:200]
        resp_json = self._update_as(
            pm_user,
            {"user_id": user_id, "username": username},
            phone=new_phone,
            email=new_email,
            remark=new_remark
        )
        _assert_update_success(resp_json, msg_prefix="PM编辑非必填项")
        data = resp_json.get("data", {})
        assertion.assert_equal(data.get("phone"), new_phone, "电话未更新")
        assertion.assert_equal(data.get("email"), new_email, "邮箱未更新")
        assertion.assert_equal(data.get("remark"), new_remark, "备注未更新")

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_edit_user_role_to_supplier_admin(self, pm_user, created_user, shared_supplier, db_roles):
        """项目管理员可将用户角色修改为供应商管理员"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp_json, username, user_id = created_user(UserType.ORG_TEAM_MEMBER)
        assertion.assert_equal(resp_json.get("code"), 0, "PM创建成员失败")

        spadm_role_id = _find_role_id_by_user_type(db_roles, UserType.SUPPLIER_ADMIN)
        resp_json = self._update_as(
            pm_user,
            {"user_id": user_id, "username": username},
            role_id=spadm_role_id,
            supplier_id=shared_supplier,
            team_id=[]
        )
        _assert_update_success(resp_json, msg_prefix="PM修改角色为供应商管理员")

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_edit_user_role_to_org_team_admin(self, pm_user, created_user, org_team, db_roles):
        """项目管理员可将用户角色修改为项目直属团队管理员（不选供应商）"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp_json, username, user_id = created_user(UserType.ORG_TEAM_MEMBER, team_id=org_team)
        assertion.assert_equal(resp_json.get("code"), 0, "PM创建成员失败")

        team_admin_role_id = _find_role_id_by_user_type(db_roles, UserType.ORG_TEAM_ADMIN)
        resp_json = self._update_as(
            pm_user,
            {"user_id": user_id, "username": username},
            role_id=team_admin_role_id,
            team_id=[org_team]
        )
        _assert_update_success(resp_json, msg_prefix="PM修改角色为项目直属团队管理员")

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_edit_user_role_to_supplier_team_admin(self, pm_user, created_user, supplier_team, db_roles):
        """项目管理员可将用户角色修改为供应商团队管理员（选择供应商）"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp_json, username, user_id = created_user(UserType.ORG_TEAM_MEMBER)
        assertion.assert_equal(resp_json.get("code"), 0, "PM创建成员失败")

        team_admin_role_id = _find_role_id_by_user_type(db_roles, UserType.SUPPLIER_TEAM_ADMIN)
        resp_json = self._update_as(
            pm_user,
            {"user_id": user_id, "username": username},
            role_id=team_admin_role_id,
            supplier_id=supplier_team["supplier_id"],
            team_id=[supplier_team["id"]]
        )
        _assert_update_success(resp_json, msg_prefix="PM修改角色为供应商团队管理员")

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_edit_user_role_to_member(self, pm_user, created_user, org_team, db_roles):
        """项目管理员可将用户角色修改为普通用户"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp_json, username, user_id = created_user(UserType.ORG_TEAM_ADMIN, team_id=org_team)
        assertion.assert_equal(resp_json.get("code"), 0, "PM创建团队管理员失败")

        member_role_id = _find_role_id_by_user_type(db_roles, UserType.ORG_TEAM_MEMBER)
        resp_json = self._update_as(
            pm_user,
            {"user_id": user_id, "username": username},
            role_id=member_role_id,
            team_id=[org_team]
        )
        _assert_update_success(resp_json, msg_prefix="PM修改角色为普通用户")

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_cannot_change_target_organization(self, pm_user, spadm_user, another_org):
        """项目管理员编辑用户时传入错误组织id，后端应忽略并保持原组织不变"""
        spadm_ctx = _get_user_edit_context(spadm_user["user_id"])
        original_org = spadm_ctx["org_id"]
        resp_json = self._update_as(
            pm_user,
            spadm_user,
            username=spadm_ctx["username"],
            display_name=faker_data.random_name(pre="pm_chg_org"),
            organization_id=another_org,
            role_id=spadm_ctx["role_id"]
        )
        _assert_update_success(resp_json, msg_prefix="PM编辑用户传错组织id")
        data = resp_json.get("data", {})
        org = data.get("organization") or {}
        assertion.assert_equal(
            org.get("id"),
            original_org,
            "PM传入错误组织id后，用户组织应保持不变"
        )

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("user_type", [
        UserType.SYSTEM_ADMIN,
        UserType.PM,
    ])
    def test_pm_cannot_assign_admin_role(self, pm_user, spadm_user, db_roles, user_type):
        """项目管理员不能给用户分配系统管理员或项目管理员角色"""
        spadm_ctx = _get_user_edit_context(spadm_user["user_id"])
        role_code = USER_TYPE_ROLE_MAP[user_type]
        role_id = _find_role_id(db_roles, role_code)
        resp_json = self._update_as(
            pm_user,
            spadm_user,
            username=spadm_ctx["username"],
            role_id=role_id
        )
        _assert_update_fail(resp_json, msg_prefix=f"PM分配{user_type}角色应失败")

    # ======================== 供应商管理员编辑权限 ========================

    @pytest.mark.system
    @pytest.mark.api
    def test_spadm_can_edit_self(self, spadm_user):
        """供应商管理员编辑自己（实际权限：自己未被自己创建，应失败）"""
        resp_json = self._update_as(spadm_user, spadm_user, display_name=faker_data.random_name(pre="sp_self"))
        _assert_update_fail(resp_json, msg_prefix="供应商管理员编辑自己应失败")

    @pytest.mark.system
    @pytest.mark.api
    def test_spadm_can_edit_user_created_by_spadm(self, spadm_user, supplier_team_admin_user):
        """供应商管理员可以编辑自己创建的供应商团队管理员"""
        target_ctx = _get_user_edit_context(supplier_team_admin_user["user_id"])
        resp_json = self._update_as(spadm_user, supplier_team_admin_user, username=target_ctx["username"], display_name=faker_data.random_name(pre="sp_edit"))
        _assert_update_success(resp_json, msg_prefix="供应商管理员编辑同供应商团队管理员")

    @pytest.mark.system
    @pytest.mark.api
    def test_spadm_can_edit_same_supplier_member_not_created_by_spadm(self, spadm_user, supplier_team_member_user):
        """供应商管理员可以编辑同供应商下非自己创建的成员（需求）"""
        target_ctx = _get_user_edit_context(supplier_team_member_user["user_id"])
        resp_json = self._update_as(spadm_user, supplier_team_member_user, username=target_ctx["username"], display_name=faker_data.random_name(pre="sp_edit2"))
        _assert_update_success(resp_json, msg_prefix="供应商管理员编辑同供应商成员")

    @pytest.mark.system
    @pytest.mark.api
    def test_spadm_cannot_edit_other_supplier_admin(self, spadm_user, another_spadm_user):
        """供应商管理员不能编辑其他供应商的供应商管理员"""
        target_ctx = _get_user_edit_context(another_spadm_user["user_id"])
        resp_json = self._update_as(spadm_user, another_spadm_user, username=target_ctx["username"], display_name=faker_data.random_name(pre="sp_other"))
        _assert_update_fail(resp_json, msg_prefix="供应商管理员编辑其他供应商管理员应失败")

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("target_fixture", [
        "pm_user",
        "org_team_admin_user",
        "org_team_member_user",
    ])
    def test_spadm_cannot_edit_non_supplier_user(self, spadm_user, target_fixture, request):
        """供应商管理员不能编辑非自己供应商下的用户"""
        target_user = request.getfixturevalue(target_fixture)
        target_ctx = _get_user_edit_context(target_user["user_id"])
        resp_json = self._update_as(spadm_user, target_user, username=target_ctx["username"], display_name=faker_data.random_name(pre="sp_nosup"))
        _assert_update_fail(resp_json, msg_prefix=f"供应商管理员编辑非供应商用户{target_fixture}应失败")

    # ======================== 项目直属团队管理员编辑权限 ========================

    @pytest.mark.system
    @pytest.mark.api
    def test_org_team_admin_can_edit_self(self, org_team_admin_user):
        """项目直属团队管理员编辑自己（实际权限：自己未被自己创建，应失败）"""
        resp_json = self._update_as(org_team_admin_user, org_team_admin_user, display_name=faker_data.random_name(pre="orgt_self"))
        _assert_update_fail(resp_json, msg_prefix="项目直属团队管理员编辑自己应失败")

    @pytest.mark.system
    @pytest.mark.api
    def test_org_team_admin_can_edit_self_created_member(self, org_team_admin_user, org_team_member_user):
        """项目直属团队管理员可以编辑自己创建的团队成员"""
        target_ctx = _get_user_edit_context(org_team_member_user["user_id"])
        resp_json = self._update_as(org_team_admin_user, org_team_member_user, username=target_ctx["username"], display_name=faker_data.random_name(pre="orgt_edit"))
        _assert_update_success(resp_json, msg_prefix="项目直属团队管理员编辑自己创建的团队成员")

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("target_fixture", [
        "pm_user",
        "spadm_user",
        "supplier_team_admin_user",
        "supplier_team_member_user",
        "another_pm_in_same_org",
    ])
    def test_org_team_admin_cannot_edit_non_self_created_user(self, org_team_admin_user, target_fixture, request):
        """项目直属团队管理员不能编辑非自己创建的用户（同组织可查看）"""
        target_user = request.getfixturevalue(target_fixture)
        target_ctx = _get_user_edit_context(target_user["user_id"])
        resp_json = self._update_as(org_team_admin_user, target_user, username=target_ctx["username"], display_name=faker_data.random_name(pre="orgt_other"))
        _assert_update_fail(resp_json, msg_prefix=f"项目直属团队管理员编辑非自己创建用户{target_fixture}应失败")

    # ======================== 供应商团队管理员编辑权限 ========================

    @pytest.mark.system
    @pytest.mark.api
    def test_supplier_team_admin_can_edit_self(self, supplier_team_admin_user):
        """供应商团队管理员编辑自己（实际权限：自己未被自己创建，应失败）"""
        resp_json = self._update_as(supplier_team_admin_user, supplier_team_admin_user, display_name=faker_data.random_name(pre="supt_self"))
        _assert_update_fail(resp_json, msg_prefix="供应商团队管理员编辑自己应失败")

    @pytest.mark.system
    @pytest.mark.api
    def test_supplier_team_admin_can_edit_self_created_member(self, supplier_team_admin_user, supplier_team_member_user):
        """供应商团队管理员可以编辑自己创建的团队成员"""
        target_ctx = _get_user_edit_context(supplier_team_member_user["user_id"])
        resp_json = self._update_as(supplier_team_admin_user, supplier_team_member_user, username=target_ctx["username"], display_name=faker_data.random_name(pre="supt_edit"))
        _assert_update_success(resp_json, msg_prefix="供应商团队管理员编辑自己创建的团队成员")

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("target_fixture", [
        "pm_user",
        "spadm_user",
        "org_team_admin_user",
        "org_team_member_user",
    ])
    def test_supplier_team_admin_cannot_edit_non_self_created_user(self, supplier_team_admin_user, target_fixture, request):
        """供应商团队管理员不能编辑非自己创建的用户（同供应商可查看）"""
        target_user = request.getfixturevalue(target_fixture)
        target_ctx = _get_user_edit_context(target_user["user_id"])
        resp_json = self._update_as(supplier_team_admin_user, target_user, username=target_ctx["username"], display_name=faker_data.random_name(pre="supt_other"))
        _assert_update_fail(resp_json, msg_prefix=f"供应商团队管理员编辑非自己创建用户{target_fixture}应失败")

    # ======================== 系统管理员字段边界与异常 ========================

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("field,value", [
        ("display_name", ""),
        ("display_name", "a" * 21),
        pytest.param("phone", "1380013800", marks=pytest.mark.xfail(
            reason="后端尚未校验手机号长度/格式")),
        pytest.param("phone", "138001380000", marks=pytest.mark.xfail(
            reason="后端尚未校验手机号长度/格式")),
        pytest.param("phone", "12345678901", marks=pytest.mark.xfail(
            reason="后端尚未校验手机号长度/格式")),
        ("phone", "abc"),
        ("email", "invalid-email"),
        pytest.param("email", "a" * 40 + "@example.com", marks=pytest.mark.xfail(
            reason="后端尚未校验邮箱长度")),
        ("remark", "a" * 201),
    ])
    def test_update_user_field_invalid(self, as_admin, editable_admin, field, value):
        """编辑用户时非必填/可编辑字段非法应失败"""
        resp_json = _do_update_user(
            editable_admin["user_id"],
            organization_id=editable_admin["org_id"],
            role_id=editable_admin["role_id"],
            **{field: value}
        )
        _assert_update_fail(resp_json, msg_prefix=f"编辑字段[{field}]={value}")

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("username_value", [
        "",
        "a" * 21,
        "user_name",
        "user中文",
        "user@123",
    ])
    def test_update_user_username_invalid(self, as_admin, editable_admin, username_value):
        """编辑用户时账号非法应失败：空、超长、含特殊字符/中文"""
        resp_json = _do_update_user(
            editable_admin["user_id"],
            username=username_value,
            organization_id=editable_admin["org_id"],
            role_id=editable_admin["role_id"]
        )
        _assert_update_fail(resp_json, msg_prefix=f"编辑账号[{username_value}]")

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("password_value", [
        "a" * 7,
        "a" * 17,
        "onlyletters",
        "12345678",
    ])
    def test_update_user_password_invalid(self, as_admin, editable_admin, password_value):
        """编辑用户时密码非法应失败：长度不够、超长、纯字母、纯数字"""
        resp_json = _do_update_user(
            editable_admin["user_id"],
            username=editable_admin["username"],
            organization_id=editable_admin["org_id"],
            role_id=editable_admin["role_id"],
            password=password_value
        )
        _assert_update_fail(resp_json, msg_prefix=f"编辑密码长度/格式非法")

    @pytest.mark.system
    @pytest.mark.api
    def test_update_user_with_non_admin_role(self, as_admin, editable_admin, db_roles):
        """系统管理员编辑用户时传入非系统管理员角色应失败"""
        pm_role_id = _find_role_id(db_roles, "PM")
        resp_json = _do_update_user(
            editable_admin["user_id"],
            organization_id=editable_admin["org_id"],
            role_id=pm_role_id
        )
        _assert_update_fail(resp_json, msg_prefix="编辑用户角色为非系统管理员")

    @pytest.mark.system
    @pytest.mark.api
    def test_update_user_not_exist(self, as_admin, shared_org):
        """编辑不存在的用户应失败"""
        resp_json = _do_update_user(
            "00000000-0000-0000-0000-000000000000",
            username="notexistuser",
            organization_id=shared_org,
            display_name=faker_data.random_name(pre="notexist")
        )
        _assert_update_fail(resp_json, msg_prefix="编辑不存在的用户")

    @pytest.mark.system
    @pytest.mark.api
    def test_update_user_with_invalid_user_id(self, as_admin, shared_org):
        """使用非法user_id编辑用户应失败"""
        resp_json = _do_update_user(
            "invalid-user-id",
            username="invaliduser",
            organization_id=shared_org,
            display_name=faker_data.random_name(pre="invalid")
        )
        _assert_update_fail(resp_json, msg_prefix="非法user_id编辑用户")
