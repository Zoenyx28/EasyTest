"""数据集管理自动化用例

需求范围：
- 新增数据集：名称/描述/类型/封面图
- 查询数据集：名称（模糊）/类型（多选）/状态（多选）/按更新时间倒序
- 权限：仅 PM 可见，仅能操作所在组织下的数据集
- 封面图：upload_temp_cover 上传，jpg/jpeg/png/webp，单文件 ≤ 5MB
- 上传数据包：三步流程（upload→process→records），支持 .zip/.tar/.tar.gz/.tar.bz2

接口定义参考：src/api/dataset_api.py
枚举参考：src/config/config.py（DatasetType / DatasetStatus）
"""
import hashlib
import io
import os
import time

import pytest

from api.apis.dataset_api import dataset_api
from api.apis.org_api import org_api
from api.apis.team_api import team_api
from api.apis.supplier_api import supplier_api
from api.apis.auth_api import login_as, login_with, auth_api
from config.settings import DatasetType, DatasetStatus
from config.settings import DEFAULT_PASSWORD, TEST_ORG_DESCRIPTION
from config.settings import UserType
from common.assert_util import assertion
from common.http_client import http_client
from common.base_log import logger
from api.apis.data_api import api_client
from utils.generate_data import faker_data
from fixtures.api_helpers import get_list_items
from fixtures.api_fixture import _do_create_user


# ======================== 常量定义 ========================

# 数据集类型/状态（字符串列表，用于参数化）
DATASET_TYPES = [
    "pointcloud_3d", "text", "image", "audio", "video",
    "image_sequence", "audio_sequence", "video_sequence",
]
DATASET_STATUSES = [
    "unused", "inuse", "deprecated", "completed", "paused", "archived",
]

# 封面图测试数据
COVER_PATH = [
    {"file": "data/static/goose-9544312_1280_test.png", "filename": "goose-9544312_1280_test.png", "type": "image/png"},
    {"file": "data/static/goose-9544312_1280_test.jpg", "filename": "goose-9544312_1280_test.jpg", "type": "image/jpeg"},
    {"file": "data/static/goose-9544312_1280_test.jpeg", "filename": "goose-9544312_1280_test.jpeg", "type": "image/jpeg"},
    {"file": "data/static/goose-9544312_1280_test.webp", "filename": "goose-9544312_1280_test.webp", "type": "image/webp"},
]

# 数据包测试数据根目录
_TEST_SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACKAGE_TEST_DATA_DIR = os.path.join(_TEST_SRC_DIR, "data", "static", "datasets")
IMAGE_SEQUENCE_DIR = os.path.join(PACKAGE_TEST_DATA_DIR, "image_sequence")

# 已准备测试数据的数据集类型 → (file_path, filename)
PACKAGE_TEST_FILES = {
    DatasetType.IMAGE: (os.path.join(PACKAGE_TEST_DATA_DIR, "image", "图象文件-序列.zip"), "图象文件-序列.zip"),
    DatasetType.SEQUENCE_IMAGE: (os.path.join(PACKAGE_TEST_DATA_DIR, "image_sequence", "图象文件-序列.zip"), "图象文件-序列.zip"),
}

# 超过 5GB 的测试压缩包
OVERSIZE_PACKAGE_PATH = os.path.join(IMAGE_SEQUENCE_DIR, "oversize_test.zip")
OVERSIZE_PACKAGE_FILENAME = "oversize_test.zip"

# tar / tar.gz / tar.bz2 合法格式测试数据
PACKAGE_TAR_FILES = {
    ".tar":     (os.path.join(IMAGE_SEQUENCE_DIR, "test_archive.tar"),     "test_archive.tar",     "application/x-tar"),
    ".tar.gz":  (os.path.join(IMAGE_SEQUENCE_DIR, "test_archive.tar.gz"),  "test_archive.tar.gz",  "application/gzip"),
    ".tar.bz2": (os.path.join(IMAGE_SEQUENCE_DIR, "test_archive.tar.bz2"), "test_archive.tar.bz2", "application/x-bzip2"),
}

# 非法格式测试数据（rar / 7z）
INVALID_PACKAGE_FILES = {
    ".rar": (os.path.join(IMAGE_SEQUENCE_DIR, "test_archive.rar"), "test_archive.rar", "application/vnd.rar"),
    ".7z":  (os.path.join(IMAGE_SEQUENCE_DIR, "test_archive.7z"),  "test_archive.7z",  "application/x-7z-compressed"),
}

# 序列中某一序列无图片的测试包
EMPTY_SEQUENCE_PACKAGE_PATH = os.path.join(IMAGE_SEQUENCE_DIR, "empty_sequence_image.zip")
EMPTY_SEQUENCE_PACKAGE_FILENAME = "empty_sequence_image.zip"

# 所有支持的数据集类型（DatasetType 列表）
ALL_DATASET_TYPES = [
    DatasetType.POINT_CLOUD, DatasetType.TEXT, DatasetType.IMAGE, DatasetType.AUDIO,
    DatasetType.VIDEO, DatasetType.SEQUENCE_IMAGE, DatasetType.SEQUENCE_AUDIO,
    DatasetType.SEQUENCE_VIDEO,
]

# 数据包异步处理轮询参数
PROCESS_POLL_MAX = 8        # 最大轮询次数
PROCESS_POLL_INTERVAL = 2   # 每次间隔秒

# ======================== 模块级辅助方法 ========================

def _create_dataset_as_pm(
    pm_user: dict, 
    name: str = None, 
    data_type: str = "image",
    description: str = "测试使用默认描述", 
    cover_url: str = None,
    allow_duplicate: bool = None, 
    tags: list = None):
    """以 PM 身份创建数据集，返回 (Response, dataset_name)"""
    login_with(pm_user["username"], DEFAULT_PASSWORD)
    dataset_name = name or faker_data.random_name(pre="ds", max_length=20)
    resp = dataset_api.create_dataset(
        name=dataset_name,
        data_type=data_type,
        description=description,
        cover_url=cover_url,
        allow_duplicate=allow_duplicate,
        tags=tags,
        org_id=pm_user["org_id"],
    )
    return resp, dataset_name


def _assert_create_success(resp, expected_name: str = None, msg_prefix: str = ""):
    """校验创建数据集成功；返回响应 data 字典"""
    resp_json = resp.json()
    assertion.assert_status_code(resp, 200)
    assertion.assert_equal(resp_json.get("code"), 0, f"{msg_prefix}创建数据集应成功")
    data = resp_json.get("data")
    assertion.assert_is_not_none(data, f"{msg_prefix}响应data不能为空")
    if expected_name:
        assertion.assert_equal(data.get("name"), expected_name, f"{msg_prefix}数据集名称不匹配")
    return data


def _assert_create_failed(resp, msg_prefix: str = ""):
    """校验创建数据集失败（业务码非 0）"""
    resp_json = resp.json()
    assertion.assert_status_code(resp, 200)
    assertion.assert_true(
        resp_json.get("code") != 0,
        f"{msg_prefix}创建数据集应失败，实际 code={resp_json.get('code')}",
    )


def _get_current_dataset(dataset_id: str) -> dict:
    """读取当前数据集的详情（name/description），供 PATCH 测试使用。

    原因：当前后端 PATCH 接口要求 body 中同时包含 name 和 description，
    否则返回 422 "此字段为必填项"。本辅助函数确保更新某一字段时把另一个必填字段也带上。
    """
    detail = dataset_api.get_dataset_detail(dataset_id).json().get("data") or {}
    return {"name": detail.get("name"), "description": detail.get("description")}


def _patch_dataset(dataset_id: str, **overrides) -> "Response":
    """封装 PATCH 调用：自动读取当前 name/description 并合并 overrides，
    解决后端 PATCH 必填 name+description 的约束。

    用法：
        resp = _patch_dataset(dataset_id, name="新名称")
        resp = _patch_dataset(dataset_id, description="新描述")
        resp = _patch_dataset(dataset_id, cover_url=cover_url)
    """
    cur = _get_current_dataset(dataset_id)
    body = {**cur, **overrides}
    return dataset_api.update_dataset(dataset_id=dataset_id, **body)


def _make_cover_bytes(fmt: str = "png", size_kb: int = 10) -> bytes:
    """构造不同格式的封面二进制；用于 upload_temp_cover。"""
    if fmt == "png":
        sig = b"\x89PNG\r\n\x1a\n"
        ihdr = b"\x00\x00\x00\x0dIHDR" + b"\x00" * 13
        idat = b"\x00" * max(size_kb, 32)
        iend = b"\x00\x00\x00\x00IEND\xaeB`\x82"
        return sig + ihdr + idat + iend
    if fmt == "jpg":
        return b"\xff\xd8\xff\xe0" + b"\x00" * max(size_kb, 64) + b"\xff\xd9"
    if fmt == "webp":
        return b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * max(size_kb, 32)
    if fmt == "gif":
        return b"GIF89a" + b"\x00" * max(size_kb, 32)
    return b"\x00" * max(size_kb, 32)


# ======================== 模块级 Fixture ========================

@pytest.fixture()
def shared_dataset(pm_user):
    """PM 共享数据集（用于更新/查询/弃用等场景）"""
    resp, name = _create_dataset_as_pm(pm_user, data_type="image", description="共享数据集")
    data = _assert_create_success(resp, expected_name=name, msg_prefix="[shared_dataset] ")
    dataset_id = data.get("id")
    logger.info(f"[datasets] 共享数据集创建成功: {dataset_id}")
    return {"id": dataset_id, "name": name, "org_id": pm_user["org_id"], "created_by": pm_user["username"]}

@pytest.fixture(scope='module')
def default_cover_url(pm_user):
    login_with(pm_user["username"], DEFAULT_PASSWORD)
    default_cover=COVER_PATH[0]
    resp = dataset_api.upload_temp_cover(
        file=open(default_cover['file'], "rb"),
        filename=default_cover['filename'],
        type=default_cover['type'],
        org_id=pm_user["org_id"],
    )
    result = resp.json()

# ======================== 权限测试 ========================

@pytest.mark.api
@pytest.mark.dataset
class TestDatasetPermission:

    def test_admin_cannot_view_dataset_list(self, shared_org, as_admin):
        """系统管理员不可查看数据集列表（仅 PM 可见）"""
        resp = dataset_api.get_datasets(org_id=shared_org)
        assertion.assert_response_success(resp, 403, "仅项目管理员可查看数据集")

    def test_pm_can_view_dataset_list(self, pm_user):
        """PM 可查看所在组织的数据集列表"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = dataset_api.get_datasets(org_id=pm_user["org_id"])
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(resp.json().get("code"), 0, "PM 应可查看数据集列表")

    # --- 非 PM 角色统一参数化（4 种角色共享同一断言逻辑） ---
    # (id, user_type, extra_create_kwargs)
    NON_PM_PERMISSION_CASES = [
        ("supplier_admin", UserType.SUPPLIER_ADMIN, "supplier_id"),
        ("org_team_admin", UserType.ORG_TEAM_ADMIN, "team_id"),
        ("org_team_member", UserType.ORG_TEAM_MEMBER, "team_id"),
    ]

    @pytest.mark.system
    @pytest.mark.parametrize(
        "case_id,user_type,extra_kwarg",
        NON_PM_PERMISSION_CASES,
        ids=[c[0] for c in NON_PM_PERMISSION_CASES],
    )
    def test_non_pm_cannot_view_dataset_list(
        self, pm_user, shared_org, shared_supplier, shared_team, db_roles,
        case_id, user_type, extra_kwarg,
    ):
        """非 PM 角色（供应商管理员/项目团队管理员/项目团队成员）不可查看数据集列表（403）

        通过参数化覆盖 3 种非 PM 角色：每个角色创建后登录，再请求数据集列表，
        期望业务码 403 + 错误信息 "仅项目管理员可查看数据集"。
        """
        if extra_kwarg == "supplier_id":
            kwargs = {"supplier_id": shared_supplier["id"]}
        else:
            kwargs = {"team_id": shared_team["id"]}

        resp_json, username, _ = _do_create_user(
            user_type, shared_org, db_roles, **kwargs
        )
        assertion.assert_equal(resp_json.get("code"), 0, f"{case_id} 用户创建应成功")

        login_with(username, DEFAULT_PASSWORD)
        resp = dataset_api.get_datasets(org_id=shared_org)
        result = resp.json()
        logger.info(
            f"[{case_id}] 角色查看数据集列表 -> code={result.get('code')}, msg={result.get('msg')}"
        )

        assertion.assert_response_success(resp, 403, "仅项目管理员可查看数据集")

# ======================== 新增数据集 ========================

@pytest.mark.api
@pytest.mark.dataset
class TestCreateDataset:
    """新增数据集测试"""
    def test_pm_create_dataset_success(self, pm_user):
        """PM 创建数据集 - 必填参数 - 创建成功"""
        resp, name = _create_dataset_as_pm(pm_user, data_type="image", description="测试数据集")
        data = _assert_create_success(resp, expected_name=name)
        assertion.assert_is_not_none(data.get("id"), "数据集ID不能为空")
        assertion.assert_equal(data.get("data_type"), "image", "数据类型不匹配")
        assertion.assert_equal(data.get("organization_id"), pm_user["org_id"], "组织ID不匹配")

    def test_pm_create_dataset_with_cover(self, pm_user):
        """PM 创建数据集 - 带封面URL - 创建成功"""
        cover_url = "covers/798176ee-d854-497e-98dc-da461e3a073f.png"
        resp, name = _create_dataset_as_pm(pm_user, cover_url=cover_url, description="带封面")
        data = _assert_create_success(resp, expected_name=name)
        assertion.assert_equal(data.get("cover_url"), cover_url, "封面URL不匹配")
    
    @pytest.mark.skip(reason='产品需求未设计')
    def test_pm_create_dataset_with_tags(self, pm_user):
        """PM 创建数据集 - 带标签 - 创建成功"""
        tags = ["tag1", "tag2"]
        resp, name = _create_dataset_as_pm(pm_user, tags=tags, description="带标签")
        _assert_create_success(resp, expected_name=name)

    @pytest.mark.skip(reason='产品需求未设计')
    def test_pm_create_dataset_allow_duplicate_true(self, pm_user):
        """PM 创建数据集 - 允许重复创建-创建成功"""
        resp, name = _create_dataset_as_pm(pm_user, allow_duplicate=True, description="允许重复")
        _assert_create_success(resp, expected_name=name)

    @pytest.mark.smoke
    @pytest.mark.parametrize("data_type", DATASET_TYPES)
    def test_pm_create_dataset_all_types(self, pm_user, data_type):
        """PM 创建数据集 - 遍历所有合法类型 - 均成功"""
        resp, name = _create_dataset_as_pm(pm_user, data_type=data_type, description=f"类型-{data_type}")
        _assert_create_success(resp, expected_name=name)

    @pytest.mark.parametrize("case_id,name,description,msg_prefix", [
        ("name_required", "", "缺名称", "名称为空: "),
        ("name_too_long", "a" * 21, "名称超长", "名称超长: "),
        ("description_too_long", None, "x" * 201, "描述超长: "),
    ], ids=["name_required", "name_too_long", "description_too_long"])
    def test_create_dataset_invalid_input(self, pm_user, case_id, name, description, msg_prefix):
        """PM 创建数据集 - 非法输入（名称为空/名称超长/描述超长）- 失败"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        actual_name = name if name is not None else faker_data.random_name(pre="ds", max_length=20)
        resp = dataset_api.create_dataset(
            name=actual_name, data_type="image", description=description, org_id=pm_user["org_id"],
        )
        _assert_create_failed(resp, msg_prefix=msg_prefix)

    def test_create_dataset_invalid_type(self, pm_user):
        """创建数据集 - 错误的数据集类型 - 失败"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = dataset_api.create_dataset(
            name=faker_data.random_name(pre="ds", max_length=20),
            data_type="unknown_type", description="非法类型", org_id=pm_user["org_id"],
        )
        _assert_create_failed(resp, msg_prefix="非法类型: ")

    def test_create_dataset_without_auth(self, pm_user):
        """未登录创建数据集 - 应返回 401"""
        http_client.remove_token()

        resp = dataset_api.create_dataset(
            name="未授权", data_type="image", description="无token", org_id=pm_user["org_id"]
        )
        assertion.assert_response_success(resp,401,"未认证，请先登录")

        login_as("admin")  # 恢复


# ======================== 查询数据集 ========================

class TestListDataset:
    """查询数据集测试"""

    def test_pm_list_only_own_org(self, pm_user, another_pm, shared_dataset):
        """PM 查询 - 仅返回所在组织的数据集（跨组织隔离）"""
        resp, _ = _create_dataset_as_pm(another_pm, data_type="text", description="另一组织数据集")
        _assert_create_success(resp)

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = dataset_api.get_datasets(org_id=pm_user["org_id"])
        assertion.assert_status_code(resp, 200)

        items = get_list_items(resp.json())
        org_ids = {item.get("organization_id") for item in items}
        assertion.assert_true(
            all(oid == pm_user["org_id"] for oid in org_ids if oid),
            f"列表中包含其他组织数据集: {org_ids}",
        )
        ids = {item.get("id") for item in items}
        assertion.assert_true(
            shared_dataset["id"] in ids,
            "未查询到当前组织数据集",
        )

    def test_pm_cannot_see_peer_org_datasets(self, pm_user, peer_pm):
        """PM 查询 - 不可见同组织其他 PM 创建的数据集"""
        resp, peer_name = _create_dataset_as_pm(
            peer_pm, data_type="text", description="同组织peer PM数据集"
        )
        peer_data = _assert_create_success(resp, expected_name=peer_name)
        peer_dataset_id = peer_data.get("id")

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = dataset_api.get_datasets(org_id=pm_user["org_id"])
        assertion.assert_status_code(resp, 200)
        items = get_list_items(resp.json())

        ids = {item.get("id") for item in items}
        assertion.assert_true(
            peer_dataset_id not in ids,
            f"PM 不应看到同组织 peer PM 创建的数据集: {peer_dataset_id}",
        )

        for item in items:
            creator = item.get("created_by_id") or item.get("created_by")
            assertion.assert_true(
                creator == pm_user["user_id"] or creator is None,
                f"列表中存在非当前 PM 创建的数据集: {creator}",
            )

    def test_pm_list_by_name_fuzzy(self, pm_user, shared_dataset):
        """PM 按名称模糊查询 - 命中"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = dataset_api.get_datasets(org_id=pm_user["org_id"], name=shared_dataset["name"][:6])
        assertion.assert_status_code(resp, 200)
        items = get_list_items(resp.json())
        ids = {item.get("id") for item in items}
        assertion.assert_true(
            shared_dataset["id"] in ids,
            "模糊查询未命中",
        )

    def test_pm_list_by_name_miss(self, pm_user):
        """PM 按名称模糊查询 - 不存在 - 返回空"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = dataset_api.get_datasets(org_id=pm_user["org_id"], name="notexist_zzz")
        assertion.assert_status_code(resp, 200)
        items = get_list_items(resp.json())
        assertion.assert_equal(len(items), 0, "不存在的名称应返回空")

    def test_pm_list_by_data_type_single(self, pm_user, shared_dataset):
        """PM 按类型单选查询 - 命中 image"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = dataset_api.get_datasets(org_id=pm_user["org_id"], data_type="image")
        items = get_list_items(resp.json())
        assertion.assert_true(
            all(item.get("data_type") == "image" for item in items),
            "列表中存在非 image 类型",
        )

    def test_pm_list_by_data_type_multi(self, pm_user):
        """PM 按类型多选查询 - 命中 image + text"""
        resp, _ = _create_dataset_as_pm(pm_user, data_type="text", description="多类型查询")
        _assert_create_success(resp)
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = dataset_api.get_datasets(org_id=pm_user["org_id"], data_type="image,text")
        items = get_list_items(resp.json())
        types = {item.get("data_type") for item in items}
        assertion.assert_true(
            types <= {"image", "text"},
            f"列表中含非预期类型: {types}",
        )

    @pytest.mark.parametrize("status", DATASET_STATUSES)
    def test_pm_list_by_status_single(self, pm_user, status):
        """PM 按状态单选查询 - 仅返回该状态的数据集"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = dataset_api.get_datasets(org_id=pm_user["org_id"], status=status)
        assertion.assert_status_code(resp, 200)
        items = get_list_items(resp.json())
        assertion.assert_true(isinstance(items, list), "items 应为列表")
        for item in items:
            assertion.assert_equal(
                item.get("status"), status,
                f"按 {status} 过滤后出现非 {status} 状态的数据集: {item.get('id')}"
            )

    def test_pm_list_by_status_multi(self, pm_user):
        """PM 按状态多选查询 - 仅返回选中状态的数据集"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        target_statuses = ["unused", "inuse"]
        resp = dataset_api.get_datasets(
            org_id=pm_user["org_id"], status=",".join(target_statuses)
        )
        assertion.assert_status_code(resp, 200)
        items = get_list_items(resp.json())
        for item in items:
            assertion.assert_true(
                item.get("status") in target_statuses,
                f"按 {target_statuses} 过滤后出现非预期状态: id={item.get('id')}, status={item.get('status')}"
            )

    def test_pm_list_order_by_updated_desc(self, pm_user):
        """PM 查询 - 按更新时间倒序"""
        resp1, _ = _create_dataset_as_pm(pm_user, data_type="audio", description="较早")
        _assert_create_success(resp1)
        time.sleep(1.2)
        resp2, _ = _create_dataset_as_pm(pm_user, data_type="video", description="较新")
        data2 = _assert_create_success(resp2)
        newer_id = data2.get("id")

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = dataset_api.get_datasets(org_id=pm_user["org_id"])
        items = get_list_items(resp.json())
        if len(items) >= 2:
            ts_list = [item.get("updated_at") for item in items if item.get("updated_at")]
            assert ts_list == sorted(ts_list, reverse=True), f"未按更新时间倒序: {ts_list[:5]}"
        ids = {item.get("id") for item in items}
        assert newer_id in ids, "新建数据集未出现在列表中"

    def test_pm_list_pagination(self, pm_user):
        """PM 查询 - 分页参数生效"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp1 = dataset_api.get_datasets(org_id=pm_user["org_id"], page=1, page_size=1)
        items1 = get_list_items(resp1.json())
        resp2 = dataset_api.get_datasets(org_id=pm_user["org_id"], page=2, page_size=1)
        items2 = get_list_items(resp2.json())
        ids1 = {item.get("id") for item in items1}
        ids2 = {item.get("id") for item in items2}
        assert ids1.isdisjoint(ids2) or len(items2) == 0, "分页结果存在重复"


# ======================== 编辑数据集 ========================

class TestUpdateDataset:
    """编辑数据集信息"""

    def test_pm_update_dataset_name(self, pm_user, shared_dataset):
        """PM 编辑自己创建数据集 - 修改名称 - 成功"""
        new_name = faker_data.random_name(pre="ds_upd", max_length=20)
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = _patch_dataset(shared_dataset["id"], name=new_name)
        assertion.assert_equal(resp.json().get("code"), 0, "编辑名称应成功")
        assertion.assert_equal(resp.json().get("data", {}).get("name"), new_name, "名称未更新")

    def test_pm_update_dataset_description(self, pm_user, shared_dataset):
        """PM 编辑自己创建数据集 - 修改描述 - 成功"""
        new_desc = "新描述"
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = _patch_dataset(shared_dataset["id"], description=new_desc)
        result = resp.json()
        assertion.assert_equal(result.get("code"), 0, "编辑描述应成功")
        assertion.assert_equal(
            result.get("data", {}).get("description"), new_desc,
            "响应 data.description 未更新",
        )
        detail = dataset_api.get_dataset_detail(shared_dataset["id"]).json().get("data") or {}
        assertion.assert_equal(
            detail.get("description"), new_desc,
            "详情接口 description 未落库",
        )

    def test_pm_update_dataset_cover(self, pm_user, shared_dataset):
        """PM 编辑自己创建数据集 - 修改封面 - 成功"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)

        cover = COVER_PATH[1]  # jpg
        with open(cover["file"], "rb") as f:
            cover_bytes = f.read()
        upload_resp = dataset_api.upload_temp_cover(
            file=cover_bytes,
            filename=cover["filename"],
            type=cover["type"],
            org_id=pm_user["org_id"],
        )
        upload_result = upload_resp.json()
        assertion.assert_equal(upload_result.get("code"), 0, "上传封面应成功")
        cover_url = (upload_result.get("data") or {}).get("cover_url")
        assertion.assert_is_not_none(cover_url, "上传响应应返回 cover_url")
        logger.info(f"上传封面成功, cover_url={cover_url}")

        resp = _patch_dataset(shared_dataset["id"], cover_url=cover_url)
        assertion.assert_equal(resp.json().get("code"), 0, "编辑封面应成功")

        detail = dataset_api.get_dataset_detail(shared_dataset["id"]).json().get("data") or {}
        assertion.assert_equal(detail.get("cover_url"), cover_url, "cover_url 未更新")

    # @pytest.mark.xfail(
    #     reason="后端 bug：无数据包时 data_type 修改返回 code=0 但实际值未更新（后端静默忽略）。"
    #            "按需求应允许修改，待后端修复后启用。",
    #     strict=False,
    # )
    def test_pm_update_data_type_no_package(self, pm_user):
        """PM 编辑数据集 - 无数据包时修改数据类型 - 成功"""
        create_resp, name = _create_dataset_as_pm(pm_user, data_type="image", description="待改类型")
        data = _assert_create_success(create_resp, expected_name=name)
        dataset_id = data.get("id")

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        cur = _get_current_dataset(dataset_id)
        resp = dataset_api.update_dataset(
            dataset_id=dataset_id,
            name=cur["name"],
            description=cur["description"],
            data_type="audio",
        )
        result = resp.json()
        logger.info(f"无数据包修改 data_type -> code={result.get('code')}, msg={result.get('msg')}")
        assertion.assert_equal(result.get("code"), 0, "无数据包时修改 data_type 应成功")

        detail = dataset_api.get_dataset_detail(dataset_id).json().get("data", {})
        assertion.assert_equal(detail.get("data_type"), "audio", "data_type 应已更新为 audio")

    def test_pm_cannot_update_data_type_with_package(self, pm_user):
        """PM 编辑数据集 - 有数据包时修改数据类型 - 不允许"""
        create_resp, name = _create_dataset_as_pm(pm_user, data_type="image", description="有数据包待改类型")
        data = _assert_create_success(create_resp, expected_name=name)
        dataset_id = data.get("id")

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        package_path, package_filename = PACKAGE_TEST_FILES[DatasetType.IMAGE]
        with open(package_path, "rb") as f:
            package_bytes = f.read()
        upload_resp = dataset_api.upload_package_to_temp(
            dataset_id=dataset_id,
            file=package_bytes,
            filename=package_filename,
            content_type="application/zip",
        )
        upload_result = upload_resp.json()
        logger.info(f"上传数据包 -> code={upload_result.get('code')}")
        assertion.assert_equal(upload_result.get("code"), 0, "上传数据包应成功")

        cur = _get_current_dataset(dataset_id)
        resp = dataset_api.update_dataset(
            dataset_id=dataset_id,
            name=cur["name"],
            description=cur["description"],
            data_type="audio",
        )
        result = resp.json()
        logger.info(f"有数据包修改 data_type -> code={result.get('code')}, msg={result.get('msg')}")

        detail = dataset_api.get_dataset_detail(dataset_id).json().get("data", {})
        assertion.assert_equal(detail.get("data_type"), "image", "有数据包时 data_type 不应被修改")

    def test_pm_update_dataset_name_too_long(self, pm_user, shared_dataset):
        """PM 编辑自己创建数据集 - 名称超长 - 失败"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = _patch_dataset(shared_dataset["id"], name="a" * 21)
        assertion.assert_true(resp.json().get("code") != 0, "名称超长应失败")

    def test_pm_cannot_update_other_org_dataset(self, pm_user, another_pm):
        """PM 不可编辑其他组织的数据集"""
        resp, name = _create_dataset_as_pm(another_pm, data_type="text", description="其他组织")
        data = _assert_create_success(resp, expected_name=name)
        other_dataset_id = data.get("id")
        other_desc = data.get("description", "其他组织")

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = _patch_dataset(other_dataset_id, name="跨界修改", description=other_desc)
        assertion.assert_equal(resp.json().get("code"), 403, "跨组织编辑应被拒绝")

    def test_pm_cannot_update_peer_pm_dataset(self, pm_user, peer_pm):
        """PM 不可编辑同组织下其他 PM 创建的数据集（403）"""
        create_resp, name = _create_dataset_as_pm(peer_pm, data_type="image", description="peer_pm的数据集")
        data = _assert_create_success(create_resp, expected_name=name)
        dataset_id = data.get("id")
        cur = _get_current_dataset(dataset_id)

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = dataset_api.update_dataset(
            dataset_id=dataset_id,
            name="同组织PM尝试修改",
            description=cur["description"],
        )
        result = resp.json()
        logger.info(f"[peer_pm] 编辑数据集 -> code={result.get('code')}, msg={result.get('msg')}")
        assertion.assert_equal(result.get("code"), 403, "同组织 PM 编辑他人数据集应返回 403")

        login_with(peer_pm["username"], DEFAULT_PASSWORD)
        detail = dataset_api.get_dataset_detail(dataset_id).json().get("data") or {}
        assertion.assert_equal(
            detail.get("name"), name,
            "数据集名称不应被同组织其他 PM 修改",
        )

    @pytest.mark.xfail(
        reason="后端 bug：系统管理员编辑数据集实际返回 code=0（成功），未做权限校验。",
        strict=False,
    )
    @pytest.mark.system
    def test_admin_cannot_update_dataset(self, pm_user, shared_dataset, as_admin):
        """系统管理员不可编辑数据集信息（403）"""
        dataset_id = shared_dataset["id"]

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        cur = _get_current_dataset(dataset_id)

        resp = dataset_api.update_dataset(
            dataset_id=dataset_id,
            name="管理员尝试修改",
            description=cur["description"],
        )
        result = resp.json()
        logger.info(f"[admin] 编辑数据集 -> code={result.get('code')}, msg={result.get('msg')}")
        assertion.assert_equal(result.get("code"), 403, "系统管理员编辑数据集应返回 403")

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        detail = dataset_api.get_dataset_detail(dataset_id).json().get("data") or {}
        assertion.assert_equal(
            detail.get("name"), shared_dataset["name"],
            "数据集名称不应被系统管理员修改",
        )

    @pytest.mark.parametrize(
        "case_id,user_type,extra_kwarg",
        TestDatasetPermission.NON_PM_PERMISSION_CASES,
        ids=[c[0] for c in TestDatasetPermission.NON_PM_PERMISSION_CASES],
    )
    @pytest.mark.system
    def test_non_pm_cannot_update_dataset(
        self, pm_user, shared_org, shared_supplier, shared_team, db_roles,
        case_id, user_type, extra_kwarg,
    ):
        """非 PM 角色（供应商管理员/项目团队管理员/项目团队成员）不可编辑数据集（403）"""
        create_resp, name = _create_dataset_as_pm(pm_user, data_type="image", description=f"待非PM编辑-{case_id}")
        data = _assert_create_success(create_resp, expected_name=name)
        dataset_id = data.get("id")
        cur = _get_current_dataset(dataset_id)

        if extra_kwarg == "supplier_id":
            kwargs = {"supplier_id": shared_supplier["id"]}
        else:
            kwargs = {"team_id": shared_team["id"]}
        resp_json, username, _ = _do_create_user(
            user_type, shared_org, db_roles, **kwargs
        )
        assertion.assert_equal(resp_json.get("code"), 0, f"{case_id} 用户创建应成功")

        login_with(username, DEFAULT_PASSWORD)
        resp = dataset_api.update_dataset(
            dataset_id=dataset_id,
            name="非PM尝试修改",
            description=cur["description"],
        )
        result = resp.json()
        logger.info(f"[{case_id}] 编辑数据集 -> code={result.get('code')}, msg={result.get('msg')}")
        assertion.assert_equal(result.get("code"), 403, f"{case_id} 编辑数据集应返回 403")

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        detail = dataset_api.get_dataset_detail(dataset_id).json().get("data") or {}
        assertion.assert_equal(
            detail.get("name"), name,
            f"{case_id} 数据集名称不应被修改",
        )


# ======================== 弃用数据集 ========================

class TestDeprecateDataset:
    """弃用数据集测试"""

    def test_pm_deprecate_dataset(self, pm_user):
        """PM 弃用 unused 数据集 - 成功"""
        resp, name = _create_dataset_as_pm(pm_user, data_type="image", description="待弃用")
        data = _assert_create_success(resp, expected_name=name)
        dataset_id = data.get("id")

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = dataset_api.deprecate_dataset(dataset_id=dataset_id, reason="测试弃用")
        assertion.assert_equal(resp.json().get("code"), 0, "弃用应成功")
        detail = dataset_api.get_dataset_detail(dataset_id).json()
        assertion.assert_equal(
            detail.get("data", {}).get("status"), "deprecated", "状态应变为 deprecated"
        )

    @pytest.mark.parametrize(
        "case_id,user_type,extra_kwarg",
        TestDatasetPermission.NON_PM_PERMISSION_CASES,
        ids=[c[0] for c in TestDatasetPermission.NON_PM_PERMISSION_CASES],
    )
    @pytest.mark.system
    def test_non_pm_cannot_deprecate_dataset(
        self, pm_user, shared_org, shared_supplier, shared_team, db_roles,
        case_id, user_type, extra_kwarg,
    ):
        """非 PM 角色（供应商管理员/项目团队管理员/项目团队成员）不可弃用数据集（403）"""
        create_resp, name = _create_dataset_as_pm(pm_user, data_type="image", description=f"待非PM弃用-{case_id}")
        data = _assert_create_success(create_resp, expected_name=name)
        dataset_id = data.get("id")

        if extra_kwarg == "supplier_id":
            kwargs = {"supplier_id": shared_supplier["id"]}
        else:
            kwargs = {"team_id": shared_team["id"]}
        resp_json, username, _ = _do_create_user(
            user_type, shared_org, db_roles, **kwargs
        )
        assertion.assert_equal(resp_json.get("code"), 0, f"{case_id} 用户创建应成功")

        login_with(username, DEFAULT_PASSWORD)
        resp = dataset_api.deprecate_dataset(dataset_id=dataset_id, reason="非PM尝试弃用")

        assertion.assert_response_success(resp,403,"当前角色权限不足")

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        detail = dataset_api.get_dataset_detail(dataset_id).json().get("data") or {}
        assertion.assert_equal(
            detail.get("status"), "unused",
            f"{case_id} 数据集状态应保持 unused，不应被非 PM 弃用，实际 status={detail.get('status')}",
        )

class TestUploadCover:
    """临时上传封面图测试"""

    @pytest.mark.parametrize("cover", COVER_PATH)
    def test_upload_cover_valid_format(self, pm_user, cover):
        """上传封面 - 合法格式 - 成功"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)

        resp = dataset_api.upload_temp_cover(
            file=open(cover["file"], "rb"),
            filename=cover["filename"],
            type=cover["type"],
            org_id=pm_user["org_id"],
        )
        result = resp.json()
        assertion.assert_true(result.get('data').get('cover_url'),"上传封面未返回cover_url值")
        logger.info(f"上传封面图请求结束， code={result.get('code')}")

    @pytest.mark.xfail(
        reason="后端 upload-cover 暂未校验文件格式（应拒绝 gif 等非允许格式），待后端增加校验后启用",
        strict=False,
    )
    def test_upload_cover_invalid_format(self, pm_user):
        """上传封面 - 非法格式（gif）- 失败（xfail：后端未做格式校验）"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = dataset_api.upload_temp_cover(
            file=_make_cover_bytes(fmt="gif"),
            org_id=pm_user["org_id"],
        )
        assertion.assert_true(resp.json().get("code") != 0, "gif 格式应被拒绝")

    @pytest.mark.xfail(
        reason="后端 upload-cover 暂未校验文件大小（应拒绝 >5MB 文件），待后端增加校验后启用",
        strict=False,
    )
    def test_upload_cover_oversize(self, pm_user):
        """上传封面 - 超过 5MB - 失败（xfail：后端未做大小校验）"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        big = _make_cover_bytes(fmt="png", size_kb=5 * 1024 + 1)
        resp = dataset_api.upload_temp_cover(
            file=big,
            org_id=pm_user["org_id"],
        )
        assertion.assert_true(resp.json().get("code") != 0, "5MB+1 应被拒绝")

    def test_upload_cover_unauthorized(self, pm_user):
        """上传封面 - 未登录 - 应返回 401"""
        http_client.remove_token()
        try:
            cover = COVER_PATH[0]  # png
            with open(cover["file"], "rb") as f:
                cover_bytes = f.read()
            resp = dataset_api.upload_temp_cover(
                file=cover_bytes,
                filename=cover["filename"],
                type=cover["type"],
                org_id=pm_user["org_id"],
            )
            assertion.assert_response_success(resp, 401, "未认证，请先登录")
        finally:
            login_as("admin")  # 恢复 session 避免污染其他用例

    @pytest.mark.parametrize(
        "case_id,user_type,extra_kwarg",
        TestDatasetPermission.NON_PM_PERMISSION_CASES,
        ids=[c[0] for c in TestDatasetPermission.NON_PM_PERMISSION_CASES],
    )
    @pytest.mark.system
    def test_upload_cover_non_pm_forbidden(
        self, pm_user, shared_org, shared_supplier, shared_team, db_roles,
        case_id, user_type, extra_kwarg,
    ):
        """非 PM 角色（供应商管理员/项目团队管理员/项目团队成员）上传封面 - 应返回 403"""
        if extra_kwarg == "supplier_id":
            kwargs = {"supplier_id": shared_supplier["id"]}
        else:
            kwargs = {"team_id": shared_team["id"]}
        resp_json, username, _ = _do_create_user(
            user_type, shared_org, db_roles, **kwargs
        )
        assertion.assert_equal(resp_json.get("code"), 0, f"{case_id} 用户创建应成功")

        login_with(username, DEFAULT_PASSWORD)
        cover = COVER_PATH[0]
        with open(cover["file"], "rb") as f:
            cover_bytes = f.read()
        resp = dataset_api.upload_temp_cover(
            file=cover_bytes,
            filename=cover["filename"],
            type=cover["type"],
            org_id=shared_org,
        )
        result = resp.json()
        logger.info(
            f"[{case_id}] 非 PM 上传封面 -> code={result.get('code')}, msg={result.get('msg')}"
        )

        assertion.assert_equal(result.get("code"), 403, f"{case_id} 上传应返回 403")
        msg = result.get("msg") or ""
        assertion.assert_true(
            "权限" in msg or "管理员" in msg or "项目" in msg,
            f"{case_id} 错误信息应提示权限/管理员限制，实际: {msg}",
        )


# ======================== 编辑数据集封面 ========================

_COVER_DIR = os.path.join(_TEST_SRC_DIR, "data", "static", "cover")
NEW_COVER_PATH = [
    {"file": os.path.join(_COVER_DIR, "test_cover.png"), "filename": "test_cover.png", "type": "image/png"},
    {"file": os.path.join(_COVER_DIR, "test_cover.jpg"), "filename": "test_cover.jpg", "type": "image/jpeg"},
    {"file": os.path.join(_COVER_DIR, "test_cover.jpeg"), "filename": "test_cover.jpeg", "type": "image/jpeg"},
    {"file": os.path.join(_COVER_DIR, "test_cover.webp"), "filename": "test_cover.webp", "type": "image/webp"},
]
OVERSIZE_COVER = os.path.join(_COVER_DIR, "oversize_cover.png")


class TestUpdateCover:
    """编辑数据集封面测试

    需求：
    - 数据集下无数据时，可修改封面
    - 封面格式：jpg/jpeg/png/webp
    - 单文件不超过 5MB
    - 仅创建数据集的 PM 可操作
    """

    @pytest.mark.parametrize("cover", NEW_COVER_PATH)
    def test_pm_update_cover_no_data(self, pm_user, cover):
        """PM 编辑无数据的数据集封面 - {cover[filename]} - 成功"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp, name = _create_dataset_as_pm(pm_user, data_type="image", description="无数据封面测试")
        data = _assert_create_success(resp, expected_name=name)
        dataset_id = data.get("id")

        with open(cover["file"], "rb") as f:
            cover_bytes = f.read()
        upload_resp = dataset_api.upload_temp_cover(
            file=cover_bytes,
            filename=cover["filename"],
            type=cover["type"],
            org_id=pm_user["org_id"],
        )
        upload_result = upload_resp.json()
        assertion.assert_equal(upload_result.get("code"), 0, "上传封面应成功")
        cover_url = (upload_result.get("data") or {}).get("cover_url")
        assertion.assert_is_not_none(cover_url, "上传响应应返回 cover_url")
        logger.info(f"上传封面成功, cover_url={cover_url}")

        resp = _patch_dataset(dataset_id, cover_url=cover_url)
        assertion.assert_equal(resp.json().get("code"), 0, "编辑封面应成功")

        detail = dataset_api.get_dataset_detail(dataset_id).json().get("data") or {}
        assertion.assert_equal(detail.get("cover_url"), cover_url, "cover_url 未更新")
        logger.info(f"[update_cover] 数据集封面更新成功: format={cover['type']}")

    def test_pm_update_cover_invalid_format(self, pm_user):
        """PM 编辑无数据的数据集封面 - 非法格式(gif) - 应失败"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp, name = _create_dataset_as_pm(pm_user, data_type="image", description="非法格式封面测试")
        data = _assert_create_success(resp, expected_name=name)
        dataset_id = data.get("id")

        gif_bytes = b"GIF89a" + b"\x00" * 100
        upload_resp = dataset_api.upload_temp_cover(
            file=gif_bytes,
            filename="test.gif",
            type="image/gif",
            org_id=pm_user["org_id"],
        )
        result = upload_resp.json()
        assertion.assert_true(result.get("code") != 0, "gif 格式应被拒绝")

    def test_pm_update_cover_oversize(self, pm_user):
        """PM 编辑无数据的数据集封面 - 超过 5MB - 应失败"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp, name = _create_dataset_as_pm(pm_user, data_type="image", description="超大封面测试")
        data = _assert_create_success(resp, expected_name=name)
        dataset_id = data.get("id")

        with open(OVERSIZE_COVER, "rb") as f:
            oversize_bytes = f.read()
        upload_resp = dataset_api.upload_temp_cover(
            file=oversize_bytes,
            filename="oversize_cover.png",
            type="image/png",
            org_id=pm_user["org_id"],
        )
        result = upload_resp.json()
        assertion.assert_true(result.get("code") != 0, "超过 5MB 应被拒绝")

    def test_pm_update_cover_cross_org_forbidden(self, pm_user, another_pm):
        """跨组织 PM 不可编辑数据集封面 - 403"""
        login_with(another_pm["username"], DEFAULT_PASSWORD)
        resp, name = _create_dataset_as_pm(another_pm, data_type="image", description="跨组织封面")
        data = _assert_create_success(resp, expected_name=name)
        dataset_id = data.get("id")
        # 用创建者 session 获取当前 name/description（PATCH 必填）
        cur = _get_current_dataset(dataset_id)

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        cover = NEW_COVER_PATH[0]
        with open(cover["file"], "rb") as f:
            cover_bytes = f.read()
        upload_resp = dataset_api.upload_temp_cover(
            file=cover_bytes, filename=cover["filename"], type=cover["type"],
            org_id=pm_user["org_id"],
        )
        upload_result = upload_resp.json()
        assertion.assert_equal(upload_result.get("code"), 0, "上传封面应成功")
        cover_url = (upload_result.get("data") or {}).get("cover_url")

        resp = dataset_api.update_dataset(
            dataset_id=dataset_id,
            name=cur["name"],
            description=cur["description"],
            cover_url=cover_url,
        )
        result = resp.json()
        logger.info(f"[cross_org] 跨组织 PM 更新封面 -> code={result.get('code')}, msg={result.get('msg')}")
        assertion.assert_equal(result.get("code"), 403, "跨组织 PM 更新封面应返回 403")

    def test_pm_update_cover_peer_pm_forbidden(self, pm_user, peer_pm):
        """同组织其他 PM 不可编辑数据集封面 - 403"""
        login_with(peer_pm["username"], DEFAULT_PASSWORD)
        resp, name = _create_dataset_as_pm(peer_pm, data_type="image", description="peer封面")
        data = _assert_create_success(resp, expected_name=name)
        dataset_id = data.get("id")
        # 用创建者 session 获取当前 name/description（PATCH 必填）
        cur = _get_current_dataset(dataset_id)

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        cover = NEW_COVER_PATH[0]
        with open(cover["file"], "rb") as f:
            cover_bytes = f.read()
        upload_resp = dataset_api.upload_temp_cover(
            file=cover_bytes, filename=cover["filename"], type=cover["type"],
            org_id=pm_user["org_id"],
        )
        upload_result = upload_resp.json()
        assertion.assert_equal(upload_result.get("code"), 0, "上传封面应成功")
        cover_url = (upload_result.get("data") or {}).get("cover_url")

        resp = dataset_api.update_dataset(
            dataset_id=dataset_id,
            name=cur["name"],
            description=cur["description"],
            cover_url=cover_url,
        )
        result = resp.json()
        logger.info(f"[peer_pm] 同组织其他 PM 更新封面 -> code={result.get('code')}, msg={result.get('msg')}")
        assertion.assert_equal(result.get("code"), 403, "同组织其他 PM 更新封面应返回 403")

    @pytest.mark.parametrize(
        "case_id,user_type,extra_kwarg",
        TestDatasetPermission.NON_PM_PERMISSION_CASES,
        ids=[c[0] for c in TestDatasetPermission.NON_PM_PERMISSION_CASES],
    )
    @pytest.mark.system
    def test_update_cover_non_pm_forbidden(
        self, pm_user, shared_org, shared_supplier, shared_team, db_roles,
        case_id, user_type, extra_kwarg,
    ):
        """非 PM 角色不可编辑数据集封面 - 403"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp, name = _create_dataset_as_pm(pm_user, data_type="image", description="非PM封面测试")
        data = _assert_create_success(resp, expected_name=name)
        dataset_id = data.get("id")

        cover = NEW_COVER_PATH[0]
        with open(cover["file"], "rb") as f:
            cover_bytes = f.read()
        upload_resp = dataset_api.upload_temp_cover(
            file=cover_bytes, filename=cover["filename"], type=cover["type"],
            org_id=pm_user["org_id"],
        )
        upload_result = upload_resp.json()
        assertion.assert_equal(upload_result.get("code"), 0, "上传封面应成功")
        cover_url = (upload_result.get("data") or {}).get("cover_url")

        cur = _get_current_dataset(dataset_id)

        if extra_kwarg == "supplier_id":
            kwargs = {"supplier_id": shared_supplier["id"]}
        else:
            kwargs = {"team_id": shared_team["id"]}
        resp_json, username, _ = _do_create_user(user_type, shared_org, db_roles, **kwargs)
        assertion.assert_equal(resp_json.get("code"), 0, f"{case_id} 用户创建应成功")

        login_with(username, DEFAULT_PASSWORD)
        resp = dataset_api.update_dataset(
            dataset_id=dataset_id,
            name=cur["name"],
            description=cur["description"],
            cover_url=cover_url,
        )
        result = resp.json()
        logger.info(
            f"[update_cover] {case_id} 非 PM 更新封面 -> code={result.get('code')}, msg={result.get('msg')}"
        )
        assertion.assert_equal(result.get("code"), 403, f"{case_id} 更新封面应返回 403")

    def test_update_cover_unauthorized(self, pm_user):
        """未登录编辑数据集封面 - 401"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp, name = _create_dataset_as_pm(pm_user, data_type="image", description="未登录封面测试")
        data = _assert_create_success(resp, expected_name=name)
        dataset_id = data.get("id")

        cur = _get_current_dataset(dataset_id)

        http_client.remove_token()
        try:
            resp = dataset_api.update_dataset(
                dataset_id=dataset_id,
                name=cur["name"],
                description=cur["description"],
                cover_url="covers/test.png",
            )
            assertion.assert_response_success(resp, 401, "未认证，请先登录")
        finally:
            login_as("admin")


def _upload_package(dataset_id: str, file: bytes, filename: str, content_type: str = "application/zip"):
    """封装：上传数据包，提取 object_keys"""
    resp = dataset_api.upload_package_to_temp(
        dataset_id=dataset_id,
        file=file,
        filename=filename,
        content_type=content_type,
    )
    result = resp.json()
    data = result.get("data")
    if not isinstance(data, dict):
        logger.warning(f"upload data 非 dict: type={type(data).__name__}, data={data}")
        return result, []

    object_key = data.get("object_key") or data.get("object_keys")
    object_keys = [object_key] if object_key else []

    logger.info(
        f"上传数据包: http={resp.status_code}, code={result.get('code')}, "
        f"object_key={object_key}, file_name={data.get('file_name')}, file_size={data.get('file_size')}"
    )
    return result, object_keys


def _poll_upload_record(dataset_id: str, file_name: str, max_wait: int = PROCESS_POLL_MAX):
    """轮询直到查询到指定 file_name 的上传记录或超时，返回 record 或 None"""
    deadline = time.time() + max_wait * PROCESS_POLL_INTERVAL
    last_records = []
    while time.time() < deadline:
        time.sleep(PROCESS_POLL_INTERVAL)
        resp = dataset_api.get_package_upload_records(dataset_id=dataset_id, page=1, page_size=20)
        result = resp.json()
        if result.get("code") != 0:
            logger.warning(f"查询上传记录失败: {result.get('msg')}")
            continue
        data_obj = result.get("data") or {}
        records = (
            data_obj.get("items")
            or data_obj.get("records")
            or data_obj.get("list")
            or (data_obj if isinstance(data_obj, list) else [])
        )
        last_records = records
        for r in records:
            name_field = r.get("file_name") or r.get("name") or r.get("original_filename") or ""
            if file_name in name_field:
                return r
    return None


def _poll_upload_record_completed(dataset_id: str, file_name: str, find_wait: int = PROCESS_POLL_MAX, done_wait: int = 6) -> dict:
    """轮询直到找到上传记录且处理状态变为 completed，返回 record"""
    record = _poll_upload_record(dataset_id, file_name, max_wait=find_wait)
    if record is None:
        return None

    # 如果记录还在 processing，继续等待完成
    record_id = record.get("id")
    deadline = time.time() + done_wait * PROCESS_POLL_INTERVAL
    while record.get("status") == "processing" and time.time() < deadline:
        time.sleep(PROCESS_POLL_INTERVAL)
        resp = dataset_api.get_package_upload_records(dataset_id=dataset_id, page=1, page_size=20)
        result = resp.json()
        if result.get("code") != 0:
            continue
        data_obj = result.get("data") or {}
        items = (
            data_obj.get("items") or data_obj.get("records")
            or data_obj.get("list") or []
        )
        for item in items:
            if item.get("id") == record_id:
                record = item
                break
    return record


class TestPackageUpload:
    """上传数据包三步流程测试"""

    @pytest.mark.parametrize("dataset_type", [
        pytest.param(DatasetType.IMAGE, id="image"),
        pytest.param(DatasetType.SEQUENCE_IMAGE, id="image_sequence"),
    ])
    def test_three_step_flow(self, pm_user, dataset_type):
        """三步流程（image / image_sequence）- 上传→处理→查询记录 - 成功"""
        package_path, package_filename = PACKAGE_TEST_FILES[dataset_type]

        create_resp, name = _create_dataset_as_pm(
            pm_user, data_type=dataset_type, description=f"测试{dataset_type}上传"
        )
        data = _assert_create_success(create_resp, expected_name=name)
        dataset_id = data.get("id")
        logger.info(f"[{dataset_type}] 数据集创建成功: id={dataset_id}, name={name}")

        with open(package_path, "rb") as f:
            package_bytes = f.read()
        upload_result, object_keys = _upload_package(
            dataset_id=dataset_id,
            file=package_bytes,
            filename=package_filename,
        )
        assertion.assert_equal(upload_result.get("code"), 0, "上传数据包应成功")
        assertion.assert_true(
            len(object_keys) > 0, f"上传应返回非空 object_keys, 实际: {object_keys}"
        )

        process_resp = dataset_api.process_uploaded_package(
            dataset_id=dataset_id, object_keys=object_keys
        )
        process_result = process_resp.json()
        logger.info(
            f"[{dataset_type}] 触发处理原始响应: http={process_resp.status_code}, "
            f"code={process_result.get('code')}, msg={process_result.get('msg')}, "
            f"data={process_result.get('data')}"
        )
        process_ok = process_result.get("code") in (0, 202)

        record = _poll_upload_record(dataset_id, package_filename)
        if record:
            logger.info(
                f"[{dataset_type}] 上传记录: {record}"
            )
        assertion.assert_is_not_none(
            record, f"[{dataset_type}] 应在 {PROCESS_POLL_MAX * PROCESS_POLL_INTERVAL}s 内查询到上传记录"
        )
        logger.info(
            f"[{dataset_type}] 上传记录: package_id={record.get('package_id')}, "
            f"status={record.get('status')}, file_name={record.get('file_name') or record.get('name')}, "
            f"process_ok={process_ok}"
        )

    @pytest.mark.parametrize("dataset_type", [
        pytest.param(t, id=t)
        for t in [DatasetType.TEXT, DatasetType.AUDIO, DatasetType.VIDEO,
                  DatasetType.POINT_CLOUD, DatasetType.SEQUENCE_AUDIO,
                  DatasetType.SEQUENCE_VIDEO]
    ])
    def test_three_step_flow_other_types_skip(self, pm_user, dataset_type):
        """三步流程（text/audio/video/pointcloud_3d/audio_sequence/video_sequence）- skip（无测试数据）"""
        pytest.skip(f"数据集类型 {dataset_type} 暂未准备测试数据")

    @pytest.mark.parametrize("dataset_type", [
        pytest.param(DatasetType.IMAGE, id="image"),
        pytest.param(DatasetType.SEQUENCE_IMAGE, id="image_sequence"),
    ])
    def test_upload_valid_zip(self, pm_user, dataset_type):
        """上传压缩包 - 合法 zip 格式 - 成功"""
        create_resp, name = _create_dataset_as_pm(pm_user, data_type=dataset_type, description="zip 上传测试")
        dataset_id = _assert_create_success(create_resp, expected_name=name).get("id")

        package_path, package_filename = PACKAGE_TEST_FILES[dataset_type]
        with open(package_path, "rb") as f:
            package_bytes = f.read()

        upload_result, object_keys = _upload_package(
            dataset_id=dataset_id, file=package_bytes, filename=package_filename,
        )
        assertion.assert_equal(upload_result.get("code"), 0, "zip 上传应成功")
        assertion.assert_true(len(object_keys) > 0, "应返回 object_keys")

    @pytest.mark.parametrize("ext", [
        pytest.param(".tar", id="tar"),
        pytest.param(".tar.gz", id="tar_gz"),
        pytest.param(".tar.bz2", id="tar_bz2"),
    ])
    def test_upload_valid_tar_format(self, pm_user, ext):
        """上传压缩包 - .tar/.tar.gz/.tar.bz2 格式 - 应成功"""
        package_path, package_filename, content_type = PACKAGE_TAR_FILES[ext]
        create_resp, name = _create_dataset_as_pm(pm_user, data_type="image", description=f"tar 上传测试{ext}")
        dataset_id = _assert_create_success(create_resp, expected_name=name).get("id")

        with open(package_path, "rb") as f:
            package_bytes = f.read()

        upload_result, object_keys = _upload_package(
            dataset_id=dataset_id, file=package_bytes, filename=package_filename,
            content_type=content_type,
        )
        assertion.assert_equal(upload_result.get("code"), 0, f"{ext} 上传应成功")
        assertion.assert_true(len(object_keys) > 0, "应返回 object_keys")

    def test_upload_empty_sequence(self, pm_user):
        """上传序列图片数据包 - 某序列下无图片 - 应成功但返回空序列提示"""
        create_resp, name = _create_dataset_as_pm(
            pm_user, data_type=DatasetType.SEQUENCE_IMAGE, description="空序列上传测试",
        )
        dataset_id = _assert_create_success(create_resp, expected_name=name).get("id")

        with open(EMPTY_SEQUENCE_PACKAGE_PATH, "rb") as f:
            package_bytes = f.read()

        upload_result, object_keys = _upload_package(
            dataset_id=dataset_id, file=package_bytes, filename=EMPTY_SEQUENCE_PACKAGE_FILENAME,
        )
        assertion.assert_equal(upload_result.get("code"), 0, "zip 上传应成功")
        assertion.assert_true(len(object_keys) > 0, "应返回 object_keys")
   
    @pytest.mark.skip("受限于服务器性能，跳过")
    def test_upload_oversize(self, pm_user, shared_dataset):
        """上传压缩包 - 超过 5GB - 应返回错误"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)

        with open(OVERSIZE_PACKAGE_PATH, "rb") as f:
            package_bytes = f.read()

        resp = dataset_api.upload_package_to_temp(
            dataset_id=shared_dataset["id"],
            file=package_bytes,
            filename=OVERSIZE_PACKAGE_FILENAME,
        )
        result = resp.json()
        logger.info(f"上传超大压缩包 -> code={result.get('code')}, msg={result.get('msg')}")
        assertion.assert_true(result.get("code") != 0, "超过 5GB 的文件应被拒绝")

    @pytest.mark.parametrize("ext", [
        pytest.param(".rar", id="rar"),
        pytest.param(".7z", id="7z"),
    ])
    def test_upload_invalid_format(self, pm_user, shared_dataset, ext):
        """上传压缩包 - 非法格式（rar/7z）- 应返回错误"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)

        package_path, package_filename, content_type = INVALID_PACKAGE_FILES[ext]
        with open(package_path, "rb") as f:
            package_bytes = f.read()

        resp = dataset_api.upload_package_to_temp(
            dataset_id=shared_dataset["id"],
            file=package_bytes,
            filename=package_filename,
            content_type=content_type,
        )
        result = resp.json()
        logger.info(f"上传非法格式 {ext} -> code={result.get('code')}, msg={result.get('msg')}")
        assertion.assert_true(result.get("code") != 0, f"{ext} 格式应被拒绝")

    def test_upload_unauthorized(self, pm_user, shared_dataset):
        """上传压缩包 - 未登录 - 应返回 401"""
        http_client.remove_token()
        try:
            package_path, package_filename = PACKAGE_TEST_FILES[DatasetType.IMAGE]
            with open(package_path, "rb") as f:
                package_bytes = f.read()
            resp = dataset_api.upload_package_to_temp(
                dataset_id=shared_dataset["id"],
                file=package_bytes,
                filename=package_filename,
            )
            assertion.assert_response_success(resp, 401, "未认证，请先登录")
        finally:
            login_as("admin")  # 恢复 session

    @pytest.mark.parametrize(
        "case_id,user_type,extra_kwarg",
        TestDatasetPermission.NON_PM_PERMISSION_CASES,
        ids=[c[0] for c in TestDatasetPermission.NON_PM_PERMISSION_CASES],
    )
    @pytest.mark.system
    def test_upload_non_pm_forbidden(
        self, pm_user, shared_org, shared_supplier, shared_team, db_roles,
        case_id, user_type, extra_kwarg,
    ):
        """非 PM 角色上传压缩包 - 应返回 403"""
        if extra_kwarg == "supplier_id":
            kwargs = {"supplier_id": shared_supplier["id"]}
        else:
            kwargs = {"team_id": shared_team["id"]}
        resp_json, username, _ = _do_create_user(user_type, shared_org, db_roles, **kwargs)
        assertion.assert_equal(resp_json.get("code"), 0, f"{case_id} 用户创建应成功")

        create_resp, name = _create_dataset_as_pm(pm_user, data_type="image", description="非 PM 上传测试")
        dataset_id = _assert_create_success(create_resp, expected_name=name).get("id")

        login_with(username, DEFAULT_PASSWORD)
        package_path, package_filename = PACKAGE_TEST_FILES[DatasetType.IMAGE]
        with open(package_path, "rb") as f:
            package_bytes = f.read()
        resp = dataset_api.upload_package_to_temp(
            dataset_id=dataset_id, file=package_bytes, filename=package_filename,
        )
        result = resp.json()
        logger.info(f"[{case_id}] 非 PM 上传压缩包 -> code={result.get('code')}, msg={result.get('msg')}")
        assertion.assert_equal(result.get("code"), 403, f"{case_id} 上传应返回 403")
        msg = result.get("msg") or ""
        assertion.assert_true(
            "权限" in msg or "管理员" in msg or "项目" in msg,
            f"{case_id} 错误信息应提示权限/管理员限制，实际: {msg}",
        )

    def test_upload_cross_org_forbidden(self, pm_user, another_pm):
        """PM 不可上传到其他组织的数据集 - 应返回 403"""
        create_resp, name = _create_dataset_as_pm(another_pm, data_type="image", description="其他组织")
        other_dataset_id = _assert_create_success(create_resp, expected_name=name).get("id")

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        package_path, package_filename = PACKAGE_TEST_FILES[DatasetType.IMAGE]
        with open(package_path, "rb") as f:
            package_bytes = f.read()
        resp = dataset_api.upload_package_to_temp(
            dataset_id=other_dataset_id, file=package_bytes, filename=package_filename,
        )
        result = resp.json()
        logger.info(f"跨组织上传 -> code={result.get('code')}, msg={result.get('msg')}")
        assertion.assert_equal(result.get("code"), 403, "跨组织上传应返回 403")

    def test_process_with_empty_object_keys(self, pm_user, shared_dataset):
        """触发处理 - object_keys 为空 - 后端返回 data=[]（视为空数据，成功处理但无记录）"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = dataset_api.process_uploaded_package(dataset_id=shared_dataset["id"], object_keys=[])
        result = resp.json()
        logger.info(f"object_keys=空 -> code={result.get('code')}, msg={result.get('msg')}, data={result.get('data')}")
        assertion.assert_status_code(resp, 200)
        assertion.assert_equal(result.get("code"), 0, f"空 object_keys 应返回 code=0, 实际: {result.get('code')}")
        data = result.get("data")
        assertion.assert_true(
            isinstance(data, list) and len(data) == 0,
            f"data 应为空列表 [], 实际: {data}",
        )

    def test_process_with_nonexistent_object_key(self, pm_user, shared_dataset):
        """触发处理 - object_key 不存在"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        fake_key = "non_existent/temp_xxx.zip"
        resp = dataset_api.process_uploaded_package(
            dataset_id=shared_dataset["id"], object_keys=[fake_key]
        )
        result = resp.json()
        logger.info(f"object_key 不存在 -> code={result.get('code')}, msg={result.get('msg')}")
        assertion.assert_status_code(resp, 200)
        assertion.assert_response_success(resp, 500, "服务器内部错误")

    @pytest.mark.parametrize(
        "case_id,user_type,extra_kwarg",
        TestDatasetPermission.NON_PM_PERMISSION_CASES,
        ids=[c[0] for c in TestDatasetPermission.NON_PM_PERMISSION_CASES],
    )
    @pytest.mark.system
    def test_process_non_pm_forbidden(
        self, pm_user, shared_org, shared_supplier, shared_team, db_roles,
        case_id, user_type, extra_kwarg,
    ):
        """非 PM 角色触发处理 - 应返回 403"""
        if extra_kwarg == "supplier_id":
            kwargs = {"supplier_id": shared_supplier["id"]}
        else:
            kwargs = {"team_id": shared_team["id"]}
        resp_json, username, _ = _do_create_user(user_type, shared_org, db_roles, **kwargs)
        assertion.assert_equal(resp_json.get("code"), 0, f"{case_id} 用户创建应成功")

        create_resp, name = _create_dataset_as_pm(pm_user, data_type="image", description="非PM处理测试")
        dataset_id = _assert_create_success(create_resp, expected_name=name).get("id")
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        package_path, package_filename = PACKAGE_TEST_FILES[DatasetType.IMAGE]
        with open(package_path, "rb") as f:
            package_bytes = f.read()
        _, object_keys = _upload_package(
            dataset_id=dataset_id, file=package_bytes, filename=package_filename,
        )
        assertion.assert_true(len(object_keys) > 0, "PM 应能上传成功")

        login_with(username, DEFAULT_PASSWORD)
        resp = dataset_api.process_uploaded_package(
            dataset_id=dataset_id, object_keys=object_keys,
        )
        result = resp.json()
        logger.info(f"[{case_id}] 非 PM 触发处理 -> code={result.get('code')}, msg={result.get('msg')}")
        code = result.get("code")
        assertion.assert_true(
            code in (403, 404),
            f"{case_id} 处理应返回 403/404，实际: {code}",
        )

    def test_query_records_basic(self, pm_user, shared_dataset):
        """查询上传记录 - 不带过滤 - 应成功"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = dataset_api.get_package_upload_records(
            dataset_id=shared_dataset["id"], page=1, page_size=10,
        )
        result = resp.json()
        logger.info(f"查询空记录 -> code={result.get('code')}, data={result.get('data')}")
        assertion.assert_equal(result.get("code"), 0, "查询应成功")
        data_obj = result.get("data") or {}
        records = (
            data_obj.get("items") or data_obj.get("records") or data_obj.get("list")
            or (data_obj if isinstance(data_obj, list) else [])
        )
        assertion.assert_true(isinstance(records, list), f"返回 records 应为列表, 实际: {type(records).__name__}")

    def test_query_records_by_file_name(self, pm_user):
        """查询上传记录 - 按 file_name 过滤 - 应能找到刚上传的记录"""
        create_resp, name = _create_dataset_as_pm(pm_user, data_type="image", description="按名查询测试")
        dataset_id = _assert_create_success(create_resp, expected_name=name).get("id")
        package_path, package_filename = PACKAGE_TEST_FILES[DatasetType.IMAGE]
        with open(package_path, "rb") as f:
            package_bytes = f.read()
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        _, object_keys = _upload_package(
            dataset_id=dataset_id, file=package_bytes, filename=package_filename,
        )
        dataset_api.process_uploaded_package(dataset_id=dataset_id, object_keys=object_keys)

        record = _poll_upload_record(dataset_id, package_filename)
        assertion.assert_is_not_none(record, "应能找到按 file_name 过滤的记录")

    def test_query_records_pagination(self, pm_user, shared_dataset):
        """查询上传记录 - 分页参数 - 接口接受并返回正确分页结构"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = dataset_api.get_package_upload_records(
            dataset_id=shared_dataset["id"], page=1, page_size=5,
        )
        result = resp.json()
        assertion.assert_equal(result.get("code"), 0, "分页查询应成功")
        data_obj = result.get("data") or {}
        has_pagination = any(k in data_obj for k in ("total", "page", "page_size", "items", "records"))
        assertion.assert_true(
            has_pagination, f"分页响应应含分页字段, 实际: {data_obj}"
        )

    @pytest.mark.parametrize(
        "case_id,user_type,extra_kwarg",
        TestDatasetPermission.NON_PM_PERMISSION_CASES,
        ids=[c[0] for c in TestDatasetPermission.NON_PM_PERMISSION_CASES],
    )
    @pytest.mark.system
    def test_query_records_non_pm_forbidden(
        self, pm_user, shared_org, shared_supplier, shared_team, db_roles,
        case_id, user_type, extra_kwarg,
    ):
        """非 PM 角色查询上传记录 - 应返回 403"""
        create_resp, name = _create_dataset_as_pm(pm_user, data_type="image", description=f"非PM查询记录-{case_id}")
        dataset_id = _assert_create_success(create_resp, expected_name=name).get("id")

        if extra_kwarg == "supplier_id":
            kwargs = {"supplier_id": shared_supplier["id"]}
        else:
            kwargs = {"team_id": shared_team["id"]}
        resp_json, username, _ = _do_create_user(user_type, shared_org, db_roles, **kwargs)
        assertion.assert_equal(resp_json.get("code"), 0, f"{case_id} 用户创建应成功")

        login_with(username, DEFAULT_PASSWORD)
        resp = dataset_api.get_package_upload_records(
            dataset_id=dataset_id, page=1, page_size=10,
        )
        result = resp.json()
        logger.info(f"[{case_id}] 非 PM 查询记录 -> code={result.get('code')}, msg={result.get('msg')}")
        assertion.assert_equal(result.get("code"), 403, f"{case_id} 查询应返回 403")

    def test_query_records_cross_pm_forbidden(self, pm_user, another_pm):
        """跨组织 PM 不可查询上传记录 - 应返回 403"""
        create_resp, name = _create_dataset_as_pm(another_pm, data_type="image", description="跨组织查询测试")
        other_dataset_id = _assert_create_success(create_resp, expected_name=name).get("id")

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = dataset_api.get_package_upload_records(
            dataset_id=other_dataset_id, page=1, page_size=10,
        )
        result = resp.json()
        logger.info(f"跨组织 PM 查询记录 -> code={result.get('code')}, msg={result.get('msg')}")
        assertion.assert_equal(result.get("code"), 403, "跨组织查询应返回 403")

    def test_query_records_peer_pm_forbidden(self, pm_user, peer_pm):
        """同组织其他 PM 不可查询上传记录 - 应返回 403"""
        create_resp, name = _create_dataset_as_pm(peer_pm, data_type="image", description="peerPM查询测试")
        peer_dataset_id = _assert_create_success(create_resp, expected_name=name).get("id")

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = dataset_api.get_package_upload_records(
            dataset_id=peer_dataset_id, page=1, page_size=10,
        )
        result = resp.json()
        logger.info(f"peer PM 查询记录 -> code={result.get('code')}, msg={result.get('msg')}")
        assertion.assert_equal(result.get("code"), 403, "同组织其他 PM 查询应返回 403")

    def test_query_records_by_file_name_fuzzy(self, pm_user):
        """查询上传记录 - 按文件名称模糊搜索 - 接口正常接受参数"""
        create_resp, name = _create_dataset_as_pm(pm_user, data_type="image", description="模糊查询测试")
        dataset_id = _assert_create_success(create_resp, expected_name=name).get("id")
        package_path, package_filename = PACKAGE_TEST_FILES[DatasetType.IMAGE]
        with open(package_path, "rb") as f:
            package_bytes = f.read()
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        _upload_package(dataset_id=dataset_id, file=package_bytes, filename=package_filename)

        fuzzy_name = package_filename[:4]
        resp = dataset_api.get_package_upload_records(
            dataset_id=dataset_id, file_name=fuzzy_name, page=1, page_size=10,
        )
        result = resp.json()
        logger.info(f"模糊搜索 file_name={fuzzy_name} -> code={result.get('code')}, data={result.get('data')}")
        assertion.assert_equal(result.get("code"), 0, "模糊搜索请求应成功")

    def test_query_records_by_status_processing(self, pm_user, shared_dataset):
        """查询上传记录 - 按解析状态筛选-processing"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = dataset_api.get_package_upload_records(
            dataset_id=shared_dataset["id"], status="processing", page=1, page_size=10,
        )
        result = resp.json()
        logger.info(f"筛选状态=processing -> code={result.get('code')}, data={result.get('data')}")
        assertion.assert_equal(result.get("code"), 0, "状态筛选(processing)请求应成功")

    def test_query_records_by_status_completed(self, pm_user, shared_dataset):
        """查询上传记录 - 按解析状态筛选-completed"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = dataset_api.get_package_upload_records(
            dataset_id=shared_dataset["id"], status="completed", page=1, page_size=10,
        )
        result = resp.json()
        logger.info(f"筛选状态=completed -> code={result.get('code')}, data={result.get('data')}")
        assertion.assert_equal(result.get("code"), 0, "状态筛选(completed)请求应成功")

    def test_query_records_by_package_id(self, pm_user, shared_dataset):
        """查询上传记录 - 按数据包 ID 模糊搜索"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = dataset_api.get_package_upload_records(
            dataset_id=shared_dataset["id"], package_id="nonexistent_pkg", page=1, page_size=10,
        )
        result = resp.json()
        logger.info(f"按 package_id 搜索 -> code={result.get('code')}, data={result.get('data')}")
        assertion.assert_equal(result.get("code"), 0, "按 package_id 搜索请求应成功")


# ======================== 下载导入记录数据包 ========================

def _setup_dataset_with_upload_record(pm_user: dict, dataset_type: str = None) -> tuple[str, dict]:
    """辅助：创建数据集并完成上传+处理流程，返回 (dataset_id, upload_record)

    - 上传序列图片类型的数据包（处理成功率较高，可生成数据项）
    - 触发处理并轮询等待上传记录生成
    """
    if dataset_type is None:
        dataset_type = DatasetType.SEQUENCE_IMAGE

    create_resp, name = _create_dataset_as_pm(pm_user, data_type=dataset_type, description="下载数据包测试")
    data = _assert_create_success(create_resp, expected_name=name)
    dataset_id = data.get("id")
    logger.info(f"[setup_upload_record] 数据集创建成功: id={dataset_id}, name={name}")

    # _create_dataset_as_pm 已登录 pm_user，直接上传
    package_path, package_filename = PACKAGE_TEST_FILES[dataset_type]
    with open(package_path, "rb") as f:
        package_bytes = f.read()

    _, object_keys = _upload_package(
        dataset_id=dataset_id, file=package_bytes, filename=package_filename,
    )
    assertion.assert_true(len(object_keys) > 0, "上传应返回非空 object_keys")

    # 触发处理
    process_resp = dataset_api.process_uploaded_package(dataset_id=dataset_id, object_keys=object_keys)
    process_result = process_resp.json()
    logger.info(
        f"[setup_upload_record] 触发处理 -> code={process_result.get('code')}, msg={process_result.get('msg')}"
    )

    # 轮询获取上传记录，等待处理完成
    record = _poll_upload_record_completed(dataset_id, package_filename)
    assertion.assert_is_not_none(
        record, f"应在 {PROCESS_POLL_MAX * PROCESS_POLL_INTERVAL}s 内查询到上传记录"
    )
    logger.info(
        f"[setup_upload_record] 上传记录: package_id={record.get('package_id')}, "
        f"status={record.get('status')}, record_id={record.get('id')}"
    )

    return dataset_id, record


class TestDownloadPackage:
    """下载导入记录数据包测试

    需求：
    - 前置条件：数据集下有上传数据包记录（可成功可失败）
    - 下载内容：原始数据包文件
    - 权限：仅创建数据集的 PM 可操作，其他角色均不能操作
    """

    def test_pm_download_success(self, pm_user):
        """PM 下载自己创建数据集的导入记录数据包 - 应成功返回原始文件内容"""
        dataset_id, record = _setup_dataset_with_upload_record(pm_user)
        login_with(pm_user["username"], DEFAULT_PASSWORD)

        upload_id = record.get("id") or record.get("package_id")
        assertion.assert_is_not_none(upload_id, "上传记录应包含 upload_id")

        # 读取原始文件作为对比基准（需与 _setup_dataset_with_upload_record 使用的包一致）
        src_type = DatasetType.SEQUENCE_IMAGE
        original_path, original_filename = PACKAGE_TEST_FILES[src_type]
        with open(original_path, "rb") as f:
            original_bytes = f.read()
        original_size = len(original_bytes)
        original_md5 = hashlib.md5(original_bytes).hexdigest()

        # 下载文件
        resp = dataset_api.download_exported_data_package(dataset_id, upload_id)
        assertion.assert_status_code(resp, 200)

        # 验证 Content-Type
        content_type = resp.headers.get("Content-Type", "")
        logger.info(f"[pm_download] Content-Type={content_type}, content_length={len(resp.content)} bytes")

        # 比较文件大小
        assertion.assert_equal(
            len(resp.content), original_size,
            f"下载文件大小({len(resp.content)})与原始文件({original_size})不一致",
        )

        # 比较 MD5
        download_md5 = hashlib.md5(resp.content).hexdigest()
        assertion.assert_equal(
            download_md5, original_md5,
            f"下载文件 MD5({download_md5})与原始文件({original_md5})不一致，文件内容可能被篡改",
        )

        # Content-Type 预期为 application/octet-stream 或 application/zip
        assertion.assert_true(
            content_type.startswith("application/"),
            f"Content-Type 应为 application/*，实际: {content_type}",
        )
        logger.info(
            f"[pm_download] 文件一致性校验通过: filename={original_filename}, "
            f"size={original_size}, md5={original_md5}"
        )

    def test_pm_download_cross_org_forbidden(self, pm_user, another_pm):
        """跨组织 PM 不可下载导入记录数据包 - 403"""
        dataset_id, record = _setup_dataset_with_upload_record(another_pm)

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        upload_id = record.get("id") or record.get("package_id")

        resp = dataset_api.download_exported_data_package(dataset_id, upload_id)
        result = resp.json()
        logger.info(f"[cross_org] 跨组织 PM 下载 -> code={result.get('code')}, msg={result.get('msg')}")
        assertion.assert_equal(result.get("code"), 403, "跨组织 PM 下载应返回 403")

    def test_pm_download_peer_pm_forbidden(self, pm_user, peer_pm):
        """同组织其他 PM 不可下载导入记录数据包 - 403"""
        dataset_id, record = _setup_dataset_with_upload_record(peer_pm)

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        upload_id = record.get("id") or record.get("package_id")

        resp = dataset_api.download_exported_data_package(dataset_id, upload_id)
        result = resp.json()
        logger.info(f"[peer_pm] 同组织其他 PM 下载 -> code={result.get('code')}, msg={result.get('msg')}")
        assertion.assert_equal(result.get("code"), 403, "同组织其他 PM 下载应返回 403")

    @pytest.mark.parametrize(
        "case_id,user_type,extra_kwarg",
        TestDatasetPermission.NON_PM_PERMISSION_CASES,
        ids=[c[0] for c in TestDatasetPermission.NON_PM_PERMISSION_CASES],
    )
    @pytest.mark.system
    def test_download_non_pm_forbidden(
        self, pm_user, shared_org, shared_supplier, shared_team, db_roles,
        case_id, user_type, extra_kwarg,
    ):
        """非 PM 角色（供应商管理员/项目团队管理员/项目团队成员）下载导入记录数据包 - 403"""
        dataset_id, record = _setup_dataset_with_upload_record(pm_user)

        if extra_kwarg == "supplier_id":
            kwargs = {"supplier_id": shared_supplier["id"]}
        else:
            kwargs = {"team_id": shared_team["id"]}
        resp_json, username, _ = _do_create_user(user_type, shared_org, db_roles, **kwargs)
        assertion.assert_equal(resp_json.get("code"), 0, f"{case_id} 用户创建应成功")

        login_with(username, DEFAULT_PASSWORD)
        upload_id = record.get("id") or record.get("package_id")

        resp = dataset_api.download_exported_data_package(dataset_id, upload_id)
        result = resp.json()
        logger.info(
            f"[{case_id}] 非 PM 下载数据包 -> code={result.get('code')}, msg={result.get('msg')}"
        )
        assertion.assert_equal(result.get("code"), 403, f"{case_id} 下载应返回 403")

    def test_download_unauthorized(self, pm_user):
        """未登录下载导入记录数据包 - 401"""
        dataset_id, record = _setup_dataset_with_upload_record(pm_user)

        http_client.remove_token()
        try:
            upload_id = record.get("id") or record.get("package_id")
            resp = dataset_api.download_exported_data_package(dataset_id, upload_id)
            assertion.assert_response_success(resp, 401, "未认证，请先登录")
        finally:
            login_as("admin")  # 恢复 session


# ======================== 导出数据 ========================

EXPORT_POLL_MAX = 12          # 最大轮询次数
EXPORT_POLL_INTERVAL = 3      # 每次间隔秒


def _get_data_item_ids(dataset_id: str, max_wait: int = PROCESS_POLL_MAX) -> list[str]:
    """查询数据集下的数据项 ID 列表，用于导出时的 item_ids 参数"""
    deadline = time.time() + max_wait * PROCESS_POLL_INTERVAL
    while time.time() < deadline:
        time.sleep(PROCESS_POLL_INTERVAL)
        resp = api_client.get_data_items(
            dataset_id=dataset_id, page=1, page_size=100
        )
        result = resp.json()
        if result.get("code") != 0:
            logger.warning(f"查询数据项列表失败: {result.get('msg')}")
            continue
        data_obj = result.get("data") or {}
        items = data_obj.get("items") or data_obj.get("records") or []
        ids = []
        for item in items:
            # ID 可能在 item.id 或 item.thumbnail.id 中
            item_id = item.get("id")
            if item_id:
                ids.append(item_id)
            elif isinstance(item.get("thumbnail"), dict):
                thumb_id = item["thumbnail"].get("id")
                if thumb_id:
                    ids.append(thumb_id)
        if ids:
            logger.info(f"[get_item_ids] 获取到 {len(ids)} 个数据项 ID")
            return ids
        logger.info(f"[get_item_ids] 暂未查询到数据项，继续轮询")
    logger.warning(f"[get_item_ids] 轮询超时，未获取到数据项 ID")
    return []


def _do_export(dataset_id: str, content_type: str, file_name: str, pm_user: dict, item_ids: list[str] = None) -> dict:
    """发起导出并轮询等待完成，返回完成的 export_record"""
    assert len(file_name) <= 20, f"file_name 长度不能超过 20 字符: {file_name}({len(file_name)})"
    login_with(pm_user["username"], DEFAULT_PASSWORD)

    body = {
        "content_type": content_type,
        "file_name": file_name,
    }
    if item_ids is not None:
        body["item_ids"] = item_ids
    resp = api_client.export_data(dataset_id, request_body=body)
    result = resp.json()
    assertion.assert_equal(result.get("code"), 0, f"导出({content_type})应成功")
    export_id = (result.get("data") or {}).get("id")
    assertion.assert_is_not_none(export_id, "导出响应应返回 id")
    logger.info(f"[export] 发起导出: content_type={content_type}, export_id={export_id}")

    # 轮询导出状态
    deadline = time.time() + EXPORT_POLL_MAX * EXPORT_POLL_INTERVAL
    last_status = None
    while time.time() < deadline:
        time.sleep(EXPORT_POLL_INTERVAL)
        records_resp = api_client.data_export_records(dataset_id, page=1, page_size=20)
        records_result = records_resp.json()
        if records_result.get("code") != 0:
            continue
        data_obj = records_result.get("data") or {}
        items = data_obj.get("items") or data_obj.get("records") or []
        for item in items:
            if item.get("id") == export_id:
                status = item.get("status")
                last_status = status
                logger.info(f"[export] 轮询状态: {status} (export_id={export_id})")
                if status == "completed":
                    return item
                if status == "failed":
                    raise AssertionError(f"导出失败: content_type={content_type}, export_id={export_id}")
                break

    raise AssertionError(
        f"导出超时: content_type={content_type}, export_id={export_id}, 最后状态={last_status}"
    )


class TestExportData:
    """导出数据测试

    需求：
    - 异步导出为 .zip，支持 content_type: original / annotation / all
    - 导出完成后可下载 zip 文件
    - 仅创建数据集的 PM 可操作
    """

    @pytest.mark.parametrize("content_type", [
        pytest.param("original", id="original"),
        pytest.param("all", id="all"),
    ])
    def test_pm_export_success(self, pm_user, content_type):
        """PM 导出数据集 - content_type={content_type} - 成功导出并下载"""
        dataset_id, _ = _setup_dataset_with_upload_record(pm_user)
        file_name = f"exp_{content_type}_{int(time.time())}.zip"
        # file_name 后端限制 20 字符，截断
        if len(file_name) > 20:
            file_name = f"exp_{content_type}.zip"

        # 获取数据项 ID 列表（item_ids 为必填）
        item_ids = _get_data_item_ids(dataset_id)
        assertion.assert_true(len(item_ids) > 0, f"应至少有一个数据项, 实际: {item_ids}")

        # 导出并等待完成
        export_record = _do_export(dataset_id, content_type, file_name, pm_user, item_ids=item_ids)
        export_id = export_record.get("id")
        logger.info(
            f"[export] 导出完成: id={export_id}, status={export_record.get('status')}, "
            f"file_name={export_record.get('file_name')}"
        )

        # 下载文件
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        download_resp = api_client.download_export_package(dataset_id, export_id)
        assertion.assert_status_code(download_resp, 200)
        assertion.assert_true(
            len(download_resp.content) > 0,
            "下载的导出 zip 不应为空",
        )
        # content_type=all 包含原文件+标注结果，大小应 >= original
        min_size = 100
        assertion.assert_true(
            len(download_resp.content) > min_size,
            f"导出文件过小: {len(download_resp.content)} bytes",
        )
        logger.info(
            f"[export] 下载成功: content_type={content_type}, "
            f"export_id={export_id}, size={len(download_resp.content)} bytes"
        )

    @pytest.mark.skip(reason="数据集尚无标注结果数据，等待标注完成后启用")
    def test_pm_export_annotation(self, pm_user):
        """PM 导出数据集 - content_type=annotation - 标注结果文件"""
        pass

    def test_pm_export_cross_org_forbidden(self, pm_user, another_pm):
        """跨组织 PM 不可导出数据 - 403"""
        dataset_id, _ = _setup_dataset_with_upload_record(another_pm)

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        body = {"content_type": "original", "file_name": "export_cross.zip", "item_ids": ["00000000-0000-0000-0000-000000000001"]}
        resp = api_client.export_data(dataset_id, request_body=body)
        result = resp.json()
        logger.info(f"[export] 跨组织 PM 导出 -> code={result.get('code')}, msg={result.get('msg')}")
        assertion.assert_equal(result.get("code"), 403, "跨组织 PM 导出应返回 403")

    def test_pm_export_peer_pm_forbidden(self, pm_user, peer_pm):
        """同组织其他 PM 不可导出数据 - 403"""
        dataset_id, _ = _setup_dataset_with_upload_record(peer_pm)

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        body = {"content_type": "original", "file_name": "export_peer.zip", "item_ids": ["00000000-0000-0000-0000-000000000001"]}
        resp = api_client.export_data(dataset_id, request_body=body)
        result = resp.json()
        logger.info(f"[export] peer PM 导出 -> code={result.get('code')}, msg={result.get('msg')}")
        assertion.assert_equal(result.get("code"), 403, "同组织其他 PM 导出应返回 403")

    @pytest.mark.parametrize(
        "case_id,user_type,extra_kwarg",
        TestDatasetPermission.NON_PM_PERMISSION_CASES,
        ids=[c[0] for c in TestDatasetPermission.NON_PM_PERMISSION_CASES],
    )
    @pytest.mark.system
    def test_export_non_pm_forbidden(
        self, pm_user, shared_org, shared_supplier, shared_team, db_roles,
        case_id, user_type, extra_kwarg,
    ):
        """非 PM 角色不可导出数据 - 403"""
        dataset_id, _ = _setup_dataset_with_upload_record(pm_user)
        item_ids = _get_data_item_ids(dataset_id)
        assertion.assert_true(len(item_ids) > 0, "应至少有一个数据项")

        if extra_kwarg == "supplier_id":
            kwargs = {"supplier_id": shared_supplier["id"]}
        else:
            kwargs = {"team_id": shared_team["id"]}
        resp_json, username, _ = _do_create_user(user_type, shared_org, db_roles, **kwargs)
        assertion.assert_equal(resp_json.get("code"), 0, f"{case_id} 用户创建应成功")

        login_with(username, DEFAULT_PASSWORD)
        body = {"content_type": "original", "file_name": f"export_{case_id}.zip", "item_ids": item_ids}
        resp = api_client.export_data(dataset_id, request_body=body)
        result = resp.json()
        logger.info(
            f"[export] {case_id} 非 PM 导出 -> code={result.get('code')}, msg={result.get('msg')}"
        )
        assertion.assert_equal(result.get("code"), 403, f"{case_id} 导出应返回 403")

    def test_export_unauthorized(self, pm_user):
        """未登录导出数据 - 401"""
        dataset_id, _ = _setup_dataset_with_upload_record(pm_user)

        http_client.remove_token()
        try:
            body = {"content_type": "original", "file_name": "export_unauth.zip", "item_ids": ["00000000-0000-0000-0000-000000000001"]}
            resp = api_client.export_data(dataset_id, request_body=body)
            assertion.assert_response_success(resp, 401, "未认证，请先登录")
        finally:
            login_as("admin")

    @pytest.mark.parametrize("case_id,file_name,msg_prefix", [
        ("file_name_required", "", "文件名为空: "),
        ("file_name_too_long", "a" * 21, "文件名超长(>20): "),
    ], ids=["file_name_required", "file_name_too_long"])
    def test_export_invalid_file_name(self, pm_user, case_id, file_name, msg_prefix):
        """PM 导出数据集 - 非法 file_name（为空/超长）- 应失败"""
        dataset_id, _ = _setup_dataset_with_upload_record(pm_user)
        login_with(pm_user["username"], DEFAULT_PASSWORD)

        body = {"content_type": "original", "file_name": file_name, "item_ids": ["00000000-0000-0000-0000-000000000001"]}
        resp = api_client.export_data(dataset_id, request_body=body)
        result = resp.json()
        assertion.assert_true(
            result.get("code") != 0,
            f"{msg_prefix}导出应失败，实际 code={result.get('code')}",
        )
        logger.info(f"[export_invalid] {msg_prefix} code={result.get('code')}, msg={result.get('msg')}")

    @pytest.mark.xfail(
        reason="后端说已做兼容（content_type为空默认导出原文件），但实际仍返回422，待部署后验证",
        strict=False,
    )
    def test_export_content_type_empty_defaults_to_original(self, pm_user):
        """PM 导出数据集 - content_type 为空 - 默认导出原文件（后端兼容）"""
        dataset_id, _ = _setup_dataset_with_upload_record(pm_user)
        item_ids = _get_data_item_ids(dataset_id)
        assertion.assert_true(len(item_ids) > 0, "应至少有一个数据项")

        login_with(pm_user["username"], DEFAULT_PASSWORD)

        body = {"content_type": "", "file_name": "ct_empty.zip", "item_ids": item_ids}
        resp = api_client.export_data(dataset_id, request_body=body)
        result = resp.json()
        assertion.assert_equal(
            result.get("code"), 0,
            f"content_type为空应默认导出原文件，实际 code={result.get('code')}, msg={result.get('msg')}",
        )
        logger.info(f"[export_content_type_empty] code={result.get('code')}, msg={result.get('msg')}")

    @pytest.mark.xfail(
        reason="后端暂未校验 content_type 缺失（不传 content_type 时仍返回 code=0）",
        strict=False,
    )
    def test_export_invalid_content_type_missing(self, pm_user):
        """PM 导出数据集 - content_type 缺失 - 应失败"""
        dataset_id, _ = _setup_dataset_with_upload_record(pm_user)
        login_with(pm_user["username"], DEFAULT_PASSWORD)

        body = {"file_name": "test_export.zip", "item_ids": ["00000000-0000-0000-0000-000000000001"]}
        resp = api_client.export_data(dataset_id, request_body=body)
        result = resp.json()
        assertion.assert_true(
            result.get("code") != 0,
            f"content_type缺失: 导出应失败，实际 code={result.get('code')}",
        )
        logger.info(f"[export_invalid] content_type缺失: code={result.get('code')}, msg={result.get('msg')}")


# ======================== 查询导出记录 ========================

class TestQueryExportRecords:
    """查询导出记录测试

    需求：
    - 支持按压缩包名(fileName)模糊搜索（非必填）
    - 支持按导出状态(status)筛选（非必填）：pending/processing/completed/failed
    - 支持按导出时间范围(startTime/endTime)筛选（非必填），格式 YYYY-MM-DD
    - 分页查询
    - 仅创建数据集的 PM 可操作
    """

    @staticmethod
    def _prepare_item_ids(dataset_id: str) -> list[str]:
        """获取数据项 ID，供导出使用"""
        item_ids = _get_data_item_ids(dataset_id)
        assert len(item_ids) > 0, f"应至少有一个数据项, dataset_id={dataset_id}"
        return item_ids

    # ---------- 基础查询 ----------

    def test_query_basic(self, pm_user):
        """PM 查询导出记录 - 不带过滤条件 - 返回所有记录"""
        dataset_id, _ = _setup_dataset_with_upload_record(pm_user)
        item_ids = self._prepare_item_ids(dataset_id)
        file_name = f"qry_{int(time.time())}.zip"
        _do_export(dataset_id, "original", file_name, pm_user, item_ids=item_ids)

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = api_client.data_export_records(dataset_id)
        result = resp.json()
        assertion.assert_equal(result.get("code"), 0, "查询应成功")
        data_obj = result.get("data") or {}
        items = data_obj.get("items") or data_obj.get("records") or []
        assertion.assert_true(len(items) >= 1, "应至少返回 1 条导出记录")
        logger.info(f"[query_basic] 返回记录数: {len(items)}")

    def test_query_no_export_records(self, pm_user, shared_dataset):
        """PM 查询导出记录 - 数据集无导出记录 - 返回空列表"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = api_client.data_export_records(shared_dataset["id"])
        result = resp.json()
        assertion.assert_equal(result.get("code"), 0, "查询应成功")
        data_obj = result.get("data") or {}
        items = data_obj.get("items") or data_obj.get("records") or []
        assertion.assert_equal(len(items), 0, "无导出记录应返回空列表")

    # ---------- 按 file_name 模糊搜索 ----------

    def test_query_by_file_name_match(self, pm_user):
        """PM 查询导出记录 - 按 file_name 模糊匹配 - 命中"""
        dataset_id, _ = _setup_dataset_with_upload_record(pm_user)
        item_ids = self._prepare_item_ids(dataset_id)
        file_name = f"fn_{int(time.time())}.zip"
        _do_export(dataset_id, "original", file_name, pm_user, item_ids=item_ids)

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        fuzzy = file_name[:6]
        resp = api_client.data_export_records(dataset_id, fileName=fuzzy)
        result = resp.json()
        assertion.assert_equal(result.get("code"), 0, "模糊查询应成功")
        data_obj = result.get("data") or {}
        items = data_obj.get("items") or data_obj.get("records") or []
        assertion.assert_true(len(items) >= 1, f"模糊搜索 '{fuzzy}' 应命中")
        names = [i.get("file_name", "") for i in items]
        assertion.assert_true(
            any(file_name in n for n in names),
            f"搜索结果中应包含 '{file_name}'，实际: {names}",
        )

    def test_query_by_file_name_no_match(self, pm_user):
        """PM 查询导出记录 - 按 file_name 模糊搜索 - 不匹配"""
        dataset_id, _ = _setup_dataset_with_upload_record(pm_user)

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = api_client.data_export_records(dataset_id, fileName="__nonexistent_export__")
        result = resp.json()
        assertion.assert_equal(result.get("code"), 0, "查询应成功")
        data_obj = result.get("data") or {}
        items = data_obj.get("items") or data_obj.get("records") or []
        assertion.assert_equal(len(items), 0, "不存在的 file_name 应返回空列表")

    # ---------- 按 status 筛选 ----------

    @pytest.mark.parametrize("status", [
        pytest.param("completed", id="completed"),
    ])
    def test_query_by_status(self, pm_user, status):
        """PM 查询导出记录 - 按 status 筛选 - 返回对应状态记录"""
        dataset_id, _ = _setup_dataset_with_upload_record(pm_user)
        item_ids = self._prepare_item_ids(dataset_id)
        file_name = f"st_{int(time.time())}.zip"
        _do_export(dataset_id, "original", file_name, pm_user, item_ids=item_ids)

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = api_client.data_export_records(dataset_id, status=status)
        result = resp.json()
        assertion.assert_equal(result.get("code"), 0, "按状态查询应成功")
        data_obj = result.get("data") or {}
        items = data_obj.get("items") or data_obj.get("records") or []
        for item in items:
            assertion.assert_equal(
                item.get("status"), status,
                f"筛选 status={status} 后出现非预期状态: {item.get('status')}",
            )
        logger.info(f"[query_status] status={status}, 返回 {len(items)} 条")

    def test_query_by_status_no_match(self, pm_user):
        """PM 查询导出记录 - 按 status 筛选 - 不匹配（failed）"""
        dataset_id, _ = _setup_dataset_with_upload_record(pm_user)
        item_ids = self._prepare_item_ids(dataset_id)
        # 创建一个成功的导出，然后查询 failed 状态应无结果
        file_name = f"nm_{int(time.time())}.zip"
        _do_export(dataset_id, "original", file_name, pm_user, item_ids=item_ids)

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = api_client.data_export_records(dataset_id, status="failed")
        result = resp.json()
        assertion.assert_equal(result.get("code"), 0, "按状态查询应成功")
        data_obj = result.get("data") or {}
        items = data_obj.get("items") or data_obj.get("records") or []
        logger.info(f"[query_status_nomatch] status=failed, 返回 {len(items)} 条")

    # ---------- 按时间范围筛选 ----------

    def test_query_by_time_range(self, pm_user):
        """PM 查询导出记录 - 按时间范围(startTime~endTime)筛选 - 命中"""
        dataset_id, _ = _setup_dataset_with_upload_record(pm_user)
        item_ids = self._prepare_item_ids(dataset_id)
        file_name = f"tm_{int(time.time())}.zip"
        _do_export(dataset_id, "original", file_name, pm_user, item_ids=item_ids)

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        today = time.strftime("%Y-%m-%d")
        resp = api_client.data_export_records(
            dataset_id, startTime=today, endTime=today,
        )
        result = resp.json()
        assertion.assert_equal(result.get("code"), 0, "按时间范围查询应成功")
        logger.info(f"[query_time] range=[{today}~{today}], total={result.get('data', {}).get('total', 'unknown')}")

    def test_query_by_time_range_no_match(self, pm_user):
        """PM 查询导出记录 - 按时间范围筛选 - 不命中"""
        dataset_id, _ = _setup_dataset_with_upload_record(pm_user)

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = api_client.data_export_records(
            dataset_id, startTime="2020-01-01", endTime="2020-01-02",
        )
        result = resp.json()
        assertion.assert_equal(result.get("code"), 0, "按时间范围查询应成功")
        data_obj = result.get("data") or {}
        items = data_obj.get("items") or data_obj.get("records") or []
        assertion.assert_equal(len(items), 0, "不匹配的时间范围应返回空列表")

    # ---------- 分页 ----------

    def test_query_pagination(self, pm_user):
        """PM 查询导出记录 - 分页参数 - 返回正确分页结构"""
        dataset_id, _ = _setup_dataset_with_upload_record(pm_user)
        item_ids = self._prepare_item_ids(dataset_id)
        # 创建 2 条导出记录
        file_name1 = f"p1_{int(time.time())}.zip"
        _do_export(dataset_id, "original", file_name1, pm_user, item_ids=item_ids)
        file_name2 = f"p2_{int(time.time()+1)}.zip"
        _do_export(dataset_id, "original", file_name2, pm_user, item_ids=item_ids)

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = api_client.data_export_records(dataset_id, page=1, page_size=1)
        result = resp.json()
        assertion.assert_equal(result.get("code"), 0, "分页查询应成功")
        data_obj = result.get("data") or {}
        items = data_obj.get("items") or data_obj.get("records") or []
        assertion.assert_equal(len(items), 1, "page_size=1 应只返回 1 条")
        total = data_obj.get("total", 0)
        assertion.assert_true(total >= 2, f"total 应 >= 2，实际: {total}")
        logger.info(f"[query_pagination] page=1, page_size=1, total={total}")

    # ---------- 权限 ----------

    def test_query_cross_org_forbidden(self, pm_user, another_pm):
        """跨组织 PM 不可查询导出记录 - 403"""
        dataset_id, _ = _setup_dataset_with_upload_record(another_pm)

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = api_client.data_export_records(dataset_id)
        result = resp.json()
        logger.info(f"[query_cross] 跨组织 PM 查询 -> code={result.get('code')}, msg={result.get('msg')}")
        assertion.assert_equal(result.get("code"), 403, "跨组织 PM 查询应返回 403")

    def test_query_peer_pm_forbidden(self, pm_user, peer_pm):
        """同组织其他 PM 不可查询导出记录 - 403"""
        dataset_id, _ = _setup_dataset_with_upload_record(peer_pm)

        login_with(pm_user["username"], DEFAULT_PASSWORD)
        resp = api_client.data_export_records(dataset_id)
        result = resp.json()
        logger.info(f"[query_peer] peer PM 查询 -> code={result.get('code')}, msg={result.get('msg')}")
        assertion.assert_equal(result.get("code"), 403, "同组织其他 PM 查询应返回 403")

    @pytest.mark.parametrize(
        "case_id,user_type,extra_kwarg",
        TestDatasetPermission.NON_PM_PERMISSION_CASES,
        ids=[c[0] for c in TestDatasetPermission.NON_PM_PERMISSION_CASES],
    )
    @pytest.mark.system
    def test_query_non_pm_forbidden(
        self, pm_user, shared_org, shared_supplier, shared_team, db_roles,
        case_id, user_type, extra_kwarg,
    ):
        """非 PM 角色不可查询导出记录 - 403"""
        dataset_id, _ = _setup_dataset_with_upload_record(pm_user)

        if extra_kwarg == "supplier_id":
            kwargs = {"supplier_id": shared_supplier["id"]}
        else:
            kwargs = {"team_id": shared_team["id"]}
        resp_json, username, _ = _do_create_user(user_type, shared_org, db_roles, **kwargs)
        assertion.assert_equal(resp_json.get("code"), 0, f"{case_id} 用户创建应成功")

        login_with(username, DEFAULT_PASSWORD)
        resp = api_client.data_export_records(dataset_id)
        result = resp.json()
        logger.info(
            f"[query] {case_id} 非 PM 查询 -> code={result.get('code')}, msg={result.get('msg')}"
        )
        assertion.assert_equal(result.get("code"), 403, f"{case_id} 查询应返回 403")

    def test_query_unauthorized(self, pm_user):
        """未登录查询导出记录 - 401"""
        dataset_id, _ = _setup_dataset_with_upload_record(pm_user)

        http_client.remove_token()
        try:
            resp = api_client.data_export_records(dataset_id)
            assertion.assert_response_success(resp, 401, "未认证，请先登录")
        finally:
            login_as("admin")
