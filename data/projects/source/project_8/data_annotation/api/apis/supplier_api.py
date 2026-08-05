from api.apis.data_api import api_client
from common.base_log import logger


class SupplierApi:
    """供应商接口业务层"""

    def create_supplier(
        self,
        name: str,
        org_id: str,
        contact: str = None,
        description: str = None
    ):
        """
        创建供应商
        :param name: 供应商名称
        :param org_id: 创建者的组织ID
        :param contact: 联系电话"
        :param description: 描述
        """
        logger.info(f"创建供应商: name={name}, org_id={org_id}")
        request_body = {
            "name": name,
            "org_id": org_id,
            "contact": contact,
            "description": description
        }
        # 过滤None值
        request_body = {k: v for k, v in request_body.items() if v is not None}
        return api_client.create_supplier(request_body=request_body)

    def update_supplier(
        self,
        supplier_id: str,
        name: str = None,
        contact: str = None,
        description: str = None
    ):
        """
        更新供应商
        :param supplier_id: 供应商ID
        :param name: 供应商名称
        :param contact: 联系电话"
        :param description: 描述
        """
        logger.info(f"更新供应商: supplier_id={supplier_id}")
        request_body = {
            "name": name,
            "contact": contact,
            "description": description
        }
        # 过滤None值
        request_body = {k: v for k, v in request_body.items() if v is not None}
        return api_client.update_supplier(supplier_id=supplier_id, request_body=request_body)

    def get_supplier_list(
        self,
        org_id: str = None,
        name: str = None,
        is_active: bool = None,
        page: int = 1,
        page_size: int = 10
    ):
        """
        获取供应商列表
        :param org_id: 组织ID
        :param name: 供应商名称
        :param is_active: 状态
        :param page: 页码
        :param page_size: 每页数量
        """
        logger.info(f"查询供应商列表: org_id={org_id}, name={name}")
        return api_client.get_supplier_list(
            org_id=org_id,
            name=name,
            is_active=is_active,
            page=page,
            page_size=page_size
        )

    def toggle_supplier_status(
        self,
        supplier_id: str
    ):
        """
        切换供应商状态
        :param supplier_id: 供应商ID
        """
        logger.info(f"切换供应商状态: supplier_id={supplier_id}")
        return api_client.toggle_supplier_status(supplier_id)

supplier_api = SupplierApi()
