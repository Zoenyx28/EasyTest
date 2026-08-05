"""组织管理接口"""
from utils.generate_data import faker_data
from api.apis.data_api import api_client
from common.base_log import logger


class OrgApi:
    """组织接口业务层"""

    def generate_org_name(self) -> str:
        return faker_data.random_name(pre="org", max_length=20)

    def create_organization(self, name: str, description: str = None):
        logger.info(f"创建组织: name={name}, description={description}")
        return api_client.create_organization(name=name, description=description)

    def get_organization_list(self, name: str = None, is_active: bool = None):
        logger.info(f"查询组织列表: name={name}, is_active={is_active}")
        return api_client.get_organizations(name=name, is_active=is_active)

    def get_organization(self, org_id: str):
        logger.info(f"查询组织详情: org_id={org_id}")
        return api_client.get_organization(org_id=org_id)

    def toggle_organization_status(self, org_id: str, is_active: bool = False):
        logger.info(f"切换组织状态: org_id={org_id}, is_active={is_active}")
        return api_client.toggle_organization_status(org_id=org_id, is_active=is_active)


org_api = OrgApi()
