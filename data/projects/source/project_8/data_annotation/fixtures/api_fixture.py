"""测试用例公共 Fixtures 与用户创建工厂方法

说明：
- 包含数据库角色查询、组织/用户/团队/供应商的公共 fixture
- 包含 _do_create_user / _find_role_id / _assert_user_match 等用户创建辅助方法
- 测试文件通过 ``from fixtures.api_fixture import ...`` 导入所需 fixture
"""
import pytest

from api.apis.auth_api import login_as, login_with
from api.apis.dataset_api import dataset_api
from api.apis.org_api import org_api
from api.apis.supplier_api import supplier_api
from api.apis.team_api import team_api
from api.apis.user_api import user_api
from common.assert_util import assertion
from common.base_log import logger
from common.db_util import pg_db
from config.settings import DEFAULT_PASSWORD
from config.settings import UserType, USER_TYPE_ROLE_MAP
from config.settings import TEST_ORG_DESCRIPTION
from utils.generate_data import faker_data


# ======================== 用户创建辅助方法 ========================

def _find_role_id(db_roles, role_code: str) -> str:
    """根据角色编码查找角色ID"""
    for role in db_roles:
        if role["code"] == role_code:
            return role["id"]
    pytest.fail(f"未找到角色编码为 [{role_code}] 的角色")


def _do_create_user(user_type: str, org_id: str, db_roles, team_id: str = None, supplier_id: str = None):
    """
    执行创建用户请求，返回(响应JSON, 用户名, 用户ID)
    根据用户类型自动计算需要传入的 role_id / team_id / supplier_id
    """
    role_code = USER_TYPE_ROLE_MAP.get(user_type)
    if not role_code:
        pytest.fail(f"未知用户类型: {user_type}")

    role_id = _find_role_id(db_roles, role_code)
    username = faker_data.random_username(pre=f"{role_code.lower()[:4]}")
    display_name = faker_data.random_name(pre=user_type.lower()[:10])

    logger.info(
        f"创建用户: username={username}, user_type={user_type}, "
        f"role={role_code}, org={org_id[:8]}..., team={team_id}, supplier={supplier_id}"
    )
    resp = user_api.create_user(
        username=username,
        display_name=display_name,
        password=DEFAULT_PASSWORD,
        organization_id=org_id,
        role_id=role_id,
        team_id=[team_id] if team_id else None,
        supplier_id=supplier_id
    )
    data = resp.json().get("data") or {}
    return resp.json(), username, data.get("id")


def _assert_user_match(resp_json: dict, expected_username: str, expected_role_code: str, msg_prefix: str = ""):
    """校验创建用户响应"""
    assertion.assert_equal(resp_json.get("code"), 0, f"{msg_prefix}创建用户应成功")
    data = resp_json.get("data")
    assertion.assert_is_not_none(data, f"{msg_prefix}响应data不能为空")
    assertion.assert_equal(data.get("username"), expected_username, f"{msg_prefix}用户名不匹配")
    actual_role_code = (data.get("role") or {}).get("code")
    assertion.assert_equal(
        str(actual_role_code).upper() if actual_role_code else None,
        expected_role_code.upper(),
        f"{msg_prefix}角色编码不匹配"
    )


def _find_role_id_by_user_type(db_roles, user_type: str) -> str:
    """根据业务用户类型查找对应数据库角色ID"""
    role_code = USER_TYPE_ROLE_MAP.get(user_type)
    if not role_code:
        pytest.fail(f"未知用户类型: {user_type}")
    return _find_role_id(db_roles, role_code)


# ======================== 基础数据（DB/角色） ========================

@pytest.fixture()
def db_roles():
    """从数据库查询所有角色信息（function 级别，避免会话间角色变更）"""
    roles = pg_db.query_all("SELECT id, code, name FROM dsp_role")
    assertion.assert_is_not_none(roles, "数据库中未初始化角色列表")
    logger.info(f"共查询到 {len(roles)} 个角色: {[r['code'] for r in roles]}")
    return roles


# ======================== 组织 Fixtures ========================

@pytest.fixture(scope="module")
def shared_org():
    """正向用例共享组织（module 作用域，整个测试模块只创建一次）"""
    login_as("admin")
    org_name = faker_data.random_name(pre="org")
    resp = org_api.create_organization(name=org_name, description=TEST_ORG_DESCRIPTION)
    assertion.assert_status_code(resp, 200)
    json_data = resp.json()
    assertion.assert_equal(json_data.get("code"), 0, "创建共享组织失败")
    org_id = json_data.get("data", {}).get("id")
    logger.info(f"[common] 共享组织创建成功: {org_id}")
    return org_id


@pytest.fixture()
def another_org():
    """另一个组织（用于跨组织权限测试，每个用例独立创建）"""
    login_as("admin")
    org_name = faker_data.random_name(pre="org2")
    resp = org_api.create_organization(name=org_name, description=TEST_ORG_DESCRIPTION)
    assertion.assert_status_code(resp, 200)
    json_data = resp.json()
    assertion.assert_equal(json_data.get("code"), 0, "创建另一个组织失败")
    org_id = json_data.get("data", {}).get("id")
    logger.info(f"[common] 另一个组织创建成功: {org_id}")
    return org_id


# ======================== 用户 Fixtures（PM 角色族） ========================

@pytest.fixture()
def pm_user(shared_org, db_roles):
    """PM 用户（系统管理员在 shared_org 下创建）"""
    login_as("admin")
    resp_json, username, user_id = _do_create_user(UserType.PM, shared_org, db_roles)
    assertion.assert_equal(resp_json.get("code"), 0, "创建PM失败")
    return {"user_id": user_id, "username": username, "org_id": shared_org}


@pytest.fixture()
def another_pm(another_org, db_roles):
    """另一个组织下的 PM 用户"""
    login_as("admin")
    resp_json, username, user_id = _do_create_user(UserType.PM, another_org, db_roles)
    assertion.assert_equal(resp_json.get("code"), 0, "创建另一个组织PM失败")
    return {"user_id": user_id, "username": username, "org_id": another_org}


@pytest.fixture()
def peer_pm(shared_org, db_roles):
    """同组织下的另一个 PM 用户（用于同组织 PM 隔离测试）"""
    login_as("admin")
    resp_json, username, user_id = _do_create_user(UserType.PM, shared_org, db_roles)
    assertion.assert_equal(resp_json.get("code"), 0, "创建同组织PM失败")
    return {"user_id": user_id, "username": username, "org_id": shared_org}


# 别名：兼容历史命名（another_pm_user）
@pytest.fixture()
def another_pm_user(another_org, db_roles):
    """another_pm 的别名（兼容历史命名）"""
    login_as("admin")
    resp_json, username, user_id = _do_create_user(UserType.PM, another_org, db_roles)
    assertion.assert_equal(resp_json.get("code"), 0, "创建另一个组织PM失败")
    return {"user_id": user_id, "username": username, "org_id": another_org}


# ======================== 团队 Fixtures ========================

@pytest.fixture()
def shared_team(pm_user, shared_org):
    """项目直属团队（PM 在 shared_org 下创建）"""
    login_with(pm_user["username"], DEFAULT_PASSWORD)
    team_name = faker_data.random_name(pre="team")
    resp = team_api.create_team(name=team_name, org_id=shared_org)
    assertion.assert_status_code(resp, 200)
    team_json = resp.json()
    assertion.assert_equal(team_json.get("code"), 0, "PM创建共享团队应成功")
    team_id = team_json.get("data", {}).get("id")
    logger.info(f"[common] 共享团队创建成功: {team_id}")
    return {"id": team_id, "name": team_name, "org_id": shared_org}


# 别名：兼容历史命名（org_team）
@pytest.fixture()
def org_team(shared_org, pm_user):
    """shared_team 的别名（兼容历史命名）"""
    login_with(pm_user["username"], DEFAULT_PASSWORD)
    resp = team_api.create_team(
        name=faker_data.random_name(pre="orgteam"),
        org_id=shared_org
    )
    assertion.assert_status_code(resp, 200)
    assertion.assert_equal(resp.json().get("code"), 0, "创建项目直属团队失败")
    team_id = resp.json().get("data", {}).get("id")
    return team_id


@pytest.fixture()
def another_org_team(another_org, another_pm):
    """另一个组织的项目直属团队"""
    login_with(another_pm["username"], DEFAULT_PASSWORD)
    resp = team_api.create_team(
        name=faker_data.random_name(pre="team2"),
        org_id=another_org
    )
    assertion.assert_status_code(resp, 200)
    assertion.assert_equal(resp.json().get("code"), 0, "创建另一个组织直属团队失败")
    team_id = resp.json().get("data", {}).get("id")
    return team_id


# ======================== 供应商 Fixtures ========================

@pytest.fixture()
def shared_supplier(pm_user, shared_org):
    """共享供应商（PM 在 shared_org 下创建）"""
    login_with(pm_user["username"], DEFAULT_PASSWORD)
    supplier_name = faker_data.random_name(pre="sup", max_length=20)
    resp = supplier_api.create_supplier(name=supplier_name, org_id=shared_org)
    assertion.assert_status_code(resp, 200)
    sup_json = resp.json()
    assertion.assert_equal(sup_json.get("code"), 0, "PM创建共享供应商应成功")
    supplier_id = sup_json.get("data", {}).get("id")
    logger.info(f"[common] 共享供应商创建成功: {supplier_id}")
    return {"id": supplier_id, "name": supplier_name, "org_id": shared_org}


@pytest.fixture()
def another_supplier(another_pm, another_org):
    """另一个组织下的供应商"""
    login_with(another_pm["username"], DEFAULT_PASSWORD)
    supplier_name = faker_data.random_name(pre="sup2", max_length=20)
    resp = supplier_api.create_supplier(name=supplier_name, org_id=another_org)
    assertion.assert_status_code(resp, 200)
    sup_json = resp.json()
    assertion.assert_equal(sup_json.get("code"), 0, "创建另一个组织供应商失败")
    supplier_id = sup_json.get("data", {}).get("id")
    return {"id": supplier_id, "name": supplier_name, "org_id": another_org}


# ======================== 数据集 Fixtures ========================

@pytest.fixture()
def shared_dataset(pm_user):
    """共享数据集（PM 在 shared_org 下创建）"""
    login_with(pm_user["username"], DEFAULT_PASSWORD)
    ds_name = faker_data.random_name(pre="ds", max_length=20)
    resp = dataset_api.create_dataset(
        name=ds_name,
        data_type="image",
        description="共享数据集",
        org_id=pm_user["org_id"],
    )
    assertion.assert_status_code(resp, 200)
    ds_json = resp.json()
    assertion.assert_equal(ds_json.get("code"), 0, "创建共享数据集失败")
    ds_id = ds_json.get("data", {}).get("id")
    logger.info(f"[common] 共享数据集创建成功: {ds_id}")
    return {"id": ds_id, "name": ds_name, "org_id": pm_user["org_id"]}
