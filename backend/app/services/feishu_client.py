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

# 读阶段最小 scope（Q13 定案；多维表格/电子表格/知识库整库权限本期暂不启用）
SCOPES = [
    'docx:document:readonly',
    'wiki:node:read',
    'drive:media:download',
    'drive:drive:readonly',
    'auth:user.id:read',
    'offline_access',
]

# 链接类型（path 段 → 内部类型）；_SUPPORTED_READ 之外返回「暂不支持」
DOC_TYPES = {
    'docx': 'docx', 'docs': 'doc', 'wiki': 'wiki',
    'sheets': 'sheet', 'base': 'bitable', 'file': 'file',
    'slides': 'slides', 'mindnotes': 'mindnote',
}
# 本期可读类型：docx + wiki（经 wiki:node:read 解析后读 docx）。
# sheet/bitable 因 scope 未启用暂不支持。
_SUPPORTED_READ = {'docx', 'doc', 'wiki'}

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
    async with httpx.AsyncClient(timeout=20) as hc:
        resp = await hc.post(_TOKEN_URL, json=payload)
    data = resp.json()
    if resp.status_code != 200 or not data.get('access_token'):
        raise FeishuError(ERR_NO_AUTH, _token_error_message(data))
    return data


async def exchange_code(code: str, user_id: int) -> dict:
    """authorization_code → user_access_token + refresh_token，落库。

    oauth/v3/token 对 authorization_code 要求 redirect_uri（须与授权时一致）。
    """
    data = await _oauth_post({
        'grant_type': 'authorization_code',
        'client_id': FEISHU_APP_ID,
        'client_secret': FEISHU_APP_SECRET,
        'code': code,
        'redirect_uri': FEISHU_REDIRECT_URI,
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
        async with httpx.AsyncClient(timeout=20) as hc:
            resp = await hc.post(
                f'{_FEISHU_HOST}/open-apis/auth/v3/tenant_access_token/internal',
                json={'app_id': FEISHU_APP_ID, 'app_secret': FEISHU_APP_SECRET},
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
    if doc_type in ('sheet', 'bitable'):
        # 本期未启用 sheet/bitable scope（用户决策），wiki 解析到该类时明确提示
        raise FeishuError(ERR_UNSUPPORTED, '该文档类型（电子表格/多维表格）本期暂不支持读取，请手动粘贴内容')
    raise FeishuError(ERR_UNSUPPORTED, f'暂不支持该链接类型（{doc_type}）')


def _raise_api_error(data: dict, fallback: str) -> None:
    """把飞书 API 的 {code, msg} 映射为 FeishuError（raw httpx 路径）。"""
    code = data.get('code')
    msg = (data.get('msg') or fallback or '').lower()
    if code in (20037, 99991668, 99991663) or ('token' in msg and ('expire' in msg or 'invalid' in msg)):
        raise FeishuError(ERR_NO_AUTH, '飞书授权已过期，请重新授权')
    if ('permission' in msg or '权限' in msg or 'forbidden' in msg):
        raise FeishuError(
            ERR_PERMISSION,
            '无权限读取该文档：请确认你本人有访问权限，或先在「设置 → 飞书授权」完成授权；也可手动粘贴文档内容',
        )
    raise FeishuError(ERR_FETCH, f'飞书读取失败：{data.get("msg") or fallback}')


async def _extract_docx(document_id: str, access_token: str) -> tuple[str, str]:
    async with httpx.AsyncClient(timeout=20) as hc:
        resp = await hc.get(
            f'{_FEISHU_HOST}/open-apis/docx/v1/documents/{document_id}/raw_content',
            headers={'Authorization': f'Bearer {access_token}'},
        )
        data = resp.json()
    if resp.status_code != 200 or data.get('code') != 0:
        _raise_api_error(data, '文档读取失败')
    return (data.get('data', {}).get('content') or ''), ''


async def _extract_wiki(token: str, access_token: str, auth_kind: str) -> tuple[str, str]:
    async with httpx.AsyncClient(timeout=20) as hc:
        resp = await hc.get(
            f'{_FEISHU_HOST}/open-apis/wiki/v2/spaces/get_node',
            params={'token': token},
            headers={'Authorization': f'Bearer {access_token}'},
        )
        data = resp.json()
    if resp.status_code != 200 or data.get('code') != 0:
        _raise_api_error(data, '知识库节点解析失败')
    node = data.get('data', {}).get('node', {})
    obj_token = node.get('obj_token', '')
    obj_type = node.get('obj_type', '')
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
    async with httpx.AsyncClient(timeout=20) as hc:
        resp = await hc.get(
            f'{_FEISHU_HOST}/open-apis/bitable/v1/apps/{token}/tables',
            params={'page_size': 5},
            headers={'Authorization': f'Bearer {access_token}'},
        )
        data = resp.json()
    if resp.status_code != 200 or data.get('code') != 0:
        _raise_api_error(data, '多维表格读取失败')
    tables = data.get('data', {}).get('items') or []
    if not tables:
        raise FeishuError(ERR_FETCH, '多维表格中无数据表')
    table_id = tables[0].get('table_id', '')
    async with httpx.AsyncClient(timeout=20) as hc:
        r2 = await hc.get(
            f'{_FEISHU_HOST}/open-apis/bitable/v1/apps/{token}/tables/{table_id}/records',
            params={'page_size': 50},
            headers={'Authorization': f'Bearer {access_token}'},
        )
        data2 = r2.json()
    if r2.status_code != 200 or data2.get('code') != 0:
        _raise_api_error(data2, '多维表格记录读取失败')
    records = data2.get('data', {}).get('items') or []
    lines = [' | '.join(f'{k}: {v}' for k, v in (rec.get('fields') or {}).items()) for rec in records]
    return '\n'.join(lines), ''


# ══════════════════════════════════════════════════════════
# 文档预览（blocks → markdown + 图片代理）
# ══════════════════════════════════════════════════════════


def _elements_text(elements) -> str:
    """把 block 的 elements 数组（text_run/mention 等）拼成纯文本。"""
    parts = []
    for e in elements or []:
        run = (e.get('text_run') or {}).get('content')
        if run:
            parts.append(run)
        mention = (e.get('mention') or {}).get('text')
        if mention:
            parts.append(mention)
    return ''.join(parts)


def _block_elements(b: dict, keys: tuple) -> list:
    """取 block 内首个存在的结构（heading1/paragraph/text 等）的 elements。"""
    for k in keys:
        if b.get(k):
            return b[k].get('elements') or []
    return []


def _cell_text(cell_id: int, by_id: dict, children_of: dict, seen: set) -> str:
    if cell_id in seen:
        return ''
    seen.add(cell_id)
    out = []
    for c in children_of.get(cell_id, []):
        t = _elements_text(_block_elements(c, ('text', 'paragraph')))
        if t:
            out.append(t)
        out.append(_cell_text(c.get('block_id'), by_id, children_of, seen))
    return ''.join(out)


def _table_md(b: dict, by_id: dict, children_of: dict) -> str:
    tbl = b.get('table') or {}
    cells = tbl.get('cells') or []
    prop = tbl.get('property') or {}
    col_size = int(prop.get('column_size') or 0)
    if not cells or not col_size:
        return '(表格)'
    rows = []
    for i in range(0, len(cells), col_size):
        row = [_cell_text(cid, by_id, children_of, set()).replace('|', '\\|') for cid in cells[i:i + col_size]]
        rows.append(row)
    header = rows[0] if rows else []
    out = ['| ' + ' | '.join(header) + ' |', '|' + '---|' * len(header)]
    for r in rows[1:]:
        out.append('| ' + ' | '.join(r) + ' |')
    return '\n'.join(out)


def _blocks_to_markdown(items: list) -> str:
    """把飞书 docx blocks 转成 markdown（标题/段落/列表/代码/引用/待办/表格/分割线/图片占位）。"""
    lines: list[str] = []
    by_id = {b.get('block_id'): b for b in items}
    children_of: dict = {}
    for b in items:
        children_of.setdefault(b.get('parent_id'), []).append(b)

    def walk(bid, depth=0):
        for b in children_of.get(bid, []):
            btype = b.get('block_type')
            indent = '  ' * min(depth, 4)
            if btype == 3:
                lines.append(f"# {_elements_text(_block_elements(b, ('heading1',)))}")
            elif btype == 4:
                lines.append(f"## {_elements_text(_block_elements(b, ('heading2',)))}")
            elif btype == 5:
                lines.append(f"### {_elements_text(_block_elements(b, ('heading3',)))}")
            elif btype in (6, 7, 8, 9, 10, 11):
                lvl = btype - 2
                lines.append(f"{'#' * lvl} {_elements_text(_block_elements(b, (f'heading{lvl}',)))}")
            elif btype == 2:
                t = _elements_text(_block_elements(b, ('text', 'paragraph')))
                if t:
                    lines.append(t)
            elif btype == 12:
                lines.append(f"{indent}- {_elements_text(_block_elements(b, ('bullet',)))}")
            elif btype == 13:
                lines.append(f"{indent}1. {_elements_text(_block_elements(b, ('ordered',)))}")
            elif btype == 14:
                lines.append("```")
                lines.append(_elements_text(_block_elements(b, ('code',))))
                lines.append("```")
            elif btype == 15:
                lines.append(f"> {_elements_text(_block_elements(b, ('quote',)))}")
            elif btype == 16:
                mark = '[x]' if (b.get('todo') or {}).get('done') else '[ ]'
                lines.append(f"{indent}- {mark} {_elements_text(_block_elements(b, ('todo',)))}")
            elif btype == 21:
                lines.append('---')
            elif btype == 27:
                token = (b.get('image') or {}).get('token', '')
                lines.append(f"![图片](/api/feishu/media/{token})" if token else '![图片]')
            elif btype == 28:
                md = _table_md(b, by_id, children_of)
                lines.append(md)
            # btype 1 (page) 与其他类型忽略；递归子块
            walk(b.get('block_id'), depth + 1)

    walk(0)
    return '\n'.join(lines)


async def _resolve_wiki_node(access_token: str, token: str) -> tuple[str, str]:
    """wiki token → (obj_token, obj_type)。"""
    async with httpx.AsyncClient(timeout=20) as hc:
        resp = await hc.get(f'{_FEISHU_HOST}/open-apis/wiki/v2/spaces/get_node',
                            params={'token': token},
                            headers={'Authorization': f'Bearer {access_token}'})
        data = resp.json()
    if resp.status_code != 200 or data.get('code') != 0:
        _raise_api_error(data, '知识库节点解析失败')
    node = data.get('data', {}).get('node', {})
    obj_token = node.get('obj_token', '')
    obj_type = node.get('obj_type', '')
    if not obj_token:
        raise FeishuError(ERR_FETCH, '知识库节点解析失败')
    return obj_token, obj_type


async def _fetch_blocks(access_token: str, document_id: str, page_token: str = '') -> list:
    """拉取 docx 全部 blocks（分页）。"""
    all_items: list = []
    params = {'page_size': 500}
    if page_token:
        params['page_token'] = page_token
    async with httpx.AsyncClient(timeout=30) as hc:
        resp = await hc.get(f'{_FEISHU_HOST}/open-apis/docx/v1/documents/{document_id}/blocks',
                            params=params, headers={'Authorization': f'Bearer {access_token}'})
        data = resp.json()
    if resp.status_code != 200 or data.get('code') != 0:
        _raise_api_error(data, '文档块读取失败')
    items = data.get('data', {}).get('items') or []
    all_items.extend(items)
    npt = data.get('data', {}).get('page_token', '')
    if npt:
        all_items.extend(await _fetch_blocks(access_token, document_id, npt))
    return all_items


async def preview_doc(url: str, user_id: int = 0) -> dict:
    """获取文档预览：markdown（blocks 转换）+ 图片 token 列表。

    返回 {markdown, images, error_kind, error_message}。任何失败不抛异常。
    """
    parsed = parse_link(url)
    if not parsed['valid']:
        return {'markdown': '', 'images': [], 'error_kind': parsed['error_kind'],
                'error_message': parsed['error_message']}
    doc_type = parsed['doc_type']
    if doc_type not in _SUPPORTED_READ:
        return {'markdown': '', 'images': [], 'error_kind': ERR_UNSUPPORTED,
                'error_message': f'暂不支持该链接类型（{doc_type}）'}
    access_token = await _get_user_token(user_id) if user_id else None
    if not access_token:
        access_token = await _get_tenant_token()
    if not access_token:
        return {'markdown': '', 'images': [], 'error_kind': ERR_NO_AUTH,
                'error_message': '尚未授权飞书，请先在「设置 → 飞书授权」完成授权'}
    try:
        if doc_type == 'wiki':
            doc_id, real_type = await _resolve_wiki_node(access_token, parsed['token'])
        else:
            doc_id, real_type = parsed['token'], doc_type
        if real_type not in ('docx', 'doc'):
            raise FeishuError(ERR_UNSUPPORTED, '预览仅支持文档类（docx），请手动粘贴内容')
        items = await _fetch_blocks(access_token, doc_id)
        images = [b.get('image', {}).get('token', '')
                  for b in items if b.get('block_type') == 27 and b.get('image', {}).get('token')]
        markdown = _blocks_to_markdown(items)
        return {'markdown': markdown, 'images': images, 'error_kind': '', 'error_message': ''}
    except FeishuError as exc:
        return {'markdown': '', 'images': [], 'error_kind': exc.kind, 'error_message': exc.message}


async def fetch_image(file_token: str, user_id: int) -> tuple[bytes, str]:
    """下载飞书图片字节 + content_type（user token）。"""
    access_token = await _get_user_token(user_id)
    if not access_token:
        raise FeishuError(ERR_NO_AUTH, '尚未授权飞书')
    async with httpx.AsyncClient(timeout=30) as hc:
        r = await hc.get(f'{_FEISHU_HOST}/open-apis/drive/v1/medias/{file_token}/download',
                         headers={'Authorization': f'Bearer {access_token}'})
    if r.status_code != 200:
        try:
            data = r.json()
        except Exception:
            data = {'msg': '图片下载失败'}
        _raise_api_error(data, '图片下载失败')
    return r.content, r.headers.get('content-type', 'image/png')
