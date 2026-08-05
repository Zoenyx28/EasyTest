"""项目管理接口业务层"""
from typing import List
from api.apis.data_api import api_client
from common.base_log import logger


class ProjectApi:
    """项目管理接口业务层"""

    # ======================== 项目基础操作 ========================

    def create_project(self, 
        name: str, 
        description: str, 
        data_type: str,
        org_id: str, 
        cover_url: str = None,
        visibility: str = "organization",
        workflow_steps: List[dict] = None
        ):
        """
        新建项目
        :param name: 项目名称（1-20字符）
        :param description: 项目描述（1-200字符）
        :param data_type: 数据类型，枚举: image/image_sequence/audio/audio_sequence/video/video_sequence/pointcloud_3d/text
        :param org_id: 组织ID
        :param cover_url: 封面图对象Key（通过 upload-cover 先上传获取）
        :param visibility: 可见范围: organization/team/private，默认organization
        :param workflow_steps: 流转策略工序配置，格式 [{"step_type": "annotate", "name": "标注"}, ...]
        """
        body = {
            "name": name,
            "description": description,
            "data_type": data_type,
            "org_id": org_id,
        }
        if cover_url is not None:
            body["cover_url"] = cover_url
        if visibility is not None:
            body["visibility"] = visibility
        if workflow_steps is not None:
            body["workflow_steps"] = workflow_steps

        logger.info(f"创建项目: name={name}, data_type={data_type}, org_id={org_id}")
        return api_client.create_project(request_body=body)

    def get_project_list(self, 
        org_id: str = None, 
        page: int = 1, 
        page_size: int = 10,                 
        name: str = None, 
        data_type: str = None, 
        status: str = None
        ):
        """
        获取项目列表
        :param org_id: 组织ID
        :param page: 页码
        :param page_size: 每页数量
        :param name: 项目名称（模糊搜索）
        :param data_type: 数据类型（多选用逗号分隔）
        :param status: 项目状态（多选用逗号分隔）
        """
        logger.info(f"查询项目列表: org_id={org_id}, name={name}, data_type={data_type}, status={status}")
        return api_client.get_projects(
            org_id=org_id, page=page, page_size=page_size,
            name=name, data_type=data_type, status=status
        )

    def get_project_detail(self, project_id: str):
        """
        获取项目详情
        :param project_id: 项目ID
        """
        logger.info(f"查询项目详情: project_id={project_id}")
        return api_client.get_project(project_id=project_id)

    def update_project(self, project_id: str, name: str = None,
                       description: str = None, cover_url: str = None,
                       visibility: str = None, data_type: str = None):
        """
        编辑项目
        :param project_id: 项目ID
        :param name: 项目名称（1-20字符）
        :param description: 项目描述（1-200字符）
        :param cover_url: 封面图对象Key
        :param visibility: 可见范围: organization/team/private
        :param data_type: 数据类型（仅项目未绑定数据集时可变更）
        """
        body = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if cover_url is not None:
            body["cover_url"] = cover_url
        if visibility is not None:
            body["visibility"] = visibility
        if data_type is not None:
            body["data_type"] = data_type

        logger.info(f"编辑项目: project_id={project_id}")
        return api_client.update_project(
            project_id=project_id, request_body=body if body else None
        )

    # ======================== 项目状态操作 ========================

    def abandon_project(self, project_id: str):
        """
        废弃项目,前置条件:项目状态为待启动或者待配置
        :param project_id: 项目ID
        """
        logger.info(f"废弃项目: project_id={project_id}")
        return api_client.abandon_project(project_id=project_id)

    def start_project(self, project_id: str, reason: str):
        """
        启动项目
        :param project_id: 项目ID
        :param reason: 操作原因（1-500字符）
        """
        logger.info(f"启动项目: project_id={project_id}")
        return api_client.start_project(project_id=project_id,
                                         request_body={"reason": reason})

    def pause_project(self, project_id: str, reason: str):
        """
        暂停项目
        :param project_id: 项目ID
        :param reason: 操作原因（1-500字符）
        """
        logger.info(f"暂停项目: project_id={project_id}")
        body={'reason':reason}
        return api_client.pause_project(project_id=project_id,request_body=body)

    def resume_project(self, project_id: str, reason: str):
        """
        恢复项目
        :param project_id: 项目ID
        :param reason: 操作原因（1-500字符）
        """
        logger.info(f"恢复项目: project_id={project_id}")
        body={'reason':reason}
        return api_client.resume_project(project_id=project_id,request_body=body)

    def archive_project(self, project_id: str, reason: str):
        """
        归档项目
        :param project_id: 项目ID
        :param reason: 操作原因（1-500字符）
        """
        logger.info(f"归档项目: project_id={project_id}")
        body={'reason':reason}
        return api_client.archive_project(project_id=project_id,request_body=body)

    # ======================== 数据集绑定 ========================

    def bind_dataset(self, project_id: str, dataset_ids: List[str]):
        """
        绑定数据集（支持多选）
        :param project_id: 项目ID
        :param dataset_ids: 数据集ID列表
        """
        logger.info(f"绑定数据集: project_id={project_id}, dataset_ids={dataset_ids}")
        return api_client.bind_dataset(
            project_id=project_id, request_body={"dataset_ids": dataset_ids}
        )

    def unbind_dataset(self, project_id: str, dataset_id: str):
        """
        解绑数据集
        :param project_id: 项目ID
        :param dataset_id: 数据集ID
        """
        logger.info(f"解绑数据集: project_id={project_id}, dataset_id={dataset_id}")
        return api_client.unbind_project_dataset(
            project_id=project_id, dataset_id=dataset_id
        )

    # ======================== 标注配置 ========================

    def save_label_config(self, project_id: str, label_config: str):
        """
        保存标注配置
        :param project_id: 项目ID
        :param label_config: Label Studio标注配置XML
        """
        logger.info(f"保存标注配置: project_id={project_id}")
        return api_client.save_label_config(
            project_id=project_id,
            request_body={"label_config": label_config}
        )

    def update_workflow(self, project_id: str, steps: List[dict]):
        """
        更新流转策略
        :param project_id: 项目ID
        :param steps: 工序步骤列表，格式 [{"step_type": "annotate", "name": "标注"}, ...]
                      工序顺序：标注 → 质检(1-3) → 审核 → 验收，数量4-6个
        """
        logger.info(f"更新流转策略: project_id={project_id}")
        return api_client.update_project_workflow(
            project_id=project_id, request_body={"steps": steps}
        )

    # ======================== CVAT集成 ========================

    def ensure_cvat_project(self, project_id: str):
        """
        获取或创建项目关联的CVAT项目配置页
        :param project_id: 项目ID
        """
        logger.info(f"获取CVAT项目配置: project_id={project_id}")
        return api_client.ensure_cvat_project(project_id=project_id)

    # ======================== 项目封面 ========================

    def upload_cover(self, file: bytes, org_id: str, filename: str = "cover.jpg",
                     content_type: str = "image/jpeg", timeout: int = 1800):
        """
        临时上传项目封面图
        :param file: 封面图片二进制数据
        :param org_id: 组织ID
        :param filename: 文件名
        :param content_type: 文件类型
        :param timeout: 超时时间（秒）
        """
        logger.info(f"上传项目封面: org_id={org_id}, filename={filename}")
        return api_client.upload_project_cover(
            file=file, org_id=org_id, filename=filename,
            content_type=content_type, timeout=timeout
        )

    def get_cover(self, project_id: str):
        """
        获取项目封面
        :param project_id: 项目ID
        """
        logger.info(f"获取项目封面: project_id={project_id}")
        return api_client.get_project_cover(project_id=project_id)

    # ======================== 任务管理 ========================

    def create_task(self, project_id: str, name: str, description: str = None):
        """
        新建任务
        :param project_id: 项目ID
        :param name: 任务名称
        :param description: 任务备注
        """
        body = {"name": name}
        if description is not None:
            body["description"] = description
        logger.info(f"创建任务: project_id={project_id}, name={name}")
        return api_client.create_task(
            project_id=project_id, request_body=body
        )

    def get_task_list(self, project_id: str, page: int = 1, page_size: int = 10):
        """
        获取任务列表
        :param project_id: 项目ID
        :param page: 页码
        :param page_size: 每页数量
        """
        logger.info(f"查询任务列表: project_id={project_id}")
        return api_client.get_tasks(
            project_id=project_id, page=page, page_size=page_size
        )

    def get_task(self, project_id: str, task_id: str):
        """
        获取任务详情
        :param project_id: 项目ID
        :param task_id: 任务ID
        """
        logger.info(f"查询任务详情: project_id={project_id}, task_id={task_id}")
        return api_client.get_task(
            project_id=project_id, task_id=task_id
        )

    def update_task(self, project_id: str, task_id: str,
                    name: str = None, description: str = None):
        """
        编辑任务
        :param project_id: 项目ID
        :param task_id: 任务ID
        :param name: 任务名称
        :param description: 任务备注
        """
        body = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        logger.info(f"编辑任务: project_id={project_id}, task_id={task_id}")
        return api_client.update_task(
            project_id=project_id, task_id=task_id,
            request_body=body if body else None
        )

    def push_data_to_task(self, project_id: str, task_id: str,
                          data_item_ids: List[str] = None,
                          batch_no: str = None, select_all: bool = False):
        """
        推送数据至任务
        :param project_id: 项目ID
        :param task_id: 任务ID
        :param data_item_ids: 数据项ID列表（指定推送的数据项）
        :param batch_no: 批次号
        :param select_all: 是否选择全部待标注数据，默认False
        """
        body = {}
        if data_item_ids is not None:
            body["data_item_ids"] = data_item_ids
        if batch_no is not None:
            body["batch_no"] = batch_no
        if select_all:
            body["select_all"] = True
        logger.info(f"推送数据至任务: project_id={project_id}, task_id={task_id}")
        return api_client.push_task_data(
            project_id=project_id, task_id=task_id,
            request_body=body if body else None
        )

    def get_push_records(self, project_id: str, task_id: str,
                         page: int = 1, page_size: int = 10):
        """
        获取推送记录
        :param project_id: 项目ID
        :param task_id: 任务ID
        :param page: 页码
        :param page_size: 每页数量
        """
        logger.info(f"获取推送记录: project_id={project_id}, task_id={task_id}")
        return api_client.get_push_records(
            project_id=project_id, task_id=task_id,
            page=page, page_size=page_size
        )

    def get_task_data_items(self, project_id: str, task_id: str,
                            page: int = 1, page_size: int = 10):
        """
        获取任务数据列表
        :param project_id: 项目ID
        :param task_id: 任务ID
        :param page: 页码
        :param page_size: 每页数量
        """
        logger.info(f"获取任务数据列表: project_id={project_id}, task_id={task_id}")
        return api_client.get_task_data_items(
            project_id=project_id, task_id=task_id,
            page=page, page_size=page_size
        )

    def get_annotations(self, project_id: str, task_id: str, item_id: str,
                        page: int = 1, page_size: int = 10):
        """
        获取标注结果
        :param project_id: 项目ID
        :param task_id: 任务ID
        :param item_id: 数据项ID
        :param page: 页码
        :param page_size: 每页数量
        """
        logger.info(f"获取标注结果: project_id={project_id}, task_id={task_id}, item_id={item_id}")
        return api_client.get_annotations(
            project_id=project_id, task_id=task_id, item_id=item_id,
            page=page, page_size=page_size
        )

    def close_task(self, project_id: str, task_id: str, name: str):
        """
        关闭任务（需输入任务名称确认）
        :param project_id: 项目ID
        :param task_id: 任务ID
        :param name: 输入任务名称进行二次确认
        """
        logger.info(f"关闭任务: project_id={project_id}, task_id={task_id}")
        return api_client.close_task(
            project_id=project_id, task_id=task_id,
            request_body={"name": name}
        )

    # ======================== 批次管理 ========================

    def create_batch(self, project_id: str, name: str,
                     description: str = None, priority: str = "P3"):
        """
        新建批次
        :param project_id: 项目ID
        :param name: 批次名称（1-20字符）
        :param description: 批次描述（最多200字符）
        :param priority: 优先级 P0-P5，默认P3
        """
        body = {"name": name}
        if description is not None:
            body["description"] = description
        if priority is not None:
            body["priority"] = priority
        logger.info(f"创建批次: project_id={project_id}, name={name}")
        return api_client.create_batch(project_id=project_id, request_body=body)

    def get_batch_list(self, project_id: str, page: int = 1, page_size: int = 10):
        """
        获取批次列表
        :param project_id: 项目ID
        :param page: 页码
        :param page_size: 每页数量
        """
        logger.info(f"查询批次列表: project_id={project_id}")
        return api_client.list_batches(
            project_id=project_id, page=page, page_size=page_size
        )

    def get_batch(self, project_id: str, batch_id: str):
        """
        获取批次详情
        :param project_id: 项目ID
        :param batch_id: 批次ID
        """
        logger.info(f"查询批次详情: project_id={project_id}, batch_id={batch_id}")
        return api_client.get_batch(project_id=project_id, batch_id=batch_id)

    def update_batch(self, project_id: str, batch_id: str,
                     name: str = None, description: str = None,
                     priority: str = None):
        """
        编辑批次
        :param project_id: 项目ID
        :param batch_id: 批次ID
        :param name: 批次名称
        :param description: 批次描述
        :param priority: 优先级 P0-P5
        """
        body = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if priority is not None:
            body["priority"] = priority
        logger.info(f"编辑批次: project_id={project_id}, batch_id={batch_id}")
        return api_client.update_batch(
            project_id=project_id, batch_id=batch_id,
            request_body=body if body else None
        )

    def push_batch(self, project_id: str, batch_id: str,
                   task_id: str, reason: str = None):
        """
        推送批次至任务
        :param project_id: 项目ID
        :param batch_id: 批次ID
        :param task_id: 目标任务ID
        :param reason: 操作原因（最多500字符）
        """
        body = {"task_id": task_id}
        if reason is not None:
            body["reason"] = reason
        logger.info(f"推送批次至任务: project_id={project_id}, batch_id={batch_id}, task_id={task_id}")
        return api_client.push_batch(
            project_id=project_id, batch_id=batch_id, request_body=body
        )

    def cancel_push_batch(self, project_id: str, batch_id: str, reason: str = None):
        """
        取消批次推送
        :param project_id: 项目ID
        :param batch_id: 批次ID
        :param reason: 操作原因（最多500字符，可选）
        """
        logger.info(f"取消批次推送: project_id={project_id}, batch_id={batch_id}")
        body = {"reason": reason} if reason else None
        return api_client.cancel_push_batch(project_id=project_id, batch_id=batch_id)

    def pause_batch(self, project_id: str, batch_id: str, reason: str = None):
        """
        暂停批次
        :param project_id: 项目ID
        :param batch_id: 批次ID
        :param reason: 操作原因（最多500字符，可选）
        """
        logger.info(f"暂停批次: project_id={project_id}, batch_id={batch_id}")
        return api_client.pause_batch(project_id=project_id, batch_id=batch_id)

    def resume_batch(self, project_id: str, batch_id: str, reason: str = None):
        """
        恢复批次
        :param project_id: 项目ID
        :param batch_id: 批次ID
        :param reason: 操作原因（最多500字符，可选）
        """
        logger.info(f"恢复批次: project_id={project_id}, batch_id={batch_id}")
        return api_client.resume_batch(project_id=project_id, batch_id=batch_id)

    def complete_batch(self, project_id: str, batch_id: str):
        """
        完成批次
        :param project_id: 项目ID
        :param batch_id: 批次ID
        """
        logger.info(f"完成批次: project_id={project_id}, batch_id={batch_id}")
        return api_client.complete_batch(project_id=project_id, batch_id=batch_id)

    def delete_batch(self, project_id: str, batch_id: str, reason: str):
        """
        删除批次
        :param project_id: 项目ID
        :param batch_id: 批次ID
        :param reason: 删除原因（1-500字符）
        """
        logger.info(f"删除批次: project_id={project_id}, batch_id={batch_id}")
        return api_client.delete_batch(
            project_id=project_id, batch_id=batch_id,
            request_body={"reason": reason}
        )

    def add_batch_data(self, project_id: str, batch_id: str, mode: str,
                       data_item_ids: List[str] = None,
                       dataset_ids: List[str] = None, count: int = None):
        """
        添加数据到批次

        支持三种互斥的添加方式：
        - manual: data_item_ids 必填
        - random: dataset_ids + count 必填，随机抽取
        - sequential: dataset_ids + count 必填，顺序选取
        :param project_id: 项目ID
        :param batch_id: 批次ID
        :param mode: 添加方式: manual/random/sequential
        :param data_item_ids: 【manual模式】数据项ID列表
        :param dataset_ids: 【random/sequential模式】数据集ID列表
        :param count: 【random/sequential模式】数据项数量
        """
        body = {"mode": mode}
        if data_item_ids is not None:
            body["data_item_ids"] = data_item_ids
        if dataset_ids is not None:
            body["dataset_ids"] = dataset_ids
        if count is not None:
            body["count"] = count
        logger.info(f"添加数据到批次: project_id={project_id}, batch_id={batch_id}, mode={mode}")
        return api_client.add_batch_data(
            project_id=project_id, batch_id=batch_id, request_body=body
        )

    def clear_batch_data(self, project_id: str, batch_id: str,
                         mode: str = "all", data_item_ids: List[str] = None):
        """
        清空批次数据
        :param project_id: 项目ID
        :param batch_id: 批次ID
        :param mode: 清空方式: all(全部清空)/manual(按数据项清空)，默认all
        :param data_item_ids: 【manual模式必填】待清空的数据项ID列表
        """
        body = {"mode": mode}
        if data_item_ids is not None:
            body["data_item_ids"] = data_item_ids
        logger.info(f"清空批次数据: project_id={project_id}, batch_id={batch_id}, mode={mode}")
        return api_client.clear_batch_data(project_id=project_id, batch_id=batch_id)


project_api = ProjectApi()
