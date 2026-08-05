import base64

from api.apis.data_api import api_client
from common.base_log import logger
from typing import Optional


class UserApi:
    """用户接口业务层"""

    def create_user(self,
        username: Optional[str] = None,
        display_name: Optional[str] = None,
        password: Optional[str] = None,
        role_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        remark: Optional[str] = None,
        team_id: Optional[list] = None,
        supplier_id: Optional[str] = None
    ):
        """创建用户"""
        # 密码base64编码
        password = base64.b64encode(password.encode('utf-8')).decode('utf-8')
        logger.info(f"创建用户: username={username}, display_name={display_name}")
        return api_client.create_user(
            username=username,
            display_name=display_name,
            password=password,
            role_id=role_id,
            organization_id=organization_id,
            email=email,
            phone=phone,
            remark=remark,
            team_id=team_id,
            supplier_id=supplier_id
        )

    def update_user(self,
        user_id: str,
        username: Optional[str] = None,
        display_name: Optional[str] = None,
        password: Optional[str] = None,
        role_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        remark: Optional[str] = None,
        team_id: Optional[list] = None,
        supplier_id: Optional[str] = None
        ):
        """编辑用户"""
        # 密码Base64编码
        if password:
            password = base64.b64encode(password.encode('utf-8')).decode('utf-8')
        logger.info(f"编辑用户信息: user_id={user_id}, username={username}")
        return api_client.update_user(
            user_id=user_id,
            username=username,
            display_name=display_name,
            password=password,
            role_id=role_id,
            organization_id=organization_id,
            email=email,
            phone=phone,
            remark=remark,
            team_id=team_id,
            supplier_id=supplier_id
        )

    def get_user_detail_by_id(self, user_id: str):
        logger.info(f"用户管理页面获取用户详情: user_id={user_id}")
        return api_client.get_user_detail(user_id=user_id)

    def query_user_list(self, 
        username: Optional[str] = None,
        role_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        org_id: Optional[str] = None,
        supplier_id: Optional[str] = None,
        team_id: Optional[str] = None,
        team_no_supplier: Optional[bool] = None,
        page: Optional[int] = 1,
        page_size: Optional[int] = 10
        ):
        """获取用户列表"""
        logger.info(f'查询用户列表: username={username}, role_id={role_id}, is_active={is_active}, org_id={org_id}, supplier_id={supplier_id}, team_id={team_id}, team_no_supplier={team_no_supplier}, page={page}, page_size={page_size}')
        return api_client.get_users(
            username=username,
            role_id=role_id,
            is_active=is_active,
            org_id=org_id,
            supplier_id=supplier_id,
            team_id=team_id,
            team_no_supplier=team_no_supplier,
            page=page,
            page_size=page_size
        )

    def update_user_status(self, user_id: str):
        """启用/禁用用户"""
        logger.info(f"【API调用】PATCH /api/users/{user_id}/toggle-status")
        return api_client.toggle_user_status(user_id=user_id)

    # 当前系统没有使用这个接口 
    def get_auth_me(self):
        """获取当前用户信息"""
        logger.info(f"【API调用】GET /api/auth/me")
        return api_client.get_auth_me()


user_api = UserApi()
