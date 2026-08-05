import pytest

from api.apis.org_api import org_api
from api.apis.user_api import user_api
from common.assert_util import assertion
from common.base_log import logger
from common.file_handler import load_testcase
from utils.generate_data import faker_data
from common.db_util import pg_db
from config.settings import TEST_ORG_DESCRIPTION, DEFAULT_PASSWORD
from fixtures.api_helpers import get_list_items
from api.apis.auth_api import login_as, login_with


@pytest.mark.system
@pytest.mark.api
class TestOrganization:
    @pytest.fixture()
    def case_data(self):
        """懒加载测试数据，避免模块导入时IO错误"""
        return load_testcase("org.yaml")

    @staticmethod
    def _get_role_id(role_code: str) -> str:
        """从数据库查询角色ID"""
        role = pg_db.query_one("SELECT id FROM dsp_role WHERE code = %s", (role_code,))
        assertion.assert_is_not_none(role, f"未找到角色: {role_code}")
        return role["id"]

    @staticmethod
    def _create_pm_user(org_id: str) -> dict:
        """动态创建PM用户，返回{user_id, username}"""
        role_id = TestOrganization._get_role_id("PM")
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
        assertion.assert_equal(resp_json.get("code"), 0, "创建PM用户失败")
        data = resp_json.get("data", {})
        return {"user_id": data.get("id"), "username": username}

    @pytest.fixture(scope="module")
    def shared_org(self):
        """模块级共享组织，减少重复创建"""
        login_as("admin")
        org_name = org_api.generate_org_name()
        resp = org_api.create_organization(name=org_name, description=TEST_ORG_DESCRIPTION)
        assertion.assert_equal(resp.json().get("code"), 0, "创建共享组织失败")
        data = resp.json().get("data", {})
        org_id = data.get("id")
        logger.info(f"共享组织创建成功: {org_id}")
        return {"id": org_id, "name": org_name}

    @pytest.fixture()
    def another_org(self):
        """另一个组织，用于跨组织/重复名称场景"""
        login_as("admin")
        org_name = org_api.generate_org_name()
        resp = org_api.create_organization(name=org_name, description=TEST_ORG_DESCRIPTION)
        assertion.assert_equal(resp.json().get("code"), 0, "创建另一个组织失败")
        data = resp.json().get("data", {})
        return {"id": data.get("id"), "name": org_name}

    @pytest.fixture()
    def pm_user(self, shared_org):
        """基于共享组织动态创建PM用户"""
        login_as("admin")
        return self._create_pm_user(shared_org["id"])

    @staticmethod
    def _assert_org_match(expected: dict, actual: dict):
        """对比创建的组织信息与查询的组织信息是否匹配"""
        assertion.assert_equal(actual.get("id"), expected.get("id"), "组织ID不匹配")
        assertion.assert_equal(actual.get("name"), expected.get("name"), "组织名称不匹配")
        assertion.assert_equal(actual.get("description"), expected.get("description"), "组织描述不匹配")
        assertion.assert_equal(actual.get("is_active"), True, "组织状态应为启用")
        assertion.assert_is_not_none(actual.get("created_at"), "创建时间不能为空")
        assertion.assert_is_not_none(actual.get("created_by_id"), "创建人ID不能为空")
        logger.info(f"组织信息匹配验证通过: id={actual.get('id')}, name={actual.get('name')}")

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.smoke
    def test_create_org(self,as_admin):
        """系统管理员创建组织后查询，验证创建信息与组织列表信息匹配"""
        # 1. 创建组织
        org_name = org_api.generate_org_name()
        org_description = TEST_ORG_DESCRIPTION
        logger.info(f"========== 创建组织: {org_name} ==========")

        create_resp = org_api.create_organization(name=org_name, description=org_description)
        assertion.assert_status_code(create_resp, 200)

        create_json = create_resp.json()
        assertion.assert_equal(create_json.get("code"), 0, "创建组织code验证失败")
        assertion.assert_equal(create_json.get("msg"), "success", "创建组织msg验证失败")

        create_data = create_json.get("data")
        assertion.assert_is_not_none(create_data, "创建组织data不能为空")

        org_id = create_data.get("id")
        assertion.assert_is_not_none(org_id, "组织ID不能为空")
        logger.info(f"组织创建成功, org_id={org_id}")

        # 2. 通过组织列表查询
        logger.info(f"========== 查询组织列表: {org_name} ==========")
        list_resp = org_api.get_organization_list(name=org_name)
        assertion.assert_status_code(list_resp, 200)

        list_json = list_resp.json()
        assertion.assert_equal(list_json.get("code"), 0, "查询组织code验证失败")

        items = get_list_items(list_json)
        assertion.assert_is_not_none(items, "组织列表items不能为空")
        assertion.assert_equal(len(items), 1, "应只查询到1个组织")

        query_item = items[0]

        # 3. 对比创建信息与查询信息
        logger.info("========== 对比创建信息与查询信息 ==========")
        self._assert_org_match(create_data, query_item)

        # 4. 通过组织详情查询并对比
        logger.info(f"========== 查询组织详情: {org_id} ==========")
        detail_resp = org_api.get_organization(org_id=org_id)
        assertion.assert_status_code(detail_resp, 200)

        detail_json = detail_resp.json()
        assertion.assert_equal(detail_json.get("code"), 0, "组织详情code验证失败")

        detail_data = detail_json.get("data")
        assertion.assert_is_not_none(detail_data, "组织详情data不能为空")

        logger.info("========== 对比创建信息与详情信息 ==========")
        self._assert_org_match(create_data, detail_data)

    @pytest.mark.system
    @pytest.mark.api
    def test_create_org_duplicate_name(self, as_admin, case_data):
        """系统管理员创建组织失败-重复名称"""
        case = case_data["test_create_org_duplicate_name"]
        logger.info(f"========== {case['description']} ==========")

        # 第一步：先创建一个组织
        org_name = org_api.generate_org_name()
        create_resp = org_api.create_organization(name=org_name, description=TEST_ORG_DESCRIPTION)
        assertion.assert_equal(create_resp.json().get("code"), 0, "首次创建组织应成功")

        # 第二步：用相同名称创建，应返回code:409
        dup_resp = org_api.create_organization(name=org_name, description=TEST_ORG_DESCRIPTION)
        assertion.assert_response(dup_resp, case["expect"])

    @pytest.mark.system
    @pytest.mark.api
    def test_create_org_empty_name(self, as_admin, case_data):
        """系统管理员创建组织-名称为空"""
        case = case_data["test_create_org_empty_name"]
        logger.info(f"========== {case['description']} ==========")

        create_resp = org_api.create_organization(name="", description=TEST_ORG_DESCRIPTION)
        assertion.assert_response(create_resp, case["expect"])
    
    @pytest.mark.system
    @pytest.mark.api    
    def test_create_org_max_orgname(self, as_admin, case_data):
        """系统管理员创建组织-名称为21个字符"""
        case = case_data["test_create_org_max_orgname"]
        logger.info(f"========== {case['description']} ==========")

        import time
        org_name = f"autotest_{int(time.time() * 1000) % 100000000:08d}aaaaa"
        
        create_resp = org_api.create_organization(name=org_name, description=case["request"]["description"])
        resp_json = create_resp.json()
        assertion.assert_equal(resp_json.get("code"), 0, "创建组织code验证失败")
        assertion.assert_equal(resp_json.get("data", {}).get("name"), org_name, "组织名称不匹配")

    @pytest.mark.system
    @pytest.mark.api    
    def test_create_org_max_orgdesc(self, as_admin, case_data):
        """系统管理员创建组织-描述为201个字符"""
        case = case_data["test_create_org_max_orgdesc"]
        logger.info(f"========== {case['description']} ==========")

        org_name = org_api.generate_org_name()
        long_desc = f"{TEST_ORG_DESCRIPTION}" + "a" * (201 - len(TEST_ORG_DESCRIPTION))
        create_resp = org_api.create_organization(name=org_name, description=long_desc)
        resp_json = create_resp.json()
        assertion.assert_equal(resp_json.get("code"), 0, "创建组织code验证失败")
        assertion.assert_equal(resp_json.get("data", {}).get("description"), long_desc, "组织描述不匹配")

    @pytest.mark.system
    @pytest.mark.api
    def test_non_admin_create_org_failure(self, pm_user):
        """非系统管理员创建组织-失败"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        logger.info("使用动态创建的PM账号创建组织")
        org_name = org_api.generate_org_name()
        create_resp = org_api.create_organization(name=org_name, description=TEST_ORG_DESCRIPTION)
        assertion.assert_equal(create_resp.json().get("code"), 403, "项目管理员创建组织应返回403")
    
    # 查询组织用例
    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.smoke
    def test_get_org_list(self,as_admin):
        """系统管理员无条件查询组织列表"""
        logger.info(f"用例名称：系统管理员无条件查询组织列表成功")
        list_resp = org_api.get_organization_list()
        assertion.assert_status_code(list_resp, 200)

        list_json = list_resp.json()
        assertion.assert_equal(list_json.get("code"), 0, "查询组织code验证失败")

        items = get_list_items(list_json)
        assertion.assert_is_not_none(items, "组织列表items不能为空")
        logger.info(f"查询到组织列表: {items}")        

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.smoke
    def test_get_org_list_by_name(self, shared_org):
        """系统管理员按照组织名称查询组织详情"""
        logger.info(f"用例名称：系统管理员按照组织名称查询组织详情成功")
        org_name = shared_org["name"]

        # 第一步：查询组织完全匹配名称
        list_resp = org_api.get_organization_list(name=org_name)
        assertion.assert_status_code(list_resp, 200)

        list_json = list_resp.json()
        assertion.assert_equal(list_json.get("code"), 0, "查询组织接口响应code验证失败")

        items = get_list_items(list_json)
        assertion.assert_equal(items[0].get("name"), org_name, f"完全匹配查询组织名称{org_name}失败")

        # 第二步：模糊查询
        fuzzy_name = org_name[:8]
        logger.info(f"模糊查询组织名称包含{fuzzy_name}的组织")
        list_resp = org_api.get_organization_list(name=fuzzy_name)
        assertion.assert_status_code(list_resp, 200)

        list_json = list_resp.json()
        assertion.assert_equal(list_json.get("code"), 0, "查询组织接口响应code验证失败")

        items = get_list_items(list_json)

        # 第三步：验证所有查询结果中均包含模糊查询的字符串
        assertion.assert_true(all([fuzzy_name in item.get("name") for item in items]), f"组织名称中不包含{fuzzy_name}")
    
    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.smoke
    def test_get_org_list_by_status(self,as_admin):
        """系统管理员按照组织状态查询组织列表"""
        logger.info(f"用例名称：系统管理员按照组织状态查询组织列表成功")
        
        # 第一步：创建组织,组织状态为启用
        org_name = org_api.generate_org_name()
        org_desc = TEST_ORG_DESCRIPTION
        response = org_api.create_organization(name=org_name, description=org_desc)
        assertion.assert_status_code(response, 200)

        detail_json = response.json()
        assertion.assert_equal(detail_json.get("code"), 0, "创建组织请求接口返回code验证失败")

        detail_data = detail_json.get("data")
        assertion.assert_is_not_none(detail_data, "创建组织请求接口返回data不能为空")
        logger.info(f"创建组织{org_name}成功,通过组织状态查询组织列表,组织状态为启用")
        
        # 第二步：查询组织状态为启用的组织列表,验证搜索结果均为启用状态，且刚刚创建的组织在列表中
        list_resp = org_api.get_organization_list(is_active=True)
        assertion.assert_status_code(list_resp, 200)

        items = get_list_items(list_resp.json())
        assertion.assert_is_not_none(items, "组织列表items不能为空")
        assertion.assert_true(detail_data.get("id") in [item.get("id") for item in items], f"组织{org_name}不在启用状态组织列表中")
        assertion.assert_true(all([item.get("is_active") for item in items]), "启用状态组织列表中包含禁用状态组织")

        # 第三步：切换组织状态为禁用
        logger.info(f"切换组织{org_name}状态为禁用")
        update_resp = org_api.toggle_organization_status(org_id=detail_data.get("id"),is_active=False)
        assertion.assert_status_code(update_resp, 200)
        
        update_json = update_resp.json()
        assertion.assert_equal(update_json.get("data").get("is_active"), False, "组织状态切换为禁用失败")
        
        # 第四步：查询组织状态为禁用的组织列表,验证搜索结果均为禁用状态，且刚刚变更状态的组织在列表中
        logger.info(f"通过组织状态查询组织列表,组织状态为禁用")
        list_resp = org_api.get_organization_list(is_active=False)
        assertion.assert_status_code(list_resp, 200)

        list_json = list_resp.json()
        assertion.assert_equal(list_json.get("code"), 0, "查询组织接口响应code验证失败")

        items = get_list_items(list_json)
        assertion.assert_true(detail_data.get("id") in [item.get("id") for item in items], f"组织{org_name}不在禁用状态组织列表中")
        assertion.assert_true(all([not item.get("is_active") for item in items]), "禁用状态组织列表中包含启用状态组织")
    
    @pytest.mark.system
    @pytest.mark.api
    def test_non_admin_get_org_list(self, pm_user):
        """非系统管理员查询组织列表-权限不足"""
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        logger.info("用例名称：项目管理员查询组织列表权限不足")
        list_resp = org_api.get_organization_list()
        assertion.assert_status_code(list_resp, 200)
        assertion.assert_equal(list_resp.json().get("code"), 403, "查询组织接口响应code验证失败")
        
    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.smoke
    def test_toggle_org_status_to_false(self,as_admin):
        """系统管理员切换组织为禁用状态"""
        logger.info(f"用例名称：系统管理员切换组织状态为禁用")
        # 第一步：创建一个组织
        org_name = org_api.generate_org_name()
        org_desc = TEST_ORG_DESCRIPTION
        response = org_api.create_organization(name=org_name, description=org_desc)
        assertion.assert_status_code(response, 200)

        detail_json = response.json()
        assertion.assert_equal(detail_json.get("code"), 0, "创建组织请求code验证失败")

        detail_data = detail_json.get("data")
        assertion.assert_is_not_none(detail_data, "创建组织响应data不能为空")
        
        # 第二步：切换这个组织状态为禁用
        org_id = detail_data.get("id")
        logger.info(f"切换组织{org_name}状态为禁用")
        update_resp = org_api.toggle_organization_status(org_id=org_id,is_active=False)
        assertion.assert_status_code(update_resp, 200)
        
        update_json = update_resp.json()
        assertion.assert_equal(update_json.get("data").get("is_active"), False, "组织状态切换为禁用失败")
        logger.info(f"组织{org_name}状态切换为禁用成功")

    @pytest.mark.system
    @pytest.mark.api
    @pytest.mark.smoke
    def test_pm_toggle_org_status_to_false(self, pm_user):
        """项目管理员切换组织为禁用状态-权限不足"""
        logger.info("用例名称：项目管理员无权限切换组织状态")
        # 第一步：admin创建组织
        login_as("admin")
        org_name = org_api.generate_org_name()
        create_resp = org_api.create_organization(name=org_name, description=TEST_ORG_DESCRIPTION)
        assertion.assert_equal(create_resp.json().get("code"), 0, "创建组织应成功")
        org_id = create_resp.json().get("data", {}).get("id")
        # 第二步：切换到动态创建的PM身份，尝试切换组织状态
        login_with(pm_user["username"], DEFAULT_PASSWORD)
        update_resp = org_api.toggle_organization_status(org_id=org_id, is_active=False)
        assertion.assert_equal(update_resp.json().get("code"), 403, "项目管理员切换组织状态应返回403")
