"""API 响应公共辅助方法"""

__all__ = ["get_list_items"]


def get_list_items(resp_json: dict) -> list:
    """
    从列表接口响应中提取 items 或 list 字段。
    兼容不同接口返回的字段命名差异，不存在时返回空列表。
    """
    data = resp_json.get("data") or {}
    return data.get("items") or data.get("list") or []
