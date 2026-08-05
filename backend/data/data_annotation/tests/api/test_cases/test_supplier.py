import pytest

from api.apis.supplier_api import supplier_api
from api.apis.org_api import org_api
from api.apis.user_api import user_api
from api.apis.auth_api import login_as, login_with, auth_api
from config.settings import UserType, USER_TYPE_ROLE_MAP, DEFAULT_PASSWORD, TEST_ORG_DESCRIPTION
from fixtures.api_fixture import _find_role_id, _do_create_user
from fixtures.api_helpers import get_list_items
from utils.generate_data import faker_data
from common.assert_util import assertion
from common.base_log import logger


# ======================== 模块级辅助方法 ========================

def _create_supplier_as_pm(pm_user: dict, org_id: str, name: str = None, description: str = None):
    """以PM身份创建供应商，返回响应JSON"""
    login_with(pm_user["username"], DEFAULT_PASSWORD)
    supplier_name = name or faker_data.random_name(pre="sup")
    resp = supplier_api.create_supplier(
        name=supplier_name,
        org_id=org_id,
        description=description
    )
    return resp.json(), supplier_name


def _assert_supplier_created(resp_json: dict, expected_name: str = None, msg_prefix: str = ""):
    """校验供应商创建成功响应"""
    assertion.assert_equal(resp_json.get("code"), 0, f"{msg_prefix}创建供应商应成功")
    data = resp_json.get("data")
    assertion.assert_is_not_none(data, f"{msg_prefix}响应data不能为空")
    if expected_name:
        assertion.assert_equal(data.get("name"), expected_name, f"{msg_prefix}供应商名称不匹配")
    return data


def _assert_supplier_failed(resp_json: dict, msg_prefix: str = ""):
    """校验供应商操作失败响应"""
    assertion.assert_true(resp_json.get("code") != 0, f"{msg_prefix}操作应失败")


def _get_current_user_org() -> str:
    """获取当前登录用户的组织ID"""
    resp = auth_api.get_current_user()
    assertion.assert_status_code(resp, 200)
    resp_json = resp.json()
    assertion.assert_equal(resp_json.get("code"), 0, "获取当前用户信息失败")
    data = resp_json.get("data", {})
    organization = data.get("organization") or {}
    return organization.get("id")


def _get_supplier_status(supplier_id: str) -> bool:
    """获取供应商当前启用状态"""
    resp = supplier_api.get_supplier_list()
    assertion.assert_status_code(resp, 200)
    resp_json = resp.json()
    assertion.assert_equal(resp_json.get("code"), 0, "查询供应商列表失败")
    items = get_list_items(resp_json)
    for item in items:
        if item.get("id") == supplier_id:
            return item.get("is_active", True)
    pytest.fail(f"未找到供应商 {supplier_id}")


# ======================== 模块级Fixture ========================

@pytest.fixture()
def cross_org_pm(shared_org, db_roles):
    """同一组织下另一个PM用户（由admin创建）"""
    login_as("admin")
    resp_json, username, user_id = _do_create_user(UserType.PM, shared_org, db_roles)
    assertion.assert_equal(resp_json.get("code"), 0, "创建同组织另一个PM失败")
    return {"user_id": user_id, "username": username, "org_id": shared_org}


@pytest.fixture()
def cross_org_supplier(shared_org, cross_org_pm):
    """同一组织下由另一个PM创建的供应商"""
    resp_json, supplier_name = _create_supplier_as_pm(cross_org_pm, shared_org)
    assertion.assert_equal(resp_json.get("code"), 0, "创建同组织另一个PM的供应商失败")
    data = resp_json.get("data", {})
    supplier_id = data.get("id")
    logger.info(f"同组织跨PM供应商创建成功: {supplier_id}")
    return {
        "id": supplier_id,
        "name": supplier_name,
        "org_id": shared_org,
        "created_by": cross_org_pm["username"]
    }


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
def supplier_member_user(shared_org, shared_supplier, spadm_user, db_roles):
    """以供应商管理员身份创建供应商团队成员"""
    login_with(spadm_user["username"], DEFAULT_PASSWORD)
    resp_json, username, user_id = _do_create_user(
        UserType.SUPPLIER_TEAM_MEMBER, shared_org, db_roles, supplier_id=shared_supplier["id"]
    )
    assertion.assert_equal(resp_json.get("code"), 0, "创建供应商成员失败")
    return {
        "user_id": user_id,
        "username": username,
        "org_id": shared_org,
        "supplier_id": shared_supplier["id"]
    }


@pytest.fixture()
def org_team_admin_user(shared_org, pm_user, db_roles):
    """用于权限菜单验证的非PM/非系统管理员账号"""
    from api.apis.team_api import team_api
    login_with(pm_user["username"], DEFAULT_PASSWORD)
    resp = team_api.create_team(name=faker_data.random_name(pre="orgteam"), org_id=shared_org)
    assertion.assert_status_code(resp, 200)
    assertion.assert_equal(resp.json().get("code"), 0, "创建项目直属团队失败")
    team_id = resp.json().get("data", {}).get("id")
    resp_json, username, user_id = _do_create_user(
        UserType.ORG_TEAM_ADMIN, shared_org, db_roles, team_id=team_id
    )
    assertion.assert_equal(resp_json.get("code"), 0, "创建团队管理员失败")
    return {"user_id": user_id, "username": username, "org_id": shared_org}


# ======================== 权限测试 ========================

class TestSupplierPermission:
    """供应商管理权限测试"""

    @pytest.mark.system
    @pytest.mark.api
    def test_admin_can_view_supplier_menu(self, as_admin):
        """系统管理员可查看供应商管理菜单/列表"""
        resp = supplier_api.get_supplier_list()
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "系统管理员应可查看供应商列表")

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_view_supplier_menu(self, pm_user):
        """项目管理员可查看供应商管理菜单/列表"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = supplier_api.get_supplier_list(org_id=pm_user["org_id"])
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "项目管理员应可查看供应商列表")

    @pytest.mark.system
    @pytest.mark.api
    def test_org_team_admin_cannot_view_supplier_menu(self, org_team_admin_user):
        """非PM/非系统管理员角色不可查看供应商管理菜单"""
        login_with(org_team_admin_user["username"], DEFAULT_PASSWORD)
        resp = supplier_api.get_supplier_list()
        assertion.assert_equal(resp.json().get('code'),403,"接口返回code有误")
        assertion.assert_equal(resp.json().get('msg'),'当前角色权限不足',"接口报错提示信息有误")

    @pytest.mark.system
    @pytest.mark.api
    def test_admin_cannot_create_supplier(self, as_admin, shared_org):
        """系统管理员不可新增供应商"""
        resp = supplier_api.create_supplier(
            name=faker_data.random_name(pre="sup"),
            org_id=shared_org,
            description="系统管理员创建"
        )
        assertion.assert_equal(resp.json().get('code'), 403,"接口响应状态码错误")

    @pytest.mark.system
    @pytest.mark.api
    def test_admin_cannot_update_supplier(self, as_admin, shared_supplier):
        """系统管理员不可编辑供应商"""
        login_as("admin")
        resp = supplier_api.update_supplier(
            supplier_id=shared_supplier["id"],
            name=faker_data.random_name(pre="sup")
        )
        assertion.assert_equal(resp.json().get('code'), 403,"接口响应状态码错误")
        assertion.assert_equal(resp.json().get('msg'),'系统管理员不能编辑供应商',"接口报错提示信息有误")

    @pytest.mark.system
    @pytest.mark.api
    def test_admin_cannot_toggle_supplier_status(self, as_admin, shared_supplier):
        """系统管理员不可禁用/启用供应商"""
        login_as("admin")
        resp = supplier_api.toggle_supplier_status(supplier_id=shared_supplier["id"])
        assertion.assert_equal(resp.json().get('code'), 403,"接口响应状态码错误")
        assertion.assert_equal(resp.json().get('msg'),'系统管理员不能启禁供应商',"接口报错提示信息有误")

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_create_supplier(self, pm_user, shared_org):
        """项目管理员可新增供应商"""
        resp_json, supplier_name = _create_supplier_as_pm(pm_user, shared_org)
        _assert_supplier_created(resp_json, supplier_name)

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_only_view_own_org_suppliers(self, pm_user, shared_supplier, another_supplier):
        """项目管理员仅能查看自己关联组织下的供应商"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = supplier_api.get_supplier_list(org_id=pm_user["org_id"])
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        assertion.assert_equal(resp_json.get("code"), 0, "查询供应商列表失败")
        items = get_list_items(resp_json)
        supplier_ids = [item.get("id") for item in items]
        assertion.assert_true(
            shared_supplier["id"] in supplier_ids,
            "当前组织供应商应出现在列表中"
        )
        assertion.assert_true(
            another_supplier["id"] not in supplier_ids,
            "跨组织供应商不应出现在列表中"
        )

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_view_supplier_created_by_other_pm(self, pm_user, cross_org_supplier):
        """项目管理员可查看非自己创建的同组织供应商"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = supplier_api.get_supplier_list(org_id=pm_user["org_id"])
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        items = get_list_items(resp_json)
        supplier_ids = [item.get("id") for item in items]
        assertion.assert_true(
            cross_org_supplier["id"] in supplier_ids,
            "同组织其他PM创建的供应商应可查看"
        )

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_edit_own_supplier(self, pm_user, shared_supplier):
        """项目管理员可编辑自己创建的供应商"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        new_name = faker_data.random_name(pre="sup_edit")
        new_desc = faker_data.random_name(pre="desc", max_length=50)
        resp = supplier_api.update_supplier(
            supplier_id=shared_supplier["id"],
            name=new_name,
            description=new_desc
        )
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        assertion.assert_equal(resp_json.get("code"), 0, "编辑自己创建的供应商应成功")
        data = resp_json.get("data", {})
        assertion.assert_equal(data.get("name"), new_name, "供应商名称应更新")
        assertion.assert_equal(data.get("description"), new_desc, "供应商描述应更新")

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_cannot_edit_supplier_created_by_other_pm(self, pm_user, cross_org_supplier):
        """项目管理员不可编辑非自己创建的供应商"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = supplier_api.update_supplier(
            supplier_id=cross_org_supplier["id"],
            name=faker_data.random_name(pre="sup_hack")
        )
        assertion.assert_equal(resp.json().get('code'), 403)

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_toggle_own_supplier(self, pm_user, shared_supplier):
        """项目管理员可禁用/启用自己创建的供应商"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = supplier_api.toggle_supplier_status(supplier_id=shared_supplier["id"])
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        assertion.assert_equal(resp_json.get("code"), 0, "切换自己创建的供应商状态应成功")

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_cannot_toggle_supplier_created_by_other_pm(self, pm_user, cross_org_supplier):
        """项目管理员不可禁用/启用非自己创建的供应商"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = supplier_api.toggle_supplier_status(supplier_id=cross_org_supplier["id"])
        assertion.assert_equal(resp.json().get('code'),403,'接口返回code不准确')


# ======================== 新增测试 ========================

class TestSupplierCreate:
    """供应商新增测试"""

    @pytest.mark.system
    @pytest.mark.api
    def test_create_supplier_with_required_name(self, pm_user, shared_org):
        """必填项名称正常新增"""
        resp_json, supplier_name = _create_supplier_as_pm(pm_user, shared_org)
        _assert_supplier_created(resp_json, supplier_name)

    @pytest.mark.system
    @pytest.mark.api
    def test_create_supplier_name_required(self, pm_user, shared_org):
        """供应商名称必填校验"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = supplier_api.create_supplier(name="", org_id=shared_org)
        assertion.assert_equal(resp.json().get('code'), 422,"接口返回code错误")
        assertion.assert_contains(resp.json().get('msg', ''),'供应商名称不能为空',"接口报错提示信息有误")

    @pytest.mark.system
    @pytest.mark.api
    def test_create_supplier_duplicate_name_same_org(self, pm_user, shared_org, shared_supplier):
        """同组织下供应商名称不可重复"""
        resp_json, _ = _create_supplier_as_pm(pm_user, shared_org, name=shared_supplier["name"])
        assertion.assert_equal(resp_json.get('code'), 409, '接口响应code有误')
        assertion.assert_contains(resp_json.get('msg', ''),'同一组织下供应商名称已存在',"接口报错提示信息有误")

    @pytest.mark.system
    @pytest.mark.api
    def test_create_supplier_same_name_different_org(self, pm_user, shared_org, another_org, another_supplier):
        """不同组织下供应商名称可重复"""
        resp_json, _ = _create_supplier_as_pm(pm_user, shared_org, name=another_supplier["name"])
        _assert_supplier_created(resp_json, another_supplier["name"])

    @pytest.mark.system
    @pytest.mark.api
    def test_create_supplier_name_max_length(self, pm_user, shared_org):
        """供应商名称20字边界"""
        name = faker_data.random_name(pre="m", max_length=20)
        resp_json, _ = _create_supplier_as_pm(pm_user, shared_org, name=name)
        _assert_supplier_created(resp_json, name)

    @pytest.mark.system
    @pytest.mark.api
    def test_create_supplier_name_over_max_length(self, pm_user, shared_org):
        """供应商名称超长校验"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = supplier_api.create_supplier(name="a" * 21, org_id=shared_org)
        assertion.assert_equal(resp.json().get('code'),422,'接口响应的code错误')
        assertion.assert_equal(resp.json().get('msg'),'供应商名称不能超过20字','接口错误提示信息有误')

    @pytest.mark.system
    @pytest.mark.api
    def test_create_supplier_description_max_length(self, pm_user, shared_org):
        """供应商描述200字边界"""
        description = "a" * 200
        resp_json, supplier_name = _create_supplier_as_pm(pm_user, shared_org, description=description)
        _assert_supplier_created(resp_json, supplier_name)

    @pytest.mark.system
    @pytest.mark.api
    def test_create_supplier_description_over_max_length(self, pm_user, shared_org):
        """供应商描述超长校验"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = supplier_api.create_supplier(
            name=faker_data.random_name(pre="sup"),
            org_id=shared_org,
            description="a" * 201
        )
        assertion.assert_equal(resp.json().get('code'),422,'接口响应的code错误')
        assertion.assert_equal(resp.json().get('msg'),'供应商描述不能超过200字','接口错误提示信息有误')


# ======================== 编辑测试 ========================

class TestSupplierUpdate:
    """供应商编辑测试"""

    @pytest.mark.system
    @pytest.mark.api
    def test_update_supplier_name_and_description(self, pm_user, shared_supplier):
        """正常编辑名称和描述"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        new_name = faker_data.random_name(pre="sup_edit")
        new_desc = faker_data.random_name(pre="desc", max_length=50)
        resp = supplier_api.update_supplier(
            supplier_id=shared_supplier["id"],
            name=new_name,
            description=new_desc
        )
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        assertion.assert_equal(resp_json.get("code"), 0, "编辑供应商应成功")
        data = resp_json.get("data", {})
        assertion.assert_equal(data.get("name"), new_name)
        assertion.assert_equal(data.get("description"), new_desc)

    @pytest.mark.system
    @pytest.mark.api
    def test_update_supplier_duplicate_name_same_org(self, pm_user, shared_supplier, cross_org_supplier):
        """编辑后同组织名称重复校验"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = supplier_api.update_supplier(
            supplier_id=shared_supplier["id"],
            name=cross_org_supplier["name"]
        )
        assertion.assert_equal(resp.json().get('code'), 409, '接口响应code有误')
        assertion.assert_contains(resp.json().get('msg', ''),'同一组织下供应商名称已存在',"接口报错提示信息有误")

    @pytest.mark.system
    @pytest.mark.api
    def test_update_supplier_name_max_length(self, pm_user, shared_supplier):
        """编辑名称20字边界"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        new_name = faker_data.random_name(pre="m", max_length=20)
        resp = supplier_api.update_supplier(
            supplier_id=shared_supplier["id"],
            name=new_name
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "编辑20字名称应成功")

    @pytest.mark.system
    @pytest.mark.api
    def test_update_supplier_name_over_max_length(self, pm_user, shared_supplier):
        """编辑名称超长校验"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = supplier_api.update_supplier(
            supplier_id=shared_supplier["id"],
            name="a" * 21
        )
        assertion.assert_equal(resp.json().get('code'),422,'接口响应的code错误')
        assertion.assert_contains(resp.json().get('msg', ''),'供应商名称不能超过20字','接口错误提示信息有误')

    @pytest.mark.system
    @pytest.mark.api
    def test_update_supplier_description_max_length(self, pm_user, shared_supplier):
        """编辑描述200字边界"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = supplier_api.update_supplier(
            supplier_id=shared_supplier["id"],
            description="a" * 200
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "编辑200字描述应成功")


# ======================== 启用/禁用测试 ========================

class TestSupplierToggleStatus:
    """供应商启用/禁用测试"""

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_disable_own_supplier(self, pm_user, shared_supplier):
        """项目管理员可禁用自己创建的供应商"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = supplier_api.toggle_supplier_status(supplier_id=shared_supplier["id"])
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        assertion.assert_equal(resp_json.get("code"), 0, "禁用供应商应成功")
        data = resp_json.get("data", {})
        assertion.assert_equal(data.get("is_active"), False, "供应商状态应为禁用")

    @pytest.mark.system
    @pytest.mark.api
    def test_pm_can_enable_disabled_supplier(self, pm_user, shared_supplier):
        """项目管理员可启用已禁用的供应商"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        # 先禁用
        resp = supplier_api.toggle_supplier_status(supplier_id=shared_supplier["id"])
        assertion.assert_equal(resp.json().get("code"), 0, "禁用供应商失败")
        # 再启用
        resp = supplier_api.toggle_supplier_status(supplier_id=shared_supplier["id"])
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        assertion.assert_equal(resp_json.get("code"), 0, "启用供应商应成功")
        data = resp_json.get("data", {})
        assertion.assert_equal(data.get("is_active"), True, "供应商状态应为启用")

    @pytest.mark.system
    @pytest.mark.api
    def test_disabled_supplier_user_cannot_login(self, pm_user, shared_supplier, supplier_member_user):
        """禁用后供应商下的用户无法登录"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = supplier_api.toggle_supplier_status(supplier_id=shared_supplier["id"])
        assertion.assert_equal(resp.json().get("code"), 0, "禁用供应商失败")

        resp = auth_api.login(username=supplier_member_user["username"], password=DEFAULT_PASSWORD)
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        assertion.assert_equal(resp_json.get("code"), 403, "被禁用供应商下用户登录应返回403")
        assertion.assert_equal(
            resp_json.get("msg", ""),"归属供应商已禁用，无权限登录","登录提示词错误"
        )

    @pytest.mark.system
    @pytest.mark.api
    def test_enabled_supplier_user_can_login(self, pm_user, shared_supplier, supplier_member_user):
        """启用后供应商下的用户可正常登录"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        # 先禁用再启用
        resp = supplier_api.toggle_supplier_status(supplier_id=shared_supplier["id"])
        assertion.assert_equal(resp.json().get("code"), 0, "禁用供应商失败")
        resp = supplier_api.toggle_supplier_status(supplier_id=shared_supplier["id"])
        assertion.assert_equal(resp.json().get("code"), 0, "启用供应商失败")

        resp = auth_api.login(username=supplier_member_user["username"], password=DEFAULT_PASSWORD)
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "启用后供应商下用户应可登录")


# ======================== 列表测试 ========================

class TestSupplierList:
    """供应商列表测试"""

    @pytest.mark.system
    @pytest.mark.api
    def test_supplier_list_fields(self, pm_user, shared_supplier):
        """列表展示字段完整"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = supplier_api.get_supplier_list(org_id=pm_user["org_id"])
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        assertion.assert_equal(resp_json.get("code"), 0, "查询供应商列表失败")
        items = get_list_items(resp_json)
        assertion.assert_true(len(items) > 0, "列表应返回供应商数据")
        item = items[0]
        expected_fields = {
            "id": "ID",
            "name": "供应商名称",
            "description": "供应商描述",
            "organization_id": "所属组织ID",
            "organization_name": "所属组织名称",
            "is_active": "供应商状态",
            "admin_list": "供应商管理员",
            "created_by": "创建人",
            "member_count": "供应商成员数",
        }
        for field, label in expected_fields.items():
            assertion.assert_true(field in item, f"列表缺少{label}字段: {field}")

    @pytest.mark.system
    @pytest.mark.api
    def test_supplier_list_active_first(self, pm_user, shared_org):
        """已启用供应商排在禁用供应商前面"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        # 创建两个供应商，一个启用一个禁用
        resp_json1, name1 = _create_supplier_as_pm(pm_user, shared_org)
        supplier1_id = resp_json1["data"]["id"]
        resp_json2, name2 = _create_supplier_as_pm(pm_user, shared_org)
        supplier2_id = resp_json2["data"]["id"]
        # 禁用第二个
        supplier_api.toggle_supplier_status(supplier_id=supplier2_id)

        resp = supplier_api.get_supplier_list(org_id=pm_user["org_id"], page_size=100)
        resp_json = resp.json()
        items = get_list_items(resp_json)
        active_index = None
        disabled_index = None
        for idx, item in enumerate(items):
            if item.get("id") == supplier1_id:
                active_index = idx
            if item.get("id") == supplier2_id:
                disabled_index = idx
        assertion.assert_is_not_none(active_index, "启用供应商应在列表中")
        assertion.assert_is_not_none(disabled_index, "禁用供应商应在列表中")
        assertion.assert_true(active_index < disabled_index, "启用供应商应排在禁用供应商前面")

    @pytest.mark.system
    @pytest.mark.api
    def test_supplier_list_sorted_by_created_at_desc(self, pm_user, shared_org):
        """按创建时间倒序"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        # 创建两个供应商
        resp_json1, _ = _create_supplier_as_pm(pm_user, shared_org)
        supplier1_id = resp_json1["data"]["id"]
        resp_json2, _ = _create_supplier_as_pm(pm_user, shared_org)
        supplier2_id = resp_json2["data"]["id"]

        resp = supplier_api.get_supplier_list(org_id=pm_user["org_id"], page_size=100)
        resp_json = resp.json()
        items = get_list_items(resp_json)
        id_order = [item.get("id") for item in items]
        idx1 = id_order.index(supplier1_id) if supplier1_id in id_order else None
        idx2 = id_order.index(supplier2_id) if supplier2_id in id_order else None
        assertion.assert_is_not_none(idx1)
        assertion.assert_is_not_none(idx2)
        assertion.assert_true(idx2 < idx1, "后创建的供应商应排在前面")

    @pytest.mark.system
    @pytest.mark.api
    def test_supplier_list_filter_by_name(self, pm_user, shared_org):
        """按名称查询供应商"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp_json, name = _create_supplier_as_pm(pm_user, shared_org)
        supplier_id = resp_json["data"]["id"]

        resp = supplier_api.get_supplier_list(org_id=pm_user["org_id"], name=name)
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        items = get_list_items(resp_json)
        ids = [item.get("id") for item in items]
        assertion.assert_true(supplier_id in ids, "按名称查询应返回目标供应商")

    @pytest.mark.system
    @pytest.mark.api
    def test_supplier_list_filter_by_status(self, pm_user, shared_org):
        """按状态查询供应商"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp_json, _ = _create_supplier_as_pm(pm_user, shared_org)
        supplier_id = resp_json["data"]["id"]
        supplier_api.toggle_supplier_status(supplier_id=supplier_id)

        resp = supplier_api.get_supplier_list(org_id=pm_user["org_id"], is_active=False)
        assertion.assert_status_code(resp, 200)
        resp_json = resp.json()
        items = get_list_items(resp_json)
        for item in items:
            assertion.assert_equal(item.get("is_active"), False, "按禁用状态查询应仅返回禁用供应商")
