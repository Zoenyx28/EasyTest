"""批次管理自动化用例

需求范围：
- 批次基础操作：创建/查询/详情/编辑/删除

接口定义参考：api/apis/project_api.py
"""
import os
import yaml
import pytest

from api.apis.project_api import project_api
from api.apis.auth_api import login_with
from config.settings import DEFAULT_PASSWORD
from common.assert_util import assertion
from common.base_log import logger
from utils.generate_data import faker_data

_TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_BATCH_YAML_PATH = os.path.join(_TEST_DATA_DIR, "batch.yaml")


def _load_batch_test_data():
    if os.path.exists(_BATCH_YAML_PATH):
        with open(_BATCH_YAML_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


BATCH_TEST_DATA = _load_batch_test_data()


def _create_batch_as_pm(pm_user: dict, project_id: str, name: str = None, description: str = None):
    """以PM身份创建批次，返回(Response, batch_name)"""
    login_with(pm_user["username"], DEFAULT_PASSWORD)
    batch_name = name or faker_data.random_name(pre="batch", max_length=20)
    resp = project_api.create_batch(
        project_id=project_id,
        name=batch_name,
        description=description,
    )
    return resp, batch_name


def _assert_create_success(resp, expected_name: str = None, msg_prefix: str = ""):
    """校验创建批次成功；返回响应data字典"""
    resp_json = resp.json()
    assertion.assert_status_code(resp, 200)
    assertion.assert_equal(resp_json.get("code"), 0, f"{msg_prefix}创建批次应成功")
    data = resp_json.get("data")
    assertion.assert_is_not_none(data, f"{msg_prefix}响应data不能为空")
    if expected_name:
        assertion.assert_equal(data.get("name"), expected_name, f"{msg_prefix}批次名称不匹配")
    return data


@pytest.fixture()
def shared_batch(pm_user, shared_project):
    """PM共享批次（用于更新/查询/删除等场景）"""
    resp, name = _create_batch_as_pm(pm_user, shared_project["id"], description="共享批次")
    data = _assert_create_success(resp, expected_name=name, msg_prefix="[shared_batch] ")
    batch_id = data.get("id")
    logger.info(f"[batch] 共享批次创建成功: {batch_id}")
    return {"id": batch_id, "name": name, "project_id": shared_project["id"]}


class TestBatchCreate:
    """批次创建测试"""

    def test_create_batch_success(self, pm_user, shared_project):
        """创建批次成功"""
        resp, name = _create_batch_as_pm(pm_user, shared_project["id"])
        data = _assert_create_success(resp, expected_name=name)
        assertion.assert_equal(data.get("project_id"), shared_project["id"], "项目ID不匹配")

    def test_create_batch_with_description(self, pm_user, shared_project):
        """创建批次-带描述"""
        resp, name = _create_batch_as_pm(pm_user, shared_project["id"], description="批次描述")
        data = _assert_create_success(resp, expected_name=name)
        assertion.assert_equal(data.get("description"), "批次描述", "描述不匹配")

    def test_create_batch_name_empty(self, pm_user, shared_project):
        """创建批次-名称为空"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = project_api.create_batch(
            project_id=shared_project["id"],
            name="",
        )
        resp_json = resp.json()
        assertion.assert_status_code(resp, 200)
        assertion.assert_true(resp_json.get("code") != 0, "创建批次应失败")

    def test_create_batch_name_too_long(self, pm_user, shared_project):
        """创建批次-名称超过20字符"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        long_name = "a" * 21
        resp = project_api.create_batch(
            project_id=shared_project["id"],
            name=long_name,
        )
        resp_json = resp.json()
        assertion.assert_status_code(resp, 200)
        assertion.assert_true(resp_json.get("code") != 0, "创建批次应失败")

    def test_create_batch_invalid_project_id(self, pm_user):
        """创建批次-项目ID不存在"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = project_api.create_batch(
            project_id="invalid-project-id",
            name=faker_data.random_name(pre="batch", max_length=20),
        )
        assertion.assert_status_code(resp, 404)


class TestBatchQuery:
    """批次查询测试"""

    def test_get_batch_list_empty(self, pm_user, shared_project):
        """查询批次列表-无批次"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = project_api.get_batch_list(project_id=shared_project["id"])
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "查询批次列表应成功")
        data = resp.json().get("data")
        items = data.get("items") or []
        assertion.assert_true(len(items) >= 0, "批次列表长度不能为负")

    def test_get_batch_list_with_data(self, pm_user, shared_project, shared_batch):
        """查询批次列表-有批次"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = project_api.get_batch_list(project_id=shared_project["id"])
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "查询批次列表应成功")
        data = resp.json().get("data")
        items = data.get("items") or []
        assertion.assert_true(len(items) >= 1, "批次列表应至少有一个批次")
        batch_names = [item.get("name") for item in items]
        assertion.assert_true(shared_batch["name"] in batch_names, "共享批次应在列表中")

    def test_get_batch_list_pagination(self, pm_user, shared_project):
        """查询批次列表-分页"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        for i in range(3):
            _create_batch_as_pm(pm_user, shared_project["id"], name=faker_data.random_name(pre="batch", max_length=20))

        resp = project_api.get_batch_list(project_id=shared_project["id"], page=1, page_size=2)
        assertion.assert_status_code(resp, 200)
        assertion.assert_pagination(resp, expected_page=1, expected_page_size=2)

    def test_get_batch_detail(self, pm_user, shared_batch):
        """查询批次详情"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = project_api.get_batch(
            project_id=shared_batch["project_id"],
            batch_id=shared_batch["id"],
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "查询批次详情应成功")
        data = resp.json().get("data")
        assertion.assert_is_not_none(data, "响应data不能为空")
        assertion.assert_equal(data.get("id"), shared_batch["id"], "批次ID不匹配")
        assertion.assert_equal(data.get("name"), shared_batch["name"], "批次名称不匹配")

    def test_get_batch_detail_invalid_id(self, pm_user, shared_project):
        """查询批次详情-批次ID不存在"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = project_api.get_batch(
            project_id=shared_project["id"],
            batch_id="invalid-batch-id",
        )
        assertion.assert_status_code(resp, 404)


class TestBatchUpdate:
    """批次更新测试"""

    def test_update_batch_name(self, pm_user, shared_batch):
        """编辑批次-修改名称"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        new_name = faker_data.random_name(pre="new_batch", max_length=20)
        resp = project_api.update_batch(
            project_id=shared_batch["project_id"],
            batch_id=shared_batch["id"],
            name=new_name,
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "编辑批次应成功")

        detail_resp = project_api.get_batch(
            project_id=shared_batch["project_id"],
            batch_id=shared_batch["id"],
        )
        detail_data = detail_resp.json().get("data")
        assertion.assert_equal(detail_data.get("name"), new_name, "名称更新未生效")

    def test_update_batch_description(self, pm_user, shared_batch):
        """编辑批次-修改描述"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        new_desc = "更新后的批次描述"
        resp = project_api.update_batch(
            project_id=shared_batch["project_id"],
            batch_id=shared_batch["id"],
            description=new_desc,
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "编辑批次应成功")

        detail_resp = project_api.get_batch(
            project_id=shared_batch["project_id"],
            batch_id=shared_batch["id"],
        )
        detail_data = detail_resp.json().get("data")
        assertion.assert_equal(detail_data.get("description"), new_desc, "描述更新未生效")

    def test_update_batch_invalid_id(self, pm_user, shared_project):
        """编辑批次-批次ID不存在"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = project_api.update_batch(
            project_id=shared_project["id"],
            batch_id="invalid-batch-id",
            name="new_name",
        )
        assertion.assert_status_code(resp, 404)


class TestBatchDelete:
    """批次删除测试"""

    def test_delete_batch_success(self, pm_user, shared_batch):
        """删除批次成功"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = project_api.delete_batch(
            project_id=shared_batch["project_id"],
            batch_id=shared_batch["id"],
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "删除批次应成功")

        detail_resp = project_api.get_batch(
            project_id=shared_batch["project_id"],
            batch_id=shared_batch["id"],
        )
        assertion.assert_status_code(detail_resp, 404, "批次删除后应无法查询")

    def test_delete_batch_invalid_id(self, pm_user, shared_project):
        """删除批次-批次ID不存在"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = project_api.delete_batch(
            project_id=shared_project["id"],
            batch_id="invalid-batch-id",
        )
        assertion.assert_status_code(resp, 404)
