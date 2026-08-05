import os
import yaml
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Dict, Any, Optional

from common.base_log import logger

__all__ = [
    "AppConfig", "DatasetType", "DatasetStatus",
    "DEFAULT_PASSWORD", "DEFAULT_PHONE", "DEFAULT_EMAIL", "DEFAULT_REMARK",
    "ADMIN_USERNAME", "ADMIN_SYS2_USERNAME",
    "UserType", "USER_TYPE_ROLE_MAP", "USER_TYPE_NAME_MAP",
    "TEST_ORG_DESCRIPTION",
    "EnvConfig", "env_handler",
]

# ======================== 测试通用常量 ========================

# 默认测试账号密码
DEFAULT_PASSWORD = "admin123"
# 默认空字段值（用于电话、邮箱、备注等非必填项）
DEFAULT_PHONE = ""
DEFAULT_EMAIL = ""
DEFAULT_REMARK = ""
# 内置系统管理员账号
ADMIN_USERNAME = "admin"
ADMIN_SYS2_USERNAME = "admin_sys2"

# 测试组织描述标识（用于数据清理）
TEST_ORG_DESCRIPTION = "权限测试共享组织"


# ======================== 用户类型与角色映射 ========================

class UserType:
    """用户类型（业务概念）"""
    SYSTEM_ADMIN = "SYSTEM_ADMIN"
    PM = "PM"
    SUPPLIER_ADMIN = "SUPPLIER_ADMIN"
    ORG_TEAM_ADMIN = "ORG_TEAM_ADMIN"
    ORG_TEAM_MEMBER = "ORG_TEAM_MEMBER"
    SUPPLIER_TEAM_ADMIN = "SUPPLIER_TEAM_ADMIN"
    SUPPLIER_TEAM_MEMBER = "SUPPLIER_TEAM_MEMBER"

# 业务用户类型 -> 数据库角色编码
USER_TYPE_ROLE_MAP = {
    UserType.SYSTEM_ADMIN: "SYSTEM_ADMIN",
    UserType.PM: "PM",
    UserType.SUPPLIER_ADMIN: "SUPPLIER_ADMIN",
    UserType.ORG_TEAM_ADMIN: "TEAM_ADMIN",
    UserType.ORG_TEAM_MEMBER: "MEMBER",
    UserType.SUPPLIER_TEAM_ADMIN: "TEAM_ADMIN",
    UserType.SUPPLIER_TEAM_MEMBER: "MEMBER",
}

# 用户类型 -> 中文名称（仅用于日志/断言信息）
USER_TYPE_NAME_MAP = {
    UserType.SYSTEM_ADMIN: "系统管理员",
    UserType.PM: "项目管理员",
    UserType.SUPPLIER_ADMIN: "供应商管理员",
    UserType.ORG_TEAM_ADMIN: "项目直属团队管理员",
    UserType.ORG_TEAM_MEMBER: "项目直属团队成员",
    UserType.SUPPLIER_TEAM_ADMIN: "供应商团队管理员",
    UserType.SUPPLIER_TEAM_MEMBER: "供应商团队成员",
}


# ======================== 数据集类型/状态（业务枚举） ========================

@dataclass
class DatasetType:
    """数据集类型"""
    POINT_CLOUD = "pointcloud_3d"
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    SEQUENCE_IMAGE = "image_sequence"
    SEQUENCE_AUDIO = "audio_sequence"
    SEQUENCE_VIDEO = "video_sequence"

@dataclass
class DatasetStatus:
    """数据集状态"""
    UNUSED: str = "unused"
    INUSE: str = "inuse"
    DEPRECATED: str = "deprecated"
    COMPLETED: str = "completed"
    PAUSED: str = "paused"
    ARCHIVED: str = "archived"


# ======================== 环境配置（从YAML/.env加载） ========================

class EnvConfig:
    def __init__(self):
        self.config = {}
        self.env_variables = {}
        self.current_env = "test"  # 默认环境
        self._load_config()
        self._load_env()

    def _load_config(self):
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "config.yaml")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)
            logger.info(f"读取配置文件: {config_path}")
        else:
            logger.warning(f"配置文件未找到: {config_path}")

    def _load_env(self):
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path)
            logger.info(f"读取环境变量文件: {env_path}")
        else:
            logger.warning(f"环境变量文件未找到: {env_path}")

    def set_env(self, env: str):
        if env in self.config.get("env", {}):
            self.current_env = env
            logger.info(f"Environment switched to: {env}")
        else:
            logger.warning(f"Environment {env} not found in config")

    def get_env_config(self) -> Dict[str, Any]:
        return self.config.get("env", {}).get(self.current_env, {})

    def get_base_url(self) -> str:
        return self.get_env_config().get("api", {}).get("base_url", "")

    def get_timeout(self) -> int:
        return self.get_env_config().get("api", {}).get("timeout", 30)

    def get_ui_base_url(self) -> str:
        return self.get_env_config().get("ui", {}).get("base_url", "")

    def get_ui_implicit_wait(self) -> int:
        return self.get_env_config().get("ui", {}).get("implicit_wait", 10)

    def get_browser_config(self) -> Dict[str, Any]:
        return self.config.get("browser", {})

    def get_request_headers(self) -> Dict[str, str]:
        return self.config.get("request", {}).get("headers", {})

    def get_log_config(self) -> Dict[str, Any]:
        return self.config.get("log", {})

    def get_report_config(self) -> Dict[str, Any]:
        return self.config.get("report", {})

    def get_database_config(self) -> Dict[str, Any]:
        return self.get_env_config().get("database", {})

    def get_env_variable(self, key: str) -> Optional[str]:
        return os.getenv(key)

    def get_all_env_variables(self) -> Dict[str, str]:
        return {k: v for k, v in os.environ.items() if k.startswith(("ADMIN_", "PM_", "SPADM_", "TADM_", "USER_", "DB_", "CURRENT_"))}


env_handler = EnvConfig()
