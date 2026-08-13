"""feishu_client.py — 飞书官方开放平台 API 封装（读阶段）。

替换 lark_cli.py。按 grilling 定案：
- 共享单应用（FEISHU_APP_ID/SECRET），每用户走 OAuth 拿 user_access_token
- user/refresh token 以 Fernet 加密存 DB（user_feishu_tokens），自动刷新
- tenant_access_token 仅做应用可见文档只读兜底；主路径 user token
- 提取链路：docx raw_content / wiki get_node 解析 / sheets 值 / bitable 记录

fetch_doc 返回契约承接 lark_cli：{extracted, text_content, title, doc_type, error_kind, error_message}
任何失败不抛异常，返回 extracted=False + 可读原因（供降级路径使用）。
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse

import httpx

from app.config import (
    FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_REDIRECT_URI, FEISHU_TOKEN_ENC_KEY, JWT_SECRET,
)
from app.db import crud

# ── 错误码（承接 lark_cli 契约）──
ERR_NO_AUTH = 'no_auth'          # 未授权 / 授权失效
ERR_PERMISSION = 'permission'    # 无权限读取该文档
ERR_UNSUPPORTED = 'unsupported'  # 不支持的链接类型
ERR_INVALID_LINK = 'invalid_link'  # 非法链接 / 域名
ERR_FETCH = 'fetch_failed'       # 读取失败（网络 / API 错误）
ERR_UNKNOWN = 'unknown'

_FEISHU_HOST = 'https://open.feishu.cn'
_OAUTH_HOST = 'https://accounts.feishu.cn'
_TOKEN_URL = f'{_OAUTH_HOST}/oauth/v3/token'

# 读阶段最小 scope（Q13 定案）
SCOPES = [
    'docx:document:readonly',
    'wiki:node:read',
    'wiki:wiki:readonly',
    'sheets:spreadsheet:readonly',
    'bitable:app:readonly',
    'auth:user.id:read',
    'offline_access',
]

# 链接类型（path 段 → 内部类型）；_SUPPORTED_READ 之外返回「暂不支持」
DOC_TYPES = {
    'docx': 'docx', 'docs': 'doc', 'wiki': 'wiki',
    'sheets': 'sheet', 'base': 'bitable', 'file': 'file',
    'slides': 'slides', 'mindnotes': 'mindnote',
}
_SUPPORTED_READ = {'docx', 'doc', 'wiki', 'sheet', 'bitable'}

_LINK_RE = re.compile(r'/(docx|docs|wiki|sheets|base|file|slides|mindnotes)/([A-Za-z0-9]+)')


class FeishuError(Exception):
    """飞书调用失败的通用异常，携带业务错误码与可读原因。"""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


# ── 链接解析 ──


def parse_link(url: str) -> dict:
    """解析飞书链接 → {valid, doc_type, token, error_kind, error_message}。"""
    url = (url or '').strip()
    if not url:
        return {'valid': False, 'doc_type': '', 'token': '',
                'error_kind': ERR_INVALID_LINK, 'error_message': '链接为空'}
    try:
        parsed = urlparse(url)
    except ValueError:
        return {'valid': False, 'doc_type': '', 'token': '',
                'error_kind': ERR_INVALID_LINK, 'error_message': '链接格式非法'}
    host = (parsed.hostname or '').lower()
    if not host.endswith('feishu.cn') and not host.endswith('larksuite.com'):
        return {'valid': False, 'doc_type': '', 'token': '',
                'error_kind': ERR_INVALID_LINK, 'error_message': '仅支持飞书 feishu.cn 链接'}
    m = _LINK_RE.search(parsed.path)
    if not m:
        return {'valid': False, 'doc_type': '', 'token': '',
                'error_kind': ERR_INVALID_LINK, 'error_message': '无法识别的飞书链接类型'}
    raw_type, token = m.group(1), m.group(2)
    if not token:
        return {'valid': False, 'doc_type': '', 'token': '',
                'error_kind': ERR_INVALID_LINK, 'error_message': '链接缺少文档标识'}
    return {'valid': True, 'doc_type': DOC_TYPES.get(raw_type, raw_type),
            'token': token, 'raw_type': raw_type,
            'error_kind': '', 'error_message': ''}


# ── token 加密（Fernet，密钥 FEISHU_TOKEN_ENC_KEY 或由 JWT_SECRET 派生）──

_fernet = None


def _fernet_key() -> bytes:
    material = (FEISHU_TOKEN_ENC_KEY or JWT_SECRET).encode('utf-8')
    return base64.urlsafe_b64encode(hashlib.sha256(material).digest())


def _get_fernet():
    global _fernet
    if _fernet is None:
        from cryptography.fernet import Fernet
        _fernet = Fernet(_fernet_key())
    return _fernet


def encrypt_token(raw: str) -> str:
    return _get_fernet().encrypt(raw.encode('utf-8')).decode('ascii')


def decrypt_token(enc: str) -> str:
    if not enc:
        return ''
    try:
        return _get_fernet().decrypt(enc.encode('ascii')).decode('utf-8')
    except Exception:
        return ''


# ── OAuth 授权（读阶段）──


def build_authorize_url(state: str = '') -> str:
    """构造网页 OAuth 授权 URL（用户浏览器访问）。"""
    params = {
        'client_id': FEISHU_APP_ID,
        'response_type': 'code',
        'redirect_uri': FEISHU_REDIRECT_URI,
        'scope': ' '.join(SCOPES),
    }
    if state:
        params['state'] = state
    return f'{_OAUTH_HOST}/open-apis/authen/v1/authorize?' + urlencode(params)


def _token_error_message(data: dict) -> str:
    code = data.get('error') or data.get('code') or ''
    desc = data.get('error_description') or data.get('msg') or ''
    if str(code) in ('invalid_grant', '20037'):
        return '飞书授权已过期，请重新授权'
    if desc:
        return f'飞书授权失败：{desc}'
    return '飞书授权失败，请稍后重试'


async def _oauth_post(payload: dict) -> dict:
    resp = await httpx.post(_TOKEN_URL, json=payload, timeout=20)
    data = resp.json()
    if resp.status_code != 200 or not data.get('access_token'):
        raise FeishuError(ERR_NO_AUTH, _token_error_message(data))
    return data


async def exchange_code(code: str, user_id: int) -> dict:
    """authorization_code → user_access_token + refresh_token，落库。"""
    data = await _oauth_post({
        'grant_type': 'authorization_code',
        'client_id': FEISHU_APP_ID,
        'client_secret': FEISHU_APP_SECRET,
        'code': code,
    })
    await _save_tokens_from_oauth(user_id, data)
    return data


async def _save_tokens_from_oauth(user_id: int, data: dict) -> None:
    now = datetime.utcnow()
    refresh_expires_in = int(data.get('refresh_token_expires_in') or 0)
    await crud.save_user_feishu_token(
        user_id,
        lark_open_id=data.get('open_id', ''),
        access_token_enc=encrypt_token(data.get('access_token', '')),
        refresh_token_enc=encrypt_token(data.get('refresh_token', '')),
        access_expires_at=now + timedelta(seconds=int(data.get('expires_in', 7200))),
        refresh_expires_at=now + timedelta(seconds=refresh_expires_in) if refresh_expires_in else None,
    )


async def _refresh_user_token(user_id: int, refresh_token: str) -> dict:
    data = await _oauth_post({
        'grant_type': 'refresh_token',
        'client_id': FEISHU_APP_ID,
        'client_secret': FEISHU_APP_SECRET,
        'refresh_token': refresh_token,
    })
    await _save_tokens_from_oauth(user_id, data)
    return data


# ── 访问 token 获取：用户优先，tenant 兜底 ──

_tenant_token: dict = {'token': '', 'expires_at': 0.0}


def _naive_utc(iso: str) -> datetime:
    """ISO 字符串 → naive UTC（dt_iso 返回带 +08:00，需归一化后才能与 utcnow() 比较）。"""
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


async def _get_user_token(user_id: int) -> str | None:
    """取用户可用 access_token；过期自动刷新；刷新失败返回 None（需重授权）。"""
    if not user_id:
        return None
    rec = await crud.get_user_feishu_token(user_id)
    if rec is None or not rec['access_token_enc']:
        return None
    access = decrypt_token(rec['access_token_enc'])
    if not access:
        return None
    if rec['access_expires_at']:
        try:
            if _naive_utc(rec['access_expires_at']) > datetime.utcnow():
                return access
        except ValueError:
            return access
    refresh = decrypt_token(rec['refresh_token_enc'])
    if not refresh:
        return None
    try:
        new_data = await _refresh_user_token(user_id, refresh)
        return new_data.get('access_token', access)
    except FeishuError:
        return None


async def _get_tenant_token() -> str:
    """应用身份 tenant_access_token（2h 有效，剩余 <30min 时刷新）。"""
    now = time.time()
    if _tenant_token['token'] and _tenant_token['expires_at'] > now + 1800:
        return _tenant_token['token']
    try:
        resp = await httpx.post(
            f'{_FEISHU_HOST}/open-apis/auth/v3/tenant_access_token/internal',
            json={'app_id': FEISHU_APP_ID, 'app_secret': FEISHU_APP_SECRET}, timeout=20,
        )
        data = resp.json()
        token = data.get('tenant_access_token', '')
        if resp.status_code != 200 or data.get('code') != 0 or not token:
            return ''
        _tenant_token['token'] = token
        _tenant_token['expires_at'] = now + int(data.get('expire', 7200))
        return token
    except Exception:
        return ''


# ── 文档提取 ──

_client = None


def _get_client():
    """惰性构建 lark_oapi 客户端（app 凭据驱动 tenant token；user token 每请求传入）。"""
    global _client
    if _client is None:
        import lark_oapi as lark
        _client = (lark.Client.builder()
                   .app_id(FEISHU_APP_ID)
                   .app_secret(FEISHU_APP_SECRET)
                   .log_level(lark.LogLevel.ERROR)
                   .build())
    return _client


def _call_sdk(method, req, access_token):
    """同步 SDK 调用（lark_oapi 为阻塞式），带 user_access_token option。"""
    from lark_oapi.core.model import RequestOptionBuilder
    opt = RequestOptionBuilder().user_access_token(access_token).build()
    return method(req, opt)


def _check_resp(resp) -> None:
    """按 SDK 响应 code 映射业务错误。code==0 成功。"""
    code = getattr(resp, 'code', 0)
    if code == 0:
        return
    msg = getattr(resp, 'msg', '') or '飞书 API 调用失败'
    if code in (20037, 99991668, 99991663):        # token 过期 / 无效
        raise FeishuError(ERR_NO_AUTH, '飞书授权已过期，请重新授权')
    if code in (99991661, 99991672, 99991671, 99991665):  # 权限不足
        raise FeishuError(ERR_PERMISSION, f'无权限读取该文档（{msg}）')
    raise FeishuError(ERR_FETCH, f'飞书读取失败：{msg}')


async def fetch_doc(url: str, user_id: int = 0) -> dict:
    """提取飞书文档正文（官方 API）。返回 {extracted, text_content, title, doc_type, error_kind, error_message}。

    - user_id>0 且已授权：用该用户 user_access_token（主路径）
    - 未授权：回退 tenant_access_token（仅应用可见文档）；再失败提示去授权
    - 任何失败不抛异常，返回 extracted=False + 可读原因
    """
    parsed = parse_link(url)
    if not parsed['valid']:
        return {'extracted': False, 'text_content': '', 'title': '', 'doc_type': '',
                'error_kind': parsed['error_kind'], 'error_message': parsed['error_message']}
    doc_type = parsed['doc_type']
    if doc_type not in _SUPPORTED_READ:
        return {'extracted': False, 'text_content': '', 'title': '', 'doc_type': doc_type,
                'error_kind': ERR_UNSUPPORTED,
                'error_message': f'暂不支持该链接类型（{doc_type}），请手动粘贴文档内容'}

    token = parsed['token']
    access_token = await _get_user_token(user_id) if user_id else None
    auth_kind = 'user' if access_token else 'tenant'
    if not access_token:
        access_token = await _get_tenant_token()
    if not access_token:
        return {'extracted': False, 'text_content': '', 'title': '', 'doc_type': doc_type,
                'error_kind': ERR_NO_AUTH,
                'error_message': '尚未授权飞书，请先在「设置 → 飞书授权」完成授权'}
    try:
        content, title = await _extract_by_type(doc_type, token, access_token, auth_kind)
    except FeishuError as exc:
        return {'extracted': False, 'text_content': '', 'title': '', 'doc_type': doc_type,
                'error_kind': exc.kind, 'error_message': exc.message}
    if not content or not content.strip():
        return {'extracted': False, 'text_content': '', 'title': title, 'doc_type': doc_type,
                'error_kind': ERR_FETCH, 'error_message': '文档内容为空'}
    return {'extracted': True, 'text_content': content, 'title': title, 'doc_type': doc_type,
            'error_kind': '', 'error_message': ''}


async def _extract_by_type(doc_type: str, token: str, access_token: str,
                           auth_kind: str) -> tuple[str, str]:
    if doc_type == 'wiki':
        return await _extract_wiki(token, access_token, auth_kind)
    if doc_type in ('docx', 'doc'):
        return await _extract_docx(token, access_token)
    if doc_type == 'sheet':
        return await _extract_sheet(token, access_token)
    if doc_type == 'bitable':
        return await _extract_bitable(token, access_token)
    raise FeishuError(ERR_UNSUPPORTED, f'暂不支持该链接类型（{doc_type}）')


async def _extract_docx(document_id: str, access_token: str) -> tuple[str, str]:
    from lark_oapi.api.docx.v1 import RawContentDocumentRequest
    req = RawContentDocumentRequest.builder().document_id(document_id).build()
    resp = await asyncio.to_thread(_call_sdk, _get_client().docx.v1.document.raw_content,
                                   req, access_token)
    _check_resp(resp)
    return (resp.data.content or ''), ''


async def _extract_wiki(token: str, access_token: str, auth_kind: str) -> tuple[str, str]:
    from lark_oapi.api.wiki.v2 import GetNodeSpaceRequest
    req = GetNodeSpaceRequest.builder().token(token).build()   # 不传 obj_type，自动解析真实类型
    resp = await asyncio.to_thread(_call_sdk, _get_client().wiki.v2.space.get_node,
                                   req, access_token)
    _check_resp(resp)
    node = resp.data.node
    obj_token = getattr(node, 'obj_token', '')
    obj_type = getattr(node, 'obj_type', '')
    if not obj_token:
        raise FeishuError(ERR_FETCH, '知识库节点解析失败')
    return await _extract_by_type(obj_type, obj_token, access_token, auth_kind)


async def _extract_sheet(token: str, access_token: str) -> tuple[str, str]:
    """表格：先取第一个 sheet_id（v3 元数据），再裸 HTTP 读值（v2 values）。"""
    async with httpx.AsyncClient() as hc:
        meta = await hc.get(
            f'{_FEISHU_HOST}/open-apis/sheets/v3/spreadsheets/{token}/sheets/query',
            headers={'Authorization': f'Bearer {access_token}'}, timeout=20,
        )
        meta_data = meta.json()
        if meta.status_code != 200 or meta_data.get('code') != 0:
            raise FeishuError(ERR_FETCH, meta_data.get('msg') or '表格信息读取失败')
        sheets = meta_data.get('data', {}).get('sheets', [])
        if not sheets:
            raise FeishuError(ERR_FETCH, '表格中无工作表')
        sheet_id = sheets[0].get('sheet_id', '')
        range_ = f'{sheet_id}!A1:Z200'
        vals = await hc.get(
            f'{_FEISHU_HOST}/open-apis/sheets/v2/spreadsheets/{token}/values/{range_}',
            headers={'Authorization': f'Bearer {access_token}'}, timeout=20,
        )
        vals_data = vals.json()
        if vals.status_code != 200 or vals_data.get('code') != 0:
            raise FeishuError(ERR_FETCH, vals_data.get('msg') or '表格数据读取失败')
        values = vals_data.get('data', {}).get('valueRange', {}).get('values', [])
    lines = ['\t'.join(str(c) for c in row) for row in values]
    return '\n'.join(lines), ''


async def _extract_bitable(token: str, access_token: str) -> tuple[str, str]:
    """多维表格：取第一个表 + 前 50 条记录，字段拼成文本。"""
    from lark_oapi.api.bitable.v1.model.list_app_table_request import ListAppTableRequest
    from lark_oapi.api.bitable.v1 import ListAppTableRecordRequest

    req = ListAppTableRequest.builder().app_token(token).page_size(5).build()
    resp = await asyncio.to_thread(_call_sdk, _get_client().bitable.v1.app_table.list,
                                   req, access_token)
    _check_resp(resp)
    tables = (resp.data.items or []) if resp.data else []
    if not tables:
        raise FeishuError(ERR_FETCH, '多维表格中无数据表')
    table_id = tables[0].table_id
    req2 = ListAppTableRecordRequest.builder().app_token(token).table_id(table_id).page_size(50).build()
    resp2 = await asyncio.to_thread(_call_sdk, _get_client().bitable.v1.app_table_record.list,
                                    req2, access_token)
    _check_resp(resp2)
    records = (resp2.data.items or []) if resp2.data else []
    lines = [' | '.join(f'{k}: {v}' for k, v in (rec.fields or {}).items()) for rec in records]
    return '\n'.join(lines), ''
