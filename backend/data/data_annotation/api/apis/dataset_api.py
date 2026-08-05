import time

from api.apis.data_api import api_client
from common.base_log import logger

class DataSetApi:
    # ============================数据集相关接口============================
    def upload_temp_cover(self,
        file: bytes,
        filename: str = "cover.jpg",
        type: str = "image/jpeg",
        org_id: str = None,
        timeout: int = 300
    ):
        """
        临时上传封面图
        在创建数据集前上传封面图，返回临时 object_key，创建数据集时传入 cover_url 字段即可。支持 jpg/jpeg/png/webp 格式，单文件不超过 5MB。
        params:
        - file: 封面图文件内容
        - filename: 封面图文件名，默认 cover.jpg
        - type: 封面图 MIME 类型，默认 image/jpeg,支持 image/jpeg, image/png, image/webp
        - org_id: 当前 PM 所在的组织 ID（必填，后端用其做权限校验）
        """
        return api_client.upload_temp_cover(file=file, filename=filename, type=type, org_id=org_id, timeout=timeout)

    """数据集管理"""
    def create_dataset(self,
        name: str,
        data_type: str,
        description: str,
        cover_url: str = None,
        allow_duplicate: bool = None,
        tags: list[str] = None,
        org_id: str = None
    ):
        """
        创建数据集
        - 数据集名称：必填，20字以内
        - 数据集描述：必填，200字以内
        - 数据集类型：必选，单选；枚举为：3D点云、文本、图像、音频、视频、序列图像、序列音频、序列视频
        创建数据集，需编辑数据集名称、数据集类型、是否允许数据重复以及标签等信息。
        封面图可通过 POST /api/datasets/upload-cover 先上传获取 cover_url，再传入此接口。
        注意：数据集类型在上传数据后不支持编辑，修改数据类型可能造成已生产数据不兼容，请在项目开始前确认数据类型。
        """
        json = {
            "name": name,
            "data_type": data_type,
            "description": description,
        }
        if cover_url is not None:
            json["cover_url"] = cover_url
        if allow_duplicate is not None:
            json["allow_duplicate"] = allow_duplicate
        if tags is not None:
            json["tags"] = tags
        if org_id is not None:
            json["org_id"] = org_id
        return api_client.create_dataset(request_body=json)

    def get_datasets(self,
        org_id: str,
        name: str = None,
        data_type: str = None,
        status: str = None,
        page: int = 1,
        page_size: int = 10
    ):
        """
        获取数据集列表

        获取数据集列表（分页）。数据集按项目管理员进行数据隔离：

        项目管理员（PM）：仅查看自己创建的数据集
        其他角色：无数据集管理权限
        支持按项目过滤：

        project_id：查询已绑定指定项目的数据集
        unbound=true：查询未绑定任何项目的数据集（可用于项目绑定数据集时的待选列表）
        两者不可同时传
        当传入 project_id 时，每条数据集返回 can_unbind 字段：

        true：数据集中无数据项被该项目分配，允许解绑
        false：存在已被分配的数据项，不可解绑
        """
        json = {
            "org_id": org_id,
            "name": name,
            "data_type": data_type,
            "status": status,
            "page": page,
            "page_size": page_size
        }
        res = api_client.get_datasets(request_body=json)
        return res

    def update_dataset(self,
        dataset_id: str,
        name: str = None,
        description: str = None,
        cover_url: str = None,
        data_type: str = None,
        allow_duplicate: bool = None,
        tags: list[str] = None,
    ):
        """
        编辑数据集

        编辑数据集基本信息。数据类型(data_type)：若数据集下无数据包则可修改，
        若已存在数据包则不可修改。
        """
        json = {}
        if name is not None:
            json["name"] = name
        if description is not None:
            json["description"] = description
        if cover_url is not None:
            json["cover_url"] = cover_url
        if data_type is not None:
            json["data_type"] = data_type
        if allow_duplicate is not None:
            json["allow_duplicate"] = allow_duplicate
        if tags is not None:
            json["tags"] = tags
        return api_client.update_dataset(dataset_id, request_body=json)

    def get_dataset_detail(self, dataset_id: str):
        """
        获取数据集详情

        获取指定数据集的详细信息，包含状态流转日志与当前绑定项目。
        """
        res = api_client.get_dataset_detail(dataset_id)
        return res

    def deprecate_dataset(self,
        dataset_id: str,
        reason: str = None
    ): 
        """
        弃用数据集

        仅「待使用(unused)」状态的数据集可废弃；
        废弃后状态变为「已废弃(deprecated)」，不可再操作。
        """
        json = {
            "reason": reason
        }
        return api_client.deprecate_dataset(dataset_id, response_body=json)


    def get_dataset_cover(self, dataset_id: str):
        """
        获取数据集封面
        """
        return api_client.get_cover(dataset_id)

    def upload_package_to_temp(self,
        dataset_id: str,
        file: bytes,
        filename: str = "package.zip",
        content_type: str = "application/zip",
        timeout: int = 300,
    ):
        """
        上传压缩包到临时目录，返回临时存储Key。支持 .zip 和 .tar（含 .tar.gz/.tar.bz2）格式。

        单个文件大小不超过 5GB
        上传后需调用「处理上传数据」接口触发解析
        """
        return api_client.upload_data(
            dataset_id=dataset_id,
            file=file,
            filename=filename,
            content_type=content_type,
            timeout=timeout,
        )

    def process_uploaded_package(self,
        dataset_id: str,
        object_keys: list[str],
    ):
        """
        处理上传数据
        携带上传接口返回的临时Key列表，触发压缩包解析处理。

        为每个压缩包生成上传记录并异步解压
        序列类型数据（image_sequence/audio_sequence/video_sequence）会自动按目录结构识别序列名称和序列索引
        处理完成后可在上传记录中查看数据上传情况
        """
        json = {
            "object_keys": object_keys
        }
        return api_client.process_uploaded_data(dataset_id, request_body=json)

    def get_package_upload_records(self,
        dataset_id: str,
        file_name: str = None,
        status: str = None,
        package_id: str = None,
        page: int = 1,
        page_size: int = 10
    ):
        """
        获取上传记录
        分页查询数据集的上传记录，支持按文件名、状态、压缩包ID等过滤。
        """
        params = {
            "file_name": file_name,
            "status": status,
            "package_id": package_id,
            "page": page,
            "page_size": page_size
        }
        return api_client.get_uploads_list(dataset_id, response_body=params)

    def export_data(self,
        content_type:str,
        file_name: str,
        item_ids: list[str] = None,
    ):
        """
        异步导出数据为 .zip 压缩包。接口立即返回导出记录，后台执行打包，通过导出记录查询状态。
        导出状态：processing=导出中，completed=导出成功，failed=导出失败。 状态为 completed 时可调用下载接口获取压缩包。
        序列类型数据集（image_sequence/audio_sequence/video_sequence/pointcloud_3d）传入 item_ids 时，会自动扩展为所选数据项同序列（同 dir_level1）下的所有数据项
        """
        params = {
            "content_type": content_type,
            "file_name": file_name,
            "item_ids": item_ids,
        }
        return api_client.export_data(response_body=params)

    def get_export_data_records(self,
        dataset_id: str,
        fileName: str = None,
        status: str = None,
        startTime: int = None,
        endTime: int = None,
        page: int = 1,
        page_size: int = 10
    ):
        """
        获取导出记录
        分页查询数据集的导出记录，支持按文件名、状态、导出时间等过滤。
        """
        params = {
            "fileName": fileName,
            "status": status,
            "startTime": startTime,
            "endTime": endTime,
            "page": page,
            "page_size": page_size
        }
        return api_client.get_export_records(dataset_id, response_body=params)

    def download_exported_data_package(self,
        dataset_id: str,
        export_id: str
    ):
        """
        下载导入记录文件，导出原始数据压缩包
        """
        return api_client.download_package(dataset_id, export_id)
    
dataset_api = DataSetApi()
