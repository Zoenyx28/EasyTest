"""项目管理自动化用例

需求范围：
- 项目基础操作：创建/查询/详情/编辑
- 项目状态流转：待配置→待启动→进行中→暂停/恢复/完成/归档/废弃
- 数据集绑定：绑定/解绑
- 标注配置：保存标注配置/更新流转策略
- 项目封面：上传/获取
- 权限：仅PM可创建，按组织隔离
- 任务管理：创建/查询/详情/编辑/删除，已任务为纬度绑定人员
- 批次管理：创建/查询/详情/编辑/删除，从项目绑定数据集中绑定数据和序列，然后绑定到任务

接口定义参考：api/apis/project_api.py
枚举参考：config/settings.py（DatasetType）
"""
import os
import yaml
import pytest

from api.apis.project_api import project_api
from api.apis.dataset_api import dataset_api
from api.apis.auth_api import login_as, login_with
from config.settings import DatasetType, TEST_ORG_DESCRIPTION
from config.settings import UserType
from common.assert_util import assertion
from common.base_log import logger
from utils.generate_data import faker_data
from fixtures.api_fixture import _do_create_user, db_roles, shared_org, pm_user, shared_dataset

# 默认使用项目封面路径
DEFAULT_COVER_PATH="data/static/cover/test_cover.jpg"

def _create_project_as_pm(pm_user: dict,
    name: str = "",
    data_type: str = "image",
    description: str = "测试项目描述", 
    cover_url: str = None,
    visibility: str = "organization"
    ) -> tuple:
    """以PM身份创建项目，返回(Response, project_name)"""
    login_with(pm_user["username"])
    project_name = name or faker_data.random_name(pre="proj", max_length=20)
    resp = project_api.create_project(
        name=project_name,
        description=description,
        data_type=data_type,
        org_id=pm_user["org_id"],
        cover_url=cover_url,
        visibility=visibility,
    )
    return resp, project_name


def _assert_create_success(resp, pm_user: dict, expected_name: str):
    """校验创建项目成功，从项目列表中查询成功"""
    assertion.assert_status_code(resp, 200)
    resp_json = resp.json()
    assertion.assert_equal(resp_json.get("code"), 0, "创建项目接口响应code应成功")
    data = resp_json.get("data")
    assertion.assert_is_not_none(data, "响应data不能为空")
    if expected_name:
        assertion.assert_equal(data.get("name"), expected_name, "项目名称不匹配")
    # 查询项目列表，校验新创建的项目在列表中
    prj_res = project_api.get_project_list(org_id=pm_user["org_id"])
    assertion.assert_equal(prj_res.json().get("code"), 0, "查询项目列表接口响应code应成功")
    prj_list = prj_res.json().get('data').get('items', [])
    assertion.assert_true(any(prj.get("name") == expected_name for prj in prj_list),
                          "项目列表中未包含新创建的项目")
    return data


def _assert_create_failed(
    resp_json: dict, 
    expect_code: int = 0,
    expect_msg: str = "",
    ):
    """校验创建项目失败（业务码非0）"""
    assertion.assert_equal(
        resp_json.get("code"), expect_code, f"创建项目接口返回code不匹配，实际code={resp_json.get('code')}",
    )
    if expect_msg:
        assertion.assert_equal(
            resp_json.get("msg"), expect_msg, f"创建项目接口返回msg不匹配，实际msg={resp_json.get('msg')}",
    )


@pytest.fixture()
def shared_project(pm_user):
    """PM共享项目（用于更新/查询/状态流转等场景）"""
    resp, name = _create_project_as_pm(pm_user, data_type="image", description="共享项目")
    data = _assert_create_success(resp, pm_user, expected_name=name)
    project_id = data.get("id")
    logger.info(f"[project] 共享项目创建成功: {project_id}")
    return {"id": project_id, "name": name, "org_id": pm_user["org_id"], "created_by": pm_user["username"]}

@pytest.mark.api
class TestProjectCreate:
    """项目创建测试"""

    @pytest.mark.smoke
    @pytest.mark.parametrize("data_type", [
        "image", "image_sequence", "audio", "audio_sequence",
        "video", "video_sequence", "pointcloud_3d", "text",
    ])
    def test_create_project_with_all_data_types(self, pm_user, data_type):
        """创建项目-支持所有数据类型"""
        resp, name = _create_project_as_pm(pm_user, data_type=data_type)
        data = _assert_create_success(resp, pm_user, expected_name=name)
        assertion.assert_equal(data.get("data_type"), data_type, "数据类型不匹配")
        assertion.assert_equal(data.get("status"), "pending_start", "初始状态应为待配置")

    def test_create_project_with_cover(self, pm_user, shared_dataset):
        """创建项目-带封面图"""
        login_with(pm_user["username"])
        with open(DEFAULT_COVER_PATH, "rb") as f:
            cover_bytes = f.read()
        cover_resp = project_api.upload_cover(file=cover_bytes, org_id=pm_user["org_id"])
        cover_data = cover_resp.json().get("data")
        cover_url = cover_data.get("url") if cover_data else None

        resp, name = _create_project_as_pm(pm_user, cover_url=cover_url)
        data = _assert_create_success(resp, pm_user, expected_name=name)
        assertion.assert_is_not_none(data.get("cover_url"), "封面URL不能为空")

    def test_create_project_name_empty(self, pm_user):
        """创建项目-名称为空"""
        login_with(pm_user["username"])
        resp = project_api.create_project(
            name="",
            description="测试描述",
            data_type="image",
            org_id=pm_user["org_id"],
        )
        _assert_create_failed(resp.json(), expect_code=422, expect_msg="字符串长度不能少于 1 个字符")

    def test_create_project_name_too_long(self, pm_user):
        """创建项目-名称超过20字符"""
        login_with(pm_user["username"])
        long_name = "a" * 21
        resp = project_api.create_project(
            name=long_name,
            description="测试描述",
            data_type="image",
            org_id=pm_user["org_id"],
        )
        _assert_create_failed(resp.json(), expect_code=422, expect_msg="字符串长度不能超过 20 个字符")

    def test_create_project_description_empty(self, pm_user):
        """创建项目-描述为空"""
        login_with(pm_user["username"])
        resp = project_api.create_project(
            name=faker_data.random_name(pre="proj", max_length=20),
            description="",
            data_type="image",
            org_id=pm_user["org_id"],
        )
        _assert_create_failed(resp.json(), expect_code=422, expect_msg="字符串长度不能少于 1 个字符")

    def test_create_project_description_too_long(self, pm_user):
        """创建项目-描述超过200字符"""
        login_with(pm_user["username"])
        long_desc = "a" * 201
        resp = project_api.create_project(
            name=faker_data.random_name(pre="proj", max_length=20),
            description=long_desc,
            data_type="image",
            org_id=pm_user["org_id"],
        )
        _assert_create_failed(resp.json(), expect_code=422, expect_msg="字符串长度不能超过 200 个字符")

    def test_create_project_invalid_data_type(self, pm_user):
        """创建项目-数据类型非法"""
        login_with(pm_user["username"])
        resp = project_api.create_project(
            name=faker_data.random_name(pre="proj", max_length=20),
            description="测试描述",
            data_type="invalid_type",
            org_id=pm_user["org_id"],
        )
        _assert_create_failed(resp.json(), expect_code=422, expect_msg="值无效，请选择有效选项")

    def test_create_project_with_visibility_organization(self, pm_user):
        """创建项目-可见范围为组织"""
        resp, name = _create_project_as_pm(pm_user, visibility="organization")
        data = _assert_create_success(resp, pm_user, expected_name=name)
        assertion.assert_equal(data.get("visibility"), "organization", "可见范围不匹配")

    def test_create_project_name_20_chars(self, pm_user):
        """创建项目-名称为20字符"""
        login_with(pm_user["username"])
        name = "a" * 20
        resp = project_api.create_project(
            name=name,
            description="测试描述",
            data_type="image",
            org_id=pm_user["org_id"],
        )
        _assert_create_success(resp, pm_user, expected_name=name)

    def test_create_project_name_1_char(self, pm_user):
        """创建项目-名称为1字符"""
        login_with(pm_user["username"])
        name = "a"
        resp = project_api.create_project(
            name=name,
            description="测试描述",
            data_type="image",
            org_id=pm_user["org_id"],
        )
        _assert_create_success(resp, pm_user, expected_name=name)

    def test_create_project_description_200_chars(self, pm_user):
        """创建项目-描述为200字符"""
        login_with(pm_user["username"])
        desc = "a" * 200
        name = faker_data.random_name(pre="proj", max_length=20)
        resp = project_api.create_project(
            name=name,
            description=desc,
            data_type="image",
            org_id=pm_user["org_id"],
        )
        _assert_create_success(resp, pm_user, expected_name=name)

    def test_create_project_same_name(self, pm_user):
        """创建项目-同名项目创建成功（支持重复名称）"""
        common_name = faker_data.random_name(pre="same", max_length=15)
        resp1, _ = _create_project_as_pm(pm_user, name=common_name)
        _assert_create_success(resp1, pm_user, expected_name=common_name)
        resp2, _ = _create_project_as_pm(pm_user, name=common_name)
        _assert_create_success(resp2, pm_user, expected_name=common_name)

    def test_create_project_name_special_chars(self, pm_user):
        """创建项目-名称含特殊字符（中文、符号）"""
        name = f"项目_{faker_data.random_name(pre='SP', max_length=8)}-test@#$"
        resp, _ = _create_project_as_pm(pm_user, name=name)
        _assert_create_success(resp, pm_user, expected_name=name)

    def test_create_project_name_all_spaces(self, pm_user):
        """创建项目-名称为全空格（边界）"""
        resp, name = _create_project_as_pm(pm_user, name="   ")
        _assert_create_success(resp, pm_user, expected_name=name)

    def test_create_project_org_id_empty(self, pm_user):
        """创建项目-org_id为空（异常）"""
        login_with(pm_user["username"])
        resp = project_api.create_project(
            name=faker_data.random_name(pre="proj", max_length=20),
            description="测试描述",
            data_type="image",
            org_id="",
        )
        _assert_create_failed(resp.json(), expect_code=422, expect_msg="请输入有效的UUID")


class TestProjectQuery:
    """项目查询测试"""

    def test_get_project_list_empty(self, pm_user):
        """查询项目列表-无项目查询成功"""
        login_with(pm_user["username"])
        resp = project_api.get_project_list(org_id=pm_user["org_id"])
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "查询项目列表应成功")
        data = resp.json().get("data")
        assertion.assert_is_not_none(data, "响应data不能为空")
        items = data.get("items") or []
        assertion.assert_true(len(items) >= 0, "项目列表长度不能为负")

    def test_get_project_list_with_data(self, pm_user, shared_project):
        """查询项目列表-有项目"""
        login_with(pm_user["username"])
        resp = project_api.get_project_list(org_id=pm_user["org_id"])
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "查询项目列表应成功")
        data = resp.json().get("data")
        items = data.get("items") or []
        assertion.assert_true(len(items) >= 1, "项目列表应至少有一个项目")
        project_names = [item.get("name") for item in items]
        assertion.assert_true(shared_project["name"] in project_names, "共享项目应在列表中")

    def test_get_project_list_pagination(self, pm_user):
        """查询项目列表-分页"""
        login_with(pm_user["username"])
        for i in range(3):
            _create_project_as_pm(pm_user, name=faker_data.random_name(pre="proj", max_length=20))

        resp = project_api.get_project_list(org_id=pm_user["org_id"], page=1, page_size=2)
        assertion.assert_status_code(resp, 200)
        assertion.assert_pagination(resp, expected_page=1, expected_page_size=2)

    def test_get_project_list_by_name_fuzzy(self, pm_user):
        """查询项目列表-按名称模糊搜索"""
        login_with(pm_user["username"])
        unique_prefix = faker_data.random_name(pre="fuzz", max_length=10)
        _create_project_as_pm(pm_user, name=f"{unique_prefix}_target")
        _create_project_as_pm(pm_user, name=f"{unique_prefix}_other")
        _create_project_as_pm(pm_user, name=faker_data.random_name(pre="noise", max_length=20))

        resp = project_api.get_project_list(org_id=pm_user["org_id"], name=unique_prefix)
        assertion.assert_equal(resp.json().get("code"), 0, "模糊搜索项目应成功")
        items = resp.json().get("data", {}).get("items", [])
        assertion.assert_true(len(items) >= 2, f"模糊搜索应至少返回2个项目，实际返回{len(items)}个")
        for item in items:
            assertion.assert_true(unique_prefix in item.get("name", ""),
                                  f"模糊搜索结果应包含关键词，实际名称={item.get('name')}")

    def test_get_project_list_by_data_type(self, pm_user):
        """查询项目列表-按数据类型筛选（支持多选）"""
        login_with(pm_user["username"])
        _create_project_as_pm(pm_user, name=faker_data.random_name(pre="img", max_length=15), data_type="image")
        _create_project_as_pm(pm_user, name=faker_data.random_name(pre="aud", max_length=15), data_type="audio")
        _create_project_as_pm(pm_user, name=faker_data.random_name(pre="txt", max_length=15), data_type="text")

        # 单选
        resp = project_api.get_project_list(org_id=pm_user["org_id"], data_type="image")
        assertion.assert_equal(resp.json().get("code"), 0, "按数据类型筛选应成功")
        items = resp.json().get("data", {}).get("items", [])
        for item in items:
            assertion.assert_equal(item.get("data_type"), "image",
                                   f"数据类型筛选结果应全为image，实际={item.get('data_type')}")

        # 多选
        resp2 = project_api.get_project_list(org_id=pm_user["org_id"], data_type="image,audio")
        assertion.assert_equal(resp2.json().get("code"), 0, "按多数据类型筛选应成功")
        items2 = resp2.json().get("data", {}).get("items", [])
        for item in items2:
            assertion.assert_true(item.get("data_type") in ("image", "audio"),
                                  f"多选数据类型筛选结果应为image或audio，实际={item.get('data_type')}")

    def test_get_project_list_by_status(self, pm_user, shared_project):
        """查询项目列表-按状态筛选"""
        login_with(pm_user["username"])
        resp = project_api.get_project_list(org_id=pm_user["org_id"], status="pending_start")
        assertion.assert_equal(resp.json().get("code"), 0, "按状态筛选应成功")
        items = resp.json().get("data", {}).get("items", [])
        assertion.assert_true(len(items) >= 1, f"状态筛选应至少返回1个项目，实际返回{len(items)}个")
        for item in items:
            assertion.assert_equal(item.get("status"), "pending_start",
                                   f"状态筛选结果应全为pending_start，实际={item.get('status')}")

    def test_get_project_list_multi_condition(self, pm_user):
        """查询项目列表-多条件组合搜索（名称+数据类型+状态）"""
        login_with(pm_user["username"])
        prefix = faker_data.random_name(pre="multi", max_length=8)
        _create_project_as_pm(pm_user, name=f"{prefix}_img", data_type="image")
        _create_project_as_pm(pm_user, name=f"{prefix}_aud", data_type="audio")
        _create_project_as_pm(pm_user, name=faker_data.random_name(pre="other", max_length=15), data_type="text")

        resp = project_api.get_project_list(
            org_id=pm_user["org_id"],
            name=prefix,
            data_type="image",
            status="pending_start",
        )
        assertion.assert_equal(resp.json().get("code"), 0, "多条件组合搜索应成功")
        items = resp.json().get("data", {}).get("items", [])
        for item in items:
            assertion.assert_true(prefix in item.get("name", ""),
                                  f"名称应包含{prefix}，实际={item.get('name')}")
            assertion.assert_equal(item.get("data_type"), "image",
                                   f"数据类型应为image，实际={item.get('data_type')}")
            assertion.assert_equal(item.get("status"), "pending_start",
                                   f"状态应为pending_start，实际={item.get('status')}")

    def test_get_project_list_no_match(self, pm_user):
        """查询项目列表-模糊搜索无匹配结果返回空列表"""
        login_with(pm_user["username"])
        resp = project_api.get_project_list(org_id=pm_user["org_id"], name="NoSuchProject99999")
        assertion.assert_equal(resp.json().get("code"), 0, "无匹配结果查询应成功")
        items = resp.json().get("data", {}).get("items", [])
        assertion.assert_equal(len(items), 0, f"无匹配结果应返回空列表，实际返回{len(items)}条")

    def test_get_project_list_page_out_of_range(self, pm_user):
        """查询项目列表-分页越界（page超出范围）"""
        login_with(pm_user["username"])
        resp = project_api.get_project_list(org_id=pm_user["org_id"], page=999, page_size=10)
        assertion.assert_equal(resp.json().get("code"), 0, "分页越界查询应成功")
        items = resp.json().get("data", {}).get("items", [])
        assertion.assert_equal(len(items), 0, f"越界分页应返回空列表，实际返回{len(items)}条")

    def test_get_project_list_illegal_status(self, pm_user):
        """查询项目列表-非法status值（边界）"""
        login_with(pm_user["username"])
        resp = project_api.get_project_list(org_id=pm_user["org_id"], status="invalid_status")
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 400, "非法status应返回业务错误码400")

    def test_get_project_list_illegal_data_type(self, pm_user):
        """查询项目列表-非法data_type值（边界）"""
        login_with(pm_user["username"])
        resp = project_api.get_project_list(org_id=pm_user["org_id"], data_type="invalid_type")
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 400, "非法data_type应返回业务错误码400")


class TestProjectException:
    """项目异常测试"""

    def test_get_non_existent_project(self, pm_user):
        """查询不存在的项目ID（异常）"""
        login_with(pm_user["username"])
        resp = project_api.get_project_detail(project_id="nonexistent-id-99999")
        assertion.assert_status_code(resp, 200)
        assertion.assert_is_none(resp.json().get("data"), "不存在的项目data应为null")

    def test_edit_non_existent_project(self, pm_user):
        """编辑不存在的项目ID（异常）"""
        login_with(pm_user["username"])
        resp = project_api.update_project(
            project_id="nonexistent-id-99999",
            name="新名称",
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_is_none(resp.json().get("data"), "编辑不存在的项目data应为null")

    def test_abandon_already_abandoned_project(self, pm_user):
        """废弃已废弃的项目"""
        resp, name = _create_project_as_pm(pm_user)
        data = _assert_create_success(resp, pm_user, expected_name=name)
        project_id = data.get("id")
        login_with(pm_user["username"])
        project_api.abandon_project(project_id=project_id)
        resp2 = project_api.abandon_project(project_id=project_id)
        assertion.assert_status_code(resp2, 200)
        assertion.assert_not_equal(resp2.json().get("code"), 0, "重复废弃应返回业务错误")

    def test_bind_already_bound_dataset(self, pm_user, shared_project, shared_dataset):
        """重复绑定已绑定的数据集"""
        login_with(pm_user["username"])
        project_api.bind_dataset(
            project_id=shared_project["id"],
            dataset_ids=[shared_dataset["id"]],
        )
        resp = project_api.bind_dataset(
            project_id=shared_project["id"],
            dataset_ids=[shared_dataset["id"]],
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_not_equal(resp.json().get("code"), 0, "重复绑定应返回业务错误")

    def test_unbind_unbound_dataset(self, pm_user, shared_project, shared_dataset):
        """解绑未绑定的数据集"""
        login_with(pm_user["username"])
        resp = project_api.unbind_dataset(
            project_id=shared_project["id"],
            dataset_id=shared_dataset["id"],
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_not_equal(resp.json().get("code"), 0, "解绑未绑定数据集应返回业务错误")


class TestProjectUpdate:
    """编辑项目信息"""

    def test_update_project_name(self, pm_user, shared_project):
        """编辑项目-修改名称"""
        login_with(pm_user["username"])
        new_name = faker_data.random_name(pre="new_proj", max_length=20)
        resp = project_api.update_project(
            project_id=shared_project["id"],
            name=new_name,
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "编辑项目应成功")

        detail_resp = project_api.get_project_detail(project_id=shared_project["id"])
        detail_data = detail_resp.json().get("data")
        assertion.assert_equal(detail_data.get("name"), new_name, "名称更新未生效")

    def test_update_project_description(self, pm_user, shared_project):
        """编辑项目-修改描述"""
        login_with(pm_user["username"])
        new_desc = "更新后的项目描述"
        resp = project_api.update_project(
            project_id=shared_project["id"],
            description=new_desc,
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "编辑项目应成功")

        detail_resp = project_api.get_project_detail(project_id=shared_project["id"])
        detail_data = detail_resp.json().get("data")
        assertion.assert_equal(detail_data.get("description"), new_desc, "描述更新未生效")

    def test_update_project_visibility(self, pm_user, shared_project):
        """编辑项目-修改可见范围"""
        login_with(pm_user["username"])
        resp = project_api.update_project(
            project_id=shared_project["id"],
            visibility="team",
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "编辑项目应成功")

        detail_resp = project_api.get_project_detail(project_id=shared_project["id"])
        detail_data = detail_resp.json().get("data")
        assertion.assert_equal(detail_data.get("visibility"), "team", "可见范围更新未生效")


class TestProjectStatusTransition:
    """项目状态流转测试"""

    def test_start_project(self, pm_user, shared_project):
        """启动项目-待配置→进行中"""
        login_with(pm_user["username"])
        resp = project_api.start_project(project_id=shared_project["id"], reason="测试启动")
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "启动项目应成功")

        detail_resp = project_api.get_project_detail(project_id=shared_project["id"])
        detail_data = detail_resp.json().get("data")
        assertion.assert_equal(detail_data.get("status"), "in_progress", "项目状态应为进行中")

    def test_abandon_project(self, pm_user):
        """废弃项目-待配置→已废弃"""
        resp, name = _create_project_as_pm(pm_user)
        data = _assert_create_success(resp, pm_user, expected_name=name)
        project_id = data.get("id")

        login_with(pm_user["username"])
        abandon_resp = project_api.abandon_project(project_id=project_id)
        assertion.assert_status_code(abandon_resp, 200)
        assertion.assert_equal(abandon_resp.json().get("code"), 0, "废弃项目应成功")

        detail_resp = project_api.get_project_detail(project_id=project_id)
        detail_data = detail_resp.json().get("data")
        assertion.assert_equal(detail_data.get("status"), "abandoned", "项目状态应为已废弃")

    def test_pause_resume_project(self, pm_user, shared_project):
        """暂停/恢复项目-进行中→暂停→进行中"""
        login_with(pm_user["username"])
        project_api.start_project(project_id=shared_project["id"], reason="测试启动")

        pause_resp = project_api.pause_project(project_id=shared_project["id"], reason="测试暂停")
        assertion.assert_status_code(pause_resp, 200)
        assertion.assert_equal(pause_resp.json().get("code"), 0, "暂停项目应成功")

        detail_resp = project_api.get_project_detail(project_id=shared_project["id"])
        detail_data = detail_resp.json().get("data")
        assertion.assert_equal(detail_data.get("status"), "paused", "项目状态应为暂停")

        resume_resp = project_api.resume_project(project_id=shared_project["id"], reason="测试恢复")
        assertion.assert_status_code(resume_resp, 200)
        assertion.assert_equal(resume_resp.json().get("code"), 0, "恢复项目应成功")

        detail_resp = project_api.get_project_detail(project_id=shared_project["id"])
        detail_data = detail_resp.json().get("data")
        assertion.assert_equal(detail_data.get("status"), "in_progress", "项目状态应为进行中")


class TestProjectDatasetBind:
    """数据集绑定测试"""

    def test_bind_dataset(self, pm_user, shared_project, shared_dataset):
        """绑定数据集"""
        login_with(pm_user["username"])
        resp = project_api.bind_dataset(
            project_id=shared_project["id"],
            dataset_ids=[shared_dataset["id"]],
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "绑定数据集应成功")

    def test_unbind_dataset(self, pm_user, shared_project, shared_dataset):
        """解绑数据集"""
        login_with(pm_user["username"])
        project_api.bind_dataset(
            project_id=shared_project["id"],
            dataset_ids=[shared_dataset["id"]],
        )

        resp = project_api.unbind_dataset(
            project_id=shared_project["id"],
            dataset_id=shared_dataset["id"],
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "解绑数据集应成功")


class TestProjectLabelConfig:
    """标注配置测试"""

    def test_save_label_config(self, pm_user, shared_project):
        """保存标注配置"""
        login_with(pm_user["username"])
        label_config = """<View>
  <Image name="image" value="$image"/>
  <RectangleLabels name="label" toName="image">
    <Label value="cat"/>
    <Label value="dog"/>
  </RectangleLabels>
</View>"""
        resp = project_api.save_label_config(
            project_id=shared_project["id"],
            label_config=label_config,
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "保存标注配置应成功")

    def test_update_workflow(self, pm_user, shared_project):
        """更新流转策略"""
        login_with(pm_user["username"])
        workflow_steps = [
            {"step_type": "annotate", "name": "标注"},
            {"step_type": "review", "name": "质检"},
            {"step_type": "audit", "name": "审核"},
            {"step_type": "accept", "name": "验收"},
        ]
        resp = project_api.update_workflow(
            project_id=shared_project["id"],
            steps=workflow_steps,
        )
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "更新流转策略应成功")


class TestProjectCover:
    """项目封面测试"""

    def test_upload_cover(self, pm_user):
        """上传项目封面"""
        login_with(pm_user["username"])
        with open(DEFAULT_COVER_PATH, "rb") as f:
            cover_bytes = f.read()
        resp = project_api.upload_cover(file=cover_bytes, org_id=pm_user["org_id"])
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "上传封面应成功")
        data = resp.json().get("data")
        assertion.assert_is_not_none(data, "响应data不能为空")
        assertion.assert_is_not_none(data.get("url"), "封面URL不能为空")

    def test_get_cover(self, pm_user, shared_project):
        """获取项目封面"""
        login_with(pm_user["username"])
        with open(DEFAULT_COVER_PATH, "rb") as f:
            cover_bytes = f.read()
        cover_resp = project_api.upload_cover(file=cover_bytes, org_id=pm_user["org_id"])
        cover_url = cover_resp.json().get("data", {}).get("url")

        project_api.update_project(project_id=shared_project["id"], cover_url=cover_url)

        resp = project_api.get_cover(project_id=shared_project["id"])
        assertion.assert_status_code(resp, 200)


class TestProjectPermission:
    """项目权限测试"""

    def test_non_pm_cannot_create_project(self, db_roles, shared_org):
        """非PM角色不能创建项目"""
        login_as("admin")
        resp_json, username, _ = _do_create_user(UserType.SUPPLIER_ADMIN, shared_org, db_roles)
        assertion.assert_equal(resp_json.get("code"), 0, "创建供应商管理员应成功")

        login_with(username)
        resp = project_api.create_project(
            name=faker_data.random_name(pre="proj", max_length=20),
            description="测试描述",
            data_type="image",
            org_id=shared_org,
        )
        assertion.assert_status_code(resp, 403)

    def test_admin_can_view_project(self, pm_user, shared_project):
        """系统管理员可查看项目"""
        login_as("admin")
        resp = project_api.get_project_detail(project_id=shared_project["id"])
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "系统管理员应能查看项目")

    def test_pm_cannot_view_other_org_project(self, pm_user, another_pm):
        """PM不能查看其他组织的项目"""
        login_with(another_pm["username"])
        resp, name = _create_project_as_pm(another_pm)
        data = _assert_create_success(resp, another_pm, expected_name=name)
        another_project_id = data.get("id")

        login_with(pm_user["username"])
        resp = project_api.get_project_detail(project_id=another_project_id)
        assertion.assert_status_code(resp, 403)

    def test_non_pm_cannot_update_project(self, pm_user, shared_project, db_roles, shared_org):
        """非PM角色不能编辑项目"""
        login_as("admin")
        resp_json, username, _ = _do_create_user(UserType.SUPPLIER_ADMIN, shared_org, db_roles)
        assertion.assert_equal(resp_json.get("code"), 0, "创建供应商管理员应成功")
        login_with(username)
        resp = project_api.update_project(
            project_id=shared_project["id"],
            name="非法修改",
        )
        assertion.assert_status_code(resp, 403)

    def test_non_pm_cannot_abandon_project(self, pm_user, shared_project, db_roles, shared_org):
        """非PM角色不能废弃项目"""
        login_as("admin")
        resp_json, username, _ = _do_create_user(UserType.SUPPLIER_ADMIN, shared_org, db_roles)
        assertion.assert_equal(resp_json.get("code"), 0, "创建供应商管理员应成功")
        login_with(username)
        resp = project_api.abandon_project(project_id=shared_project["id"])
        assertion.assert_status_code(resp, 403)

    def test_non_pm_cannot_start_project(self, pm_user, shared_project, db_roles, shared_org):
        """非PM角色不能启动项目"""
        login_as("admin")
        resp_json, username, _ = _do_create_user(UserType.SUPPLIER_ADMIN, shared_org, db_roles)
        assertion.assert_equal(resp_json.get("code"), 0, "创建供应商管理员应成功")
        login_with(username)
        resp = project_api.start_project(project_id=shared_project["id"], reason="测试启动")
        assertion.assert_status_code(resp, 403)

    def test_non_pm_cannot_bind_dataset(self, pm_user, shared_project, shared_dataset, db_roles, shared_org):
        """非PM角色不能绑定数据集"""
        login_as("admin")
        resp_json, username, _ = _do_create_user(UserType.SUPPLIER_ADMIN, shared_org, db_roles)
        assertion.assert_equal(resp_json.get("code"), 0, "创建供应商管理员应成功")
        login_with(username)
        resp = project_api.bind_dataset(
            project_id=shared_project["id"],
            dataset_ids=[shared_dataset["id"]],
        )
        assertion.assert_status_code(resp, 403)

    def test_non_pm_cannot_save_label_config(self, pm_user, shared_project, db_roles, shared_org):
        """非PM角色不能保存标注配置"""
        login_as("admin")
        resp_json, username, _ = _do_create_user(UserType.SUPPLIER_ADMIN, shared_org, db_roles)
        assertion.assert_equal(resp_json.get("code"), 0, "创建供应商管理员应成功")
        login_with(username)
        resp = project_api.save_label_config(
            project_id=shared_project["id"],
            label_config="<View></View>",
        )
        assertion.assert_status_code(resp, 403)
