"""文件访问签名 URL 工具。

缺陷模块的附件 / 内嵌图 / 临时图通过短时效签名 URL 访问：
- 签名内容为 ``resource:user_id`` 与过期时间戳的组合，用 ``FILE_SIGN_SECRET`` 做 HMAC-SHA256。
- 前端 ``<img>`` 直链无法携带 Authorization header，因此由后端在返回
  缺陷详情 / 上传响应时注入签名 URL，访问端只需校验签名有效、未过期，
  并按签名绑定的 ``user_id`` 做项目成员 / 上传者归属校验。

URL 查询参数约定：
- ``expires`` — 过期时间戳（秒）
- ``uid``     — 签名绑定的用户 id
- ``sig``     — HMAC-SHA256 签名值

resource 约定：
- 附件下载:  ``att:{attachment_id}``
- 缺陷内嵌图: ``img:{defect_id}:{filename}``
- 临时图:     ``tmp:{filename}``
"""
from __future__ import annotations

import hashlib
import hmac
import time

from app.config import FILE_SIGN_SECRET

# 签名 URL 默认有效期（秒）
DEFAULT_TTL = 600


def _sign(resource: str, user_id: int, expires: int) -> str:
    """HMAC-SHA256 计算签名值。"""
    msg = f'{resource}:{user_id}:{expires}'.encode('utf-8')
    return hmac.new(FILE_SIGN_SECRET.encode('utf-8'), msg, hashlib.sha256).hexdigest()


def build_signed_url(path: str, resource: str, user_id: int, ttl: int = DEFAULT_TTL) -> str:
    """给 ``path`` 追加 expires/uid/sig 查询参数，生成签名 URL。"""
    expires = int(time.time()) + ttl
    sig = _sign(resource, user_id, expires)
    sep = '&' if '?' in path else '?'
    return f'{path}{sep}expires={expires}&uid={user_id}&sig={sig}'


def verify_signature(resource: str, user_id: int, expires: str | None, sig: str | None) -> bool:
    """校验签名是否有效且未过期（user_id 来自 URL 的 uid 参数）。"""
    if not expires or not sig:
        return False
    try:
        expires_int = int(expires)
        uid_int = int(user_id)
    except (TypeError, ValueError):
        return False
    if expires_int < int(time.time()):
        return False
    expected = _sign(resource, uid_int, expires_int)
    return hmac.compare_digest(expected, sig)
