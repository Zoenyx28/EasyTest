import os
import yaml


def load_testcase(yaml_path: str) -> dict:
    """加载YAML测试数据文件"""
    if not os.path.isabs(yaml_path):
        base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "api", "data")
        yaml_path = os.path.join(base_dir, yaml_path)

    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
