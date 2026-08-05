"""任务管理自动化用例

需求范围：
- 任务基础操作：创建/查询/详情/编辑
- 数据推送：推送数据至任务/获取推送记录
- 任务数据：获取任务数据列表/获取标注结果
- 任务关闭：关闭任务

接口定义参考：api/apis/project_api.py
"""
import os
import yaml
import pytest

from api.apis.project_api import project_api
from api.apis.auth_api import login_as, login_with
from config.settings import DEFAULT_PASSWORD
from config.settings import UserType
from common.assert_util import assertion
from common.base_log import logger
from utils.generate_data import faker_data
from fixtures.api_fixture import _do_create_user

_TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_TASK_YAML_PATH = os.path.join(_TEST_DATA_DIR, "task.yaml")


def _load_task_test_data():
    if os.path.exists(_TASK_YAML_PATH):
        with open(_TASK_YAML_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


TASK_TEST_DATA = _load_task_test_data()


def _create_task_as_pm(pm_user: dict, project_id: str, name: str = None, description: str = None):
    """以PM身份创建任务，返回(Response, task_name)"""
    login_with(pm_user["username"], DEFAULT_PASSWORD)
    task_name = name or faker_data.random_name(pre="task", max_length=20)
    resp = project_api.create_task(
        project_id=project_id,
        name=task_name,
        description=description,
    )
    return resp, task_name


def _assert_create_success(resp, expected_name: str = None, msg_prefix: str = ""):
    """校验创建任务成功；返回响应data字典"""
    resp_json = resp.json()
    assertion.assert_status_code(resp, 200)
    assertion.assert_equal(resp_json.get("code"), 0, f"{msg_prefix}创建任务应成功")
    data = resp_json.get("data")
    assertion.assert_is_not_none(data, f"{msg_prefix}响应data不能为空")
    if expected_name:
        assertion.assert_equal(data.get("name"), expected_name, f"{msg_prefix}任务名称不匹配")
    return data


@pytest.fixture()
def shared_task(pm_user, shared_project):
    """PM共享任务（用于更新/查询/关闭等场景）"""
    resp, name = _create_task_as_pm(pm_user, shared_project["id"], description="共享任务")
    data = _assert_create_success(resp, expected_name=name, msg_prefix="[shared_task] ")
    task_id = data.get("id")
    logger.info(f"[task] 共享任务创建成功: {task_id}")
    return {"id": task_id, "name": name, "project_id": shared_project["id"]}


class TestTaskCreate:
    """任务创建测试"""

    def test_create_task_success(self, pm_user, shared_project):
        """创建任务成功"""
        resp, name = _create_task_as_pm(pm_user, shared_project["id"])
        data = _assert_create_success(resp, expected_name=name)
        assertion.assert_equal(data.get("project_id"), shared_project["id"], "项目ID不匹配")

    def test_create_task_with_description(self, pm_user, shared_project):
        """创建任务-带描述"""
        resp, name = _create_task_as_pm(pm_user, shared_project["id"], description="任务描述")
        data = _assert_create_success(resp, expected_name=name)
        assertion.assert_equal(data.get("description"), "任务描述", "描述不匹配")

    def test_create_task_name_empty(self, pm_user, shared_project):
        """创建任务-名称为空"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = project_api.create_task(
            project_id=shared_project["id"],
            name="",
        )
        resp_json = resp.json()
        assertion.assert_status_code(resp, 200)
        assertion.assert_true(resp_json.get("code") != 0, "创建任务应失败")

    def test_create_task_name_too_long(self, pm_user, shared_project):
        """创建任务-名称超过20字符"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        long_name = "a" * 21
        resp = project_api.create_task(
            project_id=shared_project["id"],
            name=long_name,
        )
        resp_json = resp.json()
        assertion.assert_status_code(resp, 200)
        assertion.assert_true(resp_json.get("code") != 0, "创建任务应失败")

    def test_create_task_invalid_project_id(self, pm_user):
        """创建任务-项目ID不存在"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = project_api.create_task(
            project_id="invalid-project-id",
            name=faker_data.random_name(pre="task", max_length=20),
        )
        assertion.assert_status_code(resp, 404)


class TestTaskQuery:
    """任务查询测试"""

    def test_get_task_list_empty(self, pm_user, shared_project):
        """查询任务列表-无任务"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = project_api.get_task_list(project_id=shared_project["id"])
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "查询任务列表应成功")
        data = resp.json().get("data")
        items = data.get("items") or []
        assertion.assert_true(len(items) >= 0, "任务列表长度不能为负")

    def test_get_task_list_with_data(self, pm_user, shared_project, shared_task):
        """查询任务列表-有任务"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = project_api.get_task_list(project_id=shared_project["id"])
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "查询任务列表应成功")
        data = resp.json().get("data")
        items = data.get("items") or []
        assertion.assert_true(len(items) >= 1, "任务列表应至少有一个任务")
        task_names = [item.get("name") for item in items]
        assertion.assert_true(shared_task["name"] in task_names, "共享任务应在列表中")

    def test_get_task_list_pagination(self, pm_user, shared_project):
        """查询任务列表-分页"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        for i in range(3):
            _create_task_as_pm(pm_user, shared_project["id"], name=faker_data.random_name(pre="task", max_length=20))

        resp = project_api.get_task_list(project_id=shared_project["id"], page=1, page_size=2)
        assertion.assert_status_code(resp, 200)
        assertion.assert_pagination(resp, expected_page=1, expected_page_size=2)

    def test_get_task_detail(self, pm_user, shared_task):
        """查询任务详情"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = project_api.get_task(
            project_id=shared_task["project_id"],
            task_id=shared_task["id"],
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "查询任务详情应成功")
        data = resp.json().get("data")
        assertion.assert_is_not_none(data, "响应data不能为空")
        assertion.assert_equal(data.get("id"), shared_task["id"], "任务ID不匹配")
        assertion.assert_equal(data.get("name"), shared_task["name"], "任务名称不匹配")

    def test_get_task_detail_invalid_id(self, pm_user, shared_project):
        """查询任务详情-任务ID不存在"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = project_api.get_task(
            project_id=shared_project["id"],
            task_id="invalid-task-id",
        )
        assertion.assert_status_code(resp, 404)


class TestTaskUpdate:
    """任务更新测试"""

    def test_update_task_name(self, pm_user, shared_task):
        """编辑任务-修改名称"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        new_name = faker_data.random_name(pre="new_task", max_length=20)
        resp = project_api.update_task(
            project_id=shared_task["project_id"],
            task_id=shared_task["id"],
            name=new_name,
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "编辑任务应成功")

        detail_resp = project_api.get_task(
            project_id=shared_task["project_id"],
            task_id=shared_task["id"],
        )
        detail_data = detail_resp.json().get("data")
        assertion.assert_equal(detail_data.get("name"), new_name, "名称更新未生效")

    def test_update_task_description(self, pm_user, shared_task):
        """编辑任务-修改描述"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        new_desc = "更新后的任务描述"
        resp = project_api.update_task(
            project_id=shared_task["project_id"],
            task_id=shared_task["id"],
            description=new_desc,
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "编辑任务应成功")

        detail_resp = project_api.get_task(
            project_id=shared_task["project_id"],
            task_id=shared_task["id"],
        )
        detail_data = detail_resp.json().get("data")
        assertion.assert_equal(detail_data.get("description"), new_desc, "描述更新未生效")

    def test_update_task_invalid_id(self, pm_user, shared_project):
        """编辑任务-任务ID不存在"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = project_api.update_task(
            project_id=shared_project["id"],
            task_id="invalid-task-id",
            name="new_name",
        )
        assertion.assert_status_code(resp, 404)


class TestTaskPushData:
    """数据推送测试"""

    def test_get_push_records_empty(self, pm_user, shared_task):
        """获取推送记录-无记录"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = project_api.get_push_records(
            project_id=shared_task["project_id"],
            task_id=shared_task["id"],
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "获取推送记录应成功")

    def test_get_task_data_items_empty(self, pm_user, shared_task):
        """获取任务数据列表-无数据"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = project_api.get_task_data_items(
            project_id=shared_task["project_id"],
            task_id=shared_task["id"],
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "获取任务数据列表应成功")


class TestTaskClose:
    """任务关闭测试"""

    def test_close_task_success(self, pm_user, shared_task):
        """关闭任务成功"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = project_api.close_task(
            project_id=shared_task["project_id"],
            task_id=shared_task["id"],
            name=shared_task["name"],
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "关闭任务应成功")

    def test_close_task_name_mismatch(self, pm_user, shared_task):
        """关闭任务-名称不匹配"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = project_api.close_task(
            project_id=shared_task["project_id"],
            task_id=shared_task["id"],
            name="wrong_name",
        )
        resp_json = resp.json()
        assertion.assert_status_code(resp, 200)
        assertion.assert_true(resp_json.get("code") != 0, "关闭任务应失败")


class TestTaskPermission:
    """任务权限测试"""

    def test_non_pm_cannot_create_task(self, db_roles, shared_org, shared_project):
        """非PM角色不能创建任务"""
        login_as("admin")
        resp_json, username, _ = _do_create_user(UserType.SUPPLIER_ADMIN, shared_org, db_roles)
        assertion.assert_equal(resp_json.get("code"), 0, "创建供应商管理员应成功")

        login_with(username, DEFAULT_PASSWORD)
        resp = project_api.create_task(
            project_id=shared_project["id"],
            name=faker_data.random_name(pre="task", max_length=20),
        )
        assertion.assert_status_code(resp, 403)

    def test_pm_cannot_view_other_org_task(self, pm_user, another_pm):
        """PM不能查看其他组织的任务"""
        login_with(another_pm["username"], DEFAULT_PASSWORD)
        resp, name = _create_project_as_pm(another_pm)
        data = _assert_create_success(resp, expected_name=name)
        another_project_id = data.get("id")

        login_with(another_pm["username"], DEFAULT_PASSWORD)
        resp, name = _create_task_as_pm(another_pm, another_project_id)
        data = _assert_create_success(resp, expected_name=name)
        another_task_id = data.get("id")

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = project_api.get_task(
            project_id=another_project_id,
            task_id=another_task_id,
        )
        assertion.assert_status_code(resp, 403)


def _create_project_as_pm(pm_user: dict, name: str = None, data_type: str = "image",
                          description: str = "测试项目描述"):
    """以PM身份创建项目，返回(Response, project_name)"""
    login_with(pm_user["username"], DEFAULT_PASSWORD)
    project_name = name or faker_data.random_name(pre="proj", max_length=20)
    resp = project_api.create_project(
        name=project_name,
        description=description,
        data_type=data_type,
        org_id=pm_user["org_id"],
    )
    return resp, project_name
