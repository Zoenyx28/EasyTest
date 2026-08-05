#!/usr/bin/env python3

import pytest

from api.apis.team_api import team_api
from api.apis.supplier_api import supplier_api
from api.apis.org_api import org_api
from api.apis.user_api import user_api
from api.apis.auth_api import login_as, login_with, auth_api
from config.settings import UserType, USER_TYPE_ROLE_MAP
from fixtures.api_fixture import _find_role_id, _do_create_user
from fixtures.api_helpers import get_list_items
from config.settings import DEFAULT_PASSWORD
from utils.generate_data import faker_data
from common.assert_util import assertion
from common.base_log import logger
from config.settings import TEST_ORG_DESCRIPTION


# ======================== 模块级辅助方法 ========================

def _create_team_as_pm(pm_user: dict, org_id: str, supplier_id: str = None,
                       admin_ids: list = None, member_ids: list = None,
                       name: str = None, description: str = None):
    """以PM身份创建团队，返回响应JSON与团队名称"""
    login_with(pm_user["username"], DEFAULT_PASSWORD)
    team_name = name or faker_data.random_name(pre="team")
    resp = team_api.create_team(
        name=team_name,
        org_id=org_id,
        supplier_id=supplier_id,
        admin_ids=admin_ids,
        member_ids=member_ids,
        description=description
    )
    return resp.json(), team_name


def _create_team_as_spadm(spadm_user: dict, org_id: str, supplier_id: str = None,
                          admin_ids: list = None, member_ids: list = None,
                          name: str = None, description: str = None):
    """以供应商管理员身份创建团队，返回响应JSON与团队名称"""
    login_with(spadm_user["username"], DEFAULT_PASSWORD)
    team_name = name or faker_data.random_name(pre="team")
    resp = team_api.create_team(
        name=team_name,
        org_id=org_id,
        supplier_id=supplier_id or spadm_user.get("supplier_id"),
        admin_ids=admin_ids,
        member_ids=member_ids,
        description=description
    )
    return resp.json(), team_name


def _assert_team_created(resp_json: dict, expected_name: str = None, msg_prefix: str = ""):
    """校验团队创建成功响应"""
    assertion.assert_equal(resp_json.get("code"), 0, f"{msg_prefix}创建团队应成功")
    data = resp_json.get("data")
    assertion.assert_is_not_none(data, f"{msg_prefix}响应data不能为空")
    if expected_name:
        assertion.assert_equal(data.get("name"), expected_name, f"{msg_prefix}团队名称不匹配")
    return data


def _assert_team_failed(resp_json: dict, expected_code: int, expected_msg: str):
    """校验团队操作失败响应"""
    assertion.assert_true(resp_json.get("code") == expected_code, "接口响应code有误")
    assertion.assert_true(resp_json.get("msg") == expected_msg, "接口错误提示信息有误")


# ======================== 模块级Fixture ========================

@pytest.fixture()
def spadm_user(shared_org, shared_supplier, pm_user, db_roles):
    """以PM身份创建供应商管理员"""
    login_with(pm_user["username"], DEFAULT_PASSWORD)
    resp_json, username, user_id = _do_create_user(
        UserType.SUPPLIER_ADMIN, shared_org, db_roles, supplier_id=shared_supplier["id"]
    )
    assertion.assert_equal(resp_json.get("code"), 0, "创建供应商管理员失败")
    return {
        "user_id": user_id,
        "username": username,
        "org_id": shared_org,
        "supplier_id": shared_supplier["id"]
    }


@pytest.fixture()
def org_team_admin_user(shared_org, pm_user, db_roles):
    """项目管理员创建的组织直属团队管理员"""
    login_with(pm_user["username"], DEFAULT_PASSWORD)
    resp = team_api.create_team(name=faker_data.random_name(pre="orgteam"), org_id=shared_org)
    assertion.assert_status_code(resp, 200)
    assertion.assert_equal(resp.json().get("code"), 0, "创建项目直属团队失败")
    team_id = resp.json().get("data", {}).get("id")
    resp_json, username, user_id = _do_create_user(
        UserType.ORG_TEAM_ADMIN, shared_org, db_roles, team_id=team_id
    )
    assertion.assert_equal(resp_json.get("code"), 0, "创建团队管理员失败")
    return {"user_id": user_id, "username": username, "org_id": shared_org, "team_id": team_id}


@pytest.fixture()
def supplier_team_admin_user(shared_org, shared_supplier, spadm_user, db_roles):
    """供应商管理员创建的供应商下团队管理员"""
    login_with(spadm_user["username"], DEFAULT_PASSWORD)
    resp = team_api.create_team(
        name=faker_data.random_name(pre="supteam"),
        org_id=shared_org,
        supplier_id=shared_supplier["id"]
    )
    assertion.assert_status_code(resp, 200)
    assertion.assert_equal(resp.json().get("code"), 0, "创建供应商团队失败")
    team_id = resp.json().get("data", {}).get("id")
    resp_json, username, user_id = _do_create_user(
        UserType.SUPPLIER_TEAM_ADMIN, shared_org, db_roles,
        team_id=team_id, supplier_id=shared_supplier["id"]
    )
    assertion.assert_equal(resp_json.get("code"), 0, "创建供应商团队管理员失败")
    return {
        "user_id": user_id,
        "username": username,
        "org_id": shared_org,
        "supplier_id": shared_supplier["id"],
        "team_id": team_id
    }


@pytest.fixture()
def org_member_user(shared_org, pm_user, db_roles):
    """项目管理员创建的组织直属成员"""
    login_with(pm_user["username"], DEFAULT_PASSWORD)
    resp_json, username, user_id = _do_create_user(
        UserType.ORG_TEAM_MEMBER, shared_org, db_roles
    )
    assertion.assert_equal(resp_json.get("code"), 0, "创建组织成员失败")
    return {"user_id": user_id, "username": username, "org_id": shared_org}


@pytest.fixture()
def org_team(shared_org, pm_user):
    """PM创建的直属团队"""
    resp_json, team_name = _create_team_as_pm(pm_user, shared_org)
    assertion.assert_equal(resp_json.get("code"), 0, "创建直属团队失败")
    team_id = resp_json.get("data", {}).get("id")
    return {"id": team_id, "name": team_name, "org_id": shared_org, "supplier_id": None}


@pytest.fixture()
def supplier_team(shared_org, shared_supplier, spadm_user):
    """供应商管理员创建的供应商团队"""
    resp_json, team_name = _create_team_as_spadm(spadm_user, shared_org)
    assertion.assert_equal(resp_json.get("code"), 0, "创建供应商团队失败")
    team_id = resp_json.get("data", {}).get("id")
    return {
        "id": team_id,
        "name": team_name,
        "org_id": shared_org,
        "supplier_id": shared_supplier["id"]
    }


@pytest.fixture()
def cross_org_pm(shared_org, db_roles):
    """同一组织下另一个PM用户"""
    login_as("admin")
    resp_json, username, user_id = _do_create_user(UserType.PM, shared_org, db_roles)
    assertion.assert_equal(resp_json.get("code"), 0, "创建同组织另一个PM失败")
    return {"user_id": user_id, "username": username, "org_id": shared_org}


@pytest.fixture()
def cross_org_supplier(shared_org, cross_org_pm):
    """同组织另一个PM创建的供应商"""
    login_with(cross_org_pm["username"], DEFAULT_PASSWORD)
    supplier_name = faker_data.random_name(pre="sup")
    resp = supplier_api.create_supplier(name=supplier_name, org_id=shared_org)
    assertion.assert_status_code(resp, 200)
    assertion.assert_equal(resp.json().get("code"), 0, "创建同组织另一个PM的供应商失败")
    supplier_id = resp.json().get("data", {}).get("id")
    return {"id": supplier_id, "name": supplier_name, "org_id": shared_org}


@pytest.fixture()
def cross_org_team(shared_org, cross_org_pm):
    """同组织另一个PM创建的直属团队"""
    resp_json, team_name = _create_team_as_pm(cross_org_pm, shared_org)
    assertion.assert_equal(resp_json.get("code"), 0, "创建同组织另一个PM的团队失败")
    team_id = resp_json.get("data", {}).get("id")
    return {"id": team_id, "name": team_name, "org_id": shared_org, "supplier_id": None}


# ======================== 权限测试 ========================

class TestTeamPermission:
    """团队管理权限测试"""

    @pytest.mark.system
    @pytest.mark.api
    def test_admin_can_view_team_menu(self, as_admin):
        """系统管理员可查看团队管理菜单/列表"""
        resp = team_api.get_team_list()
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "系统管理员应可查看团队列表")

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_view_team_menu(self, pm_user):
        """项目管理员可查看团队管理菜单/列表"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = team_api.get_team_list(org_id=pm_user["org_id"])
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "项目管理员应可查看团队列表")

    @pytest.mark.system
    @pytest.mark.api
    def test_spadm_can_view_team_menu(self, spadm_user):
        """供应商管理员可查看团队管理菜单/列表"""
        login_with(spadm_user["username"], DEFAULT_PASSWORD)
        resp = team_api.get_team_list(supplier_id=spadm_user["supplier_id"])
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "供应商管理员应可查看团队列表")

    @pytest.mark.system
    @pytest.mark.api
    def test_team_admin_can_view_team_menu(self, org_team_admin_user):
        """团队管理员可查看团队管理菜单/列表"""
        login_with(org_team_admin_user["username"], DEFAULT_PASSWORD)
        resp = team_api.get_team_list()
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "团队管理员应可查看团队列表")

    @pytest.mark.system
    @pytest.mark.api
    def test_member_cannot_view_team_menu(self, org_member_user):
        """普通成员不可查看团队管理菜单"""
        login_with(org_member_user["username"], DEFAULT_PASSWORD)
        resp = team_api.get_team_list()
        _assert_team_failed(resp.json(), 403, "当前角色权限不足")

    @pytest.mark.system
    @pytest.mark.api
    def test_admin_cannot_create_team(self, as_admin, shared_org):
        """系统管理员不可新增团队"""
        resp = team_api.create_team(
            name=faker_data.random_name(pre="team"),
            org_id=shared_org
        )
        _assert_team_failed(resp.json(), 403, "当前角色权限不足")

    @pytest.mark.system
    @pytest.mark.api
    def test_admin_cannot_update_team(self, as_admin, org_team):
        """系统管理员不可编辑团队"""
        login_as("admin")
        resp = team_api.update_team(
            team_id=org_team["id"],
            name=faker_data.random_name(pre="team")
        )
        _assert_team_failed(resp.json(), 403, "当前角色权限不足")

    @pytest.mark.system
    @pytest.mark.api
    def test_admin_cannot_toggle_team_status(self, as_admin, org_team):
        """系统管理员不可停用/启用团队"""
        login_as("admin")
        resp = team_api.toggle_team_status(team_id=org_team["id"])
        _assert_team_failed(resp.json(), 403, "当前角色权限不足")

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_create_org_team(self, pm_user, shared_org):
        """项目管理员可新增直属团队"""
        resp_json, team_name = _create_team_as_pm(pm_user, shared_org)
        _assert_team_created(resp_json, team_name)

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_create_supplier_team(self, pm_user, shared_org, shared_supplier):
        """项目管理员可新增供应商下团队"""
        resp_json, team_name = _create_team_as_pm(
            pm_user, shared_org, supplier_id=shared_supplier["id"]
        )
        _assert_team_created(resp_json, team_name)

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_view_all_teams_in_org(self, pm_user, org_team, supplier_team):
        """项目管理员可查看组织下所有团队（含供应商团队）"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = team_api.get_team_list(org_id=pm_user["org_id"])
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        items = get_list_items(resp_json)
        team_ids = [item.get("id") for item in items]
        assertion.assert_true(org_team["id"] in team_ids, "直属团队应在列表中")
        assertion.assert_true(supplier_team["id"] in team_ids, "供应商团队应在列表中")

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_edit_team_in_org(self, pm_user, cross_org_team):
        """项目管理员可编辑组织下团队"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        new_name = faker_data.random_name(pre="team")
        resp = team_api.update_team(team_id=cross_org_team["id"], name=new_name)
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "PM编辑组织下团队应成功")

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_toggle_team_in_org(self, pm_user, cross_org_team):
        """项目管理员可停用/启用组织下团队"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = team_api.toggle_team_status(team_id=cross_org_team["id"])
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "PM停用组织下团队应成功")

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_cannot_view_other_org_teams(self, pm_user, another_pm_user):
        """项目管理员不可查看其他组织团队"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = team_api.get_team_list(org_id=another_pm_user["org_id"])
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        items = get_list_items(resp_json)
        assertion.assert_equal(len(items), 0, "不应返回其他组织团队")

    @pytest.mark.system
    @pytest.mark.api
    def test_spadm_can_create_team(self, spadm_user, shared_org):
        """供应商管理员可新增团队"""
        resp_json, team_name = _create_team_as_spadm(spadm_user, shared_org)
        _assert_team_created(resp_json, team_name)

    @pytest.mark.system
    @pytest.mark.api
    def test_spadm_can_view_all_teams_in_supplier(self, spadm_user, supplier_team):
        """供应商管理员可查看供应商下所有团队"""
        login_with(spadm_user["username"], DEFAULT_PASSWORD)
        resp = team_api.get_team_list(supplier_id=spadm_user["supplier_id"])
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        items = get_list_items(resp_json)
        team_ids = [item.get("id") for item in items]
        assertion.assert_true(supplier_team["id"] in team_ids, "供应商团队应在列表中")

    @pytest.mark.system
    @pytest.mark.api
    def test_spadm_can_edit_team_in_supplier(self, spadm_user, supplier_team):
        """供应商管理员可编辑供应商下团队"""
        login_with(spadm_user["username"], DEFAULT_PASSWORD)
        new_name = faker_data.random_name(pre="team")
        resp = team_api.update_team(team_id=supplier_team["id"], name=new_name)
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "供应商管理员编辑供应商下团队应成功")

    @pytest.mark.system
    @pytest.mark.api
    def test_spadm_can_toggle_team_in_supplier(self, spadm_user, supplier_team):
        """供应商管理员可停用/启用供应商下团队"""
        login_with(spadm_user["username"], DEFAULT_PASSWORD)
        resp = team_api.toggle_team_status(team_id=supplier_team["id"])
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "供应商管理员停用供应商下团队应成功")

    @pytest.mark.system
    @pytest.mark.api
    def test_spadm_cannot_view_other_supplier_teams(self, spadm_user, cross_org_supplier):
        """供应商管理员不可查看其他供应商团队"""
        login_with(spadm_user["username"], DEFAULT_PASSWORD)
        resp = team_api.get_team_list(supplier_id=cross_org_supplier["id"])
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        items = get_list_items(resp_json)
        assertion.assert_equal(len(items), 0, "不应返回其他供应商团队")

    @pytest.mark.system
    @pytest.mark.api
    def test_team_admin_can_view_own_team(self, org_team_admin_user):
        """团队管理员可查看自己管理的团队"""
        login_with(org_team_admin_user["username"], DEFAULT_PASSWORD)
        resp = team_api.get_team_list()
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        items = get_list_items(resp_json)
        team_ids = [item.get("id") for item in items]
        assertion.assert_true(
            org_team_admin_user["team_id"] in team_ids,
            "自己管理的团队应在列表中"
        )

    @pytest.mark.system
    @pytest.mark.api
    def test_team_admin_can_edit_own_team(self, org_team_admin_user):
        """团队管理员可编辑自己管理的团队"""
        login_with(org_team_admin_user["username"], DEFAULT_PASSWORD)
        new_name = faker_data.random_name(pre="team")
        resp = team_api.update_team(team_id=org_team_admin_user["team_id"], name=new_name)
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "团队管理员编辑自己团队应成功")

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.xfail(reason="后端当前未限制团队管理员新增团队")
    def test_team_admin_cannot_create_team(self, org_team_admin_user, shared_org):
        """团队管理员不可新增团队"""
        login_with(org_team_admin_user["username"], DEFAULT_PASSWORD)
        resp = team_api.create_team(name=faker_data.random_name(pre="team"), org_id=shared_org)
        assertion.assert_status_code(resp, 403)

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.xfail(reason="后端当前未限制团队管理员停用/启用团队")
    def test_team_admin_cannot_toggle_team_status(self, org_team_admin_user):
        """团队管理员不可停用/启用团队"""
        login_with(org_team_admin_user["username"], DEFAULT_PASSWORD)
        resp = team_api.toggle_team_status(team_id=org_team_admin_user["team_id"])
        assertion.assert_status_code(resp, 403)


# ======================== 新增测试 ========================

class TestTeamCreate:
    """团队新增测试"""

    @pytest.mark.system
    @pytest.mark.api
    def test_create_org_team_with_required_name(self, pm_user, shared_org):
        """必填项名称正常新增直属团队"""
        resp_json, team_name = _create_team_as_pm(pm_user, shared_org)
        _assert_team_created(resp_json, team_name)

    @pytest.mark.system
    @pytest.mark.api
    def test_create_team_name_required(self, pm_user, shared_org):
        """团队名称必填校验"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = team_api.create_team(name="", org_id=shared_org)
        assertion.assert_equal(resp.json().get('code'),422,"接口返回的code有误")
        assertion.assert_contains(resp.json().get('msg'),'团队名称不能为空',"接口错误信息有误")

    @pytest.mark.system
    @pytest.mark.api
    def test_create_team_name_max_length(self, pm_user, shared_org):
        """团队名称20字边界"""
        name = faker_data.random_name(pre="m", max_length=20)
        resp_json, _ = _create_team_as_pm(pm_user, shared_org, name=name)
        _assert_team_created(resp_json, name)

    @pytest.mark.system
    @pytest.mark.api
    def test_create_team_name_over_max_length(self, pm_user, shared_org):
        """团队名称超长校验"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = team_api.create_team(name="a" * 21, org_id=shared_org)
        _assert_team_failed(resp.json(),422,'团队名称不能超过20字')

    @pytest.mark.system
    @pytest.mark.api
    def test_create_org_team_duplicate_name_same_org(self, pm_user, shared_org, org_team):
        """同组织直属团队名称重复校验"""
        resp_json, _ = _create_team_as_pm(pm_user, shared_org, name=org_team["name"])
        _assert_team_failed(resp_json,400,"同一组织下已存在同名团队")

    @pytest.mark.system
    @pytest.mark.api
    def test_create_supplier_team_duplicate_name_same_supplier(self, spadm_user, shared_org, supplier_team):
        """同供应商下团队名称重复校验"""
        resp_json, _ = _create_team_as_spadm(
            spadm_user, shared_org, supplier_id=supplier_team["supplier_id"], name=supplier_team["name"]
        )
        _assert_team_failed(resp_json,400,"同一供应商下已存在同名团队")

    @pytest.mark.system
    @pytest.mark.api
    def test_create_team_description_max_length(self, pm_user, shared_org):
        """团队描述200字边界"""
        description = "a" * 200
        resp_json, team_name = _create_team_as_pm(pm_user, shared_org, description=description)
        _assert_team_created(resp_json, team_name)

    @pytest.mark.system
    @pytest.mark.api
    def test_create_team_description_over_max_length(self, pm_user, shared_org):
        """团队描述超长校验"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = team_api.create_team(
            name=faker_data.random_name(pre="team"),
            org_id=shared_org,
            description="a" * 201
        )
        _assert_team_failed(resp.json(),422,'团队描述不能超过200字')

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_create_org_team_with_admins(self, pm_user, shared_org, org_team_admin_user):
        """项目管理员未选供应商时可选直属团队管理员"""
        resp_json, team_name = _create_team_as_pm(
            pm_user, shared_org, admin_ids=[org_team_admin_user["user_id"]]
        )
        _assert_team_created(resp_json, team_name)

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_create_supplier_team_with_admins(self, pm_user, shared_org, shared_supplier, supplier_team_admin_user):
        """项目管理员选择供应商后可选供应商下团队管理员"""
        resp_json, team_name = _create_team_as_pm(
            pm_user, shared_org, supplier_id=shared_supplier["id"],
            admin_ids=[supplier_team_admin_user["user_id"]]
        )
        _assert_team_created(resp_json, team_name)

    @pytest.mark.system
    @pytest.mark.api
    def test_spadm_create_team_with_admins(self, spadm_user, shared_org, supplier_team_admin_user):
        """供应商管理员新增团队可选供应商下团队管理员"""
        resp_json, team_name = _create_team_as_spadm(
            spadm_user, shared_org, admin_ids=[supplier_team_admin_user["user_id"]]
        )
        _assert_team_created(resp_json, team_name)

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_create_org_team_with_members(self, pm_user, shared_org, org_member_user):
        """项目管理员未选供应商时可选组织下所有人员"""
        resp_json, team_name = _create_team_as_pm(
            pm_user, shared_org, member_ids=[org_member_user["user_id"]]
        )
        _assert_team_created(resp_json, team_name)

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_create_supplier_team_with_members(self, pm_user, shared_org, shared_supplier, supplier_team_admin_user):
        """项目管理员选择供应商后可选供应商下所有人员"""
        resp_json, team_name = _create_team_as_pm(
            pm_user, shared_org, supplier_id=shared_supplier["id"],
            member_ids=[supplier_team_admin_user["user_id"]]
        )
        _assert_team_created(resp_json, team_name)

    @pytest.mark.system
    @pytest.mark.api
    def test_spadm_create_team_with_members(self, spadm_user, shared_org, supplier_team_admin_user):
        """供应商管理员新增团队可选供应商下所有人员"""
        resp_json, team_name = _create_team_as_spadm(
            spadm_user, shared_org, member_ids=[supplier_team_admin_user["user_id"]]
        )
        _assert_team_created(resp_json, team_name)


# ======================== 编辑测试 ========================

class TestTeamUpdate:
    """团队编辑测试"""

    @pytest.mark.system
    @pytest.mark.api
    def test_update_team_name_and_description(self, pm_user, org_team):
        """正常编辑团队名称和描述"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        new_name = faker_data.random_name(pre="team")
        new_desc = faker_data.random_name(pre="desc", max_length=50)
        resp = team_api.update_team(
            team_id=org_team["id"],
            name=new_name,
            description=new_desc
        )
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        assertion.assert_equal(resp_json.get("code"), 0, "编辑团队应成功")
        data = resp_json.get("data", {})
        assertion.assert_equal(data.get("name"), new_name)
        assertion.assert_equal(data.get("description"), new_desc)

    @pytest.mark.system
    @pytest.mark.api
    def test_update_team_duplicate_name_same_org(self, pm_user, org_team, cross_org_team):
        """编辑后同组织团队名称重复校验"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = team_api.update_team(team_id=org_team["id"], name=cross_org_team["name"])
        _assert_team_failed(resp.json(),400,"同一组织下已存在同名团队")

    @pytest.mark.system
    @pytest.mark.api
    def test_update_team_name_max_length(self, pm_user, org_team):
        """编辑团队名称20字边界"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        new_name = faker_data.random_name(pre="m", max_length=20)
        resp = team_api.update_team(team_id=org_team["id"], name=new_name)
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "编辑20字名称应成功")

    @pytest.mark.system
    @pytest.mark.api
    def test_update_team_name_over_max_length(self, pm_user, org_team):
        """编辑团队名称超长校验"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = team_api.update_team(team_id=org_team["id"], name="a" * 21)
        _assert_team_failed(resp.json(),422,'团队名称不能超过20字')

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.parametrize("description", ["a" * 200])
    def test_update_team_description_max_length(self, pm_user, org_team, description):
        """编辑团队描述200字边界"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = team_api.update_team(name=org_team["name"],team_id=org_team["id"], description=description)
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "编辑200字描述应成功")
        assertion.assert_equal(resp.json().get("data").get("description"), description, "描述内容应与输入一致")


# ======================== 停用/启用测试 ========================

class TestTeamToggleStatus:
    """团队停用/启用测试"""

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_disable_org_team(self, pm_user, org_team):
        """项目管理员可停用组织下团队"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = team_api.toggle_team_status(team_id=org_team["id"])
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        assertion.assert_equal(resp_json.get("code"), 0, "停用团队应成功")
        data = resp_json.get("data", {})
        assertion.assert_equal(data.get("is_active"), False, "团队状态应为停用")

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_enable_disabled_org_team(self, pm_user, org_team):
        """项目管理员可启用已停用的组织下团队"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        team_api.toggle_team_status(team_id=org_team["id"])
        resp = team_api.toggle_team_status(team_id=org_team["id"])
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        assertion.assert_equal(resp_json.get("code"), 0, "启用团队应成功")
        data = resp_json.get("data", {})
        assertion.assert_equal(data.get("is_active"), True, "团队状态应为启用")


# ======================== 列表测试 ========================

class TestTeamList:
    """团队列表测试"""

    @pytest.mark.system
    @pytest.mark.api
    def test_team_list_fields(self, pm_user, org_team):
        """列表展示字段完整"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = team_api.get_team_list(org_id=pm_user["org_id"])
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        assertion.assert_equal(resp_json.get("code"), 0, "查询团队列表失败")
        items = get_list_items(resp_json)
        assertion.assert_true(len(items) > 0, "列表应返回团队数据")
        item = items[0]
        expected_fields = {
            "id": "ID",
            "name": "团队名称",
            "description": "团队描述",
            "organization_id": "所属组织ID",
            "supplier_id": "所属供应商ID",
            "is_active": "团队状态",
            "admin_list": "团队管理员",
            "member_count": "团队成员数",
            "created_by": "创建人",
        }
        for field, label in expected_fields.items():
            assertion.assert_true(field in item, f"列表缺少{label}字段: {field}")

    @pytest.mark.system
    @pytest.mark.api
    def test_team_list_active_first(self, pm_user, shared_org):
        """已启用团队排在停用团队前面"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp_json1, _ = _create_team_as_pm(pm_user, shared_org)
        team1_id = resp_json1["data"]["id"]
        resp_json2, _ = _create_team_as_pm(pm_user, shared_org)
        team2_id = resp_json2["data"]["id"]
        team_api.toggle_team_status(team_id=team2_id)

        resp = team_api.get_team_list(org_id=pm_user["org_id"], page_size=100)
        resp_json = resp.json()
        items = get_list_items(resp_json)
        active_index = None
        disabled_index = None
        for idx, item in enumerate(items):
            if item.get("id") == team1_id:
                active_index = idx
            if item.get("id") == team2_id:
                disabled_index = idx
        assertion.assert_is_not_none(active_index, "启用团队应在列表中")
        assertion.assert_is_not_none(disabled_index, "停用团队应在列表中")
        assertion.assert_true(active_index < disabled_index, "启用团队应排在停用团队前面")

    @pytest.mark.system
    @pytest.mark.api
    def test_team_list_sorted_by_created_at_desc(self, pm_user, shared_org):
        """按创建时间倒序"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp_json1, _ = _create_team_as_pm(pm_user, shared_org)
        team1_id = resp_json1["data"]["id"]
        resp_json2, _ = _create_team_as_pm(pm_user, shared_org)
        team2_id = resp_json2["data"]["id"]

        resp = team_api.get_team_list(org_id=pm_user["org_id"], page_size=100)
        resp_json = resp.json()
        items = get_list_items(resp_json)
        id_order = [item.get("id") for item in items]
        idx1 = id_order.index(team1_id) if team1_id in id_order else None
        idx2 = id_order.index(team2_id) if team2_id in id_order else None
        assertion.assert_is_not_none(idx1)
        assertion.assert_is_not_none(idx2)
        assertion.assert_true(idx2 < idx1, "后创建的团队应排在前面")

    @pytest.mark.system
    @pytest.mark.api
    def test_team_list_filter_by_name(self, pm_user, shared_org):
        """按名称查询团队"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp_json, name = _create_team_as_pm(pm_user, shared_org)
        team_id = resp_json["data"]["id"]

        resp = team_api.get_team_list(org_id=pm_user["org_id"], name=name)
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        items = get_list_items(resp_json)
        ids = [item.get("id") for item in items]
        assertion.assert_true(team_id in ids, "按名称查询应返回目标团队")

    @pytest.mark.system
    @pytest.mark.api
    def test_team_list_filter_by_status(self, pm_user, shared_org):
        """按状态查询团队"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp_json, _ = _create_team_as_pm(pm_user, shared_org)
        team_id = resp_json["data"]["id"]
        team_api.toggle_team_status(team_id=team_id)

        resp = team_api.get_team_list(org_id=pm_user["org_id"], is_active=False)
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        items = get_list_items(resp_json)
        for item in items:
            assertion.assert_equal(item.get("is_active"), False, "按停用状态查询应仅返回停用团队")
