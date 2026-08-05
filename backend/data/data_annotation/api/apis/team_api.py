from api.apis.data_api import api_client
from common.base_log import logger


class TeamApi:
    """团队接口业务层"""

    def create_team(
        self,
        name: str,
        org_id: str,
        supplier_id: str = None,
        admin_ids: list = None,
        member_ids: list = None,
        description: str = None
    ):
        """
        创建团队
        :param name: 团队名称
        :param org_id: 组织ID
        :param supplier_id: 供应商ID（供应商团队必填）
        :param admin_ids: 管理员ID列表
        :param member_ids: 成员ID列表
        :param description: 团队描述
        """
        logger.info(f"创建团队: name={name}, org_id={org_id}, supplier_id={supplier_id}")
        return api_client.create_team(
            name=name,
            org_id=org_id,
            supplier_id=supplier_id,
            admin_ids=admin_ids,
            member_ids=member_ids,
            description=description
        )

    def get_team_list(
        self,
        org_id: str = None,
        supplier_id: str = None,
        name: str = None,
        is_active: bool = None,
        team_no_supplier: bool = None,
        page: int = 1,
        page_size: int = 10
    ):
        """
        获取团队列表
        :param org_id: 组织ID
        :param supplier_id: 供应商ID
        :param name: 团队名称
        :param is_active: 状态
        :param team_no_supplier: 是否查询无供应商的团队
        :param page: 页码
        :param page_size: 每页数量
        """
        logger.info(f"查询团队列表: org_id={org_id}, supplier_id={supplier_id}")
        return api_client.get_teams(
            org_id=org_id,
            supplier_id=supplier_id,
            name=name,
            is_active=is_active,
            team_no_supplier=team_no_supplier,
            page=page,
            page_size=page_size
        )
    
    def update_team(
        self,
        team_id: str,
        name: str = None,
        supplier_id: str = None,
        admin_ids: list = None,
        member_ids: list = None,
        description: str = None
    ):
        """
        编辑团队
        :param team_id: 团队ID
        :param name: 团队名称
        :param supplier_id: 供应商ID（供应商团队必填）
        :param admin_ids: 管理员ID列表
        :param member_ids: 成员ID列表
        :param description: 团队描述
        """
        logger.info(f"更新团队: team_id={team_id}")
        return api_client.update_team(
            team_id=team_id,
            name=name,
            supplier_id=supplier_id,
            admin_ids=admin_ids,
            member_ids=member_ids,
            description=description
        )

    def toggle_team_status(
        self,
        team_id: str
    ):
        """
        切换团队状态
        :param team_id: 团队ID
        """
        logger.info(f"切换团队状态: {team_id}")
        return api_client.toggle_team_status(team_id)


team_api = TeamApi()
