"""从OpenAPI规范自动生成的API客户端"""
import json
from typing import Any, List, Optional

from common.http_client import http_client
from common.base_log import logger


class AutoApiClient:
    """自动生成的API客户端"""

    @staticmethod
    def _build_params(**kwargs) -> Optional[dict]:
        params = {k: v for k, v in kwargs.items() if v is not None}
        return params if params else None

    def post_login(
        self, 
        username: str, 
        password: str #登录密码,需要base64编码后入参
        ):
        """用户登录"""
        logger.info(f"【API调用】POST /api/auth/login")
        url = "/api/auth/login"
        json = {"username": username, "password": password}
        return http_client.post(url=url, json=json)

    def get_auth_me(self):
        """获取当前用户信息"""
        logger.info(f"【API调用】GET /api/auth/me")
        url = "/api/auth/me"
        return http_client.get(url=url)

    def get_users(self, 
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
        """
        获取用户列表
        :param username: 用户账号或姓名（模糊查询）
        :param role_id: 角色ID，支持单个UUID、逗号分隔或JSON数组
        :param is_active: 用户状态，True为活跃，False为非活跃，None表示不筛选
        :param org_id: 组织ID
        :param supplier_id: 供应商ID
        :param team_id: 团队ID
        :param team_no_supplier: 是否不包含供应商团队
        :param page: 页码
        :param page_size: 每页数量
        :return: API响应
        """
        logger.info(f"【API调用】GET /api/users/")
        url = "/api/users/"
        params = self._build_params(
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
        return http_client.get(url=url, params=params)

    def create_user(self, 
        username: str, 
        display_name: str,
        password: str,
        role_id: str,
        organization_id: str,
        email: str=None, 
        phone: str=None,
        remark: str=None,
        team_id: list=None,
        supplier_id: str=None
        ):
        """
        创建用户
        :param username: 用户账号或姓名（模糊查询）
        :param display_name: 显示名
        :param password: 密码
        :param role_id: 角色ID
        :param organization_id: 组织ID
        :param email: 邮箱
        :param phone: 手机号
        :param remark: 备注
        :param team_id: 团队ID列表
        :param supplier_id: 供应商ID
        :return: API响应
        """
        logger.info(f"【API调用】POST /api/users/")
        url = "/api/users/"
        json = {
            "username": username,
            "display_name": display_name,
            "password": password,
            "role_id": role_id,
            "phone": phone if phone else "",
            "email": email if email else "",
            "remark": remark if remark else ""
        }
        if organization_id is not None:
            json["organization_id"] = organization_id
        if supplier_id is not None:
            json["supplier_id"] = supplier_id
        if team_id is not None:
            json["team_id"] = team_id
        return http_client.post(url=url, json=json)

    def get_current_user_info(self):
        """获取当前用户信息"""
        logger.info(f"【API调用】GET /api/users/me")
        url = "/api/users/me"
        return http_client.get(url=url)

    def update_current_user(self, request_body: dict = None):
        """更新当前用户信息"""
        logger.info(f"【API调用】PATCH /api/users/me")
        url = "/api/users/me"
        return http_client.patch(url=url, json=request_body)

    def change_password(self, request_body: dict = None):
        """修改当前用户密码"""
        logger.info(f"【API调用】POST /api/users/me/change-password")
        url = "/api/users/me/change-password"
        return http_client.post(url=url, json=request_body)

    def get_user_detail(self, user_id: str):
        """用户管理获取用户详情"""
        logger.info(f"【API调用】GET /api/users/{user_id}")
        
        url = f"/api/users/{user_id}"
        return http_client.get(url=url)

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
        team_id: Optional[list[str]] = None,
        supplier_id: Optional[str] = None
        ):
        """编辑用户"""
        logger.info(f"【API调用】PATCH /api/users/{user_id}")
        url = f"/api/users/{user_id}"
        json={
            "phone": phone if phone else "",
            "email": email if email else "",
            "remark": remark if remark else ""
        }
        if username is not None:
            json["username"] = username
        if display_name is not None:
            json["display_name"] = display_name
        if password is not None:
            json["password"] = password
        if role_id is not None:
            json["role_id"] = role_id
        if organization_id is not None:
            json["organization_id"] = organization_id
        if supplier_id is not None:
            json["supplier_id"] = supplier_id
        if team_id is not None:
            json["team_id"] = team_id
        return http_client.patch(url=url, json=json)

    def toggle_user_status(self, 
        user_id: str
        ):
        """启用/禁用用户"""
        logger.info(f"【API调用】PATCH /api/users/{user_id}/toggle-status")
        url = f"/api/users/{user_id}/toggle-status"
        return http_client.patch(url=url)

    def get_organizations(self, name: Any = None, is_active: Any = None, page: int = 1, page_size: int = 10):
        """获取组织列表"""
        logger.info(f"【API调用】GET /api/organizations/")
        url = "/api/organizations/"
        params = self._build_params(
            name=name,
            is_active=is_active,
            page=page,
            page_size=page_size
        )
        return http_client.get(url=url, params=params)

    def create_organization(self, name: str,description: str = None):
        """创建组织"""
        logger.info(f"【API调用】POST /api/organizations/")
        url = "/api/organizations/"
        json = {"name": name, "description": description}
        return http_client.post(url=url, json=json)

    def get_organization(self, org_id: str):
        """获取组织详情"""
        logger.info(f"【API调用】GET /api/organizations/{org_id}")
        url = f"/api/organizations/{org_id}"
        return http_client.get(url=url)

    def update_organization(self, org_id: str,
        description: str = None,
        id: str = None,
        name: str = None
        ):
        """编辑组织"""
        logger.info(f"【API调用】PATCH /api/organizations/{org_id}")
        json={"description": description, "id": id, "name": name}
        url = f"/api/organizations/{org_id}"
        return http_client.patch(url=url, json=json)

    def toggle_organization_status(self, org_id: str, is_active: bool = False):
        """启用/禁用组织"""
        logger.info(f"【API调用】PATCH /api/organizations/{org_id}/toggle-status")
        json={"is_active": is_active}
        url = f"/api/organizations/{org_id}/toggle-status"
        return http_client.patch(url=url, json=json)

    def get_members(self, org_id: int = None, page: int = None, page_size: int = None):
        """获取成员列表"""
        logger.info(f"【API调用】GET /api/members/")
        url = "/api/members/"
        params = self._build_params(
            org_id=org_id,
            page=page,
            page_size=page_size
        )
        return http_client.get(url=url, params=params)

    def add_member(self, request_body: dict = None):
        """添加成员"""
        logger.info(f"【API调用】POST /api/members/")
        url = "/api/members/"
        return http_client.post(url=url, json=request_body)

    def update_member(self, member_id: str, request_body: dict = None):
        """更新成员信息"""
        logger.info(f"【API调用】PATCH /api/members/{member_id}")
        url = f"/api/members/{member_id}"
        return http_client.patch(url=url, json=request_body)

    def remove_member(self, member_id: str):
        """移除成员"""
        logger.info(f"【API调用】DELETE /api/members/{member_id}")
        url = f"/api/members/{member_id}"
        return http_client.delete(url=url)

    def get_role_list(self):
        """获取角色列表"""
        logger.info(f"【API调用】GET /api/roles/")
        url = "/api/roles/"
        return http_client.get(url=url)

    def get_teams(self, org_id: Any = None, supplier_id: Any = None, name: Any = None, is_active: Any = None, team_no_supplier: Any = None, team_id: Any = None, page: int = None, page_size: int = None):
        """获取团队列表"""
        logger.info(f"【API调用】GET /api/teams/")
        url = "/api/teams/"
        params = self._build_params(
            org_id=org_id,
            supplier_id=supplier_id,
            name=name,
            is_active=is_active,
            team_no_supplier=team_no_supplier,
            team_id=team_id,
            page=page,
            page_size=page_size
        )
        return http_client.get(url=url, params=params)

    def create_team(self, 
        name: str,
        org_id: str, #团队所在组织ID，必填
        admin_ids: List[str] = None,#团队管理员ID列表，支持多选
        description: str = None,
        member_ids: List[str] = None,#团队成员ID列表，支持多选
        supplier_id: str = None
        ):
        """创建团队"""
        logger.info(f"【API调用】POST /api/teams/")
        url = "/api/teams/"
        json = {
            "name": name,
            "org_id": org_id,
            "admin_ids": admin_ids if admin_ids else [],
            "description": description if description else "",
            "member_ids": member_ids if member_ids else [],
            "supplier_id": supplier_id if supplier_id else None
        }
        return http_client.post(url=url, json=json)

    def update_team(self, 
    team_id: str,
    name: str = None,
    org_id: str = None,
    admin_ids: list = None,
    description: str = None,
    member_ids: list = None,
    supplier_id: str = None
    ):
        """编辑团队"""
        logger.info(f"【API调用】PATCH /api/teams/{team_id}")
        url = f"/api/teams/{team_id}"
        json = {
            "name": name,
            "org_id": org_id,
            "admin_ids": admin_ids if admin_ids else [],
            "description": description if description else "",
            "member_ids": member_ids if member_ids else [],
            "supplier_id": supplier_id if supplier_id else None
        }
        return http_client.patch(url=url, json=json)

    def toggle_team_status(self, team_id: str):
        """启用/禁用团队"""
        logger.info(f"【API调用】PATCH /api/teams/{team_id}/toggle-status")
        url = f"/api/teams/{team_id}/toggle-status"
        return http_client.patch(url=url)

    def get_supplier_list(
        self,
        org_id: Any = None,
        name: Any = None,
        is_active: Any = None,
        created_by_id: Any = None,
        page: int = None,
        page_size: int = None
    ):
        """获取供应商列表"""
        logger.info(f"【API调用】GET /api/suppliers/")
        url = "/api/suppliers/"
        params = self._build_params(
            org_id=org_id,
            name=name,
            is_active=is_active,
            created_by_id=created_by_id,
            page=page,
            page_size=page_size
        )
        return http_client.get(url=url, params=params)

    def create_supplier(self, request_body: dict = None):
        """创建供应商"""
        logger.info(f"【API调用】POST /api/suppliers/")
        url = "/api/suppliers/"
        return http_client.post(url=url, json=request_body)

    def update_supplier(self, supplier_id: str, request_body: dict = None):
        """编辑供应商"""
        logger.info(f"【API调用】PATCH /api/suppliers/{supplier_id}")
        url = f"/api/suppliers/{supplier_id}"
        return http_client.patch(url=url, json=request_body)

    def toggle_supplier_status(self, supplier_id: str):
        """启用/禁用供应商"""
        logger.info(f"【API调用】PATCH /api/suppliers/{supplier_id}/toggle-status")
        url = f"/api/suppliers/{supplier_id}/toggle-status"
        return http_client.patch(url=url)

    def get_datasets(self, request_body: dict = None ):
        """获取数据集列表"""
        logger.info(f"【API调用】GET /api/datasets/")
        url = "/api/datasets/"
        return http_client.get(url=url, params=request_body)

    def create_dataset(self, request_body: dict = None):
        """新建数据集"""
        url = "/api/datasets/"
        logger.info(f"【API调用】POST /api/datasets/,请求参数:{request_body}")
        return http_client.post(url=url, json=request_body)

    def upload_temp_cover(self,
        file: bytes,
        org_id: str,
        filename: str="cover.jpg",
        type: str="image/jpeg",
        timeout: int = 1800
    ):
        """临时上传封面图（multipart/form-data）

        :param org_id: 当前 PM 所在的组织 ID（后端权限校验必填），通过 URL query string 提交。
        """
        url = "/api/datasets/upload-cover"
        logger.info(
            f"【API调用】POST /api/datasets/upload-cover, filename={filename}, type={type}, org_id={org_id}"
        )
        files = {"file": (filename, file, type)}
        # org_id 作为 query string 提交（实测 form field 不被后端接收）
        params = {"org_id": org_id} if org_id is not None else None
        return http_client.post(url=url, files=files, params=params,timeout=timeout)

    def get_dataset_detail(self, dataset_id: str):
        """获取数据集详情"""
        logger.info(f"【API调用】GET /api/datasets/{dataset_id}")
        url = f"/api/datasets/{dataset_id}"
        return http_client.get(url=url)

    def update_dataset(self, dataset_id: str, request_body: dict = None):
        """编辑数据集"""
        logger.info(f"【API调用】PATCH /api/datasets/{dataset_id}")
        url = f"/api/datasets/{dataset_id}"
        return http_client.patch(url=url, json=request_body)

    def deprecate_dataset(self, dataset_id: str, response_body: dict = None):
        """弃用数据集"""
        logger.info(f"【API调用】POST /api/datasets/{dataset_id}/deprecate")
        url = f"/api/datasets/{dataset_id}/deprecate"
        return http_client.post(url=url, json=response_body)

    def get_cover(self, dataset_id: str):
        """获取数据集封面"""
        logger.info(f"【API调用】GET /api/datasets/{dataset_id}/cover")
        url = f"/api/datasets/{dataset_id}/cover"
        return http_client.get(url=url)

    def upload_data(self,
        dataset_id: str,
        file: bytes = None,
        filename: str = "package.zip",
        content_type: str = "application/zip",
        timeout: int = 300,
    ):
        """上传压缩包到临时目录（multipart/form-data）

        支持 .zip / .tar / .tar.gz / .tar.bz2，单文件不超过 5GB。
        返回临时存储 Key，用于 process-upload。
        """
        url = f"/api/datasets/{dataset_id}/upload"
        logger.info(
            f"【API调用】POST /api/datasets/{dataset_id}/upload, filename={filename}, content_type={content_type}"
        )
        files = {"file": (filename, file, content_type)}
        return http_client.post(url=url, files=files, timeout=timeout)

    def process_uploaded_data(self, dataset_id: str, request_body: dict = None):
        """处理上传数据"""
        logger.info(f"【API调用】POST /api/datasets/{dataset_id}/process-upload")
        url = f"/api/datasets/{dataset_id}/process-uploads"
        return http_client.post(url=url, json=request_body)

    def get_uploads_list(self, dataset_id: str, response_body: dict = None
    ):
        """获取上传记录"""
        logger.info(f"【API调用】GET /api/datasets/{dataset_id}/uploads")
        url = f"/api/datasets/{dataset_id}/uploads"
        return http_client.get(url=url, params=response_body)


    def get_package_ids(self, dataset_id: str):
        """获取数据包ID列表"""
        logger.info(f"【API调用】GET /api/datasets/{dataset_id}/uploads/package-ids")
        url = f"/api/datasets/{dataset_id}/uploads/package-ids"
        return http_client.get(url=url)

    def download_package(self, dataset_id: str, upload_id: str):
        """下载压缩包"""
        logger.info(f"【API调用】GET /api/datasets/{dataset_id}/uploads/{upload_id}/download")
        url = f"/api/datasets/{dataset_id}/uploads/{upload_id}/download"
        return http_client.get(url=url)

    def get_dir_tree(self, dataset_id: str):
        """查询文件夹层级"""
        logger.info(f"【API调用】GET /api/datasets/{dataset_id}/dir-tree")
        url = f"/api/datasets/{dataset_id}/dir-tree"
        return http_client.get(url=url)

    def get_data_items(self, dataset_id: str, dir_level1: Any = None, dir_level2: Any = None, dir_level3: Any = None, page: int = None, page_size: int = None):
        """获取数据列表"""
        logger.info(f"【API调用】GET /api/datasets/{dataset_id}/data-items")
        url = f"/api/datasets/{dataset_id}/data-items"
        params = self._build_params(
            dir_level1=dir_level1,
            dir_level2=dir_level2,
            dir_level3=dir_level3,
            page=page,
            page_size=page_size
        )
        return http_client.get(url=url, params=params)

    def preview_data_item(self, dataset_id: str, item_id: str):
        """预览数据文件"""
        logger.info(f"【API调用】GET /api/datasets/{dataset_id}/data-items/{item_id}/preview")
        url = f"/api/datasets/{dataset_id}/data-items/{item_id}/preview"
        return http_client.get(url=url)

    def export_data(self, dataset_id: str, request_body: dict = None):
        """数据导出"""
        logger.info(f"【API调用】POST /api/datasets/{dataset_id}/export")
        url = f"/api/datasets/{dataset_id}/export"
        return http_client.post(url=url, json=request_body)

    def get_export_records(self, dataset_id: str, fileName: Any = None, status: Any = None, startTime: Any = None, endTime: Any = None, page: int = None, page_size: int = None):
        """导出记录列表"""
        logger.info(f"【API调用】GET /api/datasets/{dataset_id}/exports")
        url = f"/api/datasets/{dataset_id}/exports"
        params = self._build_params(
            fileName=fileName,
            status=status,
            startTime=startTime,
            endTime=endTime,
            page=page,
            page_size=page_size
        )
        return http_client.get(url=url, params=params)

    def download_export_package(self, dataset_id: str, export_id: str):
        """下载导出文件"""
        logger.info(f"【API调用】GET /api/datasets/{dataset_id}/exports/{export_id}/download")
        url = f"/api/datasets/{dataset_id}/exports/{export_id}/download"
        return http_client.get(url=url)

    def close_data_items(self, dataset_id: str, request_body: dict = None):
        """批量关闭数据"""
        logger.info(f"【API调用】POST /api/datasets/{dataset_id}/data-items/close")
        url = f"/api/datasets/{dataset_id}/data-items/close"
        return http_client.post(url=url, json=request_body)

    # ======================== 项目管理 ========================

    def get_projects(self, 
        org_id: Any = None, 
        page: int = None, 
        page_size: int = None,
        name: str = None, 
        data_type: str = None, 
        status: str = None
        ):
        """获取项目列表"""
        logger.info(f"【API调用】GET /api/projects/")
        url = "/api/projects/"
        params = self._build_params(
            org_id=org_id,
            page=page,
            page_size=page_size,
            name=name,
            data_type=data_type,
            status=status
        )
        return http_client.get(url=url, params=params)

    def create_project(self, request_body: dict = None):
        """新建项目"""
        logger.info(f"【API调用】POST /api/projects/")
        url = "/api/projects/"
        return http_client.post(url=url, json=request_body)

    def get_project(self, project_id: str):
        """获取项目详情"""
        logger.info(f"【API调用】GET /api/projects/{project_id}")
        url = f"/api/projects/{project_id}"
        return http_client.get(url=url)

    def update_project(self, project_id: str, request_body: dict = None):
        """编辑项目"""
        logger.info(f"【API调用】PATCH /api/projects/{project_id}")
        url = f"/api/projects/{project_id}"
        return http_client.patch(url=url, json=request_body)

    def bind_dataset(self, project_id: str, request_body: dict = None):
        """绑定数据集"""
        logger.info(f"【API调用】POST /api/projects/{project_id}/bind-dataset")
        url = f"/api/projects/{project_id}/bind-dataset"
        return http_client.post(url=url, json=request_body)

    def delete_bind_dataset(self, project_id: str, dataset_id: str):
        """解绑数据集（DELETE旧版接口）"""
        logger.info(f"【API调用】DELETE /api/projects/{project_id}/bind-dataset/{dataset_id}")
        url = f"/api/projects/{project_id}/bind-dataset/{dataset_id}"
        return http_client.delete(url=url)

    def save_label_config(self, project_id: str, request_body: dict = None):
        """保存标注配置"""
        logger.info(f"【API调用】PUT /api/projects/{project_id}/label-config")
        url = f"/api/projects/{project_id}/label-config"
        return http_client.put(url=url, json=request_body)

    def get_tasks(self, project_id: str, page: int = None, page_size: int = None):
        """获取任务列表"""
        logger.info(f"【API调用】GET /api/projects/{project_id}/tasks/")
        url = f"/api/projects/{project_id}/tasks/"
        params = self._build_params(
            page=page,
            page_size=page_size
        )
        return http_client.get(url=url, params=params)

    def create_task(self, project_id: str, request_body: dict = None):
        """新建任务"""
        logger.info(f"【API调用】POST /api/projects/{project_id}/tasks/")
        url = f"/api/projects/{project_id}/tasks/"
        return http_client.post(url=url, json=request_body)

    def get_task(self, project_id: str, task_id: str):
        """获取任务详情"""
        logger.info(f"【API调用】GET /api/projects/{project_id}/tasks/{task_id}")
        url = f"/api/projects/{project_id}/tasks/{task_id}"
        return http_client.get(url=url)

    def update_task(self, project_id: str, task_id: str, request_body: dict = None):
        """编辑任务"""
        logger.info(f"【API调用】PATCH /api/projects/{project_id}/tasks/{task_id}")
        url = f"/api/projects/{project_id}/tasks/{task_id}"
        return http_client.patch(url=url, json=request_body)

    def push_task_data(self, project_id: str, task_id: str, request_body: dict = None):
        """推送数据至任务"""
        logger.info(f"【API调用】POST /api/projects/{project_id}/tasks/{task_id}/push")
        url = f"/api/projects/{project_id}/tasks/{task_id}/push"
        return http_client.post(url=url, json=request_body)

    def get_push_records(self, project_id: str, task_id: str, page: int = None, page_size: int = None):
        """获取推送记录"""
        logger.info(f"【API调用】GET /api/projects/{project_id}/tasks/{task_id}/push-records")
        url = f"/api/projects/{project_id}/tasks/{task_id}/push-records"
        params = self._build_params(
            page=page,
            page_size=page_size
        )
        return http_client.get(url=url, params=params)

    def get_task_data_items(self, project_id: str, task_id: str, page: int = None, page_size: int = None):
        """获取任务数据列表"""
        logger.info(f"【API调用】GET /api/projects/{project_id}/tasks/{task_id}/data-items")
        url = f"/api/projects/{project_id}/tasks/{task_id}/data-items"
        params = self._build_params(
            page=page,
            page_size=page_size
        )
        return http_client.get(url=url, params=params)

    def get_annotations(self, project_id: str, task_id: str, item_id: str, page: int = None, page_size: int = None):
        """获取标注结果"""
        logger.info(f"【API调用】GET /api/projects/{project_id}/tasks/{task_id}/data-items/{item_id}/annotations")
        url = f"/api/projects/{project_id}/tasks/{task_id}/data-items/{item_id}/annotations"
        params = self._build_params(
            page=page,
            page_size=page_size
        )
        return http_client.get(url=url, params=params)

    def close_task(self, project_id: str, task_id: str, request_body: dict = None):
        """关闭任务"""
        logger.info(f"【API调用】POST /api/projects/{project_id}/tasks/{task_id}/close")
        url = f"/api/projects/{project_id}/tasks/{task_id}/close"
        return http_client.post(url=url, json=request_body)

    # ======================== 项目管理 - 项目状态操作 ========================

    def abandon_project(self, project_id: str):
        """废弃项目"""
        logger.info(f"【API调用】POST /api/projects/{project_id}/abandon")
        url = f"/api/projects/{project_id}/abandon"
        return http_client.post(url=url)

    def start_project(self, project_id: str, request_body: dict = None):
        """启动项目"""
        logger.info(f"【API调用】POST /api/projects/{project_id}/start")
        url = f"/api/projects/{project_id}/start"
        return http_client.post(url=url, json=request_body)

    def pause_project(self, project_id: str, request_body: dict = None):
        """暂停项目"""
        logger.info(f"【API调用】POST /api/projects/{project_id}/pause")
        url = f"/api/projects/{project_id}/pause"
        return http_client.post(url=url, json=request_body)

    def resume_project(self, project_id: str, request_body: dict = None):
        """恢复项目"""
        logger.info(f"【API调用】POST /api/projects/{project_id}/resume")
        url = f"/api/projects/{project_id}/resume"
        return http_client.post(url=url, json=request_body)

    def archive_project(self, project_id: str, request_body: dict = None):
        """归档项目"""
        logger.info(f"【API调用】POST /api/projects/{project_id}/archive")
        url = f"/api/projects/{project_id}/archive"
        return http_client.post(url=url, json=request_body)

    # ======================== 项目管理 - 数据集绑定 ========================

    def unbind_project_dataset(self, project_id: str, dataset_id: str):
        """解绑数据集（新版POST接口）"""
        logger.info(f"【API调用】POST /api/projects/{project_id}/bind-dataset/{dataset_id}/unbind")
        url = f"/api/projects/{project_id}/bind-dataset/{dataset_id}/unbind"
        return http_client.post(url=url)

    # ======================== 项目管理 - 标注配置 ========================

    def update_project_workflow(self, project_id: str, request_body: dict = None):
        """更新流转策略"""
        logger.info(f"【API调用】PUT /api/projects/{project_id}/workflow")
        url = f"/api/projects/{project_id}/workflow"
        return http_client.put(url=url, json=request_body)

    # ======================== 项目管理 - CVAT集成 ========================

    def ensure_cvat_project(self, project_id: str):
        """获取或创建项目关联的CVAT项目配置页"""
        logger.info(f"【API调用】POST /api/projects/{project_id}/cvat-project/ensure")
        url = f"/api/projects/{project_id}/cvat-project/ensure"
        return http_client.post(url=url)

    # ======================== 项目管理 - 封面 ========================

    def upload_project_cover(self, file: bytes, org_id: str, filename: str = "cover.jpg",
                              content_type: str = "image/jpeg", timeout: int = 1800):
        """临时上传项目封面图（multipart/form-data）"""
        url = "/api/projects/upload-cover"
        logger.info(f"【API调用】POST /api/projects/upload-cover, filename={filename}, org_id={org_id}")
        files = {"file": (filename, file, content_type)}
        params = {"org_id": org_id}
        return http_client.post(url=url, files=files, params=params, timeout=timeout)

    def get_project_cover(self, project_id: str):
        """获取项目封面"""
        logger.info(f"【API调用】GET /api/projects/{project_id}/cover")
        url = f"/api/projects/{project_id}/cover"
        return http_client.get(url=url)

    # ======================== 批次管理 ========================

    def list_batches(self, project_id: str, page: int = None, page_size: int = None):
        """获取批次列表"""
        logger.info(f"【API调用】GET /api/projects/{project_id}/batches/")
        url = f"/api/projects/{project_id}/batches/"
        params = self._build_params(
            page=page,
            page_size=page_size
        )
        return http_client.get(url=url, params=params)

    def create_batch(self, project_id: str, request_body: dict = None):
        """新建批次"""
        logger.info(f"【API调用】POST /api/projects/{project_id}/batches/")
        url = f"/api/projects/{project_id}/batches/"
        return http_client.post(url=url, json=request_body)

    def get_batch(self, project_id: str, batch_id: str):
        """获取批次详情"""
        logger.info(f"【API调用】GET /api/projects/{project_id}/batches/{batch_id}")
        url = f"/api/projects/{project_id}/batches/{batch_id}"
        return http_client.get(url=url)

    def update_batch(self, project_id: str, batch_id: str, request_body: dict = None):
        """编辑批次"""
        logger.info(f"【API调用】PATCH /api/projects/{project_id}/batches/{batch_id}")
        url = f"/api/projects/{project_id}/batches/{batch_id}"
        return http_client.patch(url=url, json=request_body)

    def push_batch(self, project_id: str, batch_id: str, request_body: dict = None):
        """推送批次至任务"""
        logger.info(f"【API调用】POST /api/projects/{project_id}/batches/{batch_id}/push")
        url = f"/api/projects/{project_id}/batches/{batch_id}/push"
        return http_client.post(url=url, json=request_body)

    def cancel_push_batch(self, project_id: str, batch_id: str):
        """取消推送"""
        logger.info(f"【API调用】POST /api/projects/{project_id}/batches/{batch_id}/cancel-push")
        url = f"/api/projects/{project_id}/batches/{batch_id}/cancel-push"
        return http_client.post(url=url)

    def pause_batch(self, project_id: str, batch_id: str):
        """暂停批次"""
        logger.info(f"【API调用】POST /api/projects/{project_id}/batches/{batch_id}/pause")
        url = f"/api/projects/{project_id}/batches/{batch_id}/pause"
        return http_client.post(url=url)

    def resume_batch(self, project_id: str, batch_id: str):
        """恢复批次"""
        logger.info(f"【API调用】POST /api/projects/{project_id}/batches/{batch_id}/resume")
        url = f"/api/projects/{project_id}/batches/{batch_id}/resume"
        return http_client.post(url=url)

    def complete_batch(self, project_id: str, batch_id: str):
        """完成批次"""
        logger.info(f"【API调用】POST /api/projects/{project_id}/batches/{batch_id}/complete")
        url = f"/api/projects/{project_id}/batches/{batch_id}/complete"
        return http_client.post(url=url)

    def delete_batch(self, project_id: str, batch_id: str, request_body: dict = None):
        """删除批次"""
        logger.info(f"【API调用】POST /api/projects/{project_id}/batches/{batch_id}/delete")
        url = f"/api/projects/{project_id}/batches/{batch_id}/delete"
        return http_client.post(url=url, json=request_body)

    def add_batch_data(self, project_id: str, batch_id: str, request_body: dict = None):
        """添加数据到批次"""
        logger.info(f"【API调用】POST /api/projects/{project_id}/batches/{batch_id}/data")
        url = f"/api/projects/{project_id}/batches/{batch_id}/data"
        return http_client.post(url=url, json=request_body)

    def clear_batch_data(self, project_id: str, batch_id: str):
        """清空批次数据"""
        logger.info(f"【API调用】POST /api/projects/{project_id}/batches/{batch_id}/data/clear")
        url = f"/api/projects/{project_id}/batches/{batch_id}/data/clear"
        return http_client.post(url=url)

    # ======================== Label Studio Proxy ========================

    def ls_get_projects(self, org_id: Any = None, page: int = None, page_size: int = None):
        """获取Label Studio项目列表"""
        logger.info(f"【API调用】GET /api/ls/projects/")
        url = "/api/ls/projects/"
        params = self._build_params(
            org_id=org_id,
            page=page,
            page_size=page_size
        )
        return http_client.get(url=url, params=params)

    def ls_get_project(self, project_id: str):
        """获取Label Studio项目详情"""
        logger.info(f"【API调用】GET /api/ls/projects/{project_id}")
        url = f"/api/ls/projects/{project_id}"
        return http_client.get(url=url)

    def ls_get_tasks(self, project_id: str, page: int = None, page_size: int = None):
        """获取Label Studio任务列表"""
        logger.info(f"【API调用】GET /api/ls/projects/{project_id}/tasks/")
        url = f"/api/ls/projects/{project_id}/tasks/"
        params = self._build_params(
            page=page,
            page_size=page_size
        )
        return http_client.get(url=url, params=params)

    def ls_get_annotations(self, task_id: str, page: int = None, page_size: int = None):
        """获取Label Studio标注结果"""
        logger.info(f"【API调用】GET /api/ls/tasks/{task_id}/annotations/")
        url = f"/api/ls/tasks/{task_id}/annotations/"
        params = self._build_params(
            page=page,
            page_size=page_size
        )
        return http_client.get(url=url, params=params)

    def ls_export_project(self, project_id: str):
        """导出Label Studio项目数据"""
        logger.info(f"【API调用】POST /api/ls/projects/{project_id}/export")
        url = f"/api/ls/projects/{project_id}/export"
        return http_client.post(url=url)

    # ======================== 系统 ========================

    def health_check(self):
        """健康检查"""
        logger.info(f"【API调用】GET /health")
        url = "/health"
        return http_client.get(url=url)


api_client = AutoApiClient()
